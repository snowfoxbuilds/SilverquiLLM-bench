"""Audited tests for Glimpse of Nature (SOA collector number 53).

Verifies the Glimpse of Nature card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import GlimpseOfNature

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestGlimpseOfNatureBasicProperties:
    """Glimpse of Nature basic property tests."""

    def test_is_sorcery(self) -> None:
        """Glimpse of Nature must be a Sorcery subclass."""
        card = GlimpseOfNature(name="Glimpse of Nature", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """GlimpseOfNature.name must be 'Glimpse of Nature'."""
        card = GlimpseOfNature(name="Glimpse of Nature", owner=None)
        assert card.name == "Glimpse of Nature"

    def test_card_type(self) -> None:
        """Glimpse of Nature must have CardType.SORCERY."""
        card = GlimpseOfNature(name="Glimpse of Nature", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Glimpse of Nature must have converted mana cost 1."""
        card = GlimpseOfNature(name="Glimpse of Nature", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Glimpse of Nature must have colors ['G']."""
        card = GlimpseOfNature(name="Glimpse of Nature", owner=None)
        for c in ["G"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestGlimpseOfNatureAbilities:
    """Glimpse of Nature ability tests — expected to fail against stubs."""

    def test_on_resolve_draws_cards(self) -> None:
        """Glimpse of Nature should draw cards when it resolves.

        Oracle: Whenever you cast a creature spell this turn, draw a card.
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with cards
        for i in range(10):
            dummy = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(dummy)

        card = GlimpseOfNature(name="Glimpse of Nature", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size to increase after resolving Glimpse of Nature. "
            f"Before: {hand_before}, After: {hand_after}"
        )

    def test_on_resolve_sets_up_delayed_trigger(self) -> None:
        """Glimpse of Nature should set up a delayed trigger for creature casts.

        Oracle: Whenever you cast a creature spell this turn, draw a card.
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game

        game = create_game()
        player = game.players[0]
        card = GlimpseOfNature(name="Glimpse of Nature", owner=player)
        card.controller = player
        card.on_resolve(game)
        from engine.triggers import EventType
        has_trigger = len(game.trigger_manager.get_triggers()) > 0
        assert has_trigger, (
            f"Expected Glimpse of Nature to set up delayed draw trigger"
        )
