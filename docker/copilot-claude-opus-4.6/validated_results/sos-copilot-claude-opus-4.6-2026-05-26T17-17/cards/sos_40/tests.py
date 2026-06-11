"""Tests for SOS 40 — Campus Composer // Aqueous Aria.

Creature — Merfolk Bard for {3}{U}, 3/4 with Ward {2}.
This creature enters prepared. (While it's prepared, you may cast a copy
of its spell. Doing so unprepares it.)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_40.card_impl import CampusComposerAqueousAria
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestCampusComposerProperties:
    """Static card data should match the SOS 40 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(CampusComposerAqueousAria(owner=None), Creature)

    def test_name(self) -> None:
        card = CampusComposerAqueousAria(owner=None)
        assert card.name == "Campus Composer // Aqueous Aria"

    def test_mana_cost(self) -> None:
        card = CampusComposerAqueousAria(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")

    def test_power_toughness(self) -> None:
        card = CampusComposerAqueousAria(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_ward(self) -> None:
        card = CampusComposerAqueousAria(owner=None)
        assert Keyword.WARD in card.keywords


class TestCampusComposerPrepared:
    """The creature enters prepared and can cast a copy of its spell side."""

    def test_enters_prepared(self) -> None:
        """When entering the battlefield, the creature should be prepared."""
        game = create_game()
        p1 = game.players[0]
        card = CampusComposerAqueousAria(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Trigger ETB
        card.on_resolve(game)
        assert card.prepared is True

    def test_casting_spell_unprepares(self) -> None:
        """After casting the spell copy, the creature becomes unprepared."""
        game = create_game()
        p1 = game.players[0]
        card = CampusComposerAqueousAria(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.on_resolve(game)
        assert card.prepared is True
        # Simulate casting the spell copy
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1
        abilities[0].effect(game)
        assert card.prepared is False

    def test_cannot_cast_spell_when_unprepared(self) -> None:
        """If unprepared, the spell cannot be cast."""
        game = create_game()
        p1 = game.players[0]
        card = CampusComposerAqueousAria(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.prepared = False
        abilities = card.get_activated_abilities()
        # Either no abilities available or cost check fails
        if len(abilities) > 0:
            result = abilities[0].cost(game)
            assert result is False
