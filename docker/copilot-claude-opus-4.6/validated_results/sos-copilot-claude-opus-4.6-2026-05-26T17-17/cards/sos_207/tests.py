"""Tests for SOS 207 — Old-Growth Educator.

Creature — Treefolk Druid (4/4) {2}{B}{G}
- Vigilance, reach
- Infusion — When this creature enters, put two +1/+1 counters on it if you gained life this turn.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_207.card_impl import OldGrowthEducator
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestOldGrowthEducatorProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = OldGrowthEducator(owner=None)
        assert card.name == "Old-Growth Educator"

    def test_mana_cost(self) -> None:
        card = OldGrowthEducator(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{B}{G}")

    def test_power_toughness(self) -> None:
        card = OldGrowthEducator(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_is_creature(self) -> None:
        card = OldGrowthEducator(owner=None)
        assert isinstance(card, Creature)

    def test_has_vigilance(self) -> None:
        card = OldGrowthEducator(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_has_reach(self) -> None:
        card = OldGrowthEducator(owner=None)
        assert Keyword.REACH in card.keywords


class TestOldGrowthEducatorInfusion:
    """Infusion — When this enters, put two +1/+1 counters if you gained life this turn."""

    def test_no_life_gain_no_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = OldGrowthEducator(owner=p1, controller=p1)

        # Player has NOT gained life this turn
        game.players[0].life_gained_this_turn = 0
        card.on_enter_battlefield(game)

        assert card.plus_one_counters == 0

    def test_life_gained_this_turn_adds_two_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = OldGrowthEducator(owner=p1, controller=p1)

        # Player HAS gained life this turn
        game.players[0].life_gained_this_turn = 3
        card.on_enter_battlefield(game)

        assert card.plus_one_counters == 2

    def test_exactly_one_life_gained_still_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = OldGrowthEducator(owner=p1, controller=p1)

        game.players[0].life_gained_this_turn = 1
        card.on_enter_battlefield(game)

        assert card.plus_one_counters == 2

    def test_counters_make_it_six_six(self) -> None:
        """With infusion, the creature is effectively 6/6."""
        game = create_game()
        p1 = game.players[0]
        card = OldGrowthEducator(owner=p1, controller=p1)

        game.players[0].life_gained_this_turn = 5
        card.on_enter_battlefield(game)

        assert card.power == 6
        assert card.toughness == 6
