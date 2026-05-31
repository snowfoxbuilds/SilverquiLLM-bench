"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import inspect
from types import MethodType

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.casting import CastingError, cast_spell as cast_spell_to_stack
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


def _bind_choose(player, answers: list[object]) -> None:
    remaining = iter(answers)

    def choose(self, options, description: str):
        return next(remaining)

    player.choose = MethodType(choose, player)



def _set_main_phase(game) -> None:
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0



def _runtime_ability(source, controller, ability, *, is_mana_ability: bool) -> ActivatedAbilityInstance:
    cost_signature = inspect.signature(ability.cost)
    if len(cost_signature.parameters) >= 2:
        cost = ability.cost
    else:
        cost = lambda game, _source: ability.cost(game)

    effect = getattr(ability, 'mana_produced', None) or ability.effect
    return ActivatedAbilityInstance(
        source=source,
        controller=controller,
        cost=cost,
        effect=effect,
        is_mana_ability=is_mana_ability,
        description=ability.description,
    )



def _animate_hall(game, player, hall: GreatHallOfTheBiblioplex) -> None:
    ability = hall.get_activated_abilities()[0]
    runtime = _runtime_ability(hall, player, ability, is_mana_ability=False)
    activate_ability(game, player, runtime)
    stack_object = game.stack.pop()
    stack_object.on_resolve(game)
    game.effect_manager.apply_all(game)


class TestGreatHallOfTheBiblioplexProperties:
    """Static characteristics from the card spec."""

    def test_is_a_land_named_great_hall_of_the_biblioplex_with_no_mana_cost(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == 'Great Hall of the Biblioplex'
        assert CardType.LAND in card.card_types
        assert card.mana_cost == ManaCost()


class TestGreatHallOfTheBiblioplexManaAbilities:
    """Mana production contract."""

    def test_has_two_mana_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        abilities = card.get_mana_abilities()

        assert len(abilities) == 2
        assert '{T}: Add {C}.' in abilities[0].description
        assert 'Pay 1 life' in abilities[1].description
        assert 'instant or sorcery spell' in abilities[1].description

    def test_first_mana_ability_taps_and_adds_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])

        ability = _runtime_ability(hall, p1, hall.get_mana_abilities()[0], is_mana_ability=True)
        activate_ability(game, p1, ability)

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert p1.mana_pool.total() == 1

    def test_second_mana_ability_pays_one_life_and_adds_the_chosen_color(self) -> None:
        game = create_game(player1_life=20)
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])
        _bind_choose(p1, [ManaType.BLUE])

        ability = _runtime_ability(hall, p1, hall.get_mana_abilities()[1], is_mana_ability=True)
        activate_ability(game, p1, ability)

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.total() == 1

    def test_second_mana_ability_exposes_public_instant_or_sorcery_spend_restriction_metadata(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        ability = card.get_mana_abilities()[1]

        assert ability.spend_restriction is not None
        assert ability.spend_restriction.description == (
            'Spend this mana only to cast an instant or sorcery spell.'
        )

    def test_second_mana_ability_adds_restricted_mana_to_the_pool(self) -> None:
        game = create_game(player1_life=20)
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])
        _bind_choose(p1, [ManaType.RED])

        ability = _runtime_ability(hall, p1, hall.get_mana_abilities()[1], is_mana_ability=True)
        activate_ability(game, p1, ability)

        assert len(p1.mana_pool.restricted_mana) == 1
        restricted_mana = p1.mana_pool.restricted_mana[0]
        assert restricted_mana.mana_type == ManaType.RED
        assert restricted_mana.restriction.description == (
            'Spend this mana only to cast an instant or sorcery spell.'
        )

    def test_restricted_mana_can_be_spent_to_cast_an_instant_spell(self) -> None:
        game = create_game(player1_life=20)
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        lesson = Instant(name='Restricted Lesson', mana_cost=ManaCost.parse('{U}'))

        _set_main_phase(game)
        set_board_state(game, 0, battlefield=[hall], hand=[lesson])
        _bind_choose(p1, [ManaType.BLUE])

        ability = _runtime_ability(hall, p1, hall.get_mana_abilities()[1], is_mana_ability=True)
        activate_ability(game, p1, ability)
        cast_spell_to_stack(game, p1, lesson)

        assert len(game.stack) == 1
        assert game.stack.peek() is not None
        assert game.stack.peek().source is lesson
        assert p1.mana_pool.total() == 0
        assert p1.mana_pool.restricted_mana == []

    def test_restricted_mana_cannot_be_spent_to_cast_a_creature_spell(self) -> None:
        game = create_game(player1_life=20)
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        apprentice = Creature(
            name='Restricted Apprentice',
            mana_cost=ManaCost.parse('{U}'),
            base_power=1,
            base_toughness=1,
        )

        _set_main_phase(game)
        set_board_state(game, 0, battlefield=[hall], hand=[apprentice])
        _bind_choose(p1, [ManaType.BLUE])

        ability = _runtime_ability(hall, p1, hall.get_mana_abilities()[1], is_mana_ability=True)
        activate_ability(game, p1, ability)

        try:
            cast_spell_to_stack(game, p1, apprentice)
        except CastingError as error:
            assert 'insufficient mana' in str(error)
        else:
            raise AssertionError('Expected restricted mana to be unusable on creature spells')

        assert len(game.stack) == 0
        assert game.get_hand(p1).contains(apprentice)
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert len(p1.mana_pool.restricted_mana) == 1


class TestGreatHallOfTheBiblioplexAnimation:
    """The five-mana activation permanently animates the land."""

    def test_animation_turns_the_land_into_a_two_four_wizard_land_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _animate_hall(game, p1, hall)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert 'Wizard' in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_animated_hall_triggers_only_when_you_cast_an_instant_or_sorcery_and_the_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        lesson = Instant(name='Quick Lesson', mana_cost=ManaCost.parse('{U}'))

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[lesson],
            mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1},
        )

        _animate_hall(game, p1, hall)
        cast_spell_to_stack(game, p1, lesson)

        assert len(game.stack) == 2
        assert game.stack.peek() is not None
        assert game.stack.peek().source is hall

        trigger = game.stack.pop()
        trigger.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 2
        assert hall.toughness == 4

    def test_casting_a_creature_spell_does_not_trigger_the_animated_hall(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        bear = Creature(
            name='Campus Bear',
            mana_cost=ManaCost.parse('{1}{G}'),
            base_power=2,
            base_toughness=2,
        )

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[bear],
            mana={ManaType.COLORLESS: 6, ManaType.GREEN: 1},
        )

        _animate_hall(game, p1, hall)
        cast_spell_to_stack(game, p1, bear)

        assert len(game.stack) == 1
        assert game.stack.peek() is not None
        assert game.stack.peek().source is bear

    def test_animating_an_already_animated_hall_does_not_create_a_second_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        lesson = Instant(name='Repeat Lesson', mana_cost=ManaCost.parse('{U}'))

        _set_main_phase(game)
        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[lesson],
            mana={ManaType.COLORLESS: 10, ManaType.BLUE: 1},
        )

        _animate_hall(game, p1, hall)
        _animate_hall(game, p1, hall)
        cast_spell_to_stack(game, p1, lesson)

        assert len(game.stack) == 2
        assert game.stack.peek() is not None
        assert game.stack.peek().source is hall

        trigger = game.stack.pop()
        trigger.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4
