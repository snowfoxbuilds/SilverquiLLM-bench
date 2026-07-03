"""Tests for SOS 170 — Abigale, Poet Laureate // Heroic Stanza."""

from __future__ import annotations

import pytest

from cards.sos.sos_170.card_impl import AbigalePoetLaureateHeroicStanza
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestAbigaleProperties:
    """Static card data should match the SOS 170 spec."""

    def test_name(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)
        assert card.name == "Abigale, Poet Laureate"

    def test_is_creature(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)
        assert isinstance(card, Creature)

    def test_mana_cost(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{B}")

    def test_power_and_toughness(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_is_legendary(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)
        assert card.is_legendary is True


class TestAbigalePreparedTrigger:
    """Whenever you cast a creature spell, Abigale becomes prepared."""

    def test_becomes_prepared_on_creature_cast(self) -> None:
        """Casting any creature spell should prepare Abigale."""
        game = create_game()
        p1 = game.players[0]
        abigale = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)
        game.get_battlefield(p1).add(abigale)
        abigale.prepared = False

        # Simulate casting a creature spell
        bear = Creature(name="Test Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        abigale.on_creature_cast(game, bear)
        assert abigale.prepared is True

    def test_does_not_start_prepared(self) -> None:
        """Abigale does NOT enter prepared by default (unlike sos_166)."""
        game = create_game()
        p1 = game.players[0]
        abigale = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)
        game.get_battlefield(p1).add(abigale)
        abigale.on_enter_battlefield(game)
        assert abigale.prepared is False

    def test_casting_non_creature_does_not_prepare(self) -> None:
        """Non-creature spells should not trigger the ability."""
        game = create_game()
        p1 = game.players[0]
        abigale = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)
        game.get_battlefield(p1).add(abigale)
        abigale.prepared = False
        # Non-creature spell cast — should not trigger
        from engine.card import Sorcery
        spell = Sorcery(name="Some Spell", owner=p1, controller=p1)
        abigale.on_spell_cast(game, spell)
        assert abigale.prepared is False


class TestHeroicStanzaSpell:
    """The Heroic Stanza spell side."""

    def test_spell_name(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)
        assert card.spell_name == "Heroic Stanza"

    def test_spell_mana_cost(self) -> None:
        card = AbigalePoetLaureateHeroicStanza(owner=None)
        assert card.spell_mana_cost == ManaCost.parse("{1}{W/B}")

    def test_casting_spell_unprepares(self) -> None:
        """Casting the prepared spell unprepares Abigale."""
        game = create_game()
        p1 = game.players[0]
        abigale = AbigalePoetLaureateHeroicStanza(owner=p1, controller=p1)
        game.get_battlefield(p1).add(abigale)
        abigale.prepared = True
        abigale.cast_prepared_spell(game)
        assert abigale.prepared is False
