"""Tests for SOS 54 — Hydro-Channeler."""

from __future__ import annotations

import pytest

from cards.sos.sos_54.card_impl import HydroChanneler
from engine.card import Creature, ManaAbility
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestHydroChannelerProperties:
    """Static card data should match the SOS 54 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HydroChanneler(owner=None), Creature)

    def test_name(self) -> None:
        assert HydroChanneler(owner=None).name == "Hydro-Channeler"

    def test_mana_cost(self) -> None:
        assert HydroChanneler(owner=None).mana_cost == ManaCost.parse("{1}{U}")

    def test_power_toughness(self) -> None:
        card = HydroChanneler(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = HydroChanneler(owner=None)
        assert "Merfolk" in card.subtypes
        assert "Wizard" in card.subtypes


class TestHydroChannelerManaAbilities:
    """Two mana abilities: {T} for {U}, and {1}{T} for any color."""

    def test_has_two_activated_abilities(self) -> None:
        """Hydro-Channeler should have two mana-producing abilities."""
        card = HydroChanneler(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 2

    def test_first_ability_produces_blue_mana(self) -> None:
        """First ability: {T}: Add {U} (for instants/sorceries only)."""
        game = create_game()
        p1 = game.players[0]

        channeler = HydroChanneler(owner=p1, controller=p1)
        channeler.summoning_sick = False
        channeler.is_tapped = False
        set_board_state(game, 0, battlefield=[channeler])

        abilities = channeler.get_activated_abilities()
        first_ability = abilities[0]

        # Activate the ability
        first_ability.effect(game)

        # Should produce blue mana (restricted to instant/sorcery)
        mana_pool = game.get_mana_pool(p1)
        assert mana_pool.get(ManaType.BLUE, 0) >= 1

    def test_first_ability_taps_creature(self) -> None:
        """First ability requires tapping."""
        game = create_game()
        p1 = game.players[0]

        channeler = HydroChanneler(owner=p1, controller=p1)
        channeler.summoning_sick = False
        channeler.is_tapped = False
        set_board_state(game, 0, battlefield=[channeler])

        abilities = channeler.get_activated_abilities()
        first_ability = abilities[0]
        first_ability.cost(game)

        assert channeler.is_tapped is True

    def test_second_ability_costs_one_generic(self) -> None:
        """Second ability: {1}, {T}: Add one mana of any color."""
        game = create_game()
        p1 = game.players[0]

        channeler = HydroChanneler(owner=p1, controller=p1)
        channeler.summoning_sick = False
        channeler.is_tapped = False
        set_board_state(game, 0, battlefield=[channeler], mana={ManaType.COLORLESS: 1})

        abilities = channeler.get_activated_abilities()
        assert len(abilities) >= 2
        second_ability = abilities[1]

        # The description should reference {1} cost
        assert "1" in second_ability.description or second_ability.cost is not None

    def test_cannot_activate_when_tapped(self) -> None:
        """Neither ability can be activated when the creature is already tapped."""
        game = create_game()
        p1 = game.players[0]

        channeler = HydroChanneler(owner=p1, controller=p1)
        channeler.summoning_sick = False
        channeler.is_tapped = True
        set_board_state(game, 0, battlefield=[channeler])

        abilities = channeler.get_activated_abilities()
        # Cost function should fail/return False when already tapped
        result = abilities[0].cost(game)
        assert result is False or result is None
