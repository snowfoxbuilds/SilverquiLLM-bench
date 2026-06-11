"""Tests for SOS 166 — Vastlands Scavenger // Bind to Life."""

from __future__ import annotations

import pytest

from cards.sos.sos_166.card_impl import VastlandsScavengerBindToLife
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestVastlandsScavengerProperties:
    """Static card data should match the SOS 166 spec."""

    def test_name(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)
        assert card.name == "Vastlands Scavenger"

    def test_is_creature(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)
        assert isinstance(card, Creature)

    def test_mana_cost(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{G}{G}")

    def test_power_and_toughness(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_deathtouch(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords


class TestVastlandsScavengerPrepared:
    """Vastlands Scavenger enters prepared."""

    def test_enters_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VastlandsScavengerBindToLife(owner=p1, controller=p1)
        set_board_state(game, 0, mana={ManaType.GREEN: 3, ManaType.COLORLESS: 1})
        # After entering battlefield, should be prepared
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        assert card.prepared is True

    def test_casting_spell_unprepares(self) -> None:
        """Casting the attached spell unprepares the creature."""
        game = create_game()
        p1 = game.players[0]
        card = VastlandsScavengerBindToLife(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.prepared = True
        # Casting the spell copy should unprepare it
        card.cast_prepared_spell(game)
        assert card.prepared is False


class TestBindToLifeSpell:
    """The Bind to Life spell side (the prepared spell)."""

    def test_spell_name(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)
        assert card.spell_name == "Bind to Life"

    def test_spell_mana_cost(self) -> None:
        card = VastlandsScavengerBindToLife(owner=None)
        assert card.spell_mana_cost == ManaCost.parse("{4}{G}")
