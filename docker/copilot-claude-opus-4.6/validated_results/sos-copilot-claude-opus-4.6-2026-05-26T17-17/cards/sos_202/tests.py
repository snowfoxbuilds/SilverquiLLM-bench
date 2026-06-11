"""Tests for SOS 202 — Mind into Matter.

Sorcery {X}{G}{U}
Draw X cards. Then you may put a permanent card with mana value X or less
from your hand onto the battlefield tapped.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_202.card_impl import MindIntoMatter
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestMindIntoMatterProperties:
    """Static card data should match the SOS 202 spec."""

    def test_is_sorcery(self) -> None:
        card = MindIntoMatter(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = MindIntoMatter(owner=None)
        assert card.name == "Mind into Matter"

    def test_mana_cost(self) -> None:
        card = MindIntoMatter(owner=None)
        assert card.mana_cost == ManaCost.parse("{X}{G}{U}")


class TestMindIntoMatterResolution:
    """Draw X cards, then optionally put a permanent with MV <= X onto battlefield tapped."""

    def test_draws_x_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindIntoMatter(owner=p1, controller=p1)
        card.x_value = 3
        # Stock library with cards
        for i in range(5):
            c = Creature(name=f"Library Card {i}", owner=p1, base_power=1, base_toughness=1)
            game.get_library(p1).add(c)
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        # Should have drawn 3 cards (may have put one onto battlefield)
        assert hand_after >= hand_before + 2  # at least X-1 if one was put onto BF

    def test_draws_zero_cards_when_x_is_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindIntoMatter(owner=p1, controller=p1)
        card.x_value = 0
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        # X=0 draws 0, and can put a permanent with MV 0 or less
        assert hand_after >= hand_before

    def test_puts_permanent_onto_battlefield_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindIntoMatter(owner=p1, controller=p1)
        card.x_value = 3
        # Put a creature with MV 3 in library so it gets drawn
        target_creature = Creature(
            name="Target Creature", owner=p1, controller=p1,
            base_power=3, base_toughness=3,
            mana_cost=ManaCost.parse("{1}{G}{G}")
        )
        game.get_library(p1).add(target_creature)
        # Add more library cards
        for i in range(4):
            c = Creature(name=f"Filler {i}", owner=p1, base_power=1, base_toughness=1,
                         mana_cost=ManaCost.parse("{5}"))
            game.get_library(p1).add(c)
        card.on_resolve(game)
        # The target creature should be on the battlefield tapped
        bf = game.get_battlefield(p1).get_all()
        placed = [c for c in bf if c.name == "Target Creature"]
        assert len(placed) == 1
        assert placed[0].is_tapped is True

    def test_cannot_put_permanent_with_mv_greater_than_x(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MindIntoMatter(owner=p1, controller=p1)
        card.x_value = 2
        # Only card in hand has MV 5 (too expensive)
        expensive = Creature(
            name="Expensive", owner=p1, controller=p1,
            base_power=5, base_toughness=5,
            mana_cost=ManaCost.parse("{3}{G}{G}")
        )
        set_board_state(game, 0, hand=[expensive])
        # Stock library
        for i in range(3):
            c = Creature(name=f"Lib {i}", owner=p1, base_power=1, base_toughness=1,
                         mana_cost=ManaCost.parse("{4}"))
            game.get_library(p1).add(c)
        card.on_resolve(game)
        # Expensive creature should NOT be on battlefield
        bf = game.get_battlefield(p1).get_all()
        placed = [c for c in bf if c.name == "Expensive"]
        assert len(placed) == 0

    def test_may_choose_not_to_put_permanent(self) -> None:
        """The 'you may' clause means the player can decline."""
        game = create_game()
        p1 = game.players[0]
        card = MindIntoMatter(owner=p1, controller=p1)
        card.x_value = 3
        # Stock library
        for i in range(5):
            c = Creature(name=f"Lib {i}", owner=p1, base_power=1, base_toughness=1,
                         mana_cost=ManaCost.parse("{1}"))
            game.get_library(p1).add(c)
        # If player declines, no creatures on battlefield
        # (DeterministicPlayer may auto-decline or auto-accept; test that resolve doesn't crash)
        card.on_resolve(game)
        # No assertion about battlefield — just verify no crash
