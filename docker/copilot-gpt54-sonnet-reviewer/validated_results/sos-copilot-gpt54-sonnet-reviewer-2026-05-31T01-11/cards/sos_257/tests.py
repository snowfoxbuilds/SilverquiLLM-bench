"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.casting import cast_spell as engine_cast_spell, play_land
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)


def _activate_mana_ability(game, player, source, ability_index: int) -> None:
    ability = source.get_mana_abilities()[ability_index]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
            description=ability.description,
        ),
    )


def _activate_regular_ability(game, player, source, ability_index: int = 0) -> None:
    ability = source.get_activated_abilities()[ability_index]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=ability.cost,
            effect=ability.effect,
            is_mana_ability=False,
            description=ability.description,
        ),
    )


def _play_hall(game, hall: GreatHallOfTheBiblioplex, *, hand=None, mana=None) -> None:
    player = game.players[0]
    cards_in_hand = [hall] + list(hand or [])
    set_board_state(game, 0, hand=cards_in_hand, mana={} if mana is None else mana)
    play_land(game, player, hall)


def _apply_effects(game) -> None:
    game.effect_manager.apply_all(game)


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data should match the SOS 257 spec."""

    def test_is_a_land_named_great_hall_of_the_biblioplex_with_no_mana_cost(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert card.mana_cost == ManaCost()
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types


class TestGreatHallOfTheBiblioplexManaAbilities:
    """Great Hall should provide its two mana abilities."""

    def test_first_mana_ability_taps_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        _play_hall(game, hall)
        _activate_mana_ability(game, p1, hall, 0)

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_second_mana_ability_costs_one_life_and_adds_chosen_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        _play_hall(game, hall)
        p1.choose = lambda _options, _description: ManaType.BLUE

        _activate_mana_ability(game, p1, hall, 1)

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1


class TestGreatHallOfTheBiblioplexAnimation:
    """The activated animation ability should permanently turn the land into a Wizard creature."""

    def test_animation_makes_it_a_two_four_wizard_creature_that_is_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        _play_hall(game, hall, mana={ManaType.COLORLESS: 5})
        _activate_regular_ability(game, p1, hall)
        _resolve_all(game)
        _apply_effects(game)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.modified_power == 2
        assert hall.modified_toughness == 4


class TestGreatHallOfTheBiblioplexSpellTrigger:
    """Once animated, Great Hall should care only about instant and sorcery spells you cast."""

    def test_casting_an_instant_gives_it_plus_one_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(
            name="Lecture Notes",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{U}"),
        )

        _play_hall(game, hall, hand=[spell], mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1})
        _activate_regular_ability(game, p1, hall)
        _resolve_all(game)
        _apply_effects(game)

        engine_cast_spell(game, p1, spell)
        _resolve_all(game)
        _apply_effects(game)

        assert hall.modified_power == 3
        assert hall.modified_toughness == 4

        game.effect_manager.remove_expired(game)
        _apply_effects(game)

        assert hall.modified_power == 2
        assert hall.modified_toughness == 4

    def test_casting_a_noninstant_nonsorcery_spell_does_not_pump_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Campus Attendant",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}"),
            base_power=1,
            base_toughness=1,
        )

        _play_hall(game, hall, hand=[creature_spell], mana={ManaType.COLORLESS: 6})
        _activate_regular_ability(game, p1, hall)
        _resolve_all(game)
        _apply_effects(game)

        engine_cast_spell(game, p1, creature_spell)
        _resolve_all(game)
        _apply_effects(game)

        assert hall.modified_power == 2
        assert hall.modified_toughness == 4
        assert game.get_battlefield(p1).contains(creature_spell)

    def test_activating_animation_again_after_it_is_already_a_creature_does_not_duplicate_the_trigger(
        self,
    ) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(
            name="Pop Quiz",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{U}"),
        )

        _play_hall(game, hall, hand=[spell], mana={ManaType.COLORLESS: 10, ManaType.BLUE: 1})
        _activate_regular_ability(game, p1, hall)
        _resolve_all(game)
        _apply_effects(game)

        _activate_regular_ability(game, p1, hall)
        _resolve_all(game)
        _apply_effects(game)

        engine_cast_spell(game, p1, spell)
        _resolve_all(game)
        _apply_effects(game)

        assert hall.modified_power == 3
        assert hall.modified_toughness == 4
