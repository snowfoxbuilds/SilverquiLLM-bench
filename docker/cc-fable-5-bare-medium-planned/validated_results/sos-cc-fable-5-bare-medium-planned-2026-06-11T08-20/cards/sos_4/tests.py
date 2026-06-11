"""Tests for Together as One (sos_4)."""

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _library_filler(n):
    return [Instant(name=f"Filler {i}", mana_cost=ManaCost.parse("{1}")) for i in range(n)]


class TestTogetherAsOne:
    def test_five_colors_draws_damages_gains(self):
        game = create_game(deck2=_library_filler(15))
        p0, p1 = game.players
        set_board_state(
            game, 0, hand=[TogetherAsOne()],
            mana={
                ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1,
            },
        )
        hand_before = len(game.get_hand(p1))
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert len(game.get_hand(p1)) == hand_before + 5
        assert p1.life == 15
        assert p0.life == 25

    def test_colorless_cast_x_zero(self):
        game = create_game(deck2=_library_filler(5))
        p0, p1 = game.players
        set_board_state(game, 0, hand=[TogetherAsOne()],
                        mana={ManaType.COLORLESS: 6})
        hand_before = len(game.get_hand(p1))
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert len(game.get_hand(p1)) == hand_before
        assert p1.life == 20
        assert p0.life == 20

    def test_damage_to_creature(self):
        game = create_game(deck1=_library_filler(5))
        p0, p1 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(
            game, 0, hand=[TogetherAsOne()],
            mana={ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 4},
        )
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        # X = 2: controller draws 2, bear takes 2 damage and dies, gain 2 life
        assert p0.life == 22
        assert game.get_graveyard(p1).contains(bear)

    def test_spell_goes_to_graveyard(self):
        game = create_game()
        p0, p1 = game.players
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert game.get_graveyard(p0).contains(spell)
