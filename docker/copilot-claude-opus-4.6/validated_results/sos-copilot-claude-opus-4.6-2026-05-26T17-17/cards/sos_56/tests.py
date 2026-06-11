"""Tests for SOS 56 — Landscape Painter // Vibrant Idea."""

from __future__ import annotations

import pytest

from cards.sos.sos_56.card_impl import LandscapePainterVibrantIdea
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestLandscapePainterProperties:
    """Static card data should match the SOS 56 spec."""

    def test_is_creature(self) -> None:
        card = LandscapePainterVibrantIdea(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = LandscapePainterVibrantIdea(owner=None)
        assert card.name == "Landscape Painter"

    def test_mana_cost(self) -> None:
        card = LandscapePainterVibrantIdea(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}")

    def test_power_and_toughness(self) -> None:
        card = LandscapePainterVibrantIdea(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_has_prepared_keyword(self) -> None:
        card = LandscapePainterVibrantIdea(owner=None)
        assert Keyword.PREPARED in card.keywords

    def test_creature_types_include_merfolk_wizard(self) -> None:
        card = LandscapePainterVibrantIdea(owner=None)
        assert "Merfolk" in card.subtypes
        assert "Wizard" in card.subtypes


class TestLandscapePainterPrepared:
    """The creature enters prepared and can cast Vibrant Idea."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LandscapePainterVibrantIdea(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        # After entering, the creature should be in prepared state
        assert card.prepared is True

    def test_casting_spell_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LandscapePainterVibrantIdea(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card],
                        mana={ManaType.BLUE: 5, ManaType.COLORLESS: 5})
        card.prepared = True
        # Casting the spell side should unprepare it
        card.cast_prepared_spell(game)
        assert card.prepared is False

    def test_vibrant_idea_spell_costs_4u(self) -> None:
        """The spell side (Vibrant Idea) should cost {4}{U}."""
        card = LandscapePainterVibrantIdea(owner=None)
        assert card.spell_mana_cost == ManaCost.parse("{4}{U}")
