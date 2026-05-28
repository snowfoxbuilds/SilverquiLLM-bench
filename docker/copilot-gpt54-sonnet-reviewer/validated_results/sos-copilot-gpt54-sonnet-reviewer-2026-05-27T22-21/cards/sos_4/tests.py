"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Creature, Planeswalker, Sorcery
from engine.types import Color, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_rules_text_mentions_converge(self) -> None:
        assert "Converge" in TogetherAsOne(owner=None).rules_text


class TestTogetherAsOneTargeting:
    """Together as One needs a player target and a separate any-target choice."""

    def test_returns_two_target_requirements(self) -> None:
        game = create_game()

        reqs = TogetherAsOne(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert all(isinstance(req, TargetRequirement) for req in reqs)

    def test_first_target_requirement_accepts_players_only(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        walker = Planeswalker(name="Ajani", starting_loyalty=4)

        req = TogetherAsOne(owner=None).get_targets(game)[0]

        assert "player" in req.description.lower()
        assert req.filter_fn(p1) is True
        assert req.filter_fn(bear) is False
        assert req.filter_fn(walker) is False

    def test_second_target_requirement_accepts_any_target(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        walker = Planeswalker(name="Ajani", starting_loyalty=4)
        non_target = CardImpl(name="Blank Card")

        req = TogetherAsOne(owner=None).get_targets(game)[1]

        assert "any target" in req.description.lower()
        assert req.filter_fn(p1) is True
        assert req.filter_fn(bear) is True
        assert req.filter_fn(walker) is True
        assert req.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Converge value X drives every part of the spell's effect."""

    @staticmethod
    def _load_library(player, count: int) -> None:
        for idx in range(count):
            player.zones[Zone.LIBRARY].add(
                CardImpl(
                    name=f"Library Card {idx + 1}",
                    owner=player,
                    controller=player,
                )
            )

    def test_no_chosen_targets_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE]

        spell.on_resolve(game)

        assert p1.life == 20

    def test_resolution_draws_deals_damage_and_gains_life_equal_to_colors_spent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        bear = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[bear])
        self._load_library(p2, 3)

        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]
        spell.chosen_targets = [p2, bear]
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 3
        assert bear.damage_marked == 3
        assert p1.life == 23

    def test_zero_colors_spent_makes_the_spell_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._load_library(p2, 1)

        spell.colors_spent = []
        spell.chosen_targets = [p2, p2]
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 0
        assert p2.life == 20
        assert p1.life == 20

    def test_any_target_mode_can_damage_a_planeswalker(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        walker = Planeswalker(
            name="Test Walker",
            owner=p2,
            controller=p2,
            starting_loyalty=4,
        )
        set_board_state(game, 1, battlefield=[walker])
        self._load_library(p2, 2)

        spell.colors_spent = [Color.RED, Color.GREEN]
        spell.chosen_targets = [p2, walker]
        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 2
        assert walker.loyalty == 2
        assert p1.life == 22

    def test_cast_pipeline_uses_paid_mana_colors_for_x(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1, controller=p1)
        self._load_library(p2, 3)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.COLORLESS: 3,
            },
        )

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND].get_all()) == 3
        assert p2.life == 17
        assert p1.life == 23
