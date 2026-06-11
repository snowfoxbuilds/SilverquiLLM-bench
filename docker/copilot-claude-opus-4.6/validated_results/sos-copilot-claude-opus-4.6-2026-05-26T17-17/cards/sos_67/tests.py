"""Tests for SOS 67 — Skycoach Conductor // All Aboard.

A {2}{U} creature with Flash, Flying, Vigilance that enters prepared.
The spell side is All Aboard ({U} Instant).
"""

from __future__ import annotations

from cards.sos.sos_67.card_impl import SkycoachConductor
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestSkycoachConductorProperties:
    """Static card data should match the SOS 67 spec."""

    def test_is_creature(self) -> None:
        card = SkycoachConductor(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SkycoachConductor(owner=None)
        assert card.name == "Skycoach Conductor"

    def test_mana_cost(self) -> None:
        card = SkycoachConductor(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")

    def test_power_toughness(self) -> None:
        card = SkycoachConductor(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_flash(self) -> None:
        card = SkycoachConductor(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_has_flying(self) -> None:
        card = SkycoachConductor(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SkycoachConductor(owner=None)
        assert Keyword.VIGILANCE in card.keywords


class TestSkycoachConductorPrepared:
    """Enters prepared — can cast a copy of the spell side (All Aboard)."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkycoachConductor(owner=p1, controller=p1)
        card.on_resolve(game)
        assert card.is_prepared is True

    def test_unprepares_after_casting_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkycoachConductor(owner=p1, controller=p1)
        card.on_resolve(game)
        assert card.is_prepared is True
        # Casting the spell copy should unprepare
        card.cast_prepared_spell(game)
        assert card.is_prepared is False

    def test_cannot_cast_spell_when_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SkycoachConductor(owner=p1, controller=p1)
        card.on_resolve(game)
        card.is_prepared = False
        # Should not be able to cast spell when unprepared
        assert card.can_cast_prepared_spell(game) is False


class TestSkycoachConductorSpellSide:
    """The spell side 'All Aboard' costs {U} and is an Instant."""

    def test_spell_side_name(self) -> None:
        card = SkycoachConductor(owner=None)
        spell = card.get_spell_side()
        assert spell.name == "All Aboard"

    def test_spell_side_mana_cost(self) -> None:
        card = SkycoachConductor(owner=None)
        spell = card.get_spell_side()
        assert spell.mana_cost == ManaCost.parse("{U}")
