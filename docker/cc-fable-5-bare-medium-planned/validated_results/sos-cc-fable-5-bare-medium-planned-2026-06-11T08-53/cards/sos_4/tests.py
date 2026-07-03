"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, cast_spell, set_board_state


def _library_cards(n: int) -> list:
    return [Instant(name=f"Filler {i}", mana_cost=ManaCost(generic=1)) for i in range(n)]


class TestTogetherAsOne:
    def test_three_colors_draws_damages_gains(self) -> None:
        game = create_game(deck1=_library_cards(10))
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne()
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.COLORLESS: 3},
        )
        hand_before = len(game.get_hand(p1).get_all())
        life_before = p1.life

        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        # X = 3 colors spent: draw 3, deal 3 to the bear, gain 3 life.
        # (the spell itself left the hand when cast)
        assert len(game.get_hand(p1).get_all()) == hand_before - 1 + 3
        assert bear.damage_marked == 3
        assert p1.life == life_before + 3
        assert game.get_graveyard(p1).contains(spell)

    def test_damage_to_player(self) -> None:
        game = create_game(deck1=_library_cards(10))
        p1, p2 = game.players
        spell = TogetherAsOne()
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 4},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        # X = 2: opponent draws 2 (empty library → flagged) and takes 2.
        assert p2.life == 18

    def test_colorless_cast_x_zero(self) -> None:
        game = create_game(deck1=_library_cards(10))
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        hand_before = len(game.get_hand(p1).get_all())
        life_before = p1.life

        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        # X = 0: no draws, no damage, no life gain.
        assert len(game.get_hand(p1).get_all()) == hand_before - 1
        assert bear.damage_marked == 0
        assert p1.life == life_before
