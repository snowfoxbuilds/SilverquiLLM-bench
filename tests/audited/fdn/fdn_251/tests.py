"""Audited tests for FDN 251 — Campus Guide."""

from __future__ import annotations

from card_impl import CampusGuide
from engine.card import ArtifactCreature
from engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


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


class TestCampusGuideETB:
    """ETB: search library for a basic land, put on top."""

    def test_rules_text_mentions_search(self) -> None:
        """The card's rules text should describe the ETB search ability."""
        card = CampusGuide(owner=None)
        assert "search" in card.rules_text.lower()
        assert "basic land" in card.rules_text.lower()

    def test_on_resolve_does_not_crash_with_empty_library(self) -> None:
        """on_resolve should be callable even with an empty library."""
        game = create_game()
        p1 = game.players[0]
        guide = CampusGuide(owner=p1, controller=p1)
        game.get_battlefield(p1).add(guide)
        # Should not raise
        guide.on_resolve(game)

