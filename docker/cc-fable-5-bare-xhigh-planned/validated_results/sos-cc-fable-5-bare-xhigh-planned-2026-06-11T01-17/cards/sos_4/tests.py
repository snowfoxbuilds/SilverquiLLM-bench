"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _stock_library(game, player_index: int, n: int) -> None:
    library = game.get_library(game.players[player_index])
    for i in range(n):
        library.add(Creature(name=f"Filler {i}", base_power=1, base_toughness=1))


class TestTogetherAsOneProperties:
    def test_static_data(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")
        assert CardType.SORCERY in card.card_types


class TestTogetherAsOneConverge:
    def test_five_colors_draw_damage_life(self) -> None:
        """X=5: target player draws 5, 5 damage to a creature, gain 5 life."""
        game = create_game()
        p1, p2 = game.players
        big = Creature(name="Big Wall", base_power=6, base_toughness=6)
        set_board_state(game, 1, battlefield=[big])
        _stock_library(game, 1, 6)
        spell = TogetherAsOne(owner=None)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        hand2_before = len(game.get_hand(p2))
        cast_spell(game, 0, "Together as One", targets=[p2, big])
        assert len(game.get_hand(p2)) == hand2_before + 5
        assert big.damage_marked == 5
        assert p1.life == 25
        assert game.get_graveyard(p1).contains(spell)

    def test_colorless_cast_is_x_zero(self) -> None:
        """X=0: no draws, no damage, no life gain."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 3)
        spell = TogetherAsOne(owner=None)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        hand2_before = len(game.get_hand(p2))
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert len(game.get_hand(p2)) == hand2_before
        assert p2.life == 20
        assert p1.life == 20

    def test_two_colors_damage_to_player(self) -> None:
        """X=2 with a two-color payment; any target may be a player."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 0, 3)
        spell = TogetherAsOne(owner=None)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 3, ManaType.BLACK: 3},
        )
        hand1_before = len(game.get_hand(p1)) - 1  # the spell leaves hand
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(game.get_hand(p1)) == hand1_before + 2
        assert p2.life == 18
        assert p1.life == 22

    def test_lethal_damage_kills_creature(self) -> None:
        """X-damage to a small creature kills it via state-based actions."""
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 3)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne(owner=None)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.RED: 2, ManaType.GREEN: 2, ManaType.BLUE: 2},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, bear])
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p2).contains(bear)
