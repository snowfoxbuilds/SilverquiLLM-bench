"""Tests for SOS 151 — Hungry Graffalon.

A 3/4 Creature — Giraffe with Reach and Increment.
Increment: Whenever you cast a spell, if the amount of mana you spent is
greater than this creature's power or toughness, put a +1/+1 counter on it.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_151.card_impl import HungryGraffalon
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


class TestHungryGraffalonProperties:
    """Static card data should match the SOS 151 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HungryGraffalon(owner=None), Creature)

    def test_name(self) -> None:
        assert HungryGraffalon(owner=None).name == "Hungry Graffalon"

    def test_mana_cost(self) -> None:
        assert HungryGraffalon(owner=None).mana_cost == ManaCost.parse("{3}{G}")

    def test_power_toughness(self) -> None:
        card = HungryGraffalon(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_reach(self) -> None:
        assert Keyword.REACH in HungryGraffalon(owner=None).keywords


class TestHungryGraffalonIncrement:
    """Increment triggers when mana spent on a spell exceeds power or toughness."""

    def test_increment_triggers_when_mana_exceeds_power(self) -> None:
        """Casting a spell for 4 mana (> power 3) should trigger increment."""
        game = create_game()
        p1 = game.players[0]
        graffalon = HungryGraffalon(owner=p1, controller=p1)
        game.get_battlefield(p1).add(graffalon)
        # Simulate casting a spell that costs 4 mana (> power 3)
        graffalon.on_spell_cast(game, mana_spent=4)
        assert graffalon.plus_one_counters >= 1

    def test_increment_does_not_trigger_when_mana_equal_to_power(self) -> None:
        """Casting a spell for exactly 3 mana (= power 3) should NOT trigger."""
        game = create_game()
        p1 = game.players[0]
        graffalon = HungryGraffalon(owner=p1, controller=p1)
        game.get_battlefield(p1).add(graffalon)
        graffalon.on_spell_cast(game, mana_spent=3)
        assert graffalon.plus_one_counters == 0

    def test_increment_does_not_trigger_when_mana_less_than_both(self) -> None:
        """Casting a spell for 2 mana (< both P and T) should NOT trigger."""
        game = create_game()
        p1 = game.players[0]
        graffalon = HungryGraffalon(owner=p1, controller=p1)
        game.get_battlefield(p1).add(graffalon)
        graffalon.on_spell_cast(game, mana_spent=2)
        assert graffalon.plus_one_counters == 0

    def test_increment_triggers_when_mana_exceeds_toughness(self) -> None:
        """Casting a spell for 5 mana (> toughness 4) should trigger."""
        game = create_game()
        p1 = game.players[0]
        graffalon = HungryGraffalon(owner=p1, controller=p1)
        game.get_battlefield(p1).add(graffalon)
        graffalon.on_spell_cast(game, mana_spent=5)
        assert graffalon.plus_one_counters >= 1

    def test_increment_only_adds_one_counter_per_trigger(self) -> None:
        """Each trigger adds exactly one +1/+1 counter."""
        game = create_game()
        p1 = game.players[0]
        graffalon = HungryGraffalon(owner=p1, controller=p1)
        game.get_battlefield(p1).add(graffalon)
        graffalon.on_spell_cast(game, mana_spent=10)
        assert graffalon.plus_one_counters == 1
