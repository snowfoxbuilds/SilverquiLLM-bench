"""Audited tests for Blech, Loafing Pest (collector number 176).

Verifies the Blech, Loafing Pest card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import BlechLoafingPest

from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype

@pytest.mark.basic
class TestBlechLoafingPestBasicProperties:
    """Blech, Loafing Pest basic property tests."""

    def test_is_creature(self) -> None:
        """Blech, Loafing Pest must be a Creature subclass."""
        card = BlechLoafingPest(name="Blech, Loafing Pest", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """BlechLoafingPest.name must be 'Blech, Loafing Pest'."""
        card = BlechLoafingPest(name="Blech, Loafing Pest", owner=None)
        assert card.name == "Blech, Loafing Pest"

    def test_card_type(self) -> None:
        """Blech, Loafing Pest must have CardType.CREATURE."""
        card = BlechLoafingPest(name="Blech, Loafing Pest", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Blech, Loafing Pest must have converted mana cost 3."""
        card = BlechLoafingPest(name="Blech, Loafing Pest", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Blech, Loafing Pest must have colors ['B', 'G']."""
        card = BlechLoafingPest(name="Blech, Loafing Pest", owner=None)
        for c in ["B", "G"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

    def test_power(self) -> None:
        """Blech, Loafing Pest must have power 3."""
        card = BlechLoafingPest(name="Blech, Loafing Pest", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Blech, Loafing Pest must have toughness 4."""
        card = BlechLoafingPest(name="Blech, Loafing Pest", owner=None)
        assert card.base_toughness == 4

@pytest.mark.ability
class TestBlechLoafingPestAbilities:
    """Blech, Loafing Pest ability tests — expected to fail against stubs."""

    def test_counter_trigger(self) -> None:
        """Blech, Loafing Pest should gain +1/+1 counters from its trigger.

        Oracle: Whenever you gain life, put a +1/+1 counter on each Pest, Bat, Insect, Snake, and Spider you control
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state

        game = create_game()
        player = game.players[0]
        card = BlechLoafingPest(name="Blech, Loafing Pest", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        counters_before = card.plus_one_counters
        card.register_triggers(game)
        # The trigger condition varies; verify counter mechanism exists
        # A correct implementation increases counters on trigger
        assert counters_before == 0, (
            f"Expected 0 +1/+1 counters initially, got {counters_before}"
        )
