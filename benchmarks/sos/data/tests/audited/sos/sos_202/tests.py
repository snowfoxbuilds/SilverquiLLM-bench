"""Audited tests for Mind into Matter (collector number 202).

Verifies the Mind into Matter card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import MindIntoMatter

from engine.card import Sorcery
from engine.types import CardType

@pytest.mark.basic
class TestMindIntoMatterBasicProperties:
    """Mind into Matter basic property tests."""

    def test_is_sorcery(self) -> None:
        """Mind into Matter must be a Sorcery subclass."""
        card = MindIntoMatter(name="Mind into Matter", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """MindIntoMatter.name must be 'Mind into Matter'."""
        card = MindIntoMatter(name="Mind into Matter", owner=None)
        assert card.name == "Mind into Matter"

    def test_card_type(self) -> None:
        """Mind into Matter must have CardType.SORCERY."""
        card = MindIntoMatter(name="Mind into Matter", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_has_x(self) -> None:
        """Mind into Matter must have X in its mana cost."""
        card = MindIntoMatter(name="Mind into Matter", owner=None)
        assert card.mana_cost.x_count >= 1

    def test_colors(self) -> None:
        """Mind into Matter must have colors ['G', 'U']."""
        card = MindIntoMatter(name="Mind into Matter", owner=None)
        for c in ["G", "U"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestMindIntoMatterAbilities:
    """Mind into Matter ability tests — expected to fail against stubs."""

    def test_on_resolve_draws_x_cards(self) -> None:
        """Mind into Matter should draw exactly X cards when it resolves.

        Oracle: Draw X cards. Then you may put a permanent card with mana value X or less from your hand onto the battlefield tapped.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with cards
        for i in range(10):
            dummy = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(dummy)

        card = MindIntoMatter(name="Mind into Matter", owner=player)
        card.controller = player
        card.x_value = 3  # Set X=3
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after >= hand_before + 3, (
            f"Expected to draw 3 cards (X=3). "
            f"Before: {hand_before}, After: {hand_after}"
        )
