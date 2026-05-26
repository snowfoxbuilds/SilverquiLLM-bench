"""Audited tests for Embrace the Paradox (collector number 186).

Verifies the Embrace the Paradox card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import EmbraceTheParadox

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestEmbraceTheParadoxBasicProperties:
    """Embrace the Paradox basic property tests."""

    def test_is_instant(self) -> None:
        """Embrace the Paradox must be a Instant subclass."""
        card = EmbraceTheParadox(name="Embrace the Paradox", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """EmbraceTheParadox.name must be 'Embrace the Paradox'."""
        card = EmbraceTheParadox(name="Embrace the Paradox", owner=None)
        assert card.name == "Embrace the Paradox"

    def test_card_type(self) -> None:
        """Embrace the Paradox must have CardType.INSTANT."""
        card = EmbraceTheParadox(name="Embrace the Paradox", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Embrace the Paradox must have converted mana cost 5."""
        card = EmbraceTheParadox(name="Embrace the Paradox", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Embrace the Paradox must have colors ['G', 'U']."""
        card = EmbraceTheParadox(name="Embrace the Paradox", owner=None)
        for c in ["G", "U"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestEmbraceTheParadoxAbilities:
    """Embrace the Paradox ability tests — expected to fail against stubs."""

    def test_on_resolve_draws_cards(self) -> None:
        """Embrace the Paradox should draw cards when it resolves.

        Oracle: Draw three cards. You may put a land card from your hand onto the battlefield tapped.
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

        card = EmbraceTheParadox(name="Embrace the Paradox", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size to increase after resolving Embrace the Paradox. "
            f"Before: {hand_before}, After: {hand_after}"
        )
