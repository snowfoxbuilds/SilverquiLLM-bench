"""Tests for SOS 63 — Pensive Professor."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_63.card_impl import PensiveProfessor
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.events import CounterAddedTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import cast_spell, create_game, set_board_state


class CheapTestInstant(Instant):
    """One-mana instant used to exercise Increment."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class TestPensiveProfessorProperties:
    """Static card data should match the SOS 63 spec."""

    def test_is_a_human_wizard_creature(self) -> None:
        card = PensiveProfessor(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = PensiveProfessor(owner=None)
        assert card.name == "Pensive Professor"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert card.base_power == 0
        assert card.base_toughness == 2


class TestPensiveProfessorTriggers:
    """Pensive Professor should grow from Increment and draw from counters."""

    def test_casting_a_one_mana_spell_adds_a_counter_and_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        drawn_card = CardImpl(name="Fresh Insight", owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)
        professor = PensiveProfessor(owner=p1, controller=p1)
        game.get_library(p1).add(drawn_card)
        set_board_state(
            game,
            0,
            battlefield=[professor],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        professor.register_triggers(game)

        cast_spell(game, 0, "Cheap Test Instant")

        assert professor.plus_one_counters == 1
        assert game.get_hand(p1).contains(drawn_card)
        assert game.get_graveyard(p1).contains(spell)

    def test_casting_a_small_spell_does_not_trigger_increment_once_its_stats_are_high_enough(self) -> None:
        game = create_game()
        p1 = game.players[0]
        undrawn_card = CardImpl(name="Still Waiting", owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)
        professor = PensiveProfessor(owner=p1, controller=p1)
        professor.plus_one_counters = 1
        professor._base_plus_one_counters = 1
        game.get_library(p1).add(undrawn_card)
        set_board_state(
            game,
            0,
            battlefield=[professor],
            hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        professor.register_triggers(game)

        cast_spell(game, 0, "Cheap Test Instant")

        assert professor.plus_one_counters == 1
        assert not game.get_hand(p1).contains(undrawn_card)
        assert game.get_library(p1).contains(undrawn_card)

    def test_counter_added_trigger_draws_once_even_when_multiple_counters_are_added(self) -> None:
        game = create_game()
        p1 = game.players[0]
        drawn_card = CardImpl(name="Big Discovery", owner=p1, controller=p1)
        professor = PensiveProfessor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[professor])
        game.get_library(p1).add(drawn_card)
        professor.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            CounterAddedTriggeredEvent(
                permanent=professor,
                counter_type="+1/+1",
                amount=2,
            ),
        )
        resolve_top(game)

        assert game.get_hand(p1).contains(drawn_card)
        assert len(game.get_hand(p1).get_all()) == 1
