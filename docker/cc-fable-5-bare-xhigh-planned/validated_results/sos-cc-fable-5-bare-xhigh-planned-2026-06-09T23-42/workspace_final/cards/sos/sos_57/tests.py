"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import cast_spell as engine_cast_spell
from engine.casting import cast_spell_free
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _wizard() -> Creature:
    return Creature(
        name="Wiz", subtypes={"Wizard"}, base_power=1, base_toughness=1
    )


def _beast() -> Creature:
    return Creature(
        name="Beast", mana_cost=ManaCost.parse("{2}{R}"),
        base_power=3, base_toughness=3,
    )


def _counter_beast(game, *, free_cast=False):
    """p2 casts Beast (on the stack); p1 counters it with Mana Sculpt."""
    p1, p2 = game.players
    game.active_player_index = 1
    game.priority_player_index = 1
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    beast = _beast()
    if free_cast:
        set_board_state(game, 1, hand=[beast])
        cast_spell_free(game, p2, beast, Zone.HAND)
    else:
        set_board_state(game, 1, hand=[beast], mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        engine_cast_spell(game, p2, beast)
    beast_so = game.stack.peek()

    sculpt = ManaSculpt()
    hand = game.get_hand(p1)
    sculpt.owner = sculpt.controller = p1
    hand.add(sculpt)
    p1.mana_pool.add(ManaType.BLUE, 2)
    p1.mana_pool.add(ManaType.COLORLESS, 1)
    p1._script.extend([beast_so, "pass"])
    p2._script.extend(["pass"])
    engine_cast_spell(game, p1, sculpt)
    priority_loop(game)
    return beast, sculpt


def _advance_to_p1_main(game):
    """Advance until the precombat-main event fires for player 0, then resolve."""
    from engine.types import Step
    from test_utils import advance_to_phase

    for _ in range(2):
        if (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None):
            advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        if game.active_player is game.players[0]:
            break
    p1, p2 = game.players
    if not game.stack.is_empty():
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)


class TestManaSculpt:
    def test_counter_and_delayed_mana_with_wizard(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        beast, sculpt = _counter_beast(game)
        assert game.get_graveyard(p2).contains(beast)
        assert not game.get_battlefield(p2).contains(beast)
        assert game.get_graveyard(p1).contains(sculpt)
        _advance_to_p1_main(game)
        # Beast was cast for {2}{R} = 3 mana spent.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_no_wizard_no_delayed_mana(self):
        game = create_game()
        p1, p2 = game.players
        beast, _ = _counter_beast(game)
        assert game.get_graveyard(p2).contains(beast)
        _advance_to_p1_main(game)
        assert p1.mana_pool.total() == 0

    def test_freely_cast_spell_grants_zero_mana(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        beast, _ = _counter_beast(game, free_cast=True)
        assert game.get_graveyard(p2).contains(beast)
        _advance_to_p1_main(game)
        assert p1.mana_pool.total() == 0

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        set_board_state(
            game, 0, hand=[ManaSculpt()],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Mana Sculpt")

    def test_wizard_checked_at_resolution(self):
        from engine.game import destroy

        game = create_game()
        p1, _ = game.players
        wiz = _wizard()
        set_board_state(game, 0, battlefield=[wiz])
        _counter_beast(game)
        # Wizard leaves before the main phase — delayed mana already set up.
        destroy(game, wiz)
        _advance_to_p1_main(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
