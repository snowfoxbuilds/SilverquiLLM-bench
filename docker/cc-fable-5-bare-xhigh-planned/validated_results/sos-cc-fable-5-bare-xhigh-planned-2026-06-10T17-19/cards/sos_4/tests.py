"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaType, Zone
from test_utils import create_game, set_board_state


def _library_with(game, player_index, count):
    """Stock a player's library with vanilla cards so draws succeed."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for i in range(count):
        card = Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        card.owner = player
        card.controller = player
        library.add(card)


class TestTogetherAsOne:
    def test_four_colors_draws_deals_gains_four(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        # Pool of exactly W+U+B+3R pays {6} with four distinct colors.
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1, ManaType.RED: 3},
        )
        _library_with(game, 0, 5)
        from test_utils import cast_spell

        # Hand holds only the spell; after casting it leaves the hand.
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(game.get_hand(p1)) == 4
        assert p2.life == 16
        assert p1.life == 24

    def test_colorless_cast_x_is_zero(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        _library_with(game, 0, 5)
        from test_utils import cast_spell

        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(game.get_hand(p1)) == 0
        assert p2.life == 20
        assert p1.life == 20

    def test_damage_to_creature(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        bear = Creature(name="Bear", base_power=2, base_toughness=4)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.GREEN: 5},
        )
        set_board_state(game, 1, battlefield=[bear])
        _library_with(game, 0, 5)
        from test_utils import cast_spell

        cast_spell(game, 0, "Together as One", targets=[p1, bear])
        assert bear.damage_marked == 2
        assert p1.life == 22

    def test_lethal_damage_kills_creature(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1, ManaType.RED: 3},
        )
        set_board_state(game, 1, battlefield=[bear])
        _library_with(game, 1, 5)
        from test_utils import cast_spell

        cast_spell(game, 0, "Together as One", targets=[p2, bear])
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p2).contains(bear)

    def test_spell_goes_to_graveyard(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 6})
        _library_with(game, 0, 5)
        from test_utils import cast_spell

        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert game.get_graveyard(p1).contains(spell)
