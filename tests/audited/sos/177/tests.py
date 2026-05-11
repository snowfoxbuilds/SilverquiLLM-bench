"""Audited tests for Bogwater Lumaret (collector number 177).

Verifies the Bogwater Lumaret card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import BogwaterLumaret

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBogwaterLumaretBasicProperties:
    """Bogwater Lumaret basic property tests."""

    def test_is_creature(self) -> None:
        """Bogwater Lumaret must be a Creature subclass."""
        card = BogwaterLumaret(name="Bogwater Lumaret", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """BogwaterLumaret.name must be 'Bogwater Lumaret'."""
        card = BogwaterLumaret(name="Bogwater Lumaret", owner=None)
        assert card.name == "Bogwater Lumaret"

    def test_card_type(self) -> None:
        """Bogwater Lumaret must have CardType.CREATURE."""
        card = BogwaterLumaret(name="Bogwater Lumaret", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Bogwater Lumaret must have converted mana cost 2."""
        card = BogwaterLumaret(name="Bogwater Lumaret", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Bogwater Lumaret must have colors ['B', 'G']."""
        card = BogwaterLumaret(name="Bogwater Lumaret", owner=None)
        for c in ["B", "G"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"

    def test_power(self) -> None:
        """Bogwater Lumaret must have power 2."""
        card = BogwaterLumaret(name="Bogwater Lumaret", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Bogwater Lumaret must have toughness 2."""
        card = BogwaterLumaret(name="Bogwater Lumaret", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestBogwaterLumaretAbilities:
    """Bogwater Lumaret ability tests — expected to fail against stubs."""

    def test_etb_triggers_life_gain(self) -> None:
        """Bogwater Lumaret should trigger life gain on creature ETB.

        Oracle: Whenever this creature or another creature you control enters, you gain 1 life.
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = BogwaterLumaret(name="Bogwater Lumaret", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        life_before = player.life
        card.register_triggers(game)
        from engine.triggers import EventType
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"card": card})
        assert player.life > life_before, (
            f"Expected life gain on ETB. Before: {life_before}, After: {player.life}"
        )
