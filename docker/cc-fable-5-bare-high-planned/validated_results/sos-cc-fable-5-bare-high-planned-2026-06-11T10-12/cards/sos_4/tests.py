"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, cast_spell, set_board_state


def _stock_library(player, n):
    """Put n filler cards into a player's library."""
    library = player.zones[Zone.LIBRARY]
    for i in range(n):
        card = Instant(name=f"Filler {i}", mana_cost=ManaCost.parse("{1}"))
        card.owner = player
        card.controller = player
        library.add(card)


class TestTogetherAsOne:
    def test_five_colors_draw_damage_life(self):
        """X=5 when one mana of each color is spent: opponent draws 5,
        creature takes 5 damage, controller gains 5 life."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(p2, 6)
        big = Creature(name="Big Wall", base_power=0, base_toughness=8)
        set_board_state(game, 1, battlefield=[big])
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0,
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, big])

        assert len(p2.zones[Zone.HAND]) == 5
        assert big.damage_marked == 5
        assert p1.life == 25
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_colorless_cast_is_x_zero(self):
        """All-colorless payment: X=0 — no draws, no damage, no life gain."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(p2, 3)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne(owner=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(p2.zones[Zone.HAND]) == 0
        assert bear.damage_marked == 0
        assert p1.life == 20
        # X=0 damage does not kill the creature
        assert game.get_battlefield(p2).contains(bear)

    def test_any_target_can_be_a_player(self):
        """X=2 with two colors spent; damage dealt to a player."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(p1, 3)
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0,
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.COLORLESS: 4},
        )
        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        # Controller targeted themselves for the draw
        assert len(p1.zones[Zone.HAND]) == 2
        assert p2.life == 18
        assert p1.life == 22

    def test_lethal_damage_kills_creature(self):
        """Converge damage is real damage — a small creature dies to it."""
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0,
            hand=[spell],
            mana={ManaType.RED: 1, ManaType.GREEN: 1, ManaType.BLACK: 1,
                  ManaType.COLORLESS: 3},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert not game.get_battlefield(p2).contains(bear)
        assert p2.zones[Zone.GRAVEYARD].contains(bear)
