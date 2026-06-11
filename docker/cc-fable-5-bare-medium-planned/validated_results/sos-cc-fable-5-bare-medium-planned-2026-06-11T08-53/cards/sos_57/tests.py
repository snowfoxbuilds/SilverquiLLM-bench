"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase
from test_utils import advance_to_phase, create_game, set_board_state


def _advance_to_next_main(game) -> None:
    """Step off the current (precombat main) phase, then advance to the
    next turn's precombat main."""
    game.advance_phase()
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)


def _counter_setup(game, *, wizard: bool):
    """P2 (active) casts a 2-mana Bear; P1 counters it with Mana Sculpt."""
    p1, p2 = game.players
    game.active_player_index = 1
    game.priority_player_index = 1
    game._normal_next_index = 0  # P1 takes the next turn
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None

    battlefield = []
    if wizard:
        battlefield.append(
            Creature(name="Sage", base_power=1, base_toughness=1,
                     subtypes={"Wizard"})
        )
    set_board_state(game, 0, battlefield=battlefield,
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})

    bear = Creature(name="Bear", base_power=2, base_toughness=2,
                    mana_cost=ManaCost(generic=2))
    set_board_state(game, 1, hand=[bear], mana={ManaType.COLORLESS: 2})
    engine_cast_spell(game, p2, bear)

    sculpt = ManaSculpt()
    game.get_hand(p1).add(sculpt)
    sculpt.owner = sculpt.controller = p1
    p1._script.appendleft(game.stack.peek())  # target the Bear spell
    engine_cast_spell(game, p1, sculpt)
    priority_loop(game)
    return bear, sculpt


class TestManaSculpt:
    def test_counters_target_spell(self) -> None:
        game = create_game(scripts=(["pass"] * 4, ["pass"] * 4))
        p1, p2 = game.players
        bear, sculpt = _counter_setup(game, wizard=True)
        assert game.get_graveyard(p2).contains(bear)
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p1).contains(sculpt)

    def test_delayed_mana_with_wizard(self) -> None:
        game = create_game(scripts=(["pass"] * 8, ["pass"] * 8))
        p1, p2 = game.players
        _counter_setup(game, wizard=True)
        # Advance to P1's next precombat main; the delayed trigger fires.
        _advance_to_next_main(game)
        assert game.active_player is p1
        priority_loop(game)
        # Bear cost {2} paid in full → add {C}{C}.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_mana(self) -> None:
        game = create_game(scripts=(["pass"] * 8, ["pass"] * 8))
        p1, p2 = game.players
        _counter_setup(game, wizard=False)
        _advance_to_next_main(game)
        assert game.active_player is p1
        priority_loop(game)
        assert p1.mana_pool.total() == 0

    def test_delayed_trigger_is_one_shot(self) -> None:
        game = create_game(scripts=(["pass"] * 12, ["pass"] * 12))
        p1, p2 = game.players
        _, sculpt = _counter_setup(game, wizard=True)
        _advance_to_next_main(game)
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        # The one-shot trigger unregistered itself.
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt()
        set_board_state(game, 0, hand=[sculpt],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        try:
            engine_cast_spell(game, p1, sculpt)
            raised = False
        except CastingError:
            raised = True
        assert raised
