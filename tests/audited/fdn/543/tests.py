"""Audited tests for Raging Redcap (FDN collector number 543) — double strike."""

from __future__ import annotations

import pytest

from card_impl import RagingRedcap

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestRagingRedcapProperties:
    def test_is_creature(self) -> None:
        card = RagingRedcap(name="Raging Redcap", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = RagingRedcap(name="Raging Redcap", owner=None)
        assert card.power == 1

    def test_toughness(self) -> None:
        card = RagingRedcap(name="Raging Redcap", owner=None)
        assert card.toughness == 2

    def test_has_goblin_subtype(self) -> None:
        card = RagingRedcap(name="Raging Redcap", owner=None)
        assert "Goblin" in card.subtypes

    def test_has_knight_subtype(self) -> None:
        card = RagingRedcap(name="Raging Redcap", owner=None)
        assert "Knight" in card.subtypes


@pytest.mark.ability
class TestRagingRedcapKeywords:
    def test_has_double_strike(self) -> None:
        card = RagingRedcap(name="Raging Redcap", owner=None)
        assert Keyword.DOUBLE_STRIKE in card.keywords

    def test_only_double_strike(self) -> None:
        card = RagingRedcap(name="Raging Redcap", owner=None)
        assert card.keywords == Keyword.DOUBLE_STRIKE


@pytest.mark.behavior
class TestRagingRedcapBehavior:
    """Double strike behavior: deals damage in both first strike and normal damage steps."""

    def test_double_strike_deals_damage_twice(self) -> None:
        """Raging Redcap (1 power, double strike) deals 2 total damage unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = RagingRedcap(name="Raging Redcap", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Raging Redcap"])
        combat_damage_step(game)
        # Double strike: 1 (first strike) + 1 (normal) = 2 total
        assert game.players[1].life == 20 - 2
