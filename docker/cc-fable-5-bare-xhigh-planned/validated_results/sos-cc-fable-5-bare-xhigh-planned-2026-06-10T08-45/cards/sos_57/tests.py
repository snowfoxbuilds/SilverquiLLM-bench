"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import CastingError, cast_spell as engine_cast_spell, resolve_top
from engine.types import ManaCost, ManaType, Phase
from test_utils import advance_to_phase, create_game, set_board_state


def _counter_setup(wizard=False):
    """P2 casts a {2}{R} instant; P1 counters it with Mana Sculpt."""
    game = create_game()
    p1, p2 = game.players
    battlefield = []
    if wizard:
        battlefield.append(
            Creature(name="Apprentice", subtypes={"Wizard"},
                     base_power=1, base_toughness=1)
        )
    sculpt = ManaSculpt(owner=p1)
    set_board_state(game, 0, battlefield=battlefield, hand=[sculpt],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    opp_spell = Instant(name="Big Blast", mana_cost=ManaCost.parse("{2}{R}"))
    set_board_state(game, 1, hand=[opp_spell],
                    mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
    engine_cast_spell(game, p2, opp_spell)
    target_so = game.stack.peek()
    p1._script.append(target_so)
    engine_cast_spell(game, p1, sculpt)
    resolve_top(game)  # Mana Sculpt resolves, countering Big Blast
    return game, p1, p2, opp_spell, sculpt


class TestManaSculptCounter:
    def test_counters_spell_to_graveyard(self):
        game, p1, p2, opp_spell, sculpt = _counter_setup()
        assert game.stack.is_empty()
        assert game.get_graveyard(p2).contains(opp_spell)
        assert game.get_graveyard(p1).contains(sculpt)

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1)
        set_board_state(game, 0, hand=[sculpt],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, sculpt)

    def test_delayed_mana_with_wizard_at_your_next_main(self):
        # The counter happens during turn 1's beginning phase, so "your
        # next main phase" is this turn's own precombat main.
        game, p1, p2, _, _ = _counter_setup(wizard=True)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        assert len(game.stack) == 1
        resolve_top(game)
        # Big Blast cost {2}{R}: 3 mana was spent on it.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_does_not_fire_on_opponents_main(self):
        game, p1, p2, _, _ = _counter_setup(wizard=True)
        # Skip past p1's turn-1 main without resolving the trigger there;
        # it must not also fire on p2's main (turn 2).
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        game.stack.pop()  # discard the (unresolved) turn-1 firing
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)  # step off the main
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p2
        assert game.stack.is_empty()

    def test_no_wizard_no_delayed_mana(self):
        game, p1, p2, _, _ = _counter_setup(wizard=False)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        if not game.stack.is_empty():
            resolve_top(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_delayed_mana_is_one_shot(self):
        game, p1, p2, _, _ = _counter_setup(wizard=True)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main: fires
        resolve_top(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)  # step off the main
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p2's main
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1 again: nothing
        assert game.active_player is p1
        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
