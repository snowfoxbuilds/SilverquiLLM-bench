"""Audited tests for FDN 251 — Campus Guide."""

from __future__ import annotations

from card_impl import CampusGuide
from engine.card import ArtifactCreature
from engine.types import ManaCost
from tests.test_utils import create_game


class TestCampusGuideBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = CampusGuide(owner=None)
        assert card.name == "Campus Guide"

    def test_mana_cost(self) -> None:
        card = CampusGuide(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}")

    def test_power_toughness(self) -> None:
        card = CampusGuide(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_is_artifact_creature(self) -> None:
        card = CampusGuide(owner=None)
        assert isinstance(card, ArtifactCreature)

    def test_golem_subtype(self) -> None:
        card = CampusGuide(owner=None)
        assert "Golem" in card.subtypes

