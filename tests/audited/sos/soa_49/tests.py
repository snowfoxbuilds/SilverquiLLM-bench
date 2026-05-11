"""Audited tests for Awaken the Woods (SOA collector number 49).

Verifies the Awaken the Woods card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import AwakenTheWoods

from engine.card import Sorcery
from engine.types import CardType


@pytest.mark.basic
class TestAwakenTheWoodsBasicProperties:
    """Awaken the Woods basic property tests."""

    def test_is_sorcery(self) -> None:
        """Awaken the Woods must be a Sorcery subclass."""
        card = AwakenTheWoods(name="Awaken the Woods", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """AwakenTheWoods.name must be 'Awaken the Woods'."""
        card = AwakenTheWoods(name="Awaken the Woods", owner=None)
        assert card.name == "Awaken the Woods"

    def test_card_type(self) -> None:
        """Awaken the Woods must have CardType.SORCERY."""
        card = AwakenTheWoods(name="Awaken the Woods", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_has_x(self) -> None:
        """Awaken the Woods must have X in its mana cost."""
        card = AwakenTheWoods(name="Awaken the Woods", owner=None)
        assert card.mana_cost.x_count >= 1

    def test_colors(self) -> None:
        """Awaken the Woods must have colors ['G']."""
        card = AwakenTheWoods(name="Awaken the Woods", owner=None)
        for c in ["G"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestAwakenTheWoodsAbilities:
    """Awaken the Woods ability tests — expected to fail against stubs."""

    def test_on_resolve_creates_x_tokens(self) -> None:
        """Awaken the Woods should create exactly X 1/1 Forest Dryad tokens.

        Oracle: Create X 1/1 green Forest Dryad land creature tokens. (They're affected by summoning sickness.)
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = AwakenTheWoods(name="Awaken the Woods", owner=player)
        card.controller = player
        card.x_value = 3  # Set X=3
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after == bf_before + 3, (
            f"Expected exactly 3 tokens on battlefield (X=3). "
            f"Before: {bf_before}, After: {bf_after}"
        )
