"""Tests for Together as One (sos_4)."""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _filler(n: int) -> list:
    return [CardImpl(name=f"Filler{i}", mana_cost=ManaCost()) for i in range(n)]


class TestTogetherAsOne:
    def test_three_colors(self):
        """Spending W, U, B (3 colors): draw 3, deal 3, gain 3."""
        game = create_game(deck1=_filler(10))
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2})
        p0, p1 = game.players
        lib_before = len(game.get_library(p0))
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(game.get_hand(p0)) == 3  # drew 3
        assert len(game.get_library(p0)) == lib_before - 3
        assert p1.life == 17  # 3 damage
        assert p0.life == 23  # gained 3

    def test_zero_colors_colorless_only(self):
        """All-colorless cast: X = 0 — nothing happens."""
        game = create_game(deck1=_filler(10))
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        p0, p1 = game.players
        lib_before = len(game.get_library(p0))
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(game.get_hand(p0)) == 0  # drew 0 (only the spell, now gone)
        assert len(game.get_library(p0)) == lib_before
        assert p1.life == 20
        assert p0.life == 20

    def test_two_colors_damage_to_creature(self):
        """Two colors: deal 2 to a creature; gain 2; opponent player undamaged."""
        game = create_game(deck1=_filler(10))
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.RED: 3, ManaType.GREEN: 3})
        bear = Creature(name="Bear", base_power=2, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear])
        p0, p1 = game.players
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        assert bear.damage_marked == 2
        assert p0.life == 22
        assert p1.life == 20
        assert len(game.get_hand(p0)) == 2  # drew 2

    def test_target_player_can_be_opponent(self):
        """Target player for the draw may be the opponent."""
        game = create_game(deck2=_filler(10))
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        p0, p1 = game.players
        p1_lib_before = len(game.get_library(p1))
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert len(game.get_library(p1)) == p1_lib_before - 2  # p1 drew 2
        assert p1.life == 18  # took 2 damage
        assert p0.life == 22  # caster gained 2
