"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import (
    _resolve_top_of_stack,
    advance_to_phase,
    create_game,
    set_board_state,
)


def _counter_setup(p1_battlefield):
    """p2 casts Fleeting Flight at a bear; p1 counters it with Mana Sculpt."""
    game = create_game()
    p1, p2 = game.players
    bear = Creature(name="Bear", base_power=2, base_toughness=2)
    set_board_state(game, 1, battlefield=[bear], mana={ManaType.WHITE: 1})
    flight = FleetingFlight(owner=None)
    p2.zones[Zone.HAND].add(flight)
    flight.owner = flight.controller = p2

    sculpt = ManaSculpt(owner=None)
    set_board_state(
        game, 0,
        battlefield=p1_battlefield,
        hand=[sculpt],
        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2},
    )

    p2._script.append(bear)
    engine_cast_spell(game, p2, flight)
    target_so = game.stack.peek()

    p1._script.append(target_so)
    engine_cast_spell(game, p1, sculpt)
    _resolve_top_of_stack(game)
    return game, p1, p2, bear, flight, sculpt


class TestManaSculptCounter:
    def test_counters_target_spell(self):
        game, p1, p2, bear, flight, sculpt = _counter_setup([])
        assert game.stack.is_empty()
        assert game.get_graveyard(p2).contains(flight)
        assert bear.plus_one_counters == 0  # spell never resolved
        assert game.get_graveyard(p1).contains(sculpt)

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=None)
        set_board_state(
            game, 0, hand=[sculpt],
            mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2},
        )
        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, sculpt)


class TestManaSculptDelayedMana:
    def test_wizard_grants_colorless_at_next_main_phase(self):
        wizard = Creature(
            name="Apprentice", base_power=1, base_toughness=1,
            subtypes={"Wizard"},
        )
        game, p1, p2, bear, flight, sculpt = _counter_setup([wizard])
        # Fleeting Flight cost {W} → 1 mana spent.
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_top_of_stack(game)  # the delayed trigger
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_delayed_mana_is_one_shot(self):
        wizard = Creature(
            name="Apprentice", base_power=1, base_toughness=1,
            subtypes={"Wizard"},
        )
        game, p1, p2, bear, flight, sculpt = _counter_setup([wizard])
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        # Cross to p2's turn, then back to p1's precombat main — no re-add.
        from engine.types import Step

        advance_to_phase(game, Phase.ENDING, Step.END)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p2's main (turn 2)
        advance_to_phase(game, Phase.ENDING, Step.END)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main (turn 3)
        _resolve_top_of_stack(game)
        assert game.active_player is p1
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_wizard_no_mana(self):
        game, p1, p2, bear, flight, sculpt = _counter_setup([])
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_top_of_stack(game)
        assert p1.mana_pool.total() == 0

    def test_wizard_checked_when_trigger_fires(self):
        # No Wizard when the spell is countered, but one arrives before
        # the next main phase — the mana is still granted (per plan).
        game, p1, p2, bear, flight, sculpt = _counter_setup([])
        wizard = Creature(
            name="Late Wizard", base_power=1, base_toughness=1,
            subtypes={"Wizard"},
        )
        wizard.owner = wizard.controller = p1
        game.get_battlefield(p1).add(wizard)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_countering_free_cast_grants_nothing(self):
        from engine.casting import cast_spell_free

        game = create_game()
        p1, p2 = game.players
        wizard = Creature(
            name="Apprentice", base_power=1, base_toughness=1,
            subtypes={"Wizard"},
        )
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        flight = FleetingFlight(owner=None)
        p2.zones[Zone.HAND].add(flight)
        flight.owner = flight.controller = p2

        sculpt = ManaSculpt(owner=None)
        set_board_state(
            game, 0, battlefield=[wizard], hand=[sculpt],
            mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2},
        )

        p2._script.append(bear)
        cast_spell_free(game, p2, flight, Zone.HAND)
        target_so = game.stack.peek()
        p1._script.append(target_so)
        engine_cast_spell(game, p1, sculpt)
        _resolve_top_of_stack(game)
        assert game.get_graveyard(p2).contains(flight)

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_top_of_stack(game)
        assert p1.mana_pool.total() == 0
