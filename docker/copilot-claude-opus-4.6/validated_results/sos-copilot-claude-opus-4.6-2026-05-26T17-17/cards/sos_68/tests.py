"""Tests for SOS 68 — Spellbook Seeker // Careful Study.

A {3}{U} 3/3 Flying creature that enters prepared.
The spell side is Careful Study ({U} Sorcery).
"""

from __future__ import annotations

from cards.sos.sos_68.card_impl import SpellbookSeeker
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestSpellbookSeekerProperties:
    """Static card data should match the SOS 68 spec."""

    def test_is_creature(self) -> None:
        card = SpellbookSeeker(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SpellbookSeeker(owner=None)
        assert card.name == "Spellbook Seeker"

    def test_mana_cost(self) -> None:
        card = SpellbookSeeker(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")

    def test_power_toughness(self) -> None:
        card = SpellbookSeeker(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = SpellbookSeeker(owner=None)
        assert Keyword.FLYING in card.keywords


class TestSpellbookSeekerPrepared:
    """Enters prepared — can cast a copy of Careful Study."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SpellbookSeeker(owner=p1, controller=p1)
        card.on_resolve(game)
        assert card.is_prepared is True

    def test_unprepares_after_casting_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SpellbookSeeker(owner=p1, controller=p1)
        card.on_resolve(game)
        card.cast_prepared_spell(game)
        assert card.is_prepared is False

    def test_cannot_cast_when_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SpellbookSeeker(owner=p1, controller=p1)
        card.on_resolve(game)
        card.is_prepared = False
        assert card.can_cast_prepared_spell(game) is False


class TestSpellbookSeekerSpellSide:
    """The spell side 'Careful Study' costs {U} and is a Sorcery."""

    def test_spell_side_name(self) -> None:
        card = SpellbookSeeker(owner=None)
        spell = card.get_spell_side()
        assert spell.name == "Careful Study"

    def test_spell_side_mana_cost(self) -> None:
        card = SpellbookSeeker(owner=None)
        spell = card.get_spell_side()
        assert spell.mana_cost == ManaCost.parse("{U}")

    def test_spell_side_is_sorcery(self) -> None:
        card = SpellbookSeeker(owner=None)
        spell = card.get_spell_side()
        assert isinstance(spell, Sorcery) or CardType.SORCERY in spell.card_types
