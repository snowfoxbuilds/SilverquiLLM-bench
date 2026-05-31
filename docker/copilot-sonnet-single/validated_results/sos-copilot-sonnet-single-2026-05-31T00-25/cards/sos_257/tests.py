"""Tests for sos_257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestGreatHallOfTheBiblioplexProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types

    def test_not_creature_initially(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.CREATURE not in card.card_types
        assert card._is_creature is False


class TestGreatHallManaAbilities:
    """Mana abilities: {T} for {C} and {T}+life for colored mana."""

    def test_has_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2

    def test_mana_abilities_are_mana_ability_instances(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        for ab in card.get_mana_abilities():
            assert isinstance(ab, ManaAbility)

    def test_tap_for_colorless(self) -> None:
        """First ability: {T} adds {C} to the mana pool."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        abilities = card.get_mana_abilities()
        tap_ability = abilities[0]

        tap_ability.cost(game, card)
        tap_ability.mana_produced(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) >= 1

    def test_tap_colorless_taps_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False

        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        assert card.is_tapped is True

    def test_tap_colorless_fails_when_already_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True

        abilities = card.get_mana_abilities()
        result = abilities[0].cost(game, card)
        assert result is False

    def test_second_ability_pays_life(self) -> None:
        """Second ability: {T}, pay 1 life — adds colored mana."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        p1.life = 20

        abilities = card.get_mana_abilities()
        life_ability = abilities[1]

        life_ability.cost(game, card)
        life_ability.mana_produced(game)

        assert p1.life == 19
        assert p1.mana_pool.total() >= 1

    def test_second_ability_fails_when_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = True

        abilities = card.get_mana_abilities()
        result = abilities[1].cost(game, card)
        assert result is False

    def test_second_ability_fails_at_zero_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        card.is_tapped = False
        p1.life = 0

        abilities = card.get_mana_abilities()
        result = abilities[1].cost(game, card)
        assert result is False


class TestGreatHallActivatedAbility:
    """Activated ability: {5} animates the land as a 2/4 Wizard creature."""

    def test_has_one_activated_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1

    def test_activated_ability_is_instance(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        ab = card.get_activated_abilities()[0]
        assert isinstance(ab, ActivatedAbility)

    def test_animation_sets_creature_type(self) -> None:
        """After animation, card has CREATURE card type."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.mana_pool.add(ManaType.COLORLESS, 5)

        ab = card.get_activated_abilities()[0]
        ab.cost(game, card)
        ab.effect(game)

        assert CardType.CREATURE in card.card_types

    def test_animation_sets_power_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.mana_pool.add(ManaType.COLORLESS, 5)

        ab = card.get_activated_abilities()[0]
        ab.cost(game, card)
        ab.effect(game)

        assert card.base_power == 2
        assert card.base_toughness == 4

    def test_animation_adds_wizard_subtype(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.mana_pool.add(ManaType.COLORLESS, 5)

        ab = card.get_activated_abilities()[0]
        ab.cost(game, card)
        ab.effect(game)

        assert "Wizard" in card.subtypes

    def test_animation_preserves_land_type(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.mana_pool.add(ManaType.COLORLESS, 5)

        ab = card.get_activated_abilities()[0]
        ab.cost(game, card)
        ab.effect(game)

        assert CardType.LAND in card.card_types

    def test_animation_cannot_trigger_twice(self) -> None:
        """After becoming a creature, the ability cannot fire again (already a creature)."""
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.mana_pool.add(ManaType.COLORLESS, 10)

        ab = card.get_activated_abilities()[0]
        ab.cost(game, card)
        ab.effect(game)

        # Try to animate again — cost should fail (already a creature)
        result = ab.cost(game, card)
        assert result is False

    def test_animation_fails_without_enough_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)  # Only 2 mana, need 5

        ab = card.get_activated_abilities()[0]
        result = ab.cost(game, card)
        assert result is False
