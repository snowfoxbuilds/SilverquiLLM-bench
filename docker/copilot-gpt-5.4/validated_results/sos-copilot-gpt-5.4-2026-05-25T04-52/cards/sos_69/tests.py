"""Tests for SOS 69 — Tester of the Tangential."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_69.card_impl import (
    TesterOfTheTangential as CardTesterOfTheTangential,
)
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import BeginningOfCombatTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class OneManaTestInstant(Instant):
    """One-mana instant used to exercise Increment thresholds."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "One-Mana Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class TwoManaTestInstant(Instant):
    """Two-mana instant used to exercise Increment thresholds."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Two-Mana Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)


class TestTesterOfTheTangentialProperties:
    """Static card data should match the SOS 69 spec."""

    def test_is_djinn_wizard_creature(self) -> None:
        card = CardTesterOfTheTangential(owner=None)
        assert isinstance(card, Creature)
        assert "Djinn" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = CardTesterOfTheTangential(owner=None)
        assert card.name == "Tester of the Tangential"
        assert card.mana_cost == ManaCost.parse("{1}{U}")
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestTesterOfTheTangentialIncrement:
    """Tester of the Tangential should grow from qualifying spells."""

    def test_casting_a_two_mana_spell_adds_a_plus_one_plus_one_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestInstant(owner=p1, controller=p1)
        card = CardTesterOfTheTangential(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Instant")

        assert card.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(spell)

    def test_casting_a_two_mana_spell_does_not_trigger_increment_once_it_is_a_two_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TwoManaTestInstant(owner=p1, controller=p1)
        card = CardTesterOfTheTangential(owner=p1, controller=p1)
        card.plus_one_counters = 1
        card._base_plus_one_counters = 1
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        card.register_triggers(game)

        cast_spell(game, 0, "Two-Mana Test Instant")

        assert card.plus_one_counters == 1


class TestTesterOfTheTangentialBeginningOfCombat:
    """Tester of the Tangential should move counters at the beginning of combat on your turn."""

    def test_registers_a_beginning_of_combat_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CardTesterOfTheTangential(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(trigger.event_type is BeginningOfCombatTriggeredEvent for trigger in triggers)

    def test_does_not_trigger_on_an_opponents_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CardTesterOfTheTangential(owner=p1, controller=p1)
        game.active_player_index = 1

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())

        assert game.stack.is_empty()

    def test_beginning_of_combat_may_pay_x_to_move_that_many_counters_to_another_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CardTesterOfTheTangential(owner=p1, controller=p1)
        recipient = Creature(
            name="Study Partner",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        card.plus_one_counters = 3
        card._base_plus_one_counters = 3
        set_board_state(
            game,
            0,
            battlefield=[card, recipient],
            mana={ManaType.COLORLESS: 2},
        )
        p1.choose = lambda options, description: 2
        p1.choose_target = lambda options, requirement: recipient
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
        resolve_top(game)

        assert card.plus_one_counters == 1
        assert recipient.plus_one_counters == 2
        assert p1.mana_pool.total() == 0
