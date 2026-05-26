"""Audited tests for Abstract Paintmage (collector number 171).

Verifies the Abstract Paintmage card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""
from __future__ import annotations

from test_utils import card_colors

import pytest
from card_impl import AbstractPaintmage
from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestAbstractPaintmageBasicProperties:
    """Abstract Paintmage basic property tests."""

    def test_is_creature(self) -> None:
        """Abstract Paintmage must be a Creature subclass."""
        card = AbstractPaintmage(name='Abstract Paintmage', owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """AbstractPaintmage.name must be 'Abstract Paintmage'."""
        card = AbstractPaintmage(name='Abstract Paintmage', owner=None)
        assert card.name == 'Abstract Paintmage'

    def test_card_type(self) -> None:
        """Abstract Paintmage must have CardType.CREATURE."""
        card = AbstractPaintmage(name='Abstract Paintmage', owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Abstract Paintmage must have converted mana cost 3."""
        card = AbstractPaintmage(name='Abstract Paintmage', owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Abstract Paintmage must have colors ['R', 'U']."""
        card = AbstractPaintmage(name='Abstract Paintmage', owner=None)
        for c in ['R', 'U']:
            assert c in card_colors(card), f'Expected color {c} in {card_colors(card)}'

    def test_power(self) -> None:
        """Abstract Paintmage must have power 2."""
        card = AbstractPaintmage(name='Abstract Paintmage', owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Abstract Paintmage must have toughness 2."""
        card = AbstractPaintmage(name='Abstract Paintmage', owner=None)
        assert card.base_toughness == 2

@pytest.mark.ability
class TestAbstractPaintmageAbilities:
    """Abstract Paintmage ability tests — expected to fail against stubs."""

    def test_has_beginning_of_phase_trigger(self) -> None:
        """Abstract Paintmage should register a beginning-of-phase trigger.

        Oracle: At the beginning of your first main phase, add {U}{R}. Spend this mana only to cast instant and sorc
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = AbstractPaintmage(name='Abstract Paintmage', owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        has_trigger = len(game.trigger_manager.get_triggers()) > 0
        assert has_trigger, f'Expected Abstract Paintmage to register phase trigger'
