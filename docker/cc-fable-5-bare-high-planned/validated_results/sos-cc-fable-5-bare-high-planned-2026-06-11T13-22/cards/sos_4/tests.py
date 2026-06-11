"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _fill_library(game, player_index: int, count: int) -> None:
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for i in range(count):
        card = Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        card.owner = player
        card.controller = player
        library.add(card)


class TestTogetherAsOne:
    def test_three_colors_draws_damages_gains(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        bear = Creature(name="Bear", base_power=2, base_toughness=4)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        set_board_state(game, 1, battlefield=[bear])
        _fill_library(game, 1, 5)

        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(p2.zones[Zone.HAND]) == 3       # drew X = 3
        assert bear.damage_marked == 3             # X damage to any target
        assert p1.life == 23                       # gained X life
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_colorless_cast_x_is_zero(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        _fill_library(game, 1, 5)

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == 0
        assert p2.life == 20
        assert p1.life == 20
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_damage_to_player_target(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.RED: 3, ManaType.GREEN: 3},
        )
        _fill_library(game, 0, 4)

        # Target player = self, any target = opponent
        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(p1.zones[Zone.HAND]) == 2       # X = 2 colors
        assert p2.life == 18
        assert p1.life == 22
