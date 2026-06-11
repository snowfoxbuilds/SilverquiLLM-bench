"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _filler(n: int) -> list[Instant]:
    return [Instant(name=f"Filler {i}", mana_cost=ManaCost.parse("{1}")) for i in range(n)]


class TestTogetherAsOne:
    def test_five_colors_draw_damage_lifegain(self):
        # Opponent's deck has 12 cards: 7 drawn at setup, 5 left in library.
        game = create_game(deck2=_filler(12))
        p1, p2 = game.players
        spell = TogetherAsOne()
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert len(game.get_hand(p2)) == 7 + 5  # drew X=5 cards
        assert p2.life == 20 - 5
        assert p1.life == 20 + 5

    def test_colorless_cast_x_is_zero(self):
        game = create_game(deck2=_filler(10))
        p1, p2 = game.players
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert len(game.get_hand(p2)) == 7  # no draws
        assert p2.life == 20
        assert p1.life == 20

    def test_two_colors_damage_kills_creature(self):
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne()
        # Auto-pay spends {C}x4 first, then {W} and {U} -> X = 2.
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.COLORLESS: 4},
        )
        cast_spell(game, 0, "Together as One", targets=[p1, bear])
        # Bear took 2 damage with toughness 2 -> died to SBAs.
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p2).contains(bear)
        assert p1.life == 20 + 2

    def test_goes_to_graveyard_after_resolution(self):
        game = create_game()
        p1, p2 = game.players
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert game.get_graveyard(p1).contains(spell)
