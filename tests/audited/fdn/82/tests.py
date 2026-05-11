"""Audited tests for Temporal Manipulation (SPG collector number 82)."""
from __future__ import annotations
import pytest
from card_impl import TemporalManipulation
from engine.card import Sorcery
from engine.types import ManaCost


@pytest.mark.basic
class TestTemporalManipulationBasic:
    def test_is_sorcery(self) -> None:
        card = TemporalManipulation()
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = TemporalManipulation()
        assert card.name == "Temporal Manipulation"

    def test_mana_cost(self) -> None:
        card = TemporalManipulation()
        assert card.mana_cost == ManaCost.parse("{3}{U}{U}")


@pytest.mark.ability
class TestTemporalManipulationResolve:
    def test_on_resolve_adds_extra_turn(self) -> None:
        """Resolving grants controller an extra turn (KEY_DECISIONS: extra turn insertion)."""
        from tests.test_utils import create_game
        game = create_game()
        p = game.players[0]
        card = TemporalManipulation(owner=p)
        card.controller = p
        card.on_resolve(game)
        assert len(game.extra_turns) >= 1
        assert game.extra_turns[-1] == 0  # player index 0

    def test_on_resolve_multiple_extra_turns(self) -> None:
        """Multiple resolutions should stack extra turns."""
        from tests.test_utils import create_game
        game = create_game()
        p = game.players[0]
        card1 = TemporalManipulation(owner=p)
        card1.controller = p
        card2 = TemporalManipulation(owner=p)
        card2.controller = p
        card1.on_resolve(game)
        card2.on_resolve(game)
        assert len(game.extra_turns) >= 2
