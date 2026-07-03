"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

A 3/3 Cat Cleric for {1}{W}{W}.
ETB: target player creates a 1/1 W/B Inkling token with flying.
Then if an opponent controls more creatures than you, this creature
becomes prepared. (Prepared spell: Swords to Plowshares, {W} instant.)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestEmeritusOfTruceProperties:
    """Static card data should match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Emeritus of Truce" in card.name

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmeritusETBToken:
    """ETB creates a 1/1 W/B Inkling with flying for target player."""

    def test_creates_inkling_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Target self for the token
        card.chosen_targets = [p1]
        bf = game.get_battlefield(p1)
        before = len(bf.get_all())
        card.on_resolve(game)
        after = len(bf.get_all())
        # At least the Inkling token should be created
        assert after - before >= 1

    def test_token_has_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [obj for obj in bf.get_all() if getattr(obj, "is_token", False)]
        assert len(tokens) >= 1
        assert Keyword.FLYING in tokens[0].keywords

    def test_target_opponent_gets_token(self) -> None:
        """If target player is the opponent, token goes to opponent's battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p2]
        bf2 = game.get_battlefield(p2)
        before = len(bf2.get_all())
        card.on_resolve(game)
        after = len(bf2.get_all())
        assert after - before >= 1


class TestEmeritusPreparedCondition:
    """Becomes prepared if opponent controls more creatures than you."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Opponent has 3 creatures, we have none (besides this one entering)
        for i in range(3):
            opp_creature = Creature(
                name=f"Opp Bear {i}", owner=p2, controller=p2,
                base_power=2, base_toughness=2
            )
            game.get_battlefield(p2).add(opp_creature)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert getattr(card, "is_prepared", False) is True

    def test_not_prepared_when_you_have_more_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # We have 3 creatures already
        for i in range(3):
            our_creature = Creature(
                name=f"Our Bear {i}", owner=p1, controller=p1,
                base_power=2, base_toughness=2
            )
            game.get_battlefield(p1).add(our_creature)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert getattr(card, "is_prepared", False) is False
