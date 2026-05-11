"""Audited tests for Deduce (SOA collector number 16).

Verifies the Deduce card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Deduce

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestDeduceBasicProperties:
    """Deduce basic property tests."""

    def test_is_instant(self) -> None:
        """Deduce must be a Instant subclass."""
        card = Deduce(name="Deduce", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Deduce.name must be 'Deduce'."""
        card = Deduce(name="Deduce", owner=None)
        assert card.name == "Deduce"

    def test_card_type(self) -> None:
        """Deduce must have CardType.INSTANT."""
        card = Deduce(name="Deduce", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Deduce must have converted mana cost 2."""
        card = Deduce(name="Deduce", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Deduce must have colors ['U']."""
        card = Deduce(name="Deduce", owner=None)
        for c in ["U"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestDeduceAbilities:
    """Deduce ability tests — expected to fail against stubs."""

    def test_on_resolve_draws_cards(self) -> None:
        """Deduce should draw cards when it resolves.

        Oracle: Draw a card. Investigate. (Create a Clue token. It's an artifact with "{2}, Sacrifice this token: Dr
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with cards
        for i in range(10):
            dummy = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(dummy)

        card = Deduce(name="Deduce", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size to increase after resolving Deduce. "
            f"Before: {hand_before}, After: {hand_after}"
        )

    def test_on_resolve_creates_tokens(self) -> None:
        """Deduce should create token(s) on resolution.

        Oracle: Draw a card. Investigate. (Create a Clue token. It's an artifact with "{2}, Sacrifice this token: Dr
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = Deduce(name="Deduce", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Expected tokens on battlefield after resolving Deduce. "
            f"Before: {bf_before}, After: {bf_after}"
        )

    def test_on_resolve_creates_clue(self) -> None:
        """Deduce should create a Clue token (Investigate).

        Oracle: Draw a card. Investigate. (Create a Clue token. It's an artifact with "{2}, Sacrifice this token: Dr
        This test will fail against stubs (expected).
        """
        from tests.test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        from engine.card import CardImpl
        for i in range(5):
            player.zones[Zone.LIBRARY].add(CardImpl(name=f"Lib{i}", owner=player))
        card = Deduce(name="Deduce", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf = game.get_battlefield(player).get_all()
        clues = [c for c in bf if 'Clue' in getattr(c, 'subtypes', set())]
        assert len(clues) >= 1, (
            f"Expected at least 1 Clue token from Investigate. Found: {bf}"
        )
