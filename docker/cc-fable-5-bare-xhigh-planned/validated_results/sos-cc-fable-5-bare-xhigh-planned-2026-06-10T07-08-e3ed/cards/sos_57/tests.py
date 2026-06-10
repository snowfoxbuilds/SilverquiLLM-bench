"""Tests for Mana Sculpt (sos_57)."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import CastingError, cast_spell
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _bear() -> Creature:
    return Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                    base_power=2, base_toughness=2)


def _wizard() -> Creature:
    return Creature(name="Sage", subtypes={"Wizard"},
                    base_power=1, base_toughness=1)


def _counter_opponents_bear(game, p1_extra_battlefield=None):
    """P2 casts a bear ({1}{G}, 2 mana spent); P1 counters it with Mana Sculpt."""
    p1, p2 = game.players
    bear = _bear()
    set_board_state(game, 1, hand=[bear],
                    mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1})
    set_board_state(game, 0, hand=[ManaSculpt()],
                    battlefield=p1_extra_battlefield or [],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    game.active_player_index = 1
    game._normal_next_index = 0  # next turn belongs to p1
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None

    cast_spell(game, p2, bear)
    sculpt = p1.zones[Zone.HAND].get_all()[0]
    p1._script.append(game.stack.peek())  # target: the bear on the stack
    cast_spell(game, p1, sculpt)

    p2._script.append("pass")
    p1._script.append("pass")
    priority_loop(game)
    return bear, sculpt


class TestManaSculpt:
    def test_counters_target_spell(self):
        game = create_game()
        p1, p2 = game.players
        bear, sculpt = _counter_opponents_bear(game)

        assert p2.zones[Zone.GRAVEYARD].contains(bear)
        assert not p2.zones[Zone.BATTLEFIELD].contains(bear)
        assert p1.zones[Zone.GRAVEYARD].contains(sculpt)
        assert game.stack.is_empty()

    def test_delayed_mana_with_wizard(self):
        game = create_game()
        p1, p2 = game.players
        _counter_opponents_bear(game, p1_extra_battlefield=[_wizard()])

        # Advance to p1's next precombat main; the delayed trigger fires.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        p1._script.extend(["pass", "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        # Bear cost {1}{G}: two mana were spent to cast it.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_mana(self):
        game = create_game()
        p1, p2 = game.players
        _counter_opponents_bear(game)

        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        p1._script.extend(["pass", "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_one_shot_does_not_repeat(self):
        game = create_game()
        p1, p2 = game.players
        _counter_opponents_bear(game, p1_extra_battlefield=[_wizard()])

        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        p1._script.extend(["pass", "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

        # A full extra turn cycle back to p1's main: no second payout.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p2's main
        assert game.active_player is p2
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main again
        assert game.active_player is p1
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt()
        set_board_state(game, 0, hand=[sculpt], mana={ManaType.BLUE: 3})
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        with pytest.raises(CastingError):
            cast_spell(game, p1, sculpt)
