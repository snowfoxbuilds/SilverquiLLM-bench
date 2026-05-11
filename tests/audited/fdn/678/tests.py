"""Audited tests for Ramos, Dragon Engine (FDN collector number 678)."""
from __future__ import annotations
import pytest
from card_impl import RamosDragonEngine
from engine.types import CardType, Keyword, Supertype
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestRamosDragonEngineBasic:
    def test_is_artifact_creature(self) -> None:
        card = RamosDragonEngine(name="Ramos, Dragon Engine", owner=None)
        assert CardType.ARTIFACT in card.card_types
        assert CardType.CREATURE in card.card_types
    def test_is_legendary(self) -> None:
        card = RamosDragonEngine(name="Ramos, Dragon Engine", owner=None)
        assert Supertype.LEGENDARY in card.supertypes
    def test_power_toughness(self) -> None:
        card = RamosDragonEngine(name="Ramos, Dragon Engine", owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4
    def test_has_flying(self) -> None:
        card = RamosDragonEngine(name="Ramos, Dragon Engine", owner=None)
        assert Keyword.FLYING in card.keywords

@pytest.mark.ability
class TestRamosDragonEngineAbility:
    def test_has_activated_ability(self) -> None:
        card = RamosDragonEngine(name="Ramos, Dragon Engine", owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) > 0
