"""Tests for SOS 129 — Seize the Spoils.

Sorcery (2R). Additional cost: discard a card. Effect: draw 2, create a Treasure token.
"""

from __future__ import annotations

from cards.sos.sos_129.card_impl import SeizeTheSpoils
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestSeizeTheSpoilsProperties:
    """Static card data should match the SOS 129 spec."""

    def test_name(self) -> None:
        card = SeizeTheSpoils(owner=None)
        assert card.name == "Seize the Spoils"

    def test_is_sorcery(self) -> None:
        card = SeizeTheSpoils(owner=None)
        assert isinstance(card, Sorcery)

    def test_mana_cost(self) -> None:
        card = SeizeTheSpoils(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestSeizeTheSpoilsAdditionalCost:
    """Must discard a card as additional cost."""

    def test_has_additional_cost_discard(self) -> None:
        card = SeizeTheSpoils(owner=None)
        # The card should declare it requires an additional cost (discard)
        costs = card.get_additional_costs()
        assert costs is not None
        assert len(costs) > 0


class TestSeizeTheSpoilsResolution:
    """On resolve: draw 2 cards and create a Treasure token."""

    def test_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = SeizeTheSpoils(owner=p1, controller=p1)
        # Stock library with cards to draw
        lib_cards = [
            Creature(name=f"LibCard{i}", base_power=1, base_toughness=1)
            for i in range(5)
        ]
        game.players[0].library = lib_cards
        set_board_state(game, 0, hand=[])
        spell.on_resolve(game)
        # Should have drawn 2 cards
        assert len(game.get_hand(p1)) == 2

    def test_creates_treasure_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = SeizeTheSpoils(owner=p1, controller=p1)
        game.players[0].library = [
            Creature(name=f"LibCard{i}", base_power=1, base_toughness=1)
            for i in range(5)
        ]
        set_board_state(game, 0, hand=[])
        spell.on_resolve(game)
        # Should have a Treasure token on the battlefield
        battlefield = game.get_battlefield(p1)
        treasures = [c for c in battlefield if "Treasure" in c.name or
                     getattr(c, 'is_treasure', False)]
        assert len(treasures) >= 1
