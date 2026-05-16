"""Audited tests for Murmuring Mystic (SPG collector number 151).

Verifies the Murmuring Mystic card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""
from __future__ import annotations
import pytest
from card_impl import MurmuringMystic
from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestMurmuringMysticBasicProperties:
    """Murmuring Mystic basic property tests."""

    def test_is_creature(self) -> None:
        """Murmuring Mystic must be a Creature subclass."""
        card = MurmuringMystic(name='Murmuring Mystic', owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """MurmuringMystic.name must be 'Murmuring Mystic'."""
        card = MurmuringMystic(name='Murmuring Mystic', owner=None)
        assert card.name == 'Murmuring Mystic'

    def test_card_type(self) -> None:
        """Murmuring Mystic must have CardType.CREATURE."""
        card = MurmuringMystic(name='Murmuring Mystic', owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Murmuring Mystic must have converted mana cost 4."""
        card = MurmuringMystic(name='Murmuring Mystic', owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Murmuring Mystic must have colors ['U']."""
        card = MurmuringMystic(name='Murmuring Mystic', owner=None)
        for c in ['U']:
            assert c in card.colors, f'Expected color {c} in {card.colors}'

    def test_power(self) -> None:
        """Murmuring Mystic must have power 1."""
        card = MurmuringMystic(name='Murmuring Mystic', owner=None)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Murmuring Mystic must have toughness 5."""
        card = MurmuringMystic(name='Murmuring Mystic', owner=None)
        assert card.base_toughness == 5

@pytest.mark.ability
class TestMurmuringMysticAbilities:
    """Murmuring Mystic ability tests — expected to fail against stubs."""

    def test_has_cast_trigger(self) -> None:
        """Murmuring Mystic should register a trigger for spell casting.

        Oracle: Whenever you cast an instant or sorcery spell, create a 1/1 blue Bird Illusion creature token with f
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = MurmuringMystic(name='Murmuring Mystic', owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        has_trigger = len(game.trigger_manager.get_triggers()) > 0
        assert has_trigger, f'Expected Murmuring Mystic to register triggers on the EventBus'
