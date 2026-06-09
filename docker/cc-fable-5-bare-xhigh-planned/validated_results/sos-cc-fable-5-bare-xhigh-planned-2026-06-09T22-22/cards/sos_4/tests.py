"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


def _stock_library(game, player_index, n):
    p = game.players[player_index]
    lib = game.get_library(p)
    for i in range(n):
        c = Creature(name=f"Filler{i}", base_power=1, base_toughness=1)
        c.owner = p
        c.controller = p
        lib.add(c)


class TestProperties:
    def test_is_sorcery(self):
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name_and_cost(self):
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_three_colors(self):
        game = create_game()
        p0, p1 = game.players
        _stock_library(game, 0, 5)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2})
        hand_before = len(game.get_hand(p0).get_all())  # includes the spell
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        # X = 3: p0 drew 3, p1 took 3 damage, p0 gained 3 life.
        # Hand: started with spell only (1), spell leaves to gy, +3 drawn = 3.
        assert len(game.get_hand(p0).get_all()) == 3
        assert p1.life == 17
        assert p0.life == 23

    def test_zero_colors_colorless(self):
        game = create_game()
        p0, p1 = game.players
        _stock_library(game, 0, 5)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        # X = 0: no draws, no damage, no life gain.
        assert len(game.get_hand(p0).get_all()) == 0
        assert p1.life == 20
        assert p0.life == 20

    def test_one_color_damage_to_creature(self):
        game = create_game()
        p0, p1 = game.players
        _stock_library(game, 0, 5)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.RED: 6})
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        # X = 1: p0 draws 1, bear takes 1 damage, p0 gains 1 life.
        assert bear.damage_marked == 1
        assert p0.life == 21
        assert len(game.get_hand(p0).get_all()) == 1
