"""Tests for SOS 212 — Prismari, the Inspiration.

Legendary Creature — Elder Dragon (7/7)
Flying, Ward—Pay 5 life.
Instant and sorcery spells you cast have storm.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_212.card_impl import PrismariTheInspiration
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost
from test_utils import create_game, set_board_state


class TestPrismariTheInspirationProperties:
    """Static card data should match the SOS 212 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(PrismariTheInspiration(owner=None), Creature)

    def test_name(self) -> None:
        assert PrismariTheInspiration(owner=None).name == "Prismari, the Inspiration"

    def test_mana_cost(self) -> None:
        assert PrismariTheInspiration(owner=None).mana_cost == ManaCost.parse("{5}{U}{R}")

    def test_power_toughness(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_flying(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_ward(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert Keyword.WARD in card.keywords

    def test_is_legendary(self) -> None:
        card = PrismariTheInspiration(owner=None)
        assert card.is_legendary is True


class TestPrismariTheInspirationWard:
    """Ward — Pay 5 life."""

    def test_ward_cost_is_5_life(self) -> None:
        card = PrismariTheInspiration(owner=None)
        # Ward cost should represent paying 5 life
        assert card.ward_cost == 5


class TestPrismariTheInspirationStorm:
    """Instant and sorcery spells you cast have storm."""

    def test_grants_storm_to_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]

        dragon = PrismariTheInspiration(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)

        # Create a simple instant
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        game.get_hand(p1).append(bolt)

        # The dragon should grant storm to instants cast by its controller
        assert dragon.grants_storm_to(bolt) is True

    def test_does_not_grant_storm_to_opponent_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        dragon = PrismariTheInspiration(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)

        # Opponent's instant should not get storm
        opp_spell = Instant(name="Opp Bolt", owner=p2, controller=p2)
        assert dragon.grants_storm_to(opp_spell) is False

    def test_storm_copies_based_on_spells_cast_this_turn(self) -> None:
        """If 2 spells were cast before, storm should create 2 copies."""
        game = create_game()
        p1 = game.players[0]

        dragon = PrismariTheInspiration(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)

        # Simulate 2 spells already cast this turn
        game.storm_count = 2

        bolt = Instant(name="Storm Bolt", owner=p1, controller=p1)
        bolt.chosen_targets = []
        # When the spell resolves with storm, it should produce copies
        # equal to the number of spells cast before it
        copies = dragon.get_storm_copies(game, bolt)
        assert len(copies) == 2
