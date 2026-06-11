"""Tests for SOS 110 — Charging Strifeknight."""

from __future__ import annotations

import pytest

from cards.sos.sos_110.card_impl import ChargingStrifeknight
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestChargingStrifeknightProperties:
    """Static card data should match SOS 110 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ChargingStrifeknight(owner=None), Creature)

    def test_name(self) -> None:
        assert ChargingStrifeknight(owner=None).name == "Charging Strifeknight"

    def test_mana_cost(self) -> None:
        assert ChargingStrifeknight(owner=None).mana_cost == ManaCost.parse("{2}{R}")

    def test_power_toughness(self) -> None:
        card = ChargingStrifeknight(owner=None)
        assert card.power == 3
        assert card.toughness == 3

    def test_has_haste(self) -> None:
        card = ChargingStrifeknight(owner=None)
        assert Keyword.HASTE in card.keywords


class TestChargingStrifeknightAbility:
    """Tap, discard a card: Draw a card (rummage/loot ability)."""

    def test_activate_taps_and_draws(self) -> None:
        """Activating the ability should tap the creature and draw a card."""
        game = create_game()
        p1 = game.players[0]
        card = ChargingStrifeknight(owner=p1, controller=p1)
        card.tapped = False
        game.get_battlefield(p1).add(card)

        # Put a card in hand to discard
        discard_target = Creature(name="Fodder", owner=p1, base_power=1, base_toughness=1)
        game.get_hand(p1).add(discard_target)

        # Put a card in library to draw
        draw_target = Creature(name="DrawMe", owner=p1, base_power=2, base_toughness=2)
        game.get_library(p1).add(draw_target)

        hand_before = len(game.get_hand(p1))
        card.activate_ability(game, 0, discard=discard_target)

        # Creature is tapped
        assert card.tapped is True
        # Net card count: discarded 1, drew 1 = same hand size
        assert len(game.get_hand(p1)) == hand_before

    def test_cannot_activate_when_tapped(self) -> None:
        """Cannot activate if already tapped."""
        game = create_game()
        p1 = game.players[0]
        card = ChargingStrifeknight(owner=p1, controller=p1)
        card.tapped = True
        game.get_battlefield(p1).add(card)

        assert card.can_activate_ability(game, 0) is False

    def test_cannot_activate_with_empty_hand(self) -> None:
        """Cannot activate if no card to discard."""
        game = create_game()
        p1 = game.players[0]
        card = ChargingStrifeknight(owner=p1, controller=p1)
        card.tapped = False
        game.get_battlefield(p1).add(card)

        # Hand is empty
        assert card.can_activate_ability(game, 0) is False

    def test_discarded_card_goes_to_graveyard(self) -> None:
        """The discarded card should end up in the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = ChargingStrifeknight(owner=p1, controller=p1)
        card.tapped = False
        game.get_battlefield(p1).add(card)

        discard_target = Creature(name="Fodder", owner=p1, base_power=1, base_toughness=1)
        game.get_hand(p1).add(discard_target)

        draw_target = Creature(name="DrawMe", owner=p1, base_power=2, base_toughness=2)
        game.get_library(p1).add(draw_target)

        card.activate_ability(game, 0, discard=discard_target)

        graveyard = game.get_graveyard(p1)
        assert discard_target in graveyard
