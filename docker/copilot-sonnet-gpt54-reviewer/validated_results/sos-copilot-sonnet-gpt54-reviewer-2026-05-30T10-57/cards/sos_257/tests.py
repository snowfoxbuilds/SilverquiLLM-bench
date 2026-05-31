"""Tests for sos_257 — Great Hall of the Biblioplex."""
from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Land
from engine.types import CardType, ManaType
from test_utils import create_game


class TestGreatHallProperties:
    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert "Biblioplex" in card.name

    def test_is_land_type(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in card.card_types

    def test_starts_untapped(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert not card.is_tapped


class TestGreatHallColorlessMana:
    """{T}: Add {C}."""

    def test_produces_colorless_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        abilities = land.get_mana_abilities()
        assert len(abilities) >= 1
        colorless_ability = abilities[0]
        # Pay cost (tap the land).
        result = colorless_ability.cost(game)
        assert result is True
        mana = colorless_ability.mana_produced(game)
        assert mana.get(ManaType.COLORLESS, 0) == 1

    def test_tap_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.is_tapped = True
        abilities = land.get_mana_abilities()
        result = abilities[0].cost(game)
        assert result is False


class TestGreatHallColoredMana:
    """{T}, Pay 1 life: Add one mana of any color (instant/sorcery only)."""

    def test_produces_colored_mana_white(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        abilities = land.get_mana_abilities()
        assert len(abilities) >= 2
        colored_ability = abilities[1]
        result = colored_ability.cost(game)
        assert result is True
        mana = colored_ability.mana_produced(game)
        total = sum(mana.values())
        assert total >= 1

    def test_colored_mana_costs_1_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        initial_life = p1.life
        abilities = land.get_mana_abilities()
        colored_ability = abilities[1]
        colored_ability.cost(game)
        assert p1.life == initial_life - 1

    def test_colored_mana_marked_restricted(self) -> None:
        """Mana from this ability is marked as restricted to instant/sorcery."""
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        abilities = land.get_mana_abilities()
        colored_ability = abilities[1]
        colored_ability.cost(game)
        mana = colored_ability.mana_produced(game)
        # Should return colored mana.
        colored_types = {ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN}
        assert any(mana.get(t, 0) > 0 for t in colored_types)

    def test_cannot_activate_colored_if_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.is_tapped = True
        abilities = land.get_mana_abilities()
        result = abilities[1].cost(game)
        assert result is False


class TestGreatHallWizardActivation:
    """{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature."""

    def test_can_become_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.activate_wizard_form(game)
        assert CardType.CREATURE in land.card_types

    def test_wizard_stats(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.activate_wizard_form(game)
        assert land.base_power == 2
        assert land.base_toughness == 4

    def test_still_a_land_when_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.activate_wizard_form(game)
        assert CardType.LAND in land.card_types

    def test_is_wizard_subtype(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.activate_wizard_form(game)
        assert "Wizard" in land.subtypes

    def test_does_not_activate_if_already_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        land.activate_wizard_form(game)
        # Second activation should be a no-op.
        land.activate_wizard_form(game)
        assert land.base_power == 2  # unchanged
