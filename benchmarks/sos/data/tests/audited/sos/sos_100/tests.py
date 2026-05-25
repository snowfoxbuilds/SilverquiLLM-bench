"""Audited tests for Send in the Pest (collector number 100).

Verifies the Send in the Pest card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SendInThePest

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSendInThePestBasicProperties:
    """Send in the Pest basic property tests."""

    def test_is_sorcery(self) -> None:
        """Send in the Pest must be a Sorcery subclass."""
        card = SendInThePest(name="Send in the Pest", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """SendInThePest.name must be 'Send in the Pest'."""
        card = SendInThePest(name="Send in the Pest", owner=None)
        assert card.name == "Send in the Pest"

    def test_card_type(self) -> None:
        """Send in the Pest must have CardType.SORCERY."""
        card = SendInThePest(name="Send in the Pest", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Send in the Pest must have converted mana cost 2."""
        card = SendInThePest(name="Send in the Pest", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Send in the Pest must have colors ['B']."""
        card = SendInThePest(name="Send in the Pest", owner=None)
        for c in ["B"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestSendInThePestAbilities:
    """Send in the Pest ability tests — expected to fail against stubs."""

    def test_on_resolve_creates_tokens(self) -> None:
        """Send in the Pest should create token(s) on resolution.

        Oracle: Each opponent discards a card. You create a 1/1 black and green Pest creature token with "Whenever t
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = SendInThePest(name="Send in the Pest", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Expected tokens on battlefield after resolving Send in the Pest. "
            f"Before: {bf_before}, After: {bf_after}"
        )

    def test_on_resolve_causes_discard(self) -> None:
        """Send in the Pest should cause discard on resolution.

        Oracle: Each opponent discards a card. You create a 1/1 black and green Pest creature token with "Whenever t
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        # Give opponent cards in hand
        hand_cards = [CardImpl(name=f"HandCard{i}", owner=opponent) for i in range(4)]
        set_board_state(game, 1, hand=hand_cards)
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = SendInThePest(name="Send in the Pest", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Expected opponent hand size to decrease. Before: {hand_before}, After: {hand_after}"
        )
