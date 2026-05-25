"""Audited tests for Expressive Iteration (SOA collector number 64).

Verifies the Expressive Iteration card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ExpressiveIteration

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestExpressiveIterationBasicProperties:
    """Expressive Iteration basic property tests."""

    def test_is_sorcery(self) -> None:
        """Expressive Iteration must be a Sorcery subclass."""
        card = ExpressiveIteration(name="Expressive Iteration", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """ExpressiveIteration.name must be 'Expressive Iteration'."""
        card = ExpressiveIteration(name="Expressive Iteration", owner=None)
        assert card.name == "Expressive Iteration"

    def test_card_type(self) -> None:
        """Expressive Iteration must have CardType.SORCERY."""
        card = ExpressiveIteration(name="Expressive Iteration", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Expressive Iteration must have converted mana cost 2."""
        card = ExpressiveIteration(name="Expressive Iteration", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Expressive Iteration must have colors ['R', 'U']."""
        card = ExpressiveIteration(name="Expressive Iteration", owner=None)
        for c in ["R", "U"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestExpressiveIterationAbilities:
    """Expressive Iteration ability tests — expected to fail against stubs."""

    def test_on_resolve_puts_card_in_hand(self) -> None:
        """Expressive Iteration should put card(s) into hand on resolution.

        Oracle: Look at the top three cards of your library. Put one of them into your hand, put one of them on the 
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        for i in range(10):
            player.zones[Zone.LIBRARY].add(CardImpl(name=f"Lib{i}", owner=player))
        card = ExpressiveIteration(name="Expressive Iteration", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size increase. Before: {hand_before}, After: {hand_after}"
        )

    def test_on_resolve_exiles_card(self) -> None:
        """Expressive Iteration should exile a card you may play this turn.

        Oracle: Look at the top three cards of your library. Put one of them into your hand, put one of them on the 
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        for i in range(10):
            player.zones[Zone.LIBRARY].add(CardImpl(name=f"Lib{i}", owner=player))
        card = ExpressiveIteration(name="Expressive Iteration", owner=player)
        card.controller = player
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert len(exile) > 0, (
            f"Expected at least one card in exile after resolving Expressive Iteration"
        )
