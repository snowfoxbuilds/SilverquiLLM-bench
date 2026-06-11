"""Tests for SOS 94 — Pox Plague."""

from __future__ import annotations

import pytest

from cards.sos.sos_94.card_impl import PoxPlague
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestPoxPlagueProperties:
    """Static card data should match the SOS 94 spec."""

    def test_is_sorcery(self) -> None:
        card = PoxPlague(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        assert PoxPlague(owner=None).name == "Pox Plague"

    def test_mana_cost(self) -> None:
        assert PoxPlague(owner=None).mana_cost == ManaCost.parse("{B}{B}{B}{B}{B}")


class TestPoxPlagueLifeLoss:
    """Each player loses half their life, rounded down."""

    def test_loses_half_life_even(self) -> None:
        game = create_game(player1_life=20, player2_life=20)
        p1 = game.players[0]
        p2 = game.players[1]

        spell = PoxPlague(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 5})

        cast_spell(game, 0, "Pox Plague")

        # Half of 20 = 10, lose 10
        assert p1.life == 10
        assert p2.life == 10

    def test_loses_half_life_odd(self) -> None:
        game = create_game(player1_life=15, player2_life=7)
        p1 = game.players[0]
        p2 = game.players[1]

        spell = PoxPlague(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 5})

        cast_spell(game, 0, "Pox Plague")

        # Half of 15 rounded down = 7, so 15-7 = 8
        assert p1.life == 15 - 7  # 8
        # Half of 7 rounded down = 3, so 7-3 = 4
        assert p2.life == 7 - 3  # 4


class TestPoxPlagueDiscard:
    """Each player discards half the cards in their hand, rounded down."""

    def test_discards_half_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = PoxPlague(owner=p1, controller=p1)
        # Give players cards in hand (excluding the spell itself)
        filler1 = [Creature(name=f"Card_{i}", owner=p1, base_power=1, base_toughness=1) for i in range(4)]
        filler2 = [Creature(name=f"Opp_{i}", owner=p2, base_power=1, base_toughness=1) for i in range(3)]

        set_board_state(game, 0, hand=[spell] + filler1, mana={ManaType.BLACK: 5})
        set_board_state(game, 1, hand=filler2)

        cast_spell(game, 0, "Pox Plague")

        # P1 had 4 cards left after casting (spell goes to stack), discard half of 4 = 2
        hand_p1 = game.get_hand(p1)
        assert len(list(hand_p1)) == 2

        # P2 had 3 cards, discard half of 3 rounded down = 1, keep 2
        hand_p2 = game.get_hand(p2)
        assert len(list(hand_p2)) == 2


class TestPoxPlagueSacrifice:
    """Each player sacrifices half the permanents they control, rounded down."""

    def test_sacrifices_half_permanents(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = PoxPlague(owner=p1, controller=p1)
        creatures_p1 = [Creature(name=f"P1_Creature_{i}", owner=p1, controller=p1,
                                  base_power=1, base_toughness=1) for i in range(4)]
        creatures_p2 = [Creature(name=f"P2_Creature_{i}", owner=p2, controller=p2,
                                  base_power=1, base_toughness=1) for i in range(3)]

        set_board_state(game, 0, hand=[spell], battlefield=creatures_p1, mana={ManaType.BLACK: 5})
        set_board_state(game, 1, battlefield=creatures_p2)

        cast_spell(game, 0, "Pox Plague")

        # P1 had 4 permanents, sacrifice half = 2, keep 2
        bf_p1 = game.get_battlefield(p1)
        assert len(list(bf_p1)) == 2

        # P2 had 3 permanents, sacrifice half rounded down = 1, keep 2
        bf_p2 = game.get_battlefield(p2)
        assert len(list(bf_p2)) == 2
