"""Audited tests for Stone Docent (collector number 36).

Verifies the Stone Docent card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import StoneDocent

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestStoneDocentBasicProperties:
    """Stone Docent basic property tests."""

    def test_is_creature(self) -> None:
        """Stone Docent must be a Creature subclass."""
        card = StoneDocent(name="Stone Docent", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """StoneDocent.name must be 'Stone Docent'."""
        card = StoneDocent(name="Stone Docent", owner=None)
        assert card.name == "Stone Docent"

    def test_card_type(self) -> None:
        """Stone Docent must have CardType.CREATURE."""
        card = StoneDocent(name="Stone Docent", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Stone Docent must have converted mana cost 2."""
        card = StoneDocent(name="Stone Docent", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Stone Docent must have colors ['W']."""
        card = StoneDocent(name="Stone Docent", owner=None)
        for c in ["W"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

    def test_power(self) -> None:
        """Stone Docent must have power 3."""
        card = StoneDocent(name="Stone Docent", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Stone Docent must have toughness 1."""
        card = StoneDocent(name="Stone Docent", owner=None)
        assert card.base_toughness == 1

@pytest.mark.ability
class TestStoneDocentAbilities:
    """Stone Docent ability tests — expected to fail against stubs."""

    def test_graveyard_activated_ability(self) -> None:
        """Stone Docent has an activated ability from the graveyard.

        Oracle: {W}, Exile this card from your graveyard: You gain 2 life. Surveil 1. Activate only as a sorcery. (L
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = StoneDocent(name="Stone Docent", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        # A correct impl should have an activated ability usable from GY
        abilities = card.get_activated_abilities()
        assert len(abilities) > 0, (
            f"Expected at least one activated ability on {card.name}"
        )
