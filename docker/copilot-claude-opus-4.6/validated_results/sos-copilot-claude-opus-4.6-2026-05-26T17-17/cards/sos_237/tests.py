"""Tests for SOS 237 — Tam, Observant Sequencer // Deep Sight.

Front face: {2}{G}{U} Legendary Creature — Gorgon Wizard, 4/3
Landfall — Whenever a land you control enters, Tam becomes prepared.
(While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)
"""

from __future__ import annotations

from cards.sos.sos_237.card_impl import TamObservantSequencerDeepSight
from engine.card import Creature
from engine.types import ManaCost, Keyword, Zone
from test_utils import create_game


class TestTamProperties:
    """Static card data should match the SOS 237 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TamObservantSequencerDeepSight(owner=None), Creature)

    def test_name(self) -> None:
        card = TamObservantSequencerDeepSight(owner=None)
        assert card.name == "Tam, Observant Sequencer"

    def test_mana_cost(self) -> None:
        card = TamObservantSequencerDeepSight(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}{U}")

    def test_power_toughness(self) -> None:
        card = TamObservantSequencerDeepSight(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = TamObservantSequencerDeepSight(owner=None)
        assert "Gorgon" in card.subtypes
        assert "Wizard" in card.subtypes


class TestTamLandfall:
    """Landfall trigger should make Tam prepared."""

    def test_starts_not_prepared(self) -> None:
        card = TamObservantSequencerDeepSight(owner=None)
        assert getattr(card, "prepared", False) is False

    def test_landfall_makes_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TamObservantSequencerDeepSight(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Simulate landfall trigger
        card.on_land_enters(game, p1)
        assert card.prepared is True

    def test_casting_spell_copy_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TamObservantSequencerDeepSight(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Make prepared, then cast
        card.prepared = True
        card.cast_prepared_spell(game)
        assert card.prepared is False
