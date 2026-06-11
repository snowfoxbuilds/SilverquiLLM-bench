"""Tests for Mana Sculpt (sos_57)."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import CastingError, cast_spell as engine_cast_spell, resolve_top
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _counter_setup(game, *, wizard=True):
    """Player 0 casts a 3-mana creature; player 1 counters it with Mana Sculpt."""
    p0, p1 = game.players
    bear = Creature(name="Costly Bear", mana_cost=ManaCost.parse("{2}{G}"),
                    base_power=2, base_toughness=2)
    set_board_state(game, 0, hand=[bear], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 2})
    bf1 = [Creature(name="Lab Wizard", subtypes={"Wizard"}, base_power=1, base_toughness=1)] if wizard else []
    set_board_state(game, 1, battlefield=bf1, hand=[ManaSculpt(owner=None)],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, p0, bear)
    sculpt = p1.zones[Zone.HAND].get_all()[0]
    p1._script.append(game.stack.peek())  # target the bear spell
    engine_cast_spell(game, p1, sculpt)
    while not game.stack.is_empty():
        resolve_top(game)
    return bear


class TestManaSculpt:
    def test_counters_target_spell(self):
        game = create_game()
        p0 = game.players[0]
        bear = _counter_setup(game)
        assert p0.zones[Zone.GRAVEYARD].contains(bear)
        assert not game.get_battlefield(p0).contains(bear)

    def test_delayed_colorless_mana_with_wizard(self):
        game = create_game()
        p1 = game.players[1]
        _counter_setup(game, wizard=True)
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # wraps into p1's turn
        assert game.active_player is p1
        assert len(game.stack) == 1
        resolve_top(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3  # bear cost 3 paid

    def test_no_wizard_no_delayed_mana(self):
        game = create_game()
        p1 = game.players[1]
        _counter_setup(game, wizard=False)
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        while not game.stack.is_empty():
            resolve_top(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_trigger_is_one_shot(self):
        game = create_game()
        p1 = game.players[1]
        _counter_setup(game, wizard=True)
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        resolve_top(game)
        # Advance a full cycle to p1's next precombat main — nothing fires.
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p0's turn
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's turn again
        assert game.stack.is_empty()

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        p1 = game.players[1]
        set_board_state(game, 1, hand=[ManaSculpt(owner=None)],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        sculpt = p1.zones[Zone.HAND].get_all()[0]
        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, sculpt)
