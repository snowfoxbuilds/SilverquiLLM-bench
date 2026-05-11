"""Audited tests for Stadium Tidalmage (collector number 232).

Verifies the Stadium Tidalmage card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import StadiumTidalmage

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestStadiumTidalmageBasicProperties:
    """Stadium Tidalmage basic property tests."""

    def test_is_creature(self) -> None:
        """Stadium Tidalmage must be a Creature subclass."""
        card = StadiumTidalmage(name="Stadium Tidalmage", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """StadiumTidalmage.name must be 'Stadium Tidalmage'."""
        card = StadiumTidalmage(name="Stadium Tidalmage", owner=None)
        assert card.name == "Stadium Tidalmage"

    def test_card_type(self) -> None:
        """Stadium Tidalmage must have CardType.CREATURE."""
        card = StadiumTidalmage(name="Stadium Tidalmage", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Stadium Tidalmage must have converted mana cost 4."""
        card = StadiumTidalmage(name="Stadium Tidalmage", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Stadium Tidalmage must have colors ['R', 'U']."""
        card = StadiumTidalmage(name="Stadium Tidalmage", owner=None)
        for c in ["R", "U"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"

    def test_power(self) -> None:
        """Stadium Tidalmage must have power 4."""
        card = StadiumTidalmage(name="Stadium Tidalmage", owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Stadium Tidalmage must have toughness 4."""
        card = StadiumTidalmage(name="Stadium Tidalmage", owner=None)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestStadiumTidalmageAbilities:
    """Stadium Tidalmage ability tests — expected to fail against stubs."""

    def test_etb_draw_trigger(self) -> None:
        """Stadium Tidalmage should draw card(s) on ETB trigger.

        Oracle: Whenever this creature enters or attacks, you may draw a card. If you do, discard a card.
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        for i in range(10):
            dummy = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(dummy)

        card = StadiumTidalmage(name="Stadium Tidalmage", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.register_triggers(game)
        from engine.triggers import EventType
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"card": card})
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected draw on ETB. Before: {hand_before}, After: {hand_after}"
        )
