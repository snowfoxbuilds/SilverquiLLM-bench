"""Tests for SOS 120 — Improvisation Capstone.

{5}{R}{R} Sorcery — Lesson.
Exile cards from the top of your library until you exile cards with total
mana value 4 or greater. You may cast any number of spells from among them
without paying their mana costs.
Paradigm (Then exile this spell. After you first resolve a spell with this
name, you may cast a copy of it from exile without paying its mana cost at
the beginning of each of your first main phases.)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_has_paradigm_keyword(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert Keyword.PARADIGM in card.keywords


class TestImprovisationCapstoneResolution:
    """Exiles cards until total MV >= 4, then you may cast them free."""

    def test_exiles_cards_until_mana_value_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Build a library with known cards
        card_a = Creature(name="Bear", owner=p1, base_power=2, base_toughness=2)
        card_a.mana_cost = ManaCost.parse("{1}{G}")  # MV 2
        card_b = Creature(name="Ogre", owner=p1, base_power=3, base_toughness=3)
        card_b.mana_cost = ManaCost.parse("{2}{R}")  # MV 3

        # Set library (top to bottom: card_a, card_b)
        game.get_library(p1).cards = [card_b, card_a]  # card_a is on top

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Should exile until total MV >= 4
        # card_a (MV 2) + card_b (MV 3) = 5 >= 4, so both exiled
        library = game.get_library(p1)
        assert len(library.cards) == 0

    def test_spell_exiles_itself_after_resolution(self) -> None:
        """Paradigm: spell goes to exile, not graveyard."""
        game = create_game()
        p1 = game.players[0]

        # Provide at least one card with MV >= 4 in library
        big_card = Creature(name="Dragon", owner=p1, base_power=5, base_toughness=5)
        big_card.mana_cost = ManaCost.parse("{4}{R}{R}")  # MV 6
        game.get_library(p1).cards = [big_card]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # The spell itself should be in exile (paradigm)
        exile = game.get_exile(p1)
        assert spell in exile.cards

    def test_empty_library_does_not_crash(self) -> None:
        """Edge case: library is empty, should resolve gracefully."""
        game = create_game()
        p1 = game.players[0]

        game.get_library(p1).cards = []

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Should not raise
        spell.on_resolve(game)
