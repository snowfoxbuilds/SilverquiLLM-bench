"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.casting import CastingError, cast_spell
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


_COLORS = (
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
)


def _get_activated_abilities(card, game):
    try:
        return card.get_activated_abilities(game)
    except TypeError:
        return card.get_activated_abilities()


def _activate_mana_ability(game, controller, source, ability) -> None:
    activate_ability(
        game,
        controller,
        ActivatedAbilityInstance(
            source=source,
            controller=controller,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
            description=ability.description,
        ),
    )


def _activate_regular_ability(game, controller, source, ability) -> None:
    activate_ability(
        game,
        controller,
        ActivatedAbilityInstance(
            source=source,
            controller=controller,
            cost=ability.cost,
            effect=ability.effect,
            description=ability.description,
        ),
    )
    stack_obj = game.stack.pop()
    stack_obj.on_resolve(game)


def _resolve_all_stack(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_a_land_named_great_hall_of_the_biblioplex(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in card.card_types


class TestGreatHallOfTheBiblioplexManaAbilities:
    """Great Hall should provide its two printed mana abilities."""

    def test_has_a_tap_ability_that_adds_one_colorless(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[hall])

        colorless_ability = None
        for ability in hall.get_mana_abilities():
            controller.mana_pool.empty()
            controller.life = 20
            hall.is_tapped = False
            _activate_mana_ability(game, controller, hall, ability)
            if controller.mana_pool.get(ManaType.COLORLESS) == 1:
                colorless_ability = ability
                break
            controller.mana_pool.empty()
            hall.is_tapped = False

        assert colorless_ability is not None
        assert controller.mana_pool.get(ManaType.COLORLESS) == 1
        assert controller.mana_pool.total() == 1
        assert controller.life == 20
        assert hall.is_tapped is True

    def test_pay_life_mana_ability_can_produce_each_color(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[hall])

        life_abilities = [
            ability
            for ability in hall.get_mana_abilities()
            if "life" in ability.description.lower()
        ]

        assert life_abilities

        produced_colors = set()
        if len(life_abilities) == 1:
            ability = life_abilities[0]
            for color in _COLORS:
                controller.mana_pool.empty()
                controller.life = 20
                hall.is_tapped = False
                controller.choose = lambda options, prompt, chosen=color: chosen
                _activate_mana_ability(game, controller, hall, ability)

                assert controller.life == 19
                assert controller.mana_pool.get(color) == 1
                assert sum(controller.mana_pool.get(mana_type) for mana_type in _COLORS) == 1
                assert hall.is_tapped is True
                produced_colors.add(color)
        else:
            for ability in life_abilities:
                controller.mana_pool.empty()
                controller.life = 20
                hall.is_tapped = False
                controller.choose = lambda options, prompt: ManaType.BLUE
                _activate_mana_ability(game, controller, hall, ability)

                colors_added = {
                    mana_type for mana_type in _COLORS if controller.mana_pool.get(mana_type) == 1
                }
                assert controller.life == 19
                assert len(colors_added) == 1
                assert controller.mana_pool.total() == 1
                assert hall.is_tapped is True
                produced_colors.update(colors_added)

        assert produced_colors == set(_COLORS)


    def test_pay_life_mana_ability_adds_restricted_mana_for_instant_or_sorcery_casts(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[hall])

        ability = next(
            ability
            for ability in hall.get_mana_abilities()
            if "Spend this mana only to cast an instant or sorcery spell" in ability.description
        )
        controller.choose = lambda options, prompt: ManaType.BLUE

        _activate_mana_ability(game, controller, hall, ability)

        restricted_mana = controller.mana_pool.get_restricted_mana()
        assert len(restricted_mana) == 1
        assert restricted_mana[0].mana_type == ManaType.BLUE
        assert restricted_mana[0].restriction.description == (
            "Spend this mana only to cast an instant or sorcery spell."
        )
        assert restricted_mana[0].restriction.source is hall

    def test_restricted_mana_can_be_spent_to_cast_an_instant(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        spell = Instant(
            name="Pop Quiz",
            owner=controller,
            controller=controller,
            mana_cost=ManaCost.parse("{U}"),
        )
        set_board_state(game, 0, battlefield=[hall], hand=[spell])

        ability = next(
            ability
            for ability in hall.get_mana_abilities()
            if "Spend this mana only to cast an instant or sorcery spell" in ability.description
        )
        controller.choose = lambda options, prompt: ManaType.BLUE
        _activate_mana_ability(game, controller, hall, ability)

        cast_spell(game, controller, spell)

        assert controller.mana_pool.total() == 0
        assert game.get_hand(controller).contains(spell) is False
        assert game.stack.is_empty() is False

    def test_restricted_mana_cannot_be_spent_to_cast_a_creature_spell(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        spell = Creature(
            name="Campus Wizard",
            owner=controller,
            controller=controller,
            mana_cost=ManaCost.parse("{U}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[hall], hand=[spell])

        ability = next(
            ability
            for ability in hall.get_mana_abilities()
            if "Spend this mana only to cast an instant or sorcery spell" in ability.description
        )
        controller.choose = lambda options, prompt: ManaType.BLUE
        _activate_mana_ability(game, controller, hall, ability)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell(game, controller, spell)

        restricted_mana = controller.mana_pool.get_restricted_mana()
        assert len(restricted_mana) == 1
        assert restricted_mana[0].mana_type == ManaType.BLUE
        assert game.get_hand(controller).contains(spell) is True


class TestGreatHallOfTheBiblioplexAnimation:
    """The five-mana ability should animate the land into the printed creature."""

    def test_animation_ability_makes_it_a_two_four_wizard_creature_thats_still_a_land(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})

        ability = _get_activated_abilities(hall, game)[0]
        _activate_regular_ability(game, controller, hall, ability)
        game.effect_manager.apply_all(game)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4


class TestGreatHallOfTheBiblioplexSpellCastTrigger:
    """The granted trigger should only work after animation and only for your instants/sorceries."""

    def test_does_not_trigger_before_it_becomes_a_creature(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        spell = Instant(name="Pop Quiz", owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[hall])
        hall.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell, player=controller, card=spell, controller=controller),
        )

        assert game.stack.is_empty()

    def test_triggers_when_you_cast_an_instant_or_sorcery_after_animation(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        spell = Sorcery(name="Teach by Example", owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.register_triggers(game)

        ability = _get_activated_abilities(hall, game)[0]
        _activate_regular_ability(game, controller, hall, ability)
        game.effect_manager.apply_all(game)
        assert hall.power == 2

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell, player=controller, card=spell, controller=controller),
        )
        _resolve_all_stack(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4

    def test_does_not_trigger_for_your_creature_spell(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        spell = Creature(
            name="Campus Wizard",
            owner=controller,
            controller=controller,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.register_triggers(game)

        ability = _get_activated_abilities(hall, game)[0]
        _activate_regular_ability(game, controller, hall, ability)
        game.effect_manager.apply_all(game)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell, player=controller, card=spell, controller=controller),
        )
        game.effect_manager.apply_all(game)

        assert game.stack.is_empty()
        assert hall.power == 2

    def test_does_not_trigger_for_an_opponents_instant_or_sorcery(self) -> None:
        game = create_game()
        controller = game.players[0]
        opponent = game.players[1]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        spell = Instant(name="Frantic Lesson", owner=opponent, controller=opponent)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        hall.register_triggers(game)

        ability = _get_activated_abilities(hall, game)[0]
        _activate_regular_ability(game, controller, hall, ability)
        game.effect_manager.apply_all(game)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell, player=opponent, card=spell, controller=opponent),
        )
        game.effect_manager.apply_all(game)

        assert game.stack.is_empty()
        assert hall.power == 2

    def test_reanimating_an_already_creature_hall_does_not_double_the_spell_trigger(self) -> None:
        game = create_game()
        controller = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=controller, controller=controller)
        spell = Instant(name="Arcane Insight", owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 10})
        hall.register_triggers(game)

        ability = _get_activated_abilities(hall, game)[0]
        _activate_regular_ability(game, controller, hall, ability)
        _activate_regular_ability(game, controller, hall, ability)
        game.effect_manager.apply_all(game)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell, player=controller, card=spell, controller=controller),
        )
        _resolve_all_stack(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4
