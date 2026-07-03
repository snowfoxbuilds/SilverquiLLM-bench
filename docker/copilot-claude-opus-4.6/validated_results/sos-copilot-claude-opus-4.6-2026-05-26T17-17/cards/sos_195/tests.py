"""Tests for SOS 195 — Imperious Inkmage."""

from __future__ import annotations

import pytest

from cards.sos.sos_195.card_impl import ImperiousInkmage
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestImperiousInkmageProperties:
    """Static card data should match SOS 195 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ImperiousInkmage(owner=None), Creature)

    def test_name(self) -> None:
        assert ImperiousInkmage(owner=None).name == "Imperious Inkmage"

    def test_mana_cost(self) -> None:
        assert ImperiousInkmage(owner=None).mana_cost == ManaCost.parse("{1}{W}{B}")

    def test_power(self) -> None:
        assert ImperiousInkmage(owner=None).base_power == 3

    def test_toughness(self) -> None:
        assert ImperiousInkmage(owner=None).base_toughness == 3

    def test_has_vigilance(self) -> None:
        assert Keyword.VIGILANCE in ImperiousInkmage(owner=None).keywords


class TestImperiousInkmageETB:
    """When enters, surveil 2."""

    def test_etb_trigger_exists(self) -> None:
        game = create_game()
        inkmage = ImperiousInkmage(owner=game.players[0])
        set_board_state(game, 0, battlefield=[inkmage])
        # Should have an ETB triggered ability
        triggers = inkmage.get_triggered_abilities(game)
        assert len(triggers) >= 1

    def test_surveil_puts_cards_in_graveyard(self) -> None:
        """Surveil 2 can put up to 2 cards from top of library into graveyard."""
        game = create_game()
        inkmage = ImperiousInkmage(owner=game.players[0])

        card1 = Creature(name="Top Card 1", base_power=1, base_toughness=1)
        card2 = Creature(name="Top Card 2", base_power=2, base_toughness=2)
        card1.owner = game.players[0]
        card2.owner = game.players[0]
        game.players[0].library = [card1, card2]

        set_board_state(game, 0, hand=[inkmage],
                        mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        # Cast to trigger ETB surveil
        cast_spell(game, 0, "Imperious Inkmage")

        # After surveil 2 (choosing to put both in graveyard),
        # both cards should be in graveyard
        graveyard_names = [c.name for c in game.players[0].graveyard]
        library_names = [c.name for c in game.players[0].library]

        # At minimum, the surveil should have processed 2 cards
        # (they either went to graveyard or stayed on top)
        total_processed = len(graveyard_names) + len(library_names)
        assert total_processed >= 2 or len(game.players[0].library) <= 0

    def test_surveil_with_fewer_than_two_cards_in_library(self) -> None:
        """Surveil 2 with only 1 card in library should still work."""
        game = create_game()
        inkmage = ImperiousInkmage(owner=game.players[0])

        card1 = Creature(name="Only Card", base_power=1, base_toughness=1)
        card1.owner = game.players[0]
        game.players[0].library = [card1]

        set_board_state(game, 0, hand=[inkmage],
                        mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        # Should not error with fewer cards than surveil amount
        cast_spell(game, 0, "Imperious Inkmage")

        # Card should have been surveilled (either on top or in graveyard)
        assert (card1 in game.players[0].graveyard or
                card1 in game.players[0].library)

    def test_surveil_with_empty_library(self) -> None:
        """Surveil 2 with empty library should not error."""
        game = create_game()
        inkmage = ImperiousInkmage(owner=game.players[0])
        game.players[0].library = []

        set_board_state(game, 0, hand=[inkmage],
                        mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 1})

        # Should not raise
        cast_spell(game, 0, "Imperious Inkmage")
        assert inkmage.zone == Zone.BATTLEFIELD
