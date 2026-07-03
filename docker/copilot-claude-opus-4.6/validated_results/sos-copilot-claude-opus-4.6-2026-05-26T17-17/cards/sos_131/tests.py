"""Tests for SOS 131 — Strife Scholar // Awaken the Ages.

A 3/2 Orc Sorcerer for {2}{R} with Ward—Pay 2 life.
This creature enters prepared (while prepared, you may cast a copy of its spell;
doing so unprepares it). The back face is a Sorcery costing {5}{R}.
"""

from __future__ import annotations

from cards.sos.sos_131.card_impl import StrifeScholar
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestStrifeScholarProperties:
    """Static card data should match the SOS 131 spec."""

    def test_is_creature(self) -> None:
        card = StrifeScholar(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = StrifeScholar(owner=None)
        assert card.name == "Strife Scholar"

    def test_mana_cost(self) -> None:
        card = StrifeScholar(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")

    def test_power_toughness(self) -> None:
        card = StrifeScholar(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_has_ward_keyword(self) -> None:
        card = StrifeScholar(owner=None)
        assert Keyword.WARD in card.keywords


class TestStrifeScholarPrepared:
    """Strife Scholar enters prepared."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StrifeScholar(owner=p1, controller=p1)
        card.on_resolve(game)
        assert card.prepared is True

    def test_casting_spell_copy_unprepares(self) -> None:
        """After casting the spell copy, the creature should be unprepared."""
        game = create_game()
        p1 = game.players[0]
        card = StrifeScholar(owner=p1, controller=p1)
        card.prepared = True
        # Simulate casting the prepared spell copy
        card.cast_prepared_spell(game)
        assert card.prepared is False


class TestStrifeScholarWard:
    """Ward — Pay 2 life."""

    def test_ward_cost_is_2_life(self) -> None:
        card = StrifeScholar(owner=None)
        # The ward cost should indicate 2 life payment
        assert card.ward_cost == 2
