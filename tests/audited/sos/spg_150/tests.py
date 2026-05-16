"""Audited tests for Archmage Emeritus (SPG collector number 150).

Verifies the Archmage Emeritus card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""
from __future__ import annotations
import pytest
from card_impl import ArchmageEmeritus
from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestArchmageEmeritusBasicProperties:
    """Archmage Emeritus basic property tests."""

    def test_is_creature(self) -> None:
        """Archmage Emeritus must be a Creature subclass."""
        card = ArchmageEmeritus(name='Archmage Emeritus', owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ArchmageEmeritus.name must be 'Archmage Emeritus'."""
        card = ArchmageEmeritus(name='Archmage Emeritus', owner=None)
        assert card.name == 'Archmage Emeritus'

    def test_card_type(self) -> None:
        """Archmage Emeritus must have CardType.CREATURE."""
        card = ArchmageEmeritus(name='Archmage Emeritus', owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Archmage Emeritus must have converted mana cost 4."""
        card = ArchmageEmeritus(name='Archmage Emeritus', owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Archmage Emeritus must have colors ['U']."""
        card = ArchmageEmeritus(name='Archmage Emeritus', owner=None)
        for c in ['U']:
            assert c in card.colors, f'Expected color {c} in {card.colors}'

    def test_power(self) -> None:
        """Archmage Emeritus must have power 2."""
        card = ArchmageEmeritus(name='Archmage Emeritus', owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Archmage Emeritus must have toughness 2."""
        card = ArchmageEmeritus(name='Archmage Emeritus', owner=None)
        assert card.base_toughness == 2

@pytest.mark.ability
class TestArchmageEmeritusAbilities:
    """Archmage Emeritus ability tests — expected to fail against stubs."""

    def test_has_cast_trigger(self) -> None:
        """Archmage Emeritus should register a trigger for spell casting.

        Oracle: Magecraft — Whenever you cast or copy an instant or sorcery spell, draw a card.
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ArchmageEmeritus(name='Archmage Emeritus', owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        has_trigger = len(game.trigger_manager.get_triggers()) > 0
        assert has_trigger, f'Expected Archmage Emeritus to register triggers on the EventBus'
