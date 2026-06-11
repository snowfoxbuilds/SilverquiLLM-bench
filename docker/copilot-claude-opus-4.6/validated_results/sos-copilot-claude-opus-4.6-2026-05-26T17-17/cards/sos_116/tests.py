"""Tests for SOS 116 — Garrison Excavator.

A 3/4 red Orc Sorcerer with Menace for {3}{R}.
Triggered ability: Whenever one or more cards leave your graveyard,
create a 2/2 red and white Spirit creature token.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_116.card_impl import GarrisonExcavator
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestGarrisonExcavatorProperties:
    """Static card data should match the SOS 116 spec."""

    def test_is_creature(self) -> None:
        card = GarrisonExcavator(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert GarrisonExcavator(owner=None).name == "Garrison Excavator"

    def test_mana_cost(self) -> None:
        assert GarrisonExcavator(owner=None).mana_cost == ManaCost.parse("{3}{R}")

    def test_power_and_toughness(self) -> None:
        card = GarrisonExcavator(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_menace(self) -> None:
        card = GarrisonExcavator(owner=None)
        assert Keyword.MENACE in card.keywords


class TestGarrisonExcavatorTriggeredAbility:
    """Whenever one or more cards leave your graveyard, create a 2/2 Spirit."""

    def test_card_leaving_graveyard_creates_spirit_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        excavator = GarrisonExcavator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(excavator)

        # Put a card in graveyard then exile it to trigger the ability
        filler = Creature(name="Filler", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[filler])

        # Simulate card leaving graveyard
        game.move_card(filler, Zone.GRAVEYARD, Zone.EXILE)
        game.process_triggers()

        # Should have a 2/2 Spirit token on battlefield
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield.cards if "Spirit" in c.name]
        assert len(tokens) >= 1
        token = tokens[0]
        assert token.base_power == 2
        assert token.base_toughness == 2

    def test_multiple_cards_leaving_at_once_creates_only_one_token(self) -> None:
        """The trigger says 'one or more' — batch removal = one trigger."""
        game = create_game()
        p1 = game.players[0]
        excavator = GarrisonExcavator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(excavator)

        filler1 = Creature(name="Filler1", owner=p1, base_power=1, base_toughness=1)
        filler2 = Creature(name="Filler2", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[filler1, filler2])

        # Both leave simultaneously
        game.move_card(filler1, Zone.GRAVEYARD, Zone.EXILE)
        game.move_card(filler2, Zone.GRAVEYARD, Zone.EXILE)
        game.process_triggers()

        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield.cards if "Spirit" in c.name]
        # Only one trigger, so only one token
        assert len(tokens) == 1

    def test_opponent_graveyard_leaving_does_not_trigger(self) -> None:
        """Only YOUR graveyard matters."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        excavator = GarrisonExcavator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(excavator)

        filler = Creature(name="Filler", owner=p2, base_power=1, base_toughness=1)
        set_board_state(game, 1, graveyard=[filler])

        game.move_card(filler, Zone.GRAVEYARD, Zone.EXILE)
        game.process_triggers()

        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield.cards if "Spirit" in c.name]
        assert len(tokens) == 0
