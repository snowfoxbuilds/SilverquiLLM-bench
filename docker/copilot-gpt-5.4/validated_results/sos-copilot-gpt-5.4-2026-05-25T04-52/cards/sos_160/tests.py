"""Tests for SOS 160 — Slumbering Trudge."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_160.card_impl import SlumberingTrudge
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.game import untap
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


def _stun_count(permanent: Creature) -> int:
    return max(permanent.counters.get("stun", 0), getattr(permanent, "stun_counters", 0))


class TestSlumberingTrudgeProperties:
    """Static card data should match the SOS 160 spec."""

    def test_is_plant_beast_creature(self) -> None:
        card = SlumberingTrudge(owner=None)

        assert isinstance(card, Creature)
        assert "Plant" in card.subtypes
        assert "Beast" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = SlumberingTrudge(owner=None)

        assert card.name == "Slumbering Trudge"
        assert card.mana_cost == ManaCost.parse("{X}{G}")
        assert card.base_power == 6
        assert card.base_toughness == 6


class TestSlumberingTrudgeResolution:
    """Slumbering Trudge should enter tapped for small X and carry stun counters."""

    def test_x_zero_adds_three_stun_counters_and_enters_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SlumberingTrudge(owner=p1, controller=p1)
        card.x_value = 0  # type: ignore[attr-defined]

        card.on_resolve(game)

        assert _stun_count(card) == 3
        assert card.is_tapped is True

    def test_x_two_adds_one_stun_counter_and_enters_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SlumberingTrudge(owner=p1, controller=p1)
        card.x_value = 2  # type: ignore[attr-defined]

        card.on_resolve(game)

        assert _stun_count(card) == 1
        assert card.is_tapped is True

    def test_x_three_adds_no_stun_counters_and_does_not_enter_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SlumberingTrudge(owner=p1, controller=p1)
        card.x_value = 3  # type: ignore[attr-defined]

        card.on_resolve(game)

        assert _stun_count(card) == 0
        assert card.is_tapped is False

    def test_x_greater_than_three_does_not_add_negative_stun_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SlumberingTrudge(owner=p1, controller=p1)
        card.x_value = 4  # type: ignore[attr-defined]

        card.on_resolve(game)

        assert _stun_count(card) == 0
        assert card.is_tapped is False

    def test_stun_counter_is_consumed_when_it_next_tries_to_untap(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SlumberingTrudge(owner=p1, controller=p1)
        card.x_value = 2  # type: ignore[attr-defined]

        card.on_resolve(game)
        untapped = untap(game, card)

        assert untapped is False
        assert card.is_tapped is True
        assert _stun_count(card) == 0
