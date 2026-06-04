"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, cast_spell, set_board_state


def _stock_library(game, player_index, n):
    player = game.players[player_index]
    lib = player.zones[Zone.LIBRARY]
    for _ in range(n):
        lib.add(Creature(name="Filler", base_power=1, base_toughness=1,
                         owner=player, controller=player))


class TestProperties:
    def test_is_sorcery(self):
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self):
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self):
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_two_colors_gain_two_life(self):
        game = create_game()
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 3, ManaType.BLUE: 3}, life=20)
        _stock_library(game, 0, 5)
        cast_spell(game, 0, "Together as One",
                   targets=[game.players[0], game.players[1]])
        assert game.players[0].life == 22  # gained X=2

    def test_two_colors_deals_two_damage_to_player(self):
        game = create_game()
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        _stock_library(game, 0, 5)
        cast_spell(game, 0, "Together as One",
                   targets=[game.players[0], game.players[1]])
        assert game.players[1].life == 18  # took X=2 damage

    def test_target_player_draws_x(self):
        game = create_game()
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        _stock_library(game, 1, 5)
        before = len(game.players[1].zones[Zone.HAND].get_all())
        cast_spell(game, 0, "Together as One",
                   targets=[game.players[1], game.players[1]])
        after = len(game.players[1].zones[Zone.HAND].get_all())
        assert after - before == 2  # target player drew X=2

    def test_all_colorless_means_x_zero(self):
        game = create_game()
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.COLORLESS: 6}, life=20)
        _stock_library(game, 0, 5)
        cast_spell(game, 0, "Together as One",
                   targets=[game.players[0], game.players[1]])
        assert game.players[0].life == 20  # gained 0
        assert game.players[1].life == 20  # 0 damage

    def test_damage_to_creature(self):
        game = create_game()
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.RED: 2})
        _stock_library(game, 0, 5)
        bear = Creature(name="Bear", base_power=2, base_toughness=5)
        set_board_state(game, 1, battlefield=[bear])
        cast_spell(game, 0, "Together as One",
                   targets=[game.players[0], bear])
        assert bear.damage_marked == 3  # X=3 colors

    def test_one_color_x_one(self):
        game = create_game()
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.RED: 6}, life=20)
        _stock_library(game, 0, 5)
        cast_spell(game, 0, "Together as One",
                   targets=[game.players[0], game.players[1]])
        assert game.players[0].life == 21
        assert game.players[1].life == 19
