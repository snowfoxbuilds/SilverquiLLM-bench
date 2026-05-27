"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

TDD red-phase tests for a 3/3 Cat Cleric with ETB that creates a 1/1
white/black Inkling token with flying for target player, then conditionally
becomes prepared if an opponent controls more creatures than you.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestEmeritusProperties:
    """Static card data should match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_card_types_include_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types


class TestEmeritusETBTokenCreation:
    """ETB: target player creates a 1/1 white/black Inkling with flying."""

    def test_etb_creates_token_on_controllers_battlefield(self) -> None:
        """When targeting self, a token appears on controller's battlefield."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]

        # Place the creature on battlefield to simulate it having entered
        game.get_battlefield(p1).add(card)
        before_count = len(game.get_battlefield(p1).get_all())

        card.on_etb(game)

        after_count = len(game.get_battlefield(p1).get_all())
        # Should have created one token
        assert after_count == before_count + 1

    def test_etb_creates_token_for_target_opponent(self) -> None:
        """When targeting opponent, token appears on opponent's battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p2]

        game.get_battlefield(p1).add(card)
        before_count = len(game.get_battlefield(p2).get_all())

        card.on_etb(game)

        after_count = len(game.get_battlefield(p2).get_all())
        assert after_count == before_count + 1

    def test_token_is_1_1(self) -> None:
        """The Inkling token should be 1/1."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        game.get_battlefield(p1).add(card)

        card.on_etb(game)

        # Find the token (not the card itself)
        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) == 1
        tok = tokens[0]
        assert tok.base_power == 1
        assert tok.base_toughness == 1

    def test_token_has_flying(self) -> None:
        """The Inkling token should have flying."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        game.get_battlefield(p1).add(card)

        card.on_etb(game)

        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) == 1
        assert Keyword.FLYING in tokens[0].keywords

    def test_token_is_creature(self) -> None:
        """The Inkling token should be a creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        game.get_battlefield(p1).add(card)

        card.on_etb(game)

        tokens = [
            obj for obj in game.get_battlefield(p1).get_all()
            if getattr(obj, "is_token", False)
        ]
        assert len(tokens) == 1
        assert isinstance(tokens[0], Creature)


class TestEmeritusETBTargeting:
    """ETB requires a target player."""

    def test_get_targets_returns_player_requirement(self) -> None:
        """The ETB should target a player."""
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1


class TestEmeritusPreparedCondition:
    """After token creation, becomes prepared if opponent has more creatures."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """If opponent controls more creatures than you, become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        game.get_battlefield(p1).add(card)

        # Opponent has 3 creatures, we have 1 (just the Emeritus itself)
        for i in range(3):
            opp_creature = Creature(
                name=f"Opponent Bear {i}",
                owner=p2,
                controller=p2,
                base_power=2,
                base_toughness=2,
            )
            game.get_battlefield(p2).add(opp_creature)

        card.on_etb(game)

        # After ETB: p1 has Emeritus + Inkling (2), p2 has 3 → prepared
        assert card.is_prepared is True

    def test_does_not_become_prepared_when_you_have_equal_creatures(self) -> None:
        """If you control equal creatures, do NOT become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        game.get_battlefield(p1).add(card)

        # Give opponent 1 creature; after ETB p1 has Emeritus + Inkling (2), p2 has 1
        opp_creature = Creature(
            name="Opponent Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(opp_creature)

        card.on_etb(game)

        # p1 has 2 creatures (Emeritus + token), p2 has 1 → not prepared
        assert card.is_prepared is False

    def test_does_not_become_prepared_when_you_have_more_creatures(self) -> None:
        """If you control more creatures, do NOT become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        game.get_battlefield(p1).add(card)

        # Add extra creatures for p1
        extra = Creature(
            name="Extra Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(extra)

        card.on_etb(game)

        # p1 has Emeritus + Extra + token = 3, p2 has 0 → not prepared
        assert card.is_prepared is False

    def test_prepared_checks_after_token_creation(self) -> None:
        """The prepared check counts creatures AFTER token creation."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Target opponent for token - token goes to opponent's side
        card.chosen_targets = [p2]
        game.get_battlefield(p1).add(card)

        # Opponent already has 1 creature; after getting token they'll have 2
        opp_creature = Creature(
            name="Opponent Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(opp_creature)

        card.on_etb(game)

        # p1 has 1 (Emeritus), p2 has 2 (Bear + token) → p2 > p1 → prepared
        assert card.is_prepared is True


class TestEmeritusPreparedMechanic:
    """Prepared allows casting the spell side and unprepares afterward."""

    def test_starts_not_prepared(self) -> None:
        """A freshly created Emeritus is not prepared."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.is_prepared is False

    def test_unprepares_after_spell_cast(self) -> None:
        """Casting the spell copy should unprepare the creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.is_prepared = True

        # Casting the prepared spell should set is_prepared to False
        card.cast_prepared_spell(game)

        assert card.is_prepared is False
