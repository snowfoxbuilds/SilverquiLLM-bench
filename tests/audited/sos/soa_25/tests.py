"""Audited tests for Ad Nauseam (SOA collector number 25).

Verifies the Ad Nauseam card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import AdNauseam

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestAdNauseamBasicProperties:
    """Ad Nauseam basic property tests."""

    def test_is_instant(self) -> None:
        """Ad Nauseam must be a Instant subclass."""
        card = AdNauseam(name="Ad Nauseam", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """AdNauseam.name must be 'Ad Nauseam'."""
        card = AdNauseam(name="Ad Nauseam", owner=None)
        assert card.name == "Ad Nauseam"

    def test_card_type(self) -> None:
        """Ad Nauseam must have CardType.INSTANT."""
        card = AdNauseam(name="Ad Nauseam", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Ad Nauseam must have converted mana cost 5."""
        card = AdNauseam(name="Ad Nauseam", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Ad Nauseam must have colors ['B']."""
        card = AdNauseam(name="Ad Nauseam", owner=None)
        for c in ["B"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestAdNauseamAbilities:
    """Ad Nauseam ability tests — expected to fail against stubs."""

    def test_on_resolve_reveals_and_loses_life(self) -> None:
        """Ad Nauseam should reveal library card and lose life equal to its mana value.

        Oracle: Reveal the top card of your library and put that card into your hand. You lose life equal to its mana value. You may repeat this process any number of times.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.types import Zone, ManaCost
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Stock library with a card of known mana value (CMC 3)
        lib_card = CardImpl(name="ExpensiveCard", owner=player)
        lib_card.mana_cost = ManaCost.parse("{2}{B}")
        player.zones[Zone.LIBRARY].add(lib_card)

        card = AdNauseam(name="Ad Nauseam", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        # Should lose life equal to the revealed card's mana value (3)
        assert player.life <= life_before - 3, (
            f"Expected at least 3 life loss from revealing a CMC-3 card. "
            f"Before: {life_before}, After: {player.life}"
        )

    def test_on_resolve_puts_revealed_card_in_hand(self) -> None:
        """Ad Nauseam should put revealed cards into hand.

        Oracle: Reveal the top card of your library and put that card into your hand.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.types import Zone, ManaCost
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        lib_card = CardImpl(name="RevealedCard", owner=player)
        lib_card.mana_cost = ManaCost.parse("{1}")
        player.zones[Zone.LIBRARY].add(lib_card)

        card = AdNauseam(name="Ad Nauseam", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand = player.zones[Zone.HAND].get_all()
        hand_names = [getattr(c, "name", "") for c in hand]
        assert "RevealedCard" in hand_names, (
            f"Expected revealed card in hand, got: {hand_names}"
        )
