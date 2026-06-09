"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _fill_library(player, n):
    lib = player.zones[Zone.LIBRARY]
    for i in range(n):
        lib.add(Creature(name=f"Lib{i}", base_power=1, base_toughness=1,
                         owner=player, controller=player))


class TestProperties:
    def test_is_sorcery(self):
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_cost(self):
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_three_colors(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(p0, 5)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)], life=20,
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2})
        # target player = p0 (draws), any target = bear (takes damage)
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        assert len(p0.zones[Zone.HAND]) == 3
        assert bear.damage_marked == 3
        assert p0.life == 23

    def test_zero_colors_colorless(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(p0, 5)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)], life=20,
                        mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        assert len(p0.zones[Zone.HAND]) == 0
        assert bear.damage_marked == 0
        assert p0.life == 20

    def test_five_colors_damage_to_player(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(p0, 6)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)], life=20,
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 1,
                              ManaType.BLACK: 1, ManaType.RED: 1, ManaType.GREEN: 1})
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(p0.zones[Zone.HAND]) == 5
        assert p1.life == 15
        assert p0.life == 25
