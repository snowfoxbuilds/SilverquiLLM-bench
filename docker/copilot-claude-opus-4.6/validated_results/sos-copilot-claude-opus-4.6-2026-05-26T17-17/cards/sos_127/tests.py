"""Tests for SOS 127 — Rearing Embermare.

A simple creature: 4R for 4/5 with Reach and Haste.
"""

from __future__ import annotations

from cards.sos.sos_127.card_impl import RearingEmbermare
from engine.card import Creature
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestRearingEmbermareProperties:
    """Static card data should match the SOS 127 spec."""

    def test_name(self) -> None:
        card = RearingEmbermare(owner=None)
        assert card.name == "Rearing Embermare"

    def test_is_creature(self) -> None:
        card = RearingEmbermare(owner=None)
        assert isinstance(card, Creature)

    def test_mana_cost(self) -> None:
        card = RearingEmbermare(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{R}")

    def test_power_and_toughness(self) -> None:
        card = RearingEmbermare(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 5

    def test_has_reach(self) -> None:
        card = RearingEmbermare(owner=None)
        assert Keyword.REACH in card.keywords

    def test_has_haste(self) -> None:
        card = RearingEmbermare(owner=None)
        assert Keyword.HASTE in card.keywords

    def test_creature_type_horse_beast(self) -> None:
        card = RearingEmbermare(owner=None)
        assert "Horse" in card.subtypes
        assert "Beast" in card.subtypes
