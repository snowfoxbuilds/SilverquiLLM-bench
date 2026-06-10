"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _stock_library(game, player_index, n):
    player = game.players[player_index]
    lib = player.zones[Zone.LIBRARY]
    for i in range(n):
        lib.add(Creature(name=f"Filler{i}", base_power=1, base_toughness=1))


class TestProperties:
    def test_is_sorcery(self):
        assert isinstance(TogetherAsOne(owner=None), Sorcery)
        assert TogetherAsOne(owner=None).name == "Together as One"
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_three_colors_full_effect(self):
        game = create_game()
        p0, p1 = game.players
        _stock_library(game, 0, 5)
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.COLORLESS: 3},
            life=20,
        )
        p1.life = 20
        # target player (draw) = p0; any target (damage) = p1 player.
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(p0.zones[Zone.HAND].get_all()) == 3  # drew X=3
        assert p1.life == 17  # 3 damage
        assert p0.life == 23  # gained 3 life

    def test_colorless_cast_x_zero(self):
        game = create_game()
        p0, p1 = game.players
        _stock_library(game, 0, 5)
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.COLORLESS: 6},
            life=20,
        )
        p1.life = 20
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(p0.zones[Zone.HAND].get_all()) == 0  # X=0, no draw
        assert p1.life == 20  # no damage
        assert p0.life == 20  # no life gain

    def test_damage_to_creature(self):
        game = create_game()
        p0, p1 = game.players
        _stock_library(game, 0, 2)
        bear = Creature(name="Big Bear", base_power=2, base_toughness=5)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.WHITE: 1, ManaType.RED: 1, ManaType.COLORLESS: 4},
        )
        # X=2 (W,R). target player=p0, damage target=bear.
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        assert bear.damage_marked == 2

    def test_five_colors(self):
        game = create_game()
        p0, p1 = game.players
        _stock_library(game, 1, 10)
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1},
            life=10,
        )
        p1.life = 20
        # target player draws = p1; damage target = p1.
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert len(p1.zones[Zone.HAND].get_all()) == 5
        assert p1.life == 15  # 5 damage
        assert p0.life == 15  # gained 5
