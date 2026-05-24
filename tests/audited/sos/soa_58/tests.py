"""Audited tests for Shared Roots (SOA collector number 58).

Verifies the Shared Roots card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SharedRoots

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSharedRootsBasicProperties:
    """Shared Roots basic property tests."""

    def test_is_sorcery(self) -> None:
        """Shared Roots must be a Sorcery subclass."""
        card = SharedRoots(name="Shared Roots", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """SharedRoots.name must be 'Shared Roots'."""
        card = SharedRoots(name="Shared Roots", owner=None)
        assert card.name == "Shared Roots"

    def test_card_type(self) -> None:
        """Shared Roots must have CardType.SORCERY."""
        card = SharedRoots(name="Shared Roots", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Shared Roots must have converted mana cost 2."""
        card = SharedRoots(name="Shared Roots", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Shared Roots must have colors ['G']."""
        card = SharedRoots(name="Shared Roots", owner=None)
        for c in ["G"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestSharedRootsAbilities:
    """Shared Roots ability tests — expected to fail against stubs."""

    def test_on_resolve_searches_library(self) -> None:
        """Shared Roots should search library on resolution.

        Oracle: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl, Land

        game = create_game()
        player = game.players[0]
        # Stock library with searchable cards
        for i in range(5):
            lib_card = Land(name="Plains", owner=player)
            lib_card.subtypes = {"Plains"}
            player.zones[Zone.LIBRARY].add(lib_card)
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = SharedRoots(name="Shared Roots", owner=player)
        card.controller = player
        card.on_resolve(game)
        # After search, library should decrease or hand/bf should increase
        lib_after = len(player.zones[Zone.LIBRARY].get_all())
        hand_after = len(player.zones[Zone.HAND].get_all())
        bf_after = len(game.get_battlefield(player).get_all())
        assert lib_after < lib_before or hand_after > 0 or bf_after > 0, (
            f"Expected library search effect. Lib: {lib_before}->{lib_after}, "
            f"Hand: {hand_after}, BF: {bf_after}"
        )
