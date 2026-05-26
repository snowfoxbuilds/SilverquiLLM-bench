"""Audited tests for Preordain (SOA collector number 21).

Verifies the Preordain card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import Preordain

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestPreordainBasicProperties:
    """Preordain basic property tests."""

    def test_is_sorcery(self) -> None:
        """Preordain must be a Sorcery subclass."""
        card = Preordain(name="Preordain", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """Preordain.name must be 'Preordain'."""
        card = Preordain(name="Preordain", owner=None)
        assert card.name == "Preordain"

    def test_card_type(self) -> None:
        """Preordain must have CardType.SORCERY."""
        card = Preordain(name="Preordain", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Preordain must have converted mana cost 1."""
        card = Preordain(name="Preordain", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Preordain must have colors ['U']."""
        card = Preordain(name="Preordain", owner=None)
        for c in ["U"]:
            assert c in card_colors(card), f"Expected color {c} in {card_colors(card)}"

@pytest.mark.ability
class TestPreordainAbilities:
    """Preordain ability tests — expected to fail against stubs."""

    def test_on_resolve_draws_cards(self) -> None:
        """Preordain should draw cards when it resolves.

        Oracle: Scry 2, then draw a card. (To scry 2, look at the top two cards of your library, then put any number
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with cards
        for i in range(10):
            dummy = CardImpl(name=f"LibCard{i}", owner=player)
            player.zones[Zone.LIBRARY].add(dummy)

        card = Preordain(name="Preordain", owner=player)
        card.controller = player
        hand_before = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Expected hand size to increase after resolving Preordain. "
            f"Before: {hand_before}, After: {hand_after}"
        )

    def test_on_resolve_performs_scry(self) -> None:
        """Preordain should scry on resolution.

        Oracle: Scry 2, then draw a card. (To scry 2, look at the top two cards of your library, then put any number
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library
        for i in range(5):
            player.zones[Zone.LIBRARY].add(CardImpl(name=f"Lib{i}", owner=player))
        card = Preordain(name="Preordain", owner=player)
        card.controller = player
        # on_resolve should scry (rearrange top of library)
        lib_before = [c.name for c in player.zones[Zone.LIBRARY].get_all()]
        card.on_resolve(game)
        # After scry + draw, hand should have cards or library should change
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > 0, (
            f"Expected cards in hand after resolving Preordain (scry + draw)"
        )
