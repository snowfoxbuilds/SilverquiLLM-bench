"""Tests for SOS 117 — Goblin Glasswright // Craft with Pride.

Front face: {1}{R} 2/2 Goblin Sorcerer creature.
Back face: {R} Sorcery — Craft with Pride.
Enters prepared. While prepared, you may cast a copy of its spell (unprepares it).
Keywords: Treasure, Prepared.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_117.card_impl import GoblinGlasswright
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestGoblinGlasswrightProperties:
    """Static card data should match the SOS 117 spec."""

    def test_is_creature(self) -> None:
        card = GoblinGlasswright(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert GoblinGlasswright(owner=None).name == "Goblin Glasswright"

    def test_mana_cost(self) -> None:
        assert GoblinGlasswright(owner=None).mana_cost == ManaCost.parse("{1}{R}")

    def test_power_and_toughness(self) -> None:
        card = GoblinGlasswright(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestGoblinGlasswrightPrepared:
    """The creature enters prepared and can cast its spell side."""

    def test_enters_battlefield_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinGlasswright(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        assert card.prepared is True

    def test_casting_spell_unprepares(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinGlasswright(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        assert card.prepared is True

        # Cast the spell copy
        card.cast_prepared_spell(game)
        assert card.prepared is False

    def test_cannot_cast_spell_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GoblinGlasswright(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        card.prepared = False

        # Should not be able to cast when unprepared
        with pytest.raises(Exception):
            card.cast_prepared_spell(game)
