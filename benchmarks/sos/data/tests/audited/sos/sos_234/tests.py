"""Audited tests for Stirring Honormancer (collector number 234).

Verifies the Stirring Honormancer card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""
from __future__ import annotations
import pytest
from card_impl import StirringHonormancer
from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.events import EntersBattlefieldTriggeredEvent

@pytest.mark.basic
class TestStirringHonormancerBasicProperties:
    """Stirring Honormancer basic property tests."""

    def test_is_creature(self) -> None:
        """Stirring Honormancer must be a Creature subclass."""
        card = StirringHonormancer(name='Stirring Honormancer', owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """StirringHonormancer.name must be 'Stirring Honormancer'."""
        card = StirringHonormancer(name='Stirring Honormancer', owner=None)
        assert card.name == 'Stirring Honormancer'

    def test_card_type(self) -> None:
        """Stirring Honormancer must have CardType.CREATURE."""
        card = StirringHonormancer(name='Stirring Honormancer', owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Stirring Honormancer must have converted mana cost 5."""
        card = StirringHonormancer(name='Stirring Honormancer', owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Stirring Honormancer must have colors ['B', 'W']."""
        card = StirringHonormancer(name='Stirring Honormancer', owner=None)
        for c in ['B', 'W']:
            assert c in card.colors, f'Expected color {c} in {card.colors}'

    def test_power(self) -> None:
        """Stirring Honormancer must have power 4."""
        card = StirringHonormancer(name='Stirring Honormancer', owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Stirring Honormancer must have toughness 5."""
        card = StirringHonormancer(name='Stirring Honormancer', owner=None)
        assert card.base_toughness == 5

@pytest.mark.ability
class TestStirringHonormancerAbilities:
    """Stirring Honormancer ability tests — expected to fail against stubs."""

    def test_etb_looks_at_top(self) -> None:
        """Stirring Honormancer ETB should look at top cards of library.

        Oracle: When this creature enters, look at the top X cards of your library, where X is the number of creatur
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl
        game = create_game()
        player = game.players[0]
        for i in range(10):
            player.zones[Zone.LIBRARY].add(CardImpl(name=f'Lib{i}', owner=player))
        card = StirringHonormancer(name='Stirring Honormancer', owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(card=card))
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, f'Expected card in hand from ETB look. Before: {hand_before}, After: {hand_after}'
