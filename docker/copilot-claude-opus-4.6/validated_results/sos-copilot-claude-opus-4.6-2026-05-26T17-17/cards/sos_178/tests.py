"""Tests for SOS 178 — Borrowed Knowledge."""

from __future__ import annotations

import pytest

from cards.sos.sos_178.card_impl import BorrowedKnowledge
from engine.card import Creature, Sorcery
from engine.types import ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


class TestBorrowedKnowledgeProperties:
    """Static card properties match spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(BorrowedKnowledge(owner=None), Sorcery)

    def test_name(self) -> None:
        assert BorrowedKnowledge(owner=None).name == "Borrowed Knowledge"

    def test_mana_cost(self) -> None:
        assert BorrowedKnowledge(owner=None).mana_cost == ManaCost.parse("{2}{R}{W}")


class TestBorrowedKnowledgeMode1:
    """Mode 1: Discard hand, draw cards equal to target opponent's hand size."""

    def test_draws_cards_equal_to_opponent_hand_size(self) -> None:
        game = create_game()
        bk = BorrowedKnowledge(owner=game.players[0])
        # Give player 0 some hand cards + the spell, and opponent 4 cards
        filler1 = Creature(name="Filler A", base_power=1, base_toughness=1)
        filler2 = Creature(name="Filler B", base_power=1, base_toughness=1)
        opp_cards = [Creature(name=f"Opp Card {i}", base_power=1, base_toughness=1)
                     for i in range(4)]
        set_board_state(game, 0, hand=[bk, filler1, filler2],
                        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, hand=opp_cards)
        # Put cards in library so we can draw
        lib_cards = [Creature(name=f"Lib {i}", base_power=1, base_toughness=1)
                     for i in range(10)]
        game.players[0].library = lib_cards
        cast_spell(game, 0, "Borrowed Knowledge", targets=[game.players[1]])
        # Should have discarded hand (filler1, filler2) and drawn 4 (opponent's hand size)
        assert len(game.players[0].hand) == 4

    def test_mode1_discards_entire_hand_first(self) -> None:
        game = create_game()
        bk = BorrowedKnowledge(owner=game.players[0])
        filler = [Creature(name=f"F{i}", base_power=1, base_toughness=1) for i in range(3)]
        set_board_state(game, 0, hand=[bk] + filler,
                        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        opp_cards = [Creature(name=f"O{i}", base_power=1, base_toughness=1) for i in range(2)]
        set_board_state(game, 1, hand=opp_cards)
        lib_cards = [Creature(name=f"L{i}", base_power=1, base_toughness=1) for i in range(10)]
        game.players[0].library = lib_cards
        cast_spell(game, 0, "Borrowed Knowledge", targets=[game.players[1]])
        # Graveyard should contain the 3 discarded filler cards (+ possibly BK itself)
        graveyard_names = [c.name for c in game.players[0].graveyard]
        for i in range(3):
            assert f"F{i}" in graveyard_names

    def test_mode1_opponent_empty_hand_draws_zero(self) -> None:
        game = create_game()
        bk = BorrowedKnowledge(owner=game.players[0])
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[bk, filler],
                        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, hand=[])
        lib_cards = [Creature(name=f"L{i}", base_power=1, base_toughness=1) for i in range(10)]
        game.players[0].library = lib_cards
        cast_spell(game, 0, "Borrowed Knowledge", targets=[game.players[1]])
        # Discarded filler, draw 0 (opponent has 0 cards)
        assert len(game.players[0].hand) == 0


class TestBorrowedKnowledgeMode2:
    """Mode 2: Discard hand, draw cards equal to number discarded."""

    def test_draws_cards_equal_to_cards_discarded(self) -> None:
        game = create_game()
        bk = BorrowedKnowledge(owner=game.players[0])
        fillers = [Creature(name=f"H{i}", base_power=1, base_toughness=1) for i in range(5)]
        set_board_state(game, 0, hand=[bk] + fillers,
                        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        lib_cards = [Creature(name=f"L{i}", base_power=1, base_toughness=1) for i in range(10)]
        game.players[0].library = lib_cards
        # Mode 2 — no opponent target needed
        cast_spell(game, 0, "Borrowed Knowledge")
        # Discarded 5 cards (fillers), draw 5
        assert len(game.players[0].hand) == 5

    def test_mode2_empty_hand_draws_zero(self) -> None:
        """If you only have BK in hand, discard 0, draw 0."""
        game = create_game()
        bk = BorrowedKnowledge(owner=game.players[0])
        set_board_state(game, 0, hand=[bk],
                        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 2})
        lib_cards = [Creature(name=f"L{i}", base_power=1, base_toughness=1) for i in range(10)]
        game.players[0].library = lib_cards
        cast_spell(game, 0, "Borrowed Knowledge")
        # Discarded 0 other cards (BK itself was cast/on stack), draw 0
        assert len(game.players[0].hand) == 0
