"""Audited tests for Eternal Student (collector number 82).

Verifies the Eternal Student card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import EternalStudent

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEternalStudentBasicProperties:
    """Eternal Student basic property tests."""

    def test_is_creature(self) -> None:
        """Eternal Student must be a Creature subclass."""
        card = EternalStudent(name="Eternal Student", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EternalStudent.name must be 'Eternal Student'."""
        card = EternalStudent(name="Eternal Student", owner=None)
        assert card.name == "Eternal Student"

    def test_card_type(self) -> None:
        """Eternal Student must have CardType.CREATURE."""
        card = EternalStudent(name="Eternal Student", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Eternal Student must have converted mana cost 4."""
        card = EternalStudent(name="Eternal Student", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Eternal Student must have colors ['B']."""
        card = EternalStudent(name="Eternal Student", owner=None)
        for c in ["B"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"

    def test_power(self) -> None:
        """Eternal Student must have power 4."""
        card = EternalStudent(name="Eternal Student", owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Eternal Student must have toughness 2."""
        card = EternalStudent(name="Eternal Student", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestEternalStudentAbilities:
    """Eternal Student ability tests — expected to fail against stubs."""

    def test_graveyard_activated_ability(self) -> None:
        """Eternal Student has an activated ability from the graveyard.

        Oracle: {1}{B}, Exile this card from your graveyard: Create two 1/1 white and black Inkling creature tokens 
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = EternalStudent(name="Eternal Student", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        # A correct impl should have an activated ability usable from GY
        abilities = card.get_activated_abilities()
        assert len(abilities) > 0, (
            f"Expected at least one activated ability on {card.name}"
        )
