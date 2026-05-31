"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant, Planeswalker, Sorcery
from engine.types import Color, ManaCost, TargetRequirement, Zone
from test_utils import create_game, set_board_state


def _load_library(player, cards) -> None:
    """Add cards to a player's library for draw-based resolution tests."""
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestTogetherAsOneProperties:
    """Static characteristics should match the card spec."""

    def test_is_a_six_mana_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneTargeting:
    """The spell should require one player target and one 'any target'."""

    def test_get_targets_declares_target_player_then_any_target(self) -> None:
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        planeswalker = Planeswalker(name="Test Walker", starting_loyalty=4)
        non_target = Sorcery(name="Divination")

        requirements = TogetherAsOne(owner=None).get_targets(game)

        assert len(requirements) == 2
        player_requirement, any_target_requirement = requirements
        assert isinstance(player_requirement, TargetRequirement)
        assert isinstance(any_target_requirement, TargetRequirement)
        assert player_requirement.zone == Zone.BATTLEFIELD
        assert any_target_requirement.zone == Zone.BATTLEFIELD
        assert player_requirement.filter_fn(player) is True
        assert player_requirement.filter_fn(creature) is False
        assert any_target_requirement.filter_fn(player) is True
        assert any_target_requirement.filter_fn(creature) is True
        assert any_target_requirement.filter_fn(planeswalker) is True
        assert any_target_requirement.filter_fn(non_target) is False


class TestTogetherAsOneResolution:
    """Converge count should drive all three parts of the spell."""

    def test_three_colors_make_target_player_draw_three_take_three_and_gain_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _load_library(
            p2,
            [
                Instant(name="Draw 1"),
                Instant(name="Draw 2"),
                Instant(name="Draw 3"),
            ],
        )
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.chosen_targets = [p2, p2]
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]

        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 3
        assert p2.life == 17
        assert p1.life == 23

    def test_damage_can_hit_a_creature_while_target_player_still_draws(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        _load_library(
            p2,
            [
                Instant(name="Draw 1"),
                Instant(name="Draw 2"),
            ],
        )
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.chosen_targets = [p2, creature]
        spell.colors_spent = [Color.RED, Color.GREEN]

        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 2
        assert creature.damage_marked == 2
        assert p2.life == 20
        assert p1.life == 22

    def test_damage_can_hit_a_planeswalker(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        planeswalker = Planeswalker(
            name="Test Walker",
            owner=p2,
            controller=p2,
            starting_loyalty=4,
        )
        set_board_state(game, 1, battlefield=[planeswalker])
        _load_library(p2, [Instant(name="Draw 1")])
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.chosen_targets = [p2, planeswalker]
        spell.colors_spent = [Color.RED]

        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 1
        assert planeswalker.loyalty == 3
        assert p2.life == 20
        assert p1.life == 21

    def test_colorless_payment_makes_x_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        _load_library(p2, [Instant(name="Draw 1")])
        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.chosen_targets = [p2, creature]
        spell.colors_spent = []

        spell.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 0
        assert creature.damage_marked == 0
        assert p2.life == 20
        assert p1.life == 20
