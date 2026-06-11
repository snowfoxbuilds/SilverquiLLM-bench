"""Tests for SOS 49 — Flow State.

Sorcery for {1}{U}.
Look at the top three cards of your library. Put one into your hand and
the rest on the bottom of your library in any order.
If there is an instant card AND a sorcery card in your graveyard, instead
put two into your hand and the rest on the bottom.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_49.card_impl import FlowState
from engine.card import Sorcery, Instant, CardImpl
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestFlowStateProperties:
    """Static card data should match the SOS 49 spec."""

    def test_is_sorcery(self) -> None:
        card = FlowState(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = FlowState(owner=None)
        assert card.name == "Flow State"

    def test_mana_cost(self) -> None:
        card = FlowState(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}")


class TestFlowStateBasicMode:
    """Without instant+sorcery in graveyard: draw 1, bottom 2."""

    def test_draws_one_card_normally(self) -> None:
        """With no instant+sorcery in GY, puts one card into hand."""
        game = create_game()
        p1 = game.players[0]
        flow = FlowState(owner=p1, controller=p1)
        # Library with 3+ cards
        lib_cards = [CardImpl(name=f"LibCard {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[flow], library=lib_cards,
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        hand_before = len(game.get_hand(p1).get_all()) - 1  # subtract flow state itself
        cast_spell(game, 0, "Flow State")
        hand_after = len(game.get_hand(p1).get_all())
        # Should have gained 1 card in hand (flow left hand, +1 from effect)
        assert hand_after == hand_before + 1

    def test_remaining_cards_go_to_bottom(self) -> None:
        """The other two cards go to the bottom of the library."""
        game = create_game()
        p1 = game.players[0]
        flow = FlowState(owner=p1, controller=p1)
        lib_cards = [CardImpl(name=f"LibCard {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[flow], library=lib_cards,
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Flow State")
        # Library should still have 5 - 1 (drawn) = 4 cards remaining
        # (top 3 looked at: 1 to hand, 2 to bottom; plus 2 untouched = 4 total)
        lib_after = len(game.get_library(p1).get_all())
        assert lib_after == 4


class TestFlowStateEnhancedMode:
    """With both instant and sorcery in graveyard: draw 2, bottom 1."""

    def test_draws_two_with_instant_and_sorcery_in_gy(self) -> None:
        """If GY has both an instant and a sorcery, draws 2 instead of 1."""
        game = create_game()
        p1 = game.players[0]
        flow = FlowState(owner=p1, controller=p1)
        # Put an instant and a sorcery in the graveyard
        gy_instant = Instant(name="Think Twice")
        gy_instant.owner = p1
        gy_sorcery = Sorcery(name="Divination")
        gy_sorcery.owner = p1
        lib_cards = [CardImpl(name=f"LibCard {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[flow], library=lib_cards,
                        graveyard=[gy_instant, gy_sorcery],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        hand_before = len(game.get_hand(p1).get_all()) - 1  # subtract flow
        cast_spell(game, 0, "Flow State")
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before + 2

    def test_only_instant_in_gy_draws_one(self) -> None:
        """Only an instant (no sorcery) in GY means normal mode."""
        game = create_game()
        p1 = game.players[0]
        flow = FlowState(owner=p1, controller=p1)
        gy_instant = Instant(name="Think Twice")
        gy_instant.owner = p1
        lib_cards = [CardImpl(name=f"LibCard {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[flow], library=lib_cards,
                        graveyard=[gy_instant],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        hand_before = len(game.get_hand(p1).get_all()) - 1
        cast_spell(game, 0, "Flow State")
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before + 1

    def test_only_sorcery_in_gy_draws_one(self) -> None:
        """Only a sorcery (no instant) in GY means normal mode."""
        game = create_game()
        p1 = game.players[0]
        flow = FlowState(owner=p1, controller=p1)
        gy_sorcery = Sorcery(name="Divination")
        gy_sorcery.owner = p1
        lib_cards = [CardImpl(name=f"LibCard {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[flow], library=lib_cards,
                        graveyard=[gy_sorcery],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        hand_before = len(game.get_hand(p1).get_all()) - 1
        cast_spell(game, 0, "Flow State")
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before + 1

    def test_library_remaining_in_enhanced_mode(self) -> None:
        """In enhanced mode, library loses 2 (to hand) and gains 1 (to bottom)."""
        game = create_game()
        p1 = game.players[0]
        flow = FlowState(owner=p1, controller=p1)
        gy_instant = Instant(name="Think Twice")
        gy_instant.owner = p1
        gy_sorcery = Sorcery(name="Divination")
        gy_sorcery.owner = p1
        lib_cards = [CardImpl(name=f"LibCard {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[flow], library=lib_cards,
                        graveyard=[gy_instant, gy_sorcery],
                        mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Flow State")
        # Top 3 looked at: 2 to hand, 1 to bottom; plus 2 untouched = 3 total
        lib_after = len(game.get_library(p1).get_all())
        assert lib_after == 3
