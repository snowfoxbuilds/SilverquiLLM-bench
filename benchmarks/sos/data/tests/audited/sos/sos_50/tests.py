"""Audited tests for Fractal Anomaly (collector number 50).

Verifies the Fractal Anomaly card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import FractalAnomaly

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestFractalAnomalyBasicProperties:
    """Fractal Anomaly basic property tests."""

    def test_is_instant(self) -> None:
        """Fractal Anomaly must be a Instant subclass."""
        card = FractalAnomaly(name="Fractal Anomaly", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """FractalAnomaly.name must be 'Fractal Anomaly'."""
        card = FractalAnomaly(name="Fractal Anomaly", owner=None)
        assert card.name == "Fractal Anomaly"

    def test_card_type(self) -> None:
        """Fractal Anomaly must have CardType.INSTANT."""
        card = FractalAnomaly(name="Fractal Anomaly", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Fractal Anomaly must have converted mana cost 1."""
        card = FractalAnomaly(name="Fractal Anomaly", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Fractal Anomaly must have colors ['U']."""
        card = FractalAnomaly(name="Fractal Anomaly", owner=None)
        for c in ["U"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestFractalAnomalyAbilities:
    """Fractal Anomaly ability tests — expected to fail against stubs."""

    def test_on_resolve_token_has_counters_based_on_drawn_cards(self) -> None:
        """Fractal Anomaly token should have +1/+1 counters equal to cards drawn this turn.

        Oracle: Create a 0/0 green and blue Fractal creature token and put X +1/+1 counters on it, where X is the number of cards you've drawn this turn.
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Simulate having drawn 3 cards this turn
        player.cards_drawn_this_turn = 3

        card = FractalAnomaly(name="Fractal Anomaly", owner=player)
        card.controller = player
        card.on_resolve(game)

        bf = game.get_battlefield(player).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) >= 1, "Expected at least one Fractal token on battlefield"
        token = tokens[0]
        assert getattr(token, "plus_one_counters", 0) == 3, (
            f"Expected 3 +1/+1 counters (cards drawn this turn), got {getattr(token, 'plus_one_counters', 0)}"
        )

    def test_on_resolve_creates_tokens(self) -> None:
        """Fractal Anomaly should create token(s) on resolution.

        Oracle: Create a 0/0 green and blue Fractal creature token and put X +1/+1 counters on it, where X is the nu
        This test will fail against stubs (expected).
        """
        from test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        card = FractalAnomaly(name="Fractal Anomaly", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Expected tokens on battlefield after resolving Fractal Anomaly. "
            f"Before: {bf_before}, After: {bf_after}"
        )
