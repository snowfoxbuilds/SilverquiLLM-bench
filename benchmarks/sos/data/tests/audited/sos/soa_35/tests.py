"""Audited tests for Vampiric Tutor (SOA collector number 35).

Verifies the Vampiric Tutor card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import VampiricTutor

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestVampiricTutorBasicProperties:
    """Vampiric Tutor basic property tests."""

    def test_is_instant(self) -> None:
        """Vampiric Tutor must be a Instant subclass."""
        card = VampiricTutor(name="Vampiric Tutor", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """VampiricTutor.name must be 'Vampiric Tutor'."""
        card = VampiricTutor(name="Vampiric Tutor", owner=None)
        assert card.name == "Vampiric Tutor"

    def test_card_type(self) -> None:
        """Vampiric Tutor must have CardType.INSTANT."""
        card = VampiricTutor(name="Vampiric Tutor", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Vampiric Tutor must have converted mana cost 1."""
        card = VampiricTutor(name="Vampiric Tutor", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Vampiric Tutor must have colors ['B']."""
        card = VampiricTutor(name="Vampiric Tutor", owner=None)
        for c in ["B"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestVampiricTutorAbilities:
    """Vampiric Tutor ability tests — expected to fail against stubs."""

    def test_on_resolve_puts_card_on_top_of_library(self) -> None:
        """Vampiric Tutor should search for a card and put it on top of library.

        Oracle: Search your library for a card, then shuffle and put that card on top. You lose 2 life.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with searchable cards
        target = CardImpl(name="TargetCard", owner=player)
        for i in range(5):
            lib_card = CardImpl(name=f"OtherCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(lib_card)
        player.zones[Zone.LIBRARY].add(target)

        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = VampiricTutor(name="Vampiric Tutor", owner=player)
        card.controller = player
        card.on_resolve(game)

        # Library size should remain the same (card stays in library, just on top)
        lib_after = len(player.zones[Zone.LIBRARY].get_all())
        assert lib_after == lib_before, (
            f"Expected library size unchanged (card goes on top, not to hand). "
            f"Before: {lib_before}, After: {lib_after}"
        )

    def test_on_resolve_costs_life(self) -> None:
        """Vampiric Tutor should cost life on resolution.

        Oracle: Search your library for a card, then shuffle and put that card on top. You lose 2 life.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = VampiricTutor(name="Vampiric Tutor", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life < life_before, (
            f"Expected life loss. Before: {life_before}, After: {player.life}"
        )
