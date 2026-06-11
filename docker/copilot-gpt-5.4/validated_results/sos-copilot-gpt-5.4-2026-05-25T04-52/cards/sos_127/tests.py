"""Tests for SOS 127 — Rearing Embermare."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_127.card_impl import RearingEmbermare
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost


class TestRearingEmbermareProperties:
    """Static card data should match the SOS 127 spec."""

    def test_is_horse_beast_creature_with_reach_and_haste(self) -> None:
        card = RearingEmbermare(owner=None)

        assert isinstance(card, Creature)
        assert "Horse" in card.subtypes
        assert "Beast" in card.subtypes
        assert Keyword.REACH in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = RearingEmbermare(owner=None)

        assert card.name == "Rearing Embermare"
        assert card.mana_cost == ManaCost.parse("{4}{R}")
        assert card.base_power == 4
        assert card.base_toughness == 5
