"""Tests for SOS 168 — Wildgrowth Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_168.card_impl import WildgrowthArchaic
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestWildgrowthArchaicProperties:
    """Static card data should match the SOS 168 spec."""

    def test_name(self) -> None:
        card = WildgrowthArchaic(owner=None)
        assert card.name == "Wildgrowth Archaic"

    def test_is_creature(self) -> None:
        card = WildgrowthArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_mana_cost_hybrid(self) -> None:
        card = WildgrowthArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{2/G}{2/G}")

    def test_base_power_toughness(self) -> None:
        card = WildgrowthArchaic(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 0

    def test_has_trample(self) -> None:
        card = WildgrowthArchaic(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_has_reach(self) -> None:
        card = WildgrowthArchaic(owner=None)
        assert Keyword.REACH in card.keywords


class TestWildgrowthArchaicConverge:
    """Converge — enters with +1/+1 counters equal to colors of mana spent."""

    def test_enters_with_one_counter_one_color(self) -> None:
        """Cast with only green mana → 1 counter."""
        game = create_game()
        p1 = game.players[0]
        card = WildgrowthArchaic(owner=p1, controller=p1)
        card.colors_of_mana_spent = {"G"}
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        assert card.plus_one_counters == 1

    def test_enters_with_two_counters_two_colors(self) -> None:
        """Cast with green + white mana → 2 counters."""
        game = create_game()
        p1 = game.players[0]
        card = WildgrowthArchaic(owner=p1, controller=p1)
        card.colors_of_mana_spent = {"G", "W"}
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        assert card.plus_one_counters == 2

    def test_enters_with_five_counters_all_colors(self) -> None:
        """Cast with all 5 colors → 5 counters."""
        game = create_game()
        p1 = game.players[0]
        card = WildgrowthArchaic(owner=p1, controller=p1)
        card.colors_of_mana_spent = {"W", "U", "B", "R", "G"}
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        assert card.plus_one_counters == 5

    def test_no_color_no_counters(self) -> None:
        """Cast with only colorless mana → 0 counters (stays 0/0)."""
        game = create_game()
        p1 = game.players[0]
        card = WildgrowthArchaic(owner=p1, controller=p1)
        card.colors_of_mana_spent = set()
        game.get_battlefield(p1).add(card)
        card.on_enter_battlefield(game)
        assert card.plus_one_counters == 0


class TestWildgrowthArchaicTriggeredAbility:
    """Whenever you cast a creature spell, that creature enters with X additional counters."""

    def test_creature_spell_gets_additional_counters(self) -> None:
        """A creature cast while Wildgrowth Archaic is on field gets extra counters."""
        game = create_game()
        p1 = game.players[0]
        archaic = WildgrowthArchaic(owner=p1, controller=p1)
        archaic.plus_one_counters = 3  # already on battlefield
        game.get_battlefield(p1).add(archaic)

        bear = Creature(name="Test Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.colors_of_mana_spent = {"G", "R"}  # 2 colors
        # Trigger the ability
        archaic.on_creature_cast(game, bear)
        assert bear.additional_counters_on_enter == 2

    def test_creature_spell_all_colors(self) -> None:
        """5-color creature spell gets 5 additional counters."""
        game = create_game()
        p1 = game.players[0]
        archaic = WildgrowthArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(archaic)

        bear = Creature(name="Test Bear", owner=p1, controller=p1,
                        base_power=1, base_toughness=1)
        bear.colors_of_mana_spent = {"W", "U", "B", "R", "G"}
        archaic.on_creature_cast(game, bear)
        assert bear.additional_counters_on_enter == 5
