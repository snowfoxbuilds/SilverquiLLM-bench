"""Tests for SOS 33 — Spiritcall Enthusiast // Scrollboost.

Front face: 3/3 Cat Cleric for {2}{W}.
Whenever one or more tokens you control enter, this creature becomes prepared.
(While prepared, you may cast a copy of its spell side. Doing so unprepares it.)
"""

from __future__ import annotations

import pytest
from cards.sos.sos_33.card_impl import SpiritcallEnthusiastScrollboost
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSpiritcallEnthusiastProperties:
    """Static card data should match the SOS 33 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SpiritcallEnthusiastScrollboost(owner=None), Creature)

    def test_name(self) -> None:
        card = SpiritcallEnthusiastScrollboost(owner=None)
        assert card.name == "Spiritcall Enthusiast // Scrollboost"

    def test_mana_cost(self) -> None:
        card = SpiritcallEnthusiastScrollboost(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}")

    def test_power_toughness(self) -> None:
        card = SpiritcallEnthusiastScrollboost(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestSpiritcallEnthusiastPrepared:
    """Token entering triggers 'prepared' status."""

    def test_becomes_prepared_when_token_enters(self) -> None:
        """When a token enters under your control, creature becomes prepared."""
        game = create_game()
        p1 = game.players[0]
        enthusiast = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)
        enthusiast.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(enthusiast)

        # Create a token entering the battlefield
        token = Creature(name="Soldier Token", base_power=1, base_toughness=1,
                         owner=p1, controller=p1)
        token.is_token = True
        token.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(token)
        game.trigger_enters_battlefield(token)

        assert enthusiast.is_prepared is True

    def test_starts_not_prepared(self) -> None:
        """The creature should not be prepared initially."""
        game = create_game()
        p1 = game.players[0]
        enthusiast = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)
        enthusiast.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(enthusiast)

        assert enthusiast.is_prepared is False

    def test_casting_spell_copy_unprepares(self) -> None:
        """Casting the spell copy should unprepare the creature."""
        game = create_game()
        p1 = game.players[0]
        enthusiast = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)
        enthusiast.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(enthusiast)

        # Mark as prepared
        enthusiast.is_prepared = True

        # Cast the spell copy
        enthusiast.cast_prepared_spell(game)

        assert enthusiast.is_prepared is False

    def test_multiple_tokens_entering_still_just_prepares_once(self) -> None:
        """'One or more tokens' — multiple tokens in one event still prepares once."""
        game = create_game()
        p1 = game.players[0]
        enthusiast = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)
        enthusiast.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(enthusiast)

        token1 = Creature(name="Token A", base_power=1, base_toughness=1,
                          owner=p1, controller=p1)
        token1.is_token = True
        token2 = Creature(name="Token B", base_power=1, base_toughness=1,
                          owner=p1, controller=p1)
        token2.is_token = True

        game.get_battlefield(p1).add(token1)
        game.get_battlefield(p1).add(token2)
        game.trigger_enters_battlefield(token1)
        game.trigger_enters_battlefield(token2)

        # Should be prepared (just once, not double-prepared)
        assert enthusiast.is_prepared is True
