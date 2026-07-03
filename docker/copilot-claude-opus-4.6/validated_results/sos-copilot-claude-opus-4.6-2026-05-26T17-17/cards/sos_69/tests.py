"""Tests for SOS 69 — Tester of the Tangential.

A {1}{U} 1/1 Djinn Wizard with Increment and a combat trigger that moves
+1/+1 counters to another creature for {X}.
"""

from __future__ import annotations

from cards.sos.sos_69.card_impl import TesterOfTheTangential
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestTesterOfTheTangentialProperties:
    """Static card data should match the SOS 69 spec."""

    def test_is_creature(self) -> None:
        card = TesterOfTheTangential(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TesterOfTheTangential(owner=None)
        assert card.name == "Tester of the Tangential"

    def test_mana_cost(self) -> None:
        card = TesterOfTheTangential(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}")

    def test_power_toughness(self) -> None:
        card = TesterOfTheTangential(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_has_increment(self) -> None:
        card = TesterOfTheTangential(owner=None)
        assert Keyword.INCREMENT in card.keywords


class TestTesterOfTheTangentialIncrement:
    """Increment: gains +1/+1 counter when mana spent on a spell > power or toughness."""

    def test_increment_triggers_when_mana_exceeds_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TesterOfTheTangential(owner=p1, controller=p1)
        card.plus_one_counters = 0
        game.get_battlefield(p1).add(card)
        # Simulate casting a spell that cost 2 mana (> power 1)
        card.on_increment_trigger(game, mana_spent=2)
        assert card.plus_one_counters == 1

    def test_increment_does_not_trigger_when_mana_equals_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TesterOfTheTangential(owner=p1, controller=p1)
        card.plus_one_counters = 0
        game.get_battlefield(p1).add(card)
        # Mana spent (1) is not greater than power (1) or toughness (1)
        card.on_increment_trigger(game, mana_spent=1)
        assert card.plus_one_counters == 0

    def test_increment_triggers_when_mana_exceeds_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TesterOfTheTangential(owner=p1, controller=p1)
        card.plus_one_counters = 0
        # After gaining counters, toughness grows — but base is 1
        game.get_battlefield(p1).add(card)
        card.on_increment_trigger(game, mana_spent=2)
        assert card.plus_one_counters == 1


class TestTesterOfTheTangentialCombatAbility:
    """At beginning of combat, pay {X} to move X +1/+1 counters to another creature."""

    def test_move_counters_to_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TesterOfTheTangential(owner=p1, controller=p1)
        card.plus_one_counters = 3
        game.get_battlefield(p1).add(card)

        target = Creature(
            name="Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        target.plus_one_counters = 0
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(target)

        # Move 2 counters
        card.move_counters(game, target=target, x=2)
        assert card.plus_one_counters == 1
        assert target.plus_one_counters == 2

    def test_cannot_move_more_counters_than_available(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TesterOfTheTangential(owner=p1, controller=p1)
        card.plus_one_counters = 2
        game.get_battlefield(p1).add(card)

        target = Creature(
            name="Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        target.plus_one_counters = 0
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(target)

        # Trying to move 5 but only has 2 — should move at most 2 or fail
        card.move_counters(game, target=target, x=5)
        # Should not move more than available
        assert card.plus_one_counters >= 0
        assert target.plus_one_counters <= 2

    def test_move_zero_counters_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TesterOfTheTangential(owner=p1, controller=p1)
        card.plus_one_counters = 3
        game.get_battlefield(p1).add(card)

        target = Creature(
            name="Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        target.plus_one_counters = 0
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(target)

        card.move_counters(game, target=target, x=0)
        assert card.plus_one_counters == 3
        assert target.plus_one_counters == 0
