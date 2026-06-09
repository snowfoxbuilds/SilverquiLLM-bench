"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land, Sorcery
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _gain(name, cmc, amount):
    class _G(Instant):
        def __init__(self, **kw):
            kw.setdefault("name", name)
            kw.setdefault("mana_cost", ManaCost(generic=cmc))
            super().__init__(**kw)

        def on_resolve(self, game):
            if self.controller is not None:
                self.controller.life += amount
    return _G(owner=None)


def _lib_add(game, player_index, cards):
    p = game.players[player_index]
    for c in cards:
        c.owner = p
        c.controller = p
        p.zones[Zone.LIBRARY].add(c)


def _advance_to_p0_precombat_main(game):
    for _ in range(40):
        game.advance_phase()
        if game.active_player_index == 0 and game.phase == Phase.PRECOMBAT_MAIN:
            return
    raise AssertionError("did not reach p0 precombat main")


def _resolve_stack(game):
    from engine.state_based_actions import resolve_state_based_actions
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _cast_capstone(game, scripts_p0):
    p0 = game.players[0]
    cap = ImprovisationCapstone(owner=p0, controller=p0)
    set_board_state(game, 0, hand=[cap],
                    mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
    for s in reversed(scripts_p0):
        p0._script.appendleft(s)
    cast_spell(game, 0, "Improvisation Capstone")
    return cap


class TestProperties:
    def test_is_sorcery_lesson(self):
        c = ImprovisationCapstone(owner=None)
        assert isinstance(c, Sorcery)
        assert "Lesson" in c.subtypes
        assert c.mana_cost == ManaCost.parse("{5}{R}{R}")


class TestResolve:
    def test_peel_until_mv4_and_cast(self):
        game = create_game()
        p0 = game.players[0]
        a = _gain("A", 2, 2)
        b = _gain("B", 3, 3)
        _lib_add(game, 0, [a, b])  # top = b
        set_board_state(game, 0, life=20)
        cap = _cast_capstone(game, [True, True])
        # Peeled b(3)+a(2)=5 >= 4; both cast → +5 life; both in graveyard.
        assert p0.life == 25
        assert game.get_graveyard(p0).contains(a)
        assert game.get_graveyard(p0).contains(b)
        # Paradigm: Capstone exiled, not in graveyard.
        assert game.get_exile(p0).contains(cap)
        assert not game.get_graveyard(p0).contains(cap)

    def test_land_stays_exiled(self):
        game = create_game()
        p0 = game.players[0]
        spell4 = _gain("Four", 4, 4)
        land = Land(name="Wastes")
        _lib_add(game, 0, [spell4, land])  # top = land
        set_board_state(game, 0, life=20)
        _cast_capstone(game, [True])  # only spell4 prompts
        assert game.get_exile(p0).contains(land)
        assert game.get_graveyard(p0).contains(spell4)
        assert p0.life == 24

    def test_library_runs_out(self):
        game = create_game()
        p0 = game.players[0]
        only = _gain("Solo", 2, 2)
        _lib_add(game, 0, [only])  # total 2 < 4, then empty
        set_board_state(game, 0, life=20)
        _cast_capstone(game, [True])
        assert p0.life == 22
        assert game.get_graveyard(p0).contains(only)


class TestParadigm:
    def test_recurring_copy_casts_again(self):
        game = create_game()
        p0 = game.players[0]
        c = _gain("C", 4, 4)
        a = _gain("A", 2, 2)
        b = _gain("B", 3, 3)
        _lib_add(game, 0, [c, a, b])  # top = b
        set_board_state(game, 0, life=20)
        # First cast: peel b+a (cast both). Then next main: cast a copy → peel c.
        cap = _cast_capstone(game, [True, True, True, True])
        assert p0.life == 25  # +5 from first cast
        _advance_to_p0_precombat_main(game)
        _resolve_stack(game)
        # Copy peeled c(4) and cast it → +4 more.
        assert p0.life == 29
        assert game.get_graveyard(p0).contains(c)
        # Original Capstone remains in exile for future turns.
        assert game.get_exile(p0).contains(cap)
