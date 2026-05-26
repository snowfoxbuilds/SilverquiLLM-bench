"""Audited tests for Quick Study (collector number 65).

Verifies the Quick Study card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import QuickStudy

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestQuickStudyBasicProperties:
    """Quick Study basic property tests."""

    def test_is_instant(self) -> None:
        """Quick Study must be a Instant subclass."""
        card = QuickStudy(name="Quick Study", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """QuickStudy.name must be 'Quick Study'."""
        card = QuickStudy(name="Quick Study", owner=None)
        assert card.name == "Quick Study"

    def test_card_type(self) -> None:
        """Quick Study must have CardType.INSTANT."""
        card = QuickStudy(name="Quick Study", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Quick Study must have converted mana cost 3."""
        card = QuickStudy(name="Quick Study", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Quick Study must have colors ['U']."""
        card = QuickStudy(name="Quick Study", owner=None)
        for c in ["U"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestQuickStudyAbilities:
    """Quick Study ability tests — expected to fail against stubs."""

    def test_on_resolve_draws_cards(self) -> None:
        """Quick Study should draw cards when it resolves.

        Oracle: Draw two cards.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with cards
        for i in range(10):
            dummy = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(dummy)

        card = QuickStudy(name="Quick Study", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size to increase after resolving Quick Study. "
            f"Before: {hand_before}, After: {hand_after}"
        )
