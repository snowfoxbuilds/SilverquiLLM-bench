"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _stock_library(game, player_index: int, count: int) -> None:
    """Put *count* filler cards in a player's library."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for i in range(count):
        filler = Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        filler.owner = player
        filler.controller = player
        library.add(filler)


class TestTogetherAsOne:
    def test_three_colors_draw_damage_lifegain(self):
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 5)
        spell = TogetherAsOne(owner=None)
        # Pool is exactly {W}{W}{U}{U}{B}{B}: auto-pay spends all six,
        # so three colors of mana are spent.
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert len(game.get_hand(p2)) == 3
        assert p2.life == 20 - 3
        assert p1.life == 20 + 3

    def test_colorless_cast_x_is_zero(self):
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 5)
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert len(game.get_hand(p2)) == 0
        assert p2.life == 20
        assert p1.life == 20

    def test_five_colors_damage_kills_creature(self):
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 6)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne(owner=None)
        set_board_state(
            game, 0, hand=[spell],
            mana={
                ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1,
            },
        )
        cast_spell(game, 0, "Together as One", targets=[p1, bear])
        # 5 colors: controller draws 5, the bear takes 5 (dies), gain 5.
        assert len(game.get_hand(p1)) == 5
        assert game.get_graveyard(p2).contains(bear)
        assert p1.life == 25

    def test_spell_ends_in_graveyard(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert game.get_graveyard(p1).contains(spell)
