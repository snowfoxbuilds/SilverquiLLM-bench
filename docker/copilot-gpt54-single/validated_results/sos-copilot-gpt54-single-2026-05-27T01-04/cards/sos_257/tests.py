"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.casting import CastingError, cast_spell
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


def _current_power(card) -> int | None:
    """Return the most specific readable power-like attribute on *card*."""
    for attr in ("power", "modified_power", "base_power"):
        value = getattr(card, attr, None)
        if value is not None:
            return value
    return None


def _current_toughness(card) -> int | None:
    """Return the most specific readable toughness-like attribute on *card*."""
    for attr in ("toughness", "modified_toughness", "base_toughness"):
        value = getattr(card, attr, None)
        if value is not None:
            return value
    return None


def _training_instant(player, name: str = "Training Instant") -> Instant:
    """Create a simple instant spell for spell-cast trigger checks."""
    return Instant(name=name, mana_cost=ManaCost.parse("{U}"), owner=player, controller=player)


def _training_sorcery(player, name: str = "Training Sorcery") -> Sorcery:
    """Create a simple sorcery spell for spell-cast trigger checks."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{1}{R}"), owner=player, controller=player)


def _training_creature_spell(player, name: str = "Training Creature") -> Creature:
    """Create a simple creature spell for non-trigger checks."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        owner=player,
        controller=player,
        base_power=2,
        base_toughness=2,
    )


def _training_blue_creature_spell(player, name: str = "Training Blue Creature") -> Creature:
    """Create a creature spell whose cost matches Hall's restricted blue mana."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{U}"),
        owner=player,
        controller=player,
        base_power=1,
        base_toughness=1,
    )


def _animate_hall(game, hall: GreatHallOfTheBiblioplex) -> None:
    """Activate Great Hall's {5} ability and apply resulting effects."""
    ability = hall.get_activated_abilities()[0]
    assert ability.cost(game, hall) is True
    ability.effect(game)
    game.effect_manager.apply_all(game)


