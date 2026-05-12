"""Comprehensive tests for Plains (SOS #267).

Verifies basic land properties, mana ability behavior, and edge cases.
"""

from __future__ import annotations

import pytest

from card_impl import Plains

from engine.card import Land
from engine.types import CardType, ManaType, Supertype

from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestPlainsBasicProperties:
    """Plains basic property tests."""

    def test_is_land_subclass(self) -> None:
        """Plains must be a Land subclass."""
        card = Plains(name="Plains", owner=None)
        assert isinstance(card, Land)

    def test_has_basic_supertype(self) -> None:
        """Plains must have the BASIC supertype."""
        card = Plains(name="Plains", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_plains_subtype(self) -> None:
        """Plains must have the 'Plains' land subtype."""
        card = Plains(name="Plains", owner=None)
        assert "Plains" in card.subtypes

    def test_name(self) -> None:
        """Plains.name must be 'Plains'."""
        card = Plains(name="Plains", owner=None)
        assert card.name == "Plains"

    def test_enters_untapped(self) -> None:
        """Plains enters the battlefield untapped."""
        card = Plains(name="Plains", owner=None)
        assert not card.is_tapped

    def test_has_land_card_type(self) -> None:
        """Plains must have LAND in its card_types."""
        card = Plains(name="Plains", owner=None)
        assert CardType.LAND in card.card_types

    def test_no_power_or_toughness(self) -> None:
        """Plains is a land and should not have power/toughness attributes."""
        card = Plains(name="Plains", owner=None)
        assert not hasattr(card, "base_power")
        assert not hasattr(card, "base_toughness")

    def test_no_mana_cost(self) -> None:
        """Plains has no mana cost (cmc == 0)."""
        card = Plains(name="Plains", owner=None)
        assert card.mana_cost.cmc == 0

    def test_cannot_be_cast(self) -> None:
        """Plains cannot be cast as a spell."""
        game = create_game()
        card = Plains(name="Plains", owner=game.players[0])
        assert card.can_cast(game) is False


@pytest.mark.mana_ability
class TestPlainsManaAbility:
    """Plains mana ability tests."""

    def test_has_mana_abilities(self) -> None:
        """Plains must provide at least one mana ability."""
        card = Plains(name="Plains", owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_mana_ability_description(self) -> None:
        """Plains' mana ability description should reference tapping and white mana."""
        card = Plains(name="Plains", owner=None)
        abilities = card.get_mana_abilities()
        descriptions = [a.description for a in abilities]
        assert any("{T}" in d and "{W}" in d for d in descriptions)

    def test_tap_produces_white_mana(self) -> None:
        """Tapping Plains adds {W} to controller's mana pool."""
        game = create_game()
        plains = Plains(name="Plains", owner=game.players[0])
        set_board_state(game, 0, battlefield=[plains])

        assert game.players[0].mana_pool.get(ManaType.WHITE) == 0

        abilities = plains.get_mana_abilities()
        ability = abilities[0]
        cost_result = ability.cost(game, plains)
        assert cost_result is True

        ability.mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 1

    def test_tap_cost_taps_the_land(self) -> None:
        """Paying the mana ability cost sets is_tapped to True."""
        game = create_game()
        plains = Plains(name="Plains", owner=game.players[0])
        set_board_state(game, 0, battlefield=[plains])

        assert plains.is_tapped is False

        abilities = plains.get_mana_abilities()
        ability = abilities[0]
        cost_result = ability.cost(game, plains)

        assert cost_result is True
        assert plains.is_tapped is True

    def test_cannot_produce_mana_if_tapped(self) -> None:
        """Plains that is already tapped cannot activate its mana ability."""
        game = create_game()
        plains = Plains(name="Plains", owner=game.players[0])
        plains.is_tapped = True
        set_board_state(game, 0, battlefield=[plains])

        abilities = plains.get_mana_abilities()
        ability = abilities[0]
        cost_result = ability.cost(game, plains)

        assert cost_result is False
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 0

    def test_produces_exactly_one_white_mana(self) -> None:
        """Plains produces exactly 1 white mana, no other mana types."""
        game = create_game()
        plains = Plains(name="Plains", owner=game.players[0])
        set_board_state(game, 0, battlefield=[plains])

        abilities = plains.get_mana_abilities()
        ability = abilities[0]
        ability.cost(game, plains)
        ability.mana_produced(game)

        assert game.players[0].mana_pool.get(ManaType.WHITE) == 1
        assert game.players[0].mana_pool.get(ManaType.BLUE) == 0
        assert game.players[0].mana_pool.get(ManaType.BLACK) == 0
        assert game.players[0].mana_pool.get(ManaType.RED) == 0
        assert game.players[0].mana_pool.get(ManaType.GREEN) == 0
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) == 0

    def test_accumulates_mana_over_multiple_plains(self) -> None:
        """Multiple Plains on battlefield each produce {W} independently."""
        game = create_game()
        plains1 = Plains(name="Plains", owner=game.players[0])
        plains2 = Plains(name="Plains", owner=game.players[0])
        plains3 = Plains(name="Plains", owner=game.players[0])
        set_board_state(game, 0, battlefield=[plains1, plains2, plains3])

        for plains in (plains1, plains2, plains3):
            ability = plains.get_mana_abilities()[0]
            ability.cost(game, plains)
            ability.mana_produced(game)

        assert game.players[0].mana_pool.get(ManaType.WHITE) == 3
        assert all(p.is_tapped for p in (plains1, plains2, plains3))

    def test_controller_receives_mana(self) -> None:
        """The controller of Plains receives the mana, not the owner (if different)."""
        game = create_game()
        plains = Plains(name="Plains", owner=game.players[1], controller=game.players[0])
        set_board_state(game, 0, battlefield=[plains])

        abilities = plains.get_mana_abilities()
        ability = abilities[0]
        ability.cost(game, plains)
        ability.mana_produced(game)

        assert game.players[0].mana_pool.get(ManaType.WHITE) == 1


@pytest.mark.edge_cases
class TestPlainsEdgeCases:
    """Plains edge case tests."""

    def test_no_effect_if_no_controller(self) -> None:
        """If Plains has no controller, mana ability produces no mana."""
        game = create_game()
        plains = Plains(name="Plains", owner=None, controller=None)

        abilities = plains.get_mana_abilities()
        ability = abilities[0]
        ability.cost(game, plains)
        ability.mana_produced(game)

        assert game.players[0].mana_pool.get(ManaType.WHITE) == 0
        assert game.players[1].mana_pool.get(ManaType.WHITE) == 0

    def test_rules_text_present(self) -> None:
        """Plains rules text contains tap-for-white-mana instruction."""
        card = Plains(name="Plains", owner=None)
        assert "{T}" in card.rules_text
        assert "{W}" in card.rules_text

    def test_unique_object_id(self) -> None:
        """Each Plains instance gets a unique object_id."""
        plains1 = Plains(name="Plains", owner=None)
        plains2 = Plains(name="Plains", owner=None)
        assert plains1.object_id != plains2.object_id

    def test_multiple_activations_same_turn_after_untap(self) -> None:
        """A Plains that is untapped can activate again."""
        game = create_game()
        plains = Plains(name="Plains", owner=game.players[0])
        set_board_state(game, 0, battlefield=[plains])

        # First tap
        ability = plains.get_mana_abilities()[0]
        ability.cost(game, plains)
        ability.mana_produced(game)
        assert plains.is_tapped is True
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 1

        # Untap
        plains.is_tapped = False

        # Second tap
        ability.cost(game, plains)
        ability.mana_produced(game)
        assert plains.is_tapped is True
        assert game.players[0].mana_pool.get(ManaType.WHITE) == 2
