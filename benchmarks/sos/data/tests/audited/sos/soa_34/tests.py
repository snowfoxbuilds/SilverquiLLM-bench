"""Audited tests for Stargaze (SOA collector number 34).

Verifies the Stargaze card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Stargaze

from engine.card import Sorcery
from engine.types import CardType


@pytest.mark.basic
class TestStargazeBasicProperties:
    """Stargaze basic property tests."""

    def test_is_sorcery(self) -> None:
        """Stargaze must be a Sorcery subclass."""
        card = Stargaze(name="Stargaze", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """Stargaze.name must be 'Stargaze'."""
        card = Stargaze(name="Stargaze", owner=None)
        assert card.name == "Stargaze"

    def test_card_type(self) -> None:
        """Stargaze must have CardType.SORCERY."""
        card = Stargaze(name="Stargaze", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_has_x(self) -> None:
        """Stargaze must have X in its mana cost."""
        card = Stargaze(name="Stargaze", owner=None)
        assert card.mana_cost.x_count >= 1

    def test_colors(self) -> None:
        """Stargaze must have colors ['B']."""
        card = Stargaze(name="Stargaze", owner=None)
        for c in ["B"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestStargazeAbilities:
    """Stargaze ability tests — expected to fail against stubs."""

    def test_on_resolve_loses_x_life(self) -> None:
        """Stargaze should cause X life loss on resolution.

        Oracle: Look at twice X cards from the top of your library. Put X cards from among them into your hand and the rest into your graveyard. You lose X life.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with 2*X = 6 cards
        for i in range(6):
            lib_card = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(lib_card)

        card = Stargaze(name="Stargaze", owner=player)
        card.controller = player
        card.x_value = 3  # Set X=3
        life_before = player.life
        card.on_resolve(game)
        assert player.life == life_before - 3, (
            f"Expected 3 life loss (X=3). Before: {life_before}, After: {player.life}"
        )

    def test_on_resolve_puts_x_cards_in_hand(self) -> None:
        """Stargaze should put X cards into hand from the top 2X.

        Oracle: Look at twice X cards from the top of your library. Put X cards from among them into your hand and the rest into your graveyard. You lose X life.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        for i in range(6):
            lib_card = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(lib_card)

        card = Stargaze(name="Stargaze", owner=player)
        card.controller = player
        card.x_value = 3
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after == hand_before + 3, (
            f"Expected 3 cards added to hand (X=3). Before: {hand_before}, After: {hand_after}"
        )