def _fire_spell_cast(game, spell, player) -> None:
    """Fire a spell-cast event for *spell* cast by *player*."""
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(
            spell=spell,
            player=player,
            card=spell,
            controller=player,
        ),
    )


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_a_land_named_great_hall_of_the_biblioplex(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types

    def test_has_no_mana_cost_and_expected_rules_text(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert card.mana_cost == ManaCost()
        assert card.rules_text == (
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard creature with '
            '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn." '
            "It's still a land."
        )


class TestGreatHallOfTheBiblioplexManaAbilities:
    """Great Hall should provide its two printed mana abilities."""

    def test_has_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert len(card.get_mana_abilities()) == 2

    def test_first_mana_ability_taps_and_adds_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])
        ability = hall.get_mana_abilities()[0]

        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_second_mana_ability_costs_one_life_taps_adds_the_chosen_color_and_tags_it_as_restricted(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.choose = lambda options, _description="": ManaType.BLUE  # type: ignore[method-assign]

        set_board_state(game, 0, battlefield=[hall], life=20)
        ability = hall.get_mana_abilities()[1]

        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.has_restricted_mana() is True
        assert len(p1.mana_pool.restricted_entries) == 1
        restricted = p1.mana_pool.restricted_entries[0]
        assert restricted.mana_type is ManaType.BLUE
        assert restricted.restriction is not None
        assert restricted.restriction.description == (
            "Spend this mana only to cast an instant or sorcery spell."
        )
        assert restricted.restriction.metadata["usage"] == "cast"
        assert set(restricted.restriction.metadata["allowed_card_types"]) == {
            "instant",
            "sorcery",
        }

    def test_second_mana_ability_cannot_be_activated_while_the_land_is_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        hall.is_tapped = True

        set_board_state(game, 0, battlefield=[hall], life=20)
        ability = hall.get_mana_abilities()[1]

        assert ability.cost(game, hall) is False
        assert p1.life == 20
        assert p1.mana_pool.total() == 0

    def test_restricted_mana_can_be_spent_to_cast_an_instant_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        instant = _training_instant(p1, "Hall Lesson")
        p1.choose = lambda options, _description="": ManaType.BLUE  # type: ignore[method-assign]

        set_board_state(game, 0, battlefield=[hall], hand=[instant], life=20)
        ability = hall.get_mana_abilities()[1]

        assert ability.cost(game, hall) is True
        ability.mana_produced(game)
        assert p1.mana_pool.has_restricted_mana() is True

        cast_spell(game, p1, instant)

        assert p1.mana_pool.total() == 0
        assert game.stack.peek() is not None
        assert game.stack.peek().source is instant

        game.stack.pop().on_resolve(game)

        assert not game.get_hand(p1).contains(instant)
        assert game.get_graveyard(p1).contains(instant)

    def test_restricted_mana_cannot_be_spent_to_cast_a_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature = _training_blue_creature_spell(p1)
        p1.choose = lambda options, _description="": ManaType.BLUE  # type: ignore[method-assign]

        set_board_state(game, 0, battlefield=[hall], hand=[creature], life=20)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        ability = hall.get_mana_abilities()[1]
        assert ability.cost(game, hall) is True
        ability.mana_produced(game)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell(game, p1, creature)

        assert game.get_hand(p1).contains(creature)
        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.has_restricted_mana() is True

    def test_restricted_mana_cannot_pay_for_the_noncasting_animation_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.choose = lambda options, _description="": ManaType.BLUE  # type: ignore[method-assign]

        set_board_state(
            game,
            0,
            battlefield=[hall],
            life=20,
            mana={ManaType.COLORLESS: 4},
        )

        mana_ability = hall.get_mana_abilities()[1]
        assert mana_ability.cost(game, hall) is True
        mana_ability.mana_produced(game)

        animation = hall.get_activated_abilities()[0]

        assert animation.cost(game, hall) is False
        assert CardType.CREATURE not in hall.card_types
        assert p1.mana_pool.total() == 5
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4
        assert p1.mana_pool.get(ManaType.BLUE) == 1


class TestGreatHallOfTheBiblioplexAnimation:
    """The {5} ability should animate the land into a Wizard creature permanently."""

    def test_has_one_five_mana_animation_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert len(card.get_activated_abilities()) == 1

    def test_animation_makes_it_a_two_four_wizard_creature_thats_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        assert p1.mana_pool.total() == 0

        ability.effect(game)
        game.effect_manager.apply_all(game)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert _current_power(hall) == 2
        assert _current_toughness(hall) == 4

    def test_animation_survives_end_of_turn_cleanup_of_temporary_effects(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _animate_hall(game, hall)
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert _current_power(hall) == 2
        assert _current_toughness(hall) == 4

    def test_animating_an_existing_creature_hall_does_not_add_duplicate_spell_cast_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 10},
        )
        hall.register_triggers(game)

        _animate_hall(game, hall)
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = hall.get_activated_abilities()[0]
        assert ability.cost(game, hall) is True
        ability.effect(game)
        game.effect_manager.apply_all(game)

        _fire_spell_cast(game, _training_instant(p1), p1)

        assert len(game.stack) == 1
        assert game.stack.peek() is not None
        assert game.stack.peek().source is hall


class TestGreatHallOfTheBiblioplexSpellCastTrigger:
    """The animated land should pump itself when you cast instants and sorceries."""

    def test_animated_hall_gets_plus_two_power_from_casting_an_instant_and_a_sorcery_same_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        hall.register_triggers(game)
        _animate_hall(game, hall)

        assert _current_power(hall) == 2

        _fire_spell_cast(game, _training_instant(p1), p1)
        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)
        game.effect_manager.apply_all(game)
        assert _current_power(hall) == 3

        _fire_spell_cast(game, _training_sorcery(p1), p1)
        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)
        game.effect_manager.apply_all(game)
        assert _current_power(hall) == 4

    def test_spell_cast_bonus_expires_during_end_of_turn_cleanup_but_animation_remains(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        hall.register_triggers(game)
        _animate_hall(game, hall)

        _fire_spell_cast(game, _training_instant(p1), p1)
        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)
        game.effect_manager.apply_all(game)

        assert _current_power(hall) == 3

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert _current_power(hall) == 2
        assert _current_toughness(hall) == 4

    def test_animated_hall_does_not_trigger_from_your_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        hall.register_triggers(game)
        _animate_hall(game, hall)

        _fire_spell_cast(game, _training_creature_spell(p1), p1)

        assert game.stack.is_empty()

    def test_animated_hall_does_not_trigger_from_opponents_instant_or_sorcery_spells(self) -> None:
        game = create_game()
        p1, p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        hall.register_triggers(game)
        _animate_hall(game, hall)

        _fire_spell_cast(game, _training_instant(p2, "Opposing Instant"), p2)
        _fire_spell_cast(game, _training_sorcery(p2, "Opposing Sorcery"), p2)

        assert game.stack.is_empty()
