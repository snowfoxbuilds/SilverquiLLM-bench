"""Tests for SOS 2 — Rancorous Archaic."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_2.card_impl import RancorousArchaic
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestRancorousArchaicProperties:
    """Static card data should match the SOS 2 spec."""

    def test_is_creature_with_trample_and_reach(self) -> None:
        card = RancorousArchaic(owner=None)
        assert isinstance(card, Creature)
        assert Keyword.TRAMPLE in card.keywords
        assert Keyword.REACH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = RancorousArchaic(owner=None)
        assert card.name == "Rancorous Archaic"
        assert card.mana_cost == ManaCost.parse("{5}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestRancorousArchaicConverge:
    """The creature should enter with a counter per color spent."""

    def test_empty_colors_spent_adds_no_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RancorousArchaic(owner=p1, controller=p1)

        card.colors_spent = []
        card.on_resolve(game)

        assert card.plus_one_counters == 0
        assert card.power == 2
        assert card.toughness == 2

    def test_three_colors_spent_adds_three_plus_one_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RancorousArchaic(owner=p1, controller=p1)

        card.colors_spent = [Color.W, Color.U, Color.B]
        card.on_resolve(game)

        assert card.plus_one_counters == 3
        assert card.power == 5
        assert card.toughness == 5
