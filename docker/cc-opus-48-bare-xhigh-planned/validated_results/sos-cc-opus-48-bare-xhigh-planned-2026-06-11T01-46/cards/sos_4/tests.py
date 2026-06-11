"""Tests for Together as One (sos_4) — Converge."""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _fill_library(game, player_index, n):
    lib = game.players[player_index].zones[Zone.LIBRARY]
    p = game.players[player_index]
    for i in range(n):
        c = Creature(name=f"Dummy{i}", base_power=1, base_toughness=1, owner=p, controller=p)
        lib.add(c)


class TestTogetherAsOne:
    def test_converge_three_colors(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 0, 6)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2})
        lib_before = len(p0.zones[Zone.LIBRARY])
        # draw to self (p0), damage to opponent player (p1)
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert lib_before - len(p0.zones[Zone.LIBRARY]) == 3  # drew X=3
        assert p1.life == 17   # took 3 damage
        assert p0.life == 23   # gained 3 life

    def test_converge_colorless_x_zero(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 0, 6)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.COLORLESS: 6})
        lib_before = len(p0.zones[Zone.LIBRARY])
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert lib_before - len(p0.zones[Zone.LIBRARY]) == 0
        assert p1.life == 20
        assert p0.life == 20

    def test_converge_five_colors(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 0, 6)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 1, ManaType.BLACK: 1,
                              ManaType.RED: 1, ManaType.GREEN: 1})
        lib_before = len(p0.zones[Zone.LIBRARY])
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert lib_before - len(p0.zones[Zone.LIBRARY]) == 5
        assert p1.life == 15
        assert p0.life == 25

    def test_converge_damage_to_creature(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 0, 6)
        bear = Creature(name="Bear", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 3, ManaType.GREEN: 3})
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        assert bear.damage_marked == 2   # X=2 colors
        assert p0.life == 22
