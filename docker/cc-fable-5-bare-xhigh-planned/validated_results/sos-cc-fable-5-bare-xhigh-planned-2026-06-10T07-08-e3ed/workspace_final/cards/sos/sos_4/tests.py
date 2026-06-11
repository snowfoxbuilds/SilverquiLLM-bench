"""Tests for Together as One (sos_4)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _stock_library(game, player_index, count):
    library = game.players[player_index].zones[Zone.LIBRARY]
    for i in range(count):
        library.add(Creature(name=f"Filler {i}", base_power=1, base_toughness=1))


class TestTogetherAsOne:
    def test_three_colors_draw_damage_gain(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(
            game, 0,
            hand=[TogetherAsOne()],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        _stock_library(game, 1, 5)
        hand_before = len(p2.zones[Zone.HAND])

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == hand_before + 3
        assert p2.life == 17
        assert p1.life == 23

    def test_colorless_cast_x_is_zero(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(
            game, 0,
            hand=[TogetherAsOne()],
            mana={ManaType.COLORLESS: 6},
        )
        hand_before = len(p1.zones[Zone.HAND])  # includes the spell itself

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        # Spell left hand; X = 0 so no cards were drawn.
        assert len(p1.zones[Zone.HAND]) == hand_before - 1
        assert p1.life == 20
        assert p2.life == 20

    def test_any_target_creature_dies_from_damage(self):
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=3, base_toughness=3)
        set_board_state(
            game, 0,
            hand=[TogetherAsOne()],
            mana={ManaType.RED: 2, ManaType.GREEN: 2, ManaType.WHITE: 2},
        )
        set_board_state(game, 1, battlefield=[bear])
        _stock_library(game, 0, 5)

        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        assert p2.zones[Zone.GRAVEYARD].contains(bear)
        assert not p2.zones[Zone.BATTLEFIELD].contains(bear)
        assert p1.life == 23

    def test_five_colors(self):
        game = create_game()
        p1, p2 = game.players
        set_board_state(
            game, 0,
            hand=[TogetherAsOne()],
            mana={
                ManaType.WHITE: 1,
                ManaType.BLUE: 1,
                ManaType.BLACK: 1,
                ManaType.RED: 1,
                ManaType.GREEN: 1,
                ManaType.COLORLESS: 1,
            },
        )
        _stock_library(game, 1, 6)
        hand_before = len(p2.zones[Zone.HAND])

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == hand_before + 5
        assert p2.life == 15
        assert p1.life == 25

    def test_spell_ends_in_graveyard(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert p1.zones[Zone.GRAVEYARD].contains(spell)
