"""Tests for Together as One (sos_4)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _stock_library(game, player_index, n=5):
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for i in range(n):
        card = Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        card.owner = player
        card.controller = player
        library.add(card)


class TestTogetherAsOne:
    def test_three_colors_draw_damage_gain(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0, hand=[TogetherAsOne(owner=None)],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        _stock_library(game, 0)
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(p0.zones[Zone.HAND]) == 3  # spell left hand; drew 3
        assert p1.life == 17
        assert p0.life == 23

    def test_colorless_cast_x_is_zero(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0, hand=[TogetherAsOne(owner=None)],
            mana={ManaType.COLORLESS: 6},
        )
        _stock_library(game, 0)
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(p0.zones[Zone.HAND]) == 0
        assert p1.life == 20
        assert p0.life == 20
        assert p0.zones[Zone.GRAVEYARD].get_all()[-1].name == "Together as One"

    def test_damage_to_creature_kills_bear(self):
        game = create_game()
        p0, p1 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(
            game, 0, hand=[TogetherAsOne(owner=None)],
            mana={ManaType.RED: 3, ManaType.GREEN: 3},
        )
        _stock_library(game, 0)
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        assert not game.get_battlefield(p1).contains(bear)
        assert p0.life == 22

    def test_duplicate_colors_count_once(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0, hand=[TogetherAsOne(owner=None)],
            mana={ManaType.RED: 6},
        )
        _stock_library(game, 1)
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert len(p1.zones[Zone.HAND]) == 1
        assert p1.life == 19
        assert p0.life == 21
