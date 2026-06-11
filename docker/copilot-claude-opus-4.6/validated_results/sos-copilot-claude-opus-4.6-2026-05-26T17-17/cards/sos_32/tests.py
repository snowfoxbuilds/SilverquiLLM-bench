"""Tests for SOS 32 — Soaring Stoneglider.

A 4/3 Elephant Cleric for {2}{W} with Flying, Vigilance.
Additional cost: exile two cards from your graveyard or pay {1}{W}.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_32.card_impl import SoaringStoneglider
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestSoaringStonegliderProperties:
    """Static card data should match the SOS 32 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SoaringStoneglider(owner=None), Creature)

    def test_name(self) -> None:
        assert SoaringStoneglider(owner=None).name == "Soaring Stoneglider"

    def test_mana_cost(self) -> None:
        assert SoaringStoneglider(owner=None).mana_cost == ManaCost.parse("{2}{W}")

    def test_power_toughness(self) -> None:
        card = SoaringStoneglider(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in SoaringStoneglider(owner=None).keywords

    def test_has_vigilance(self) -> None:
        assert Keyword.VIGILANCE in SoaringStoneglider(owner=None).keywords


class TestSoaringStonegliderAdditionalCost:
    """As additional cost: exile two cards from graveyard OR pay {1}{W}."""

    def test_can_cast_by_exiling_two_graveyard_cards(self) -> None:
        """If graveyard has 2+ cards, can pay the additional cost by exiling them."""
        game = create_game()
        p1 = game.players[0]
        stoneglider = SoaringStoneglider(owner=p1)

        # Put two cards in graveyard
        card_a = Creature(name="Card A", base_power=1, base_toughness=1, owner=p1)
        card_b = Creature(name="Card B", base_power=1, base_toughness=1, owner=p1)

        set_board_state(game, 0,
                        hand=[stoneglider],
                        graveyard=[card_a, card_b],
                        mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2})

        cast_spell(game, 0, "Soaring Stoneglider")

        # After cast, the two graveyard cards should be exiled
        assert card_a not in game.get_graveyard(p1)
        assert card_b not in game.get_graveyard(p1)
        # Stoneglider on battlefield
        assert any(c.name == "Soaring Stoneglider" for c in game.get_battlefield(p1))

    def test_can_cast_by_paying_extra_mana(self) -> None:
        """If paying {1}{W} extra, can cast without exiling graveyard cards."""
        game = create_game()
        p1 = game.players[0]
        stoneglider = SoaringStoneglider(owner=p1)

        # Empty graveyard, but enough mana for base + additional cost
        set_board_state(game, 0,
                        hand=[stoneglider],
                        graveyard=[],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 3})

        cast_spell(game, 0, "Soaring Stoneglider")

        # Stoneglider on battlefield
        assert any(c.name == "Soaring Stoneglider" for c in game.get_battlefield(p1))

    def test_cannot_cast_without_additional_cost(self) -> None:
        """With empty graveyard and only base mana, cannot cast."""
        game = create_game()
        p1 = game.players[0]
        stoneglider = SoaringStoneglider(owner=p1)

        # Only enough for base cost, no graveyard cards
        set_board_state(game, 0,
                        hand=[stoneglider],
                        graveyard=[],
                        mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2})

        with pytest.raises(Exception):
            cast_spell(game, 0, "Soaring Stoneglider")
