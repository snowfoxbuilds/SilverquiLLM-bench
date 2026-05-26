"""Audited tests for Dina's Guidance (collector number 184).

Verifies the Dina's Guidance card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import DinasGuidance

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestDinasGuidanceBasicProperties:
    """Dina's Guidance basic property tests."""

    def test_is_instant(self) -> None:
        """Dina's Guidance must be a Instant subclass."""
        card = DinasGuidance(name="Dina\'s Guidance", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """DinasGuidance.name must be 'Dina's Guidance'."""
        card = DinasGuidance(name="Dina\'s Guidance", owner=None)
        assert card.name == "Dina\'s Guidance"

    def test_card_type(self) -> None:
        """Dina's Guidance must have CardType.INSTANT."""
        card = DinasGuidance(name="Dina\'s Guidance", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Dina's Guidance must have converted mana cost 3."""
        card = DinasGuidance(name="Dina\'s Guidance", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Dina's Guidance must have colors ['B', 'G']."""
        card = DinasGuidance(name="Dina\'s Guidance", owner=None)
        for c in ["B", "G"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestDinasGuidanceAbilities:
    """Dina's Guidance ability tests — expected to fail against stubs."""

    def test_on_resolve_searches_library_for_creature(self) -> None:
        """Dina's Guidance should search library for a creature card.

        Oracle: Search your library for a creature card, reveal it, put it into your hand or graveyard, then shuffle.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone
        from engine.card import Creature as CreatureBase

        game = create_game()
        player = game.players[0]
        # Stock library with creature cards
        for i in range(5):
            lib_card = CreatureBase(name=f"Creature{i}", owner=player, base_power=1, base_toughness=1)
            player.zones[Zone.LIBRARY].add(lib_card)
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = DinasGuidance(name="Dina\'s Guidance", owner=player)
        card.controller = player
        card.on_resolve(game)
        # After search, library should decrease or hand/graveyard should increase
        lib_after = len(player.zones[Zone.LIBRARY].get_all())
        hand_after = len(player.zones[Zone.HAND].get_all())
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert lib_after < lib_before or hand_after > 0 or gy_after > 0, (
            f"Expected creature search effect. Lib: {lib_before}->{lib_after}, "
            f"Hand: {hand_after}, GY: {gy_after}"
        )
