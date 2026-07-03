"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant
from engine.types import ManaType
from test_utils import create_game, cast_spell, set_board_state


def _library_filler(n: int) -> list[Instant]:
    from engine.types import ManaCost

    return [Instant(name=f"Filler {i}", mana_cost=ManaCost.parse("{1}")) for i in range(n)]


class TestTogetherAsOne:
    def test_five_colors_draw_damage_life(self) -> None:
        """5 colors + 1 colorless spent -> X=5: draw 5, deal 5, gain 5."""
        game = create_game(deck1=_library_filler(15))
        p1, p2 = game.players
        set_board_state(
            game,
            0,
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
        hand_before = len(game.get_hand(p1).get_all())
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # Casting removed Together as One from hand, then p1 drew 5.
        assert len(game.get_hand(p1).get_all()) == hand_before - 1 + 5
        assert p2.life == 15
        assert p1.life == 25

    def test_colorless_only_x_is_zero(self) -> None:
        """All-colorless payment -> X=0: no draws, no damage, no life."""
        game = create_game(deck1=_library_filler(10))
        p1, p2 = game.players
        set_board_state(game, 0, hand=[TogetherAsOne()], mana={ManaType.COLORLESS: 6})
        hand_before = len(game.get_hand(p1).get_all())
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(game.get_hand(p1).get_all()) == hand_before - 1
        assert p2.life == 20
        assert p1.life == 20

    def test_damage_to_creature(self) -> None:
        """'Any target' may be a creature; X=2 marks 2 damage and SBAs kill a 2-toughness creature."""
        game = create_game(deck1=_library_filler(5))
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(
            game,
            0,
            hand=[TogetherAsOne()],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.COLORLESS: 4},
        )
        cast_spell(game, 0, "Together as One", targets=[p1, bear])
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p2).contains(bear)
        assert p1.life == 22

    def test_opponent_can_be_drawer(self) -> None:
        """Target player can be the opponent; duplicate colors count once."""
        game = create_game(deck2=_library_filler(12))
        p1, p2 = game.players
        set_board_state(
            game,
            0,
            hand=[TogetherAsOne()],
            mana={ManaType.RED: 4, ManaType.GREEN: 2},
        )
        p2_hand_before = len(game.get_hand(p2).get_all())
        cast_spell(game, 0, "Together as One", targets=[p2, p1])
        # 4 R + 2 G spent -> 2 distinct colors.
        assert len(game.get_hand(p2).get_all()) == p2_hand_before + 2
        assert p1.life == 20 - 2 + 2  # took 2 damage, gained 2 life

    def test_spell_goes_to_graveyard(self) -> None:
        game = create_game(deck1=_library_filler(5))
        p1 = game.players[0]
        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert game.get_graveyard(p1).contains(spell)
