"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_colors_spent_defaults_to_zero(self) -> None:
        assert TogetherAsOne(owner=None).colors_spent == 0


class TestTogetherAsOneTargeting:
    """get_targets() should declare one player target and one any-target slot."""

    def test_get_targets_returns_two_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)

    def test_first_target_requirement_accepts_players_only(self) -> None:
        game = create_game()
        p1 = game.players[0]
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)

        assert req.zone == Zone.BATTLEFIELD
        assert req.filter_fn(p1) is True
        assert req.filter_fn(creature) is False

    def test_second_target_requirement_accepts_players_and_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        non_target = Instant(name="Not a battlefield target", mana_cost=ManaCost.parse("{U}"))

        assert req.zone == Zone.BATTLEFIELD
        assert req.filter_fn(p1) is True
        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Resolution should draw, damage, and gain life based on distinct colors spent."""

    @staticmethod
    def _add_library_cards(player, count: int) -> None:
        library = player.zones[Zone.LIBRARY]
        for i in range(count):
            card = Instant(name=f"Draw Card {i}", mana_cost=ManaCost.parse("{U}"))
            card.owner = player
            card.controller = player
            library.add(card)

    def test_no_chosen_targets_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        self._add_library_cards(p2, 2)

        spell = TogetherAsOne(owner=p1, controller=p1)
        hand_before = len(p2.zones[Zone.HAND].get_all())
        life_before = p1.life

        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == hand_before
        assert p1.life == life_before

    def test_zero_colors_spent_causes_no_draw_damage_or_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        self._add_library_cards(p2, 2)

        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(bear)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 0
        spell.chosen_targets = [p2, bear]

        hand_before = len(p2.zones[Zone.HAND].get_all())
        life_before = p1.life
        damage_before = bear.damage_marked

        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == hand_before
        assert bear.damage_marked == damage_before
        assert p1.life == life_before

    def test_distinct_colors_drive_draw_damage_and_life_gain(self) -> None:
        game = create_game(player1_life=10)
        p1 = game.players[0]
        p2 = game.players[1]
        self._add_library_cards(p2, 3)

        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(bear)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [ManaType.WHITE, ManaType.WHITE, ManaType.BLUE]
        spell.chosen_targets = [p2, bear]

        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 2
        assert bear.damage_marked == 2
        assert p1.life == 12
