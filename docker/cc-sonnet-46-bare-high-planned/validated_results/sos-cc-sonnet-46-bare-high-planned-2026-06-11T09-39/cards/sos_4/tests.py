"""Tests for sos_4 — Together as One."""

from __future__ import annotations

import pytest
from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.types import ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestTogetherAsOneProperties:
    def test_name(self) -> None:
        assert TogetherAsOne().name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne()
        assert card.mana_cost.generic == 6


class TestTogetherAsOneConverge:
    def test_x_zero_colorless_only(self) -> None:
        """Colorless mana → X = 0, nothing happens."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = TogetherAsOne()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 6})
        initial_life = p0.life
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert p0.life == initial_life  # no life gain
        assert p1.life == 20  # no damage

    def test_x_one_single_color(self) -> None:
        """One color → X = 1."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = TogetherAsOne()
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 6})
        p0_start = p0.life
        p1_start = p1.life
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        # p1 draws 1 (library may be empty, but no loss in test)
        assert p1.life == p1_start - 1  # 1 damage
        assert p0.life == p0_start + 1  # 1 life gain

    def test_x_two_colors(self) -> None:
        """Two colors → X = 2."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = TogetherAsOne()
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        p0_start = p0.life
        p1_start = p1.life
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert p1.life == p1_start - 2
        assert p0.life == p0_start + 2

    def test_x_five_all_colors(self) -> None:
        """Five colors → X = 5."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = TogetherAsOne()
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 2, ManaType.BLUE: 1, ManaType.BLACK: 1,
            ManaType.RED: 1, ManaType.GREEN: 1,
        })
        p0_start = p0.life
        p1_start = p1.life
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert p1.life == p1_start - 5
        assert p0.life == p0_start + 5
