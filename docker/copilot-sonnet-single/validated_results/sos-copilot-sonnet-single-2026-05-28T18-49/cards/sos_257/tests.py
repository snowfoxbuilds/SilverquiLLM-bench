"""Tests for Great Hall of the Biblioplex (sos_257)."""

from __future__ import annotations

import pytest
from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.card import Land
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


class TestGreatHallProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert card.name == "Great Hall of the Biblioplex"

    def test_is_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types

    def test_not_a_creature_initially(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert not card._is_creature
        assert CardType.CREATURE not in card.card_types


class TestGreatHallManaAbilities:
    """Mana abilities."""

    def test_has_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 2

    def test_tap_produces_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])

        mana_ability = hall.get_mana_abilities()[0]
        # Verify it's not tapped
        hall.is_tapped = False
        # Pay cost (tap)
        result = mana_ability.cost(game)
        assert result is True
        assert hall.is_tapped is True
        # Get mana produced
        mana = mana_ability.mana_produced(game)
        assert mana.get(ManaType.COLORLESS, 0) == 1 or ManaType.COLORLESS in mana

    def test_tap_pay_life_produces_colored_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall])
        set_board_state(game, 0, life=20)

        mana_ability = hall.get_mana_abilities()[1]
        hall.is_tapped = False

        # Script: choose blue mana
        p1._script.append(ManaType.BLUE)

        life_before = p1.life
        result = mana_ability.cost(game)
        assert result is True
        assert hall.is_tapped is True
        assert p1.life == life_before - 1  # paid 1 life

        mana = mana_ability.mana_produced(game)
        # Should produce one colored mana
        total = sum(mana.values()) if isinstance(mana, dict) else 0
        assert total >= 1

    def test_cannot_tap_already_tapped_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        hall.is_tapped = True

        mana_ability = hall.get_mana_abilities()[0]
        result = mana_ability.cost(game)
        assert result is False

    def test_cannot_use_life_ability_with_too_little_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        hall.is_tapped = False
        p1.life = 1  # Cannot pay 1 life

        mana_ability = hall.get_mana_abilities()[1]
        result = mana_ability.cost(game)
        assert result is False


class TestGreatHallActivatedAbility:
    """{5}: Animate the land as a 2/4 Wizard creature."""

    def test_has_one_activated_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)
        assert len(card.get_activated_abilities()) == 1

    def test_animation_costs_five_generic(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})

        ability = hall.get_activated_abilities()[0]
        result = ability.cost(game)
        assert result is True

    def test_animation_fails_without_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={})

        ability = hall.get_activated_abilities()[0]
        result = ability.cost(game)
        assert result is False

    def test_animation_makes_it_a_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})

        ability = hall.get_activated_abilities()[0]
        ability.cost(game)
        ability.effect(game)

        assert hall._is_creature is True
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes

    def test_animated_land_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})

        ability = hall.get_activated_abilities()[0]
        ability.cost(game)
        ability.effect(game)

        assert CardType.LAND in hall.card_types

    def test_animated_stats(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})

        ability = hall.get_activated_abilities()[0]
        ability.cost(game)
        ability.effect(game)

        assert hall.power == 2
        assert hall.toughness == 4

    def test_cannot_animate_twice(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 10})

        ability = hall.get_activated_abilities()[0]
        ability.cost(game)
        ability.effect(game)

        # Try to animate again — cost should fail (already a creature)
        result = ability.cost(game)
        assert result is False


class TestGreatHallPowerBump:
    """When animated, gets +1/+0 when controller casts instant/sorcery."""

    def test_power_bumps_on_spell_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})

        ability = hall.get_activated_abilities()[0]
        ability.cost(game)
        ability.effect(game)

        # Fire the spell cast trigger
        from engine.events import SpellCastTriggeredEvent
        from engine.card import Instant
        spell = Instant(name="Shock", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=spell, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        # Stack should have the bump trigger; resolve it
        if not game.stack.is_empty():
            from engine.casting import resolve_top
            resolve_top(game)

        assert hall.power >= 3  # base 2 + at least 1 bump
