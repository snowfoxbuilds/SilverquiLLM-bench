"""Tests for SOS 162 — Studious First-Year // Rampant Growth.

A 1/1 Bear Wizard creature for {G} that enters prepared.
While prepared, you may cast a copy of its spell (Rampant Growth).
Doing so unprepares it.
"""

from __future__ import annotations

from cards.sos.sos_162.card_impl import StudiousFirstYearRampantGrowth
from engine.card import Creature
from engine.types import ManaCost
from test_utils import create_game


class TestStudiousFirstYearProperties:
    """Static card data should match the SOS 162 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(StudiousFirstYearRampantGrowth(owner=None), Creature)

    def test_name(self) -> None:
        card = StudiousFirstYearRampantGrowth(owner=None)
        assert card.name == "Studious First-Year // Rampant Growth"

    def test_mana_cost(self) -> None:
        card = StudiousFirstYearRampantGrowth(owner=None)
        assert card.mana_cost == ManaCost.parse("{G}")

    def test_power_toughness(self) -> None:
        card = StudiousFirstYearRampantGrowth(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestStudiousFirstYearPrepared:
    """Prepared mechanic: enters prepared, can cast spell copy, unprepares."""

    def test_enters_battlefield_prepared(self) -> None:
        """The creature should enter the battlefield in a prepared state."""
        game = create_game()
        p1 = game.players[0]
        card = StudiousFirstYearRampantGrowth(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.enter_battlefield(game)
        assert card.is_prepared is True

    def test_casting_spell_unprepares(self) -> None:
        """After casting the associated spell copy, creature becomes unprepared."""
        game = create_game()
        p1 = game.players[0]
        card = StudiousFirstYearRampantGrowth(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.enter_battlefield(game)
        assert card.is_prepared is True
        # Cast the prepared spell
        card.cast_prepared_spell(game)
        assert card.is_prepared is False

    def test_cannot_cast_spell_when_unprepared(self) -> None:
        """Should not be able to cast the prepared spell if already unprepared."""
        game = create_game()
        p1 = game.players[0]
        card = StudiousFirstYearRampantGrowth(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.enter_battlefield(game)
        card.is_prepared = False
        # Should not allow casting again
        result = card.can_cast_prepared_spell(game)
        assert result is False

    def test_prepared_spell_is_rampant_growth(self) -> None:
        """The prepared spell should be a copy of Rampant Growth."""
        game = create_game()
        p1 = game.players[0]
        card = StudiousFirstYearRampantGrowth(owner=p1, controller=p1)
        spell = card.get_prepared_spell(game)
        assert spell.name == "Rampant Growth"
