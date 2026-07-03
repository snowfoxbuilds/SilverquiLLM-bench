"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant
from engine.basic_lands import Forest
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaType, Phase, Zone
from test_utils import create_game, set_board_state, cast_spell


class Bolt(Instant):
    """{2} — deal 3 damage to the non-active player (mana value 2)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Bolt")
        kwargs.setdefault("mana_cost", __import__("engine.types", fromlist=["ManaCost"]).ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        deal_damage(game, self, game.non_active_player, 3)


def _lib_add(game, pidx, cards):
    """Add cards to a library; last item ends up on top."""
    p = game.players[pidx]
    for c in cards:
        c.owner = p
        c.controller = p
        p.zones[Zone.LIBRARY].add(c)


def _resolve_stack(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _advance_to_p0_precombat(game, after_turn):
    for _ in range(60):
        game.advance_phase()
        if (game.phase is Phase.PRECOMBAT_MAIN
                and game.active_player_index == 0
                and game.turn_number > after_turn):
            break
    _resolve_stack(game)


def _cast_capstone(game, p0_choices):
    """Cast the Capstone from p0's hand with scripted choose_yes_no answers."""
    for ans in reversed(p0_choices):
        p0 = game.players[0]
        p0._script.appendleft(ans)
    cast_spell(game, 0, "Improvisation Capstone")


class TestProperties:
    def test_static(self):
        c = ImprovisationCapstone(owner=None)
        assert c.name == "Improvisation Capstone"
        from engine.types import ManaCost
        assert c.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in c.subtypes


class TestImprovise:
    def test_exiles_until_mv4_and_casts(self):
        game = create_game()
        p0, p1 = game.players
        # bottom filler, then two MV-2 bolts on top
        _lib_add(game, 0, [Forest(owner=None), Bolt(), Bolt()])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        _cast_capstone(game, [True, True])  # cast both bolts
        assert p1.life == 14                # 2 bolts × 3
        # Exactly two cards peeled (the Forest remains).
        assert len(game.get_library(p0)) == 1
        # Capstone exiled by Paradigm.
        cap = next(c for c in game.get_exile(p0).get_all()
                   if getattr(c, "name", "") == "Improvisation Capstone")
        assert cap is not None

    def test_lands_stay_exiled(self):
        game = create_game()
        p0, p1 = game.players
        # Top is a Forest (MV0) then a bolt (MV2) — keep peeling until MV>=4.
        _lib_add(game, 0, [Bolt(), Bolt(), Forest()])  # top=Forest
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        _cast_capstone(game, [True, True])  # cast the two bolts; land not offered
        from engine.types import CardType
        lands = [c for c in game.get_exile(p0).get_all()
                 if CardType.LAND in getattr(c, "card_types", set())]
        assert len(lands) == 1  # the land was peeled but never cast
        assert p1.life == 14

    def test_library_runs_out(self):
        game = create_game()
        p0, p1 = game.players
        _lib_add(game, 0, [Bolt()])  # only one card, MV2 < 4
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        _cast_capstone(game, [True])  # cast the single bolt
        assert len(game.get_library(p0)) == 0
        assert p1.life == 17

    def test_may_decline_casting(self):
        game = create_game()
        p0, p1 = game.players
        _lib_add(game, 0, [Forest(owner=None), Bolt(), Bolt()])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        _cast_capstone(game, [False, False])  # decline both
        assert p1.life == 20
        # The bolts remain exiled.
        assert sum(1 for c in game.get_exile(p0).get_all()
                   if getattr(c, "name", "") == "Bolt") == 2


class TestParadigm:
    def test_recurring_copy_from_exile(self):
        game = create_game()
        p0, p1 = game.players
        _lib_add(game, 0, [Forest(owner=None), Bolt(), Bolt()])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        _cast_capstone(game, [True, True])
        assert p1.life == 14
        # Refill the library for the Paradigm copy to improvise from.
        _lib_add(game, 0, [Bolt(), Bolt()])
        cast_turn = game.turn_number
        # On p0's next first main phase: cast a copy, then cast both new bolts.
        p0._script.extend([True, True, True])
        _advance_to_p0_precombat(game, after_turn=cast_turn)
        assert p1.life == 8  # two more bolts × 3
        # Original Capstone still in exile (the copy ceased to exist).
        caps = [c for c in game.get_exile(p0).get_all()
                if getattr(c, "name", "") == "Improvisation Capstone"]
        assert len(caps) == 1
