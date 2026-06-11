"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Phase, Step
from test_utils import create_game, set_board_state, advance_to_phase


def _advance_to_next_precombat_main(game) -> None:
    """Advance into the NEXT turn's precombat main (advance_to_phase
    no-ops when the game is already in a precombat main)."""
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)


def _setup_countered_bear(game, *, wizard: bool = False):
    """Opponent (p2, active) casts a 2-mana bear; p1 counters it.

    Returns (bear_card, sculpt_card). Leaves the game in p2's precombat
    main with an empty stack and the delayed-mana trigger (if any) armed.
    """
    p1, p2 = game.players
    # p2 is the active player in their precombat main.
    game.active_player_index = 1
    game.priority_player_index = 1
    game._normal_next_index = 0  # p1 takes the next turn
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None

    bf1 = []
    if wizard:
        bf1.append(Creature(name="Lab Wizard", base_power=1, base_toughness=1,
                            subtypes={"Wizard"}))
    set_board_state(game, 0, battlefield=bf1)

    bear = Creature(name="Bear", base_power=2, base_toughness=2,
                    mana_cost=ManaCost.parse("{2}"))
    set_board_state(game, 1, hand=[bear], mana={ManaType.COLORLESS: 2})
    engine_cast_spell(game, p2, bear)  # on the stack, unresolved

    sculpt = ManaSculpt()
    set_board_state(game, 0, hand=[sculpt],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    # Consumption order: p1 pops the target during the sculpt cast; then
    # in the priority loop the active player (p2) passes first, then p1;
    # the sculpt resolves and counters the bear, emptying the stack.
    p1._script.extend([game.stack.peek(), "pass"])
    p2._script.extend(["pass"])
    engine_cast_spell(game, p1, sculpt)
    priority_loop(game)
    return bear, sculpt


class TestManaSculptProperties:
    def test_static_data(self) -> None:
        card = ManaSculpt()
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert CardType.INSTANT in card.card_types


class TestManaSculptCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear, sculpt = _setup_countered_bear(game)
        assert game.get_graveyard(p2).contains(bear)
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p1).contains(sculpt)
        assert game.stack.is_empty()

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt()
        set_board_state(game, 0, hand=[sculpt],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        with pytest.raises(Exception):
            engine_cast_spell(game, p1, sculpt)


class TestManaSculptDelayedMana:
    def test_wizard_grants_mana_at_next_main(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _setup_countered_bear(game, wizard=True)
        # Advance to p1's precombat main (next turn) — the trigger fires
        # there and resolves through the priority loop.
        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2  # bear cost {2}

    def test_no_wizard_no_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _setup_countered_bear(game, wizard=False)
        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_delayed_mana_is_one_shot(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _setup_countered_bear(game, wizard=True)
        _advance_to_next_precombat_main(game)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        # A full extra turn cycle back to p1's main must not re-fire.
        _advance_to_next_precombat_main(game)  # p2's main
        assert game.active_player is not p1
        _advance_to_next_precombat_main(game)  # p1's main again
        assert game.active_player is p1
        priority_loop(game)  # nothing on the stack — auto-passes
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
