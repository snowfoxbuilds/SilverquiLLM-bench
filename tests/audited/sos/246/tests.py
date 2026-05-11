"""Audited tests for Zaffai and the Tempests (collector number 246).

Verifies the Zaffai and the Tempests card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ZaffaiAndTheTempests

from engine.card import Creature
from engine.types import CardType, ManaCost, Supertype


@pytest.mark.basic
class TestZaffaiAndTheTempestsBasicProperties:
    """Zaffai and the Tempests basic property tests."""

    def test_is_creature(self) -> None:
        """Zaffai and the Tempests must be a Creature subclass."""
        card = ZaffaiAndTheTempests(name="Zaffai and the Tempests", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ZaffaiAndTheTempests.name must be 'Zaffai and the Tempests'."""
        card = ZaffaiAndTheTempests(name="Zaffai and the Tempests", owner=None)
        assert card.name == "Zaffai and the Tempests"

    def test_card_type(self) -> None:
        """Zaffai and the Tempests must have CardType.CREATURE."""
        card = ZaffaiAndTheTempests(name="Zaffai and the Tempests", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Zaffai and the Tempests must have converted mana cost 7."""
        card = ZaffaiAndTheTempests(name="Zaffai and the Tempests", owner=None)
        assert card.mana_cost.cmc == 7

    def test_colors(self) -> None:
        """Zaffai and the Tempests must have colors ['R', 'U']."""
        card = ZaffaiAndTheTempests(name="Zaffai and the Tempests", owner=None)
        for c in ["R", "U"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"

    def test_power(self) -> None:
        """Zaffai and the Tempests must have power 5."""
        card = ZaffaiAndTheTempests(name="Zaffai and the Tempests", owner=None)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        """Zaffai and the Tempests must have toughness 7."""
        card = ZaffaiAndTheTempests(name="Zaffai and the Tempests", owner=None)
        assert card.base_toughness == 7


@pytest.mark.ability
class TestZaffaiAndTheTempestsAbilities:
    """Zaffai and the Tempests ability tests — expected to fail against stubs."""

    def test_has_special_casting_ability(self) -> None:
        """Zaffai and the Tempests grants ability to cast spells.

        Oracle: Once during each of your turns, you may cast an instant or sorcery spell from your hand without payi
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        player = game.players[0]
        card = ZaffaiAndTheTempests(name="Zaffai and the Tempests", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        # Correct impl allows free casting; verify ability is registered
        from engine.triggers import EventType
        has_trigger = len(game.trigger_manager.get_triggers()) > 0
        assert has_trigger, (
            f"Expected Zaffai and the Tempests to register special casting ability"
        )
