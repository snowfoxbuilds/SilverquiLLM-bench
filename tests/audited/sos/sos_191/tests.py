"""Audited tests for Geometer's Arthropod (collector number 191).

Verifies the Geometer's Arthropod card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""
from __future__ import annotations
import pytest
from card_impl import GeometersArthropod
from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestGeometersArthropodBasicProperties:
    """Geometer's Arthropod basic property tests."""

    def test_is_creature(self) -> None:
        """Geometer's Arthropod must be a Creature subclass."""
        card = GeometersArthropod(name="Geometer's Arthropod", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """GeometersArthropod.name must be 'Geometer's Arthropod'."""
        card = GeometersArthropod(name="Geometer's Arthropod", owner=None)
        assert card.name == "Geometer's Arthropod"

    def test_card_type(self) -> None:
        """Geometer's Arthropod must have CardType.CREATURE."""
        card = GeometersArthropod(name="Geometer's Arthropod", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Geometer's Arthropod must have converted mana cost 2."""
        card = GeometersArthropod(name="Geometer's Arthropod", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Geometer's Arthropod must have colors ['G', 'U']."""
        card = GeometersArthropod(name="Geometer's Arthropod", owner=None)
        for c in ['G', 'U']:
            assert c in card.colors, f'Expected color {c} in {card.colors}'

    def test_power(self) -> None:
        """Geometer's Arthropod must have power 1."""
        card = GeometersArthropod(name="Geometer's Arthropod", owner=None)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Geometer's Arthropod must have toughness 4."""
        card = GeometersArthropod(name="Geometer's Arthropod", owner=None)
        assert card.base_toughness == 4

@pytest.mark.ability
class TestGeometersArthropodAbilities:
    """Geometer's Arthropod ability tests — expected to fail against stubs."""

    def test_has_cast_trigger(self) -> None:
        """Geometer's Arthropod should register a trigger for spell casting.

        Oracle: Whenever you cast a spell with {X} in its mana cost, look at the top X cards of your library. Put on
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = GeometersArthropod(name="Geometer's Arthropod", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        has_trigger = len(game.trigger_manager.get_triggers()) > 0
        assert has_trigger, f"Expected Geometer's Arthropod to register triggers on the EventBus"
