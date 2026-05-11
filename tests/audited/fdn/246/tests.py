"""Audited tests for Swiftblade Vindicator (FDN collector number 246) — double strike + vigilance + trample."""

from __future__ import annotations

import pytest

from card_impl import SwiftbladeVindicator

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestSwiftbladeVindicatorProperties:
    def test_is_creature(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        assert card.power == 1

    def test_toughness(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        assert card.toughness == 1

    def test_has_human_subtype(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        assert "Human" in card.subtypes

    def test_has_warrior_subtype(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        assert "Warrior" in card.subtypes


@pytest.mark.ability
class TestSwiftbladeVindicatorKeywords:
    def test_has_double_strike(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        assert Keyword.DOUBLE_STRIKE in card.keywords

    def test_has_vigilance(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_has_trample(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_exact_keywords(self) -> None:
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=None)
        expected = Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE | Keyword.TRAMPLE
        assert card.keywords == expected


@pytest.mark.behavior
class TestSwiftbladeVindicatorBehavior:
    """Double strike + vigilance + trample behavior tests."""

    def test_vigilance_does_not_tap_on_attack(self) -> None:
        """Swiftblade Vindicator does not tap when attacking."""
        from tests.test_utils import create_game, set_board_state, declare_attackers

        game = create_game()
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Swiftblade Vindicator"])
        assert not card.is_tapped

    def test_double_strike_deals_damage_twice(self) -> None:
        """Swiftblade Vindicator (1 power, double strike) deals 2 total unblocked."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = SwiftbladeVindicator(name="Swiftblade Vindicator", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Swiftblade Vindicator"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - 2
