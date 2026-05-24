"""Audited tests for Rapturous Moment (collector number 219).

Verifies the Rapturous Moment card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import RapturousMoment

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestRapturousMomentBasicProperties:
    """Rapturous Moment basic property tests."""

    def test_is_sorcery(self) -> None:
        """Rapturous Moment must be a Sorcery subclass."""
        card = RapturousMoment(name="Rapturous Moment", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """RapturousMoment.name must be 'Rapturous Moment'."""
        card = RapturousMoment(name="Rapturous Moment", owner=None)
        assert card.name == "Rapturous Moment"

    def test_card_type(self) -> None:
        """Rapturous Moment must have CardType.SORCERY."""
        card = RapturousMoment(name="Rapturous Moment", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Rapturous Moment must have converted mana cost 6."""
        card = RapturousMoment(name="Rapturous Moment", owner=None)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Rapturous Moment must have colors ['R', 'U']."""
        card = RapturousMoment(name="Rapturous Moment", owner=None)
        for c in ["R", "U"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestRapturousMomentAbilities:
    """Rapturous Moment ability tests — expected to fail against stubs."""

    def test_on_resolve_draws_cards(self) -> None:
        """Rapturous Moment should draw cards when it resolves.

        Oracle: Draw three cards, then discard two cards. Add {U}{U}{R}{R}{R}.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with cards
        for i in range(10):
            dummy = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(dummy)

        card = RapturousMoment(name="Rapturous Moment", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size to increase after resolving Rapturous Moment. "
            f"Before: {hand_before}, After: {hand_after}"
        )

    def test_on_resolve_adds_mana(self) -> None:
        """Rapturous Moment should add mana to pool on resolution.

        Oracle: Draw three cards, then discard two cards. Add {U}{U}{R}{R}{R}.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = RapturousMoment(name="Rapturous Moment", owner=player)
        card.controller = player
        pool_before = player.mana_pool.total()
        card.on_resolve(game)
        pool_after = player.mana_pool.total()
        assert pool_after > pool_before, (
            f"Expected mana added. Pool before: {pool_before}, after: {pool_after}"
        )
