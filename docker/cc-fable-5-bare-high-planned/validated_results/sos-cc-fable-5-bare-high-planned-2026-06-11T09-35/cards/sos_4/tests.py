"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _stock_library(player, count):
    """Put *count* filler cards into a player's library."""
    library = player.zones[Zone.LIBRARY]
    for i in range(count):
        filler = Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        filler.owner = player
        filler.controller = player
        library.add(filler)


class TestTogetherAsOne:
    def test_converge_three_colors(self):
        """3 colors spent: opponent draws 3, creature takes 3, gain 3 life."""
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear])
        _stock_library(p2, 5)
        spell = TogetherAsOne(owner=None)
        # Pool is exactly {W}{U}{B}{C}{C}{C}: paying {6} drains it → 3 colors.
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.COLORLESS: 3},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(p2.zones[Zone.HAND]) == 3
        assert bear.damage_marked == 3
        assert p1.life == 23
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_converge_five_colors_damage_to_player(self):
        """All five colors: X = 5, damage dealt to a player."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(p1, 6)
        spell = TogetherAsOne(owner=None)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(p1.zones[Zone.HAND]) == 5
        assert p2.life == 15
        assert p1.life == 25

    def test_converge_zero_colors(self):
        """All-colorless cast: X = 0 — no draws, no damage, no life."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(p2, 3)
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == 0
        assert p2.life == 20
        assert p1.life == 20
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_duplicate_colors_count_once(self):
        """Colors, not pips: {R}{R}{R}{G}{G}{G} is X = 2."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(p2, 4)
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.RED: 3, ManaType.GREEN: 3})
        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == 2
        assert p2.life == 18
        assert p1.life == 22
