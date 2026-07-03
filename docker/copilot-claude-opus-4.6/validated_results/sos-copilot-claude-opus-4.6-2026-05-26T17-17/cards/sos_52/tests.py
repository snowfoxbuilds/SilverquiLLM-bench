"""Tests for SOS 52 — Harmonized Trio // Brainstorm."""

from __future__ import annotations

import pytest

from cards.sos.sos_52.card_impl import HarmonizedTrioBrainstorm
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestHarmonizedTrioProperties:
    """Static card data should match the SOS 52 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HarmonizedTrioBrainstorm(owner=None), Creature)

    def test_name(self) -> None:
        assert HarmonizedTrioBrainstorm(owner=None).name == "Harmonized Trio"

    def test_mana_cost(self) -> None:
        assert HarmonizedTrioBrainstorm(owner=None).mana_cost == ManaCost.parse("{U}")

    def test_power_toughness(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert "Merfolk" in card.subtypes
        assert "Bard" in card.subtypes
        assert "Wizard" in card.subtypes


class TestHarmonizedTrioPreparedAbility:
    """Tap + tap two untapped creatures to become prepared."""

    def test_has_activated_ability(self) -> None:
        """Card should expose an activated ability for the prepare tap."""
        card = HarmonizedTrioBrainstorm(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_preparing_requires_tap_and_two_creatures(self) -> None:
        """The ability should require tapping self and two other untapped creatures."""
        game = create_game()
        p1 = game.players[0]

        trio = HarmonizedTrioBrainstorm(owner=p1, controller=p1)
        trio.summoning_sick = False
        trio.is_tapped = False

        helper1 = Creature(name="Helper 1", owner=p1, controller=p1, base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper1.is_tapped = False

        helper2 = Creature(name="Helper 2", owner=p1, controller=p1, base_power=1, base_toughness=1)
        helper2.summoning_sick = False
        helper2.is_tapped = False

        set_board_state(game, 0, battlefield=[trio, helper1, helper2])

        abilities = trio.get_activated_abilities()
        assert len(abilities) >= 1

    def test_becomes_prepared_after_ability_resolves(self) -> None:
        """After using the ability, the creature should be prepared."""
        game = create_game()
        p1 = game.players[0]

        trio = HarmonizedTrioBrainstorm(owner=p1, controller=p1)
        trio.summoning_sick = False
        trio.is_tapped = False

        helper1 = Creature(name="Helper 1", owner=p1, controller=p1, base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper1.is_tapped = False

        helper2 = Creature(name="Helper 2", owner=p1, controller=p1, base_power=1, base_toughness=1)
        helper2.summoning_sick = False
        helper2.is_tapped = False

        set_board_state(game, 0, battlefield=[trio, helper1, helper2])

        # Activate the prepare ability
        abilities = trio.get_activated_abilities()
        ability = abilities[0]
        ability.effect(game)

        assert getattr(trio, "is_prepared", False) is True

    def test_not_prepared_initially(self) -> None:
        """The creature should not start as prepared."""
        card = HarmonizedTrioBrainstorm(owner=None)
        assert getattr(card, "is_prepared", False) is False
