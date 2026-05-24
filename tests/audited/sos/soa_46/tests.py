"""Audited tests for Pyretic Ritual (SOA collector number 46).

Verifies the Pyretic Ritual card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PyreticRitual

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPyreticRitualBasicProperties:
    """Pyretic Ritual basic property tests."""

    def test_is_instant(self) -> None:
        """Pyretic Ritual must be a Instant subclass."""
        card = PyreticRitual(name="Pyretic Ritual", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """PyreticRitual.name must be 'Pyretic Ritual'."""
        card = PyreticRitual(name="Pyretic Ritual", owner=None)
        assert card.name == "Pyretic Ritual"

    def test_card_type(self) -> None:
        """Pyretic Ritual must have CardType.INSTANT."""
        card = PyreticRitual(name="Pyretic Ritual", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Pyretic Ritual must have converted mana cost 2."""
        card = PyreticRitual(name="Pyretic Ritual", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Pyretic Ritual must have colors ['R']."""
        card = PyreticRitual(name="Pyretic Ritual", owner=None)
        for c in ["R"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestPyreticRitualAbilities:
    """Pyretic Ritual ability tests — expected to fail against stubs."""

    def test_on_resolve_adds_mana(self) -> None:
        """Pyretic Ritual should add mana to pool on resolution.

        Oracle: Add {R}{R}{R}.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = PyreticRitual(name="Pyretic Ritual", owner=player)
        card.controller = player
        pool_before = player.mana_pool.total()
        card.on_resolve(game)
        pool_after = player.mana_pool.total()
        assert pool_after > pool_before, (
            f"Expected mana added. Pool before: {pool_before}, after: {pool_after}"
        )
