"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land, Sorcery
from engine.casting import CastingError, cast_spell
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


def _main_phase_game():
    game = create_game()
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    return game


def _activate_mana_ability(game, player, land: GreatHallOfTheBiblioplex, ability_index: int) -> None:
    ability = land.get_mana_abilities()[ability_index]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=land,
            controller=player,
            cost=ability.cost,
            effect=ability.mana_produced,
            is_mana_ability=True,
            description=ability.description,
        ),
    )


def _activate_animation_ability(game, player, land: GreatHallOfTheBiblioplex) -> None:
    ability = land.get_activated_abilities()[0]
    activate_ability(
        game,
        player,
        ActivatedAbilityInstance(
            source=land,
            controller=player,
            cost=ability.cost,
            effect=ability.effect,
            description=ability.description,
        ),
    )
    stack_obj = game.stack.pop()
    assert stack_obj.source is land
    stack_obj.on_resolve(game)
    game.effect_manager.apply_all(game)


def _fire_spell_cast(game, player, spell) -> None:
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
    """Static characteristics should match the card spec."""

    def test_is_a_land_named_great_hall_with_two_mana_abilities_and_one_animation_ability(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert card.mana_cost == ManaCost()
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types
        assert len(card.get_mana_abilities()) == 2
        assert len(card.get_activated_abilities()) == 1

    def test_animation_ability_description_mentions_becoming_a_two_four_wizard_still_a_land(self) -> None:
        ability = GreatHallOfTheBiblioplex(owner=None).get_activated_abilities()[0]

        assert "2/4" in ability.description
        assert "Wizard" in ability.description
        assert "still a land" in ability.description


class TestGreatHallOfTheBiblioplexManaAbilities:
    """The land should produce the printed mana with the printed costs."""

    def test_first_mana_ability_taps_to_add_colorless(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])

        _activate_mana_ability(game, p1, hall, 0)

        assert hall.is_tapped is True
        assert p1.life == 20
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert p1.mana_pool.total() == 1

    def test_second_mana_ability_taps_costs_one_life_and_adds_the_chosen_color(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])
        p1.choose = lambda options, description: ManaType.BLUE

        _activate_mana_ability(game, p1, hall, 1)

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.total() == 1

    def test_second_mana_ability_adds_restricted_mana_in_the_chosen_color(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])
        p1.choose = lambda options, description: ManaType.GREEN

        _activate_mana_ability(game, p1, hall, 1)

        assert p1.life == 19
        assert p1.mana_pool.get_instant_or_sorcery_only(ManaType.GREEN) == 1
        assert p1.mana_pool.get_unrestricted(ManaType.GREEN) == 0
        assert p1.mana_pool.restricted_total(restriction="instant_or_sorcery_only") == 1

    def test_restricted_mana_can_cast_an_instant_spell(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Pop Quiz", mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        p1.choose = lambda options, description: ManaType.BLUE

        _activate_mana_ability(game, p1, hall, 1)
        cast_spell(game, p1, spell)

        assert game.stack.peek().source is spell
        assert p1.mana_pool.total() == 0
        assert not game.get_hand(p1).contains(spell)

    def test_restricted_mana_can_cast_a_sorcery_spell(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Sorcery(name="Environmental Sciences", mana_cost=ManaCost.parse("{G}"))

        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        p1.choose = lambda options, description: ManaType.GREEN

        _activate_mana_ability(game, p1, hall, 1)
        cast_spell(game, p1, spell)

        assert game.stack.peek().source is spell
        assert p1.mana_pool.total() == 0
        assert not game.get_hand(p1).contains(spell)

    def test_restricted_mana_cannot_cast_a_creature_spell(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Creature(
            name="Campus Familiar",
            mana_cost=ManaCost.parse("{U}"),
            base_power=1,
            base_toughness=1,
        )

        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        p1.choose = lambda options, description: ManaType.BLUE

        _activate_mana_ability(game, p1, hall, 1)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell(game, p1, spell)

        assert game.get_hand(p1).contains(spell)
        assert p1.mana_pool.get_instant_or_sorcery_only(ManaType.BLUE) == 1

    def test_restricted_mana_cannot_pay_for_the_animation_ability(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        ability = hall.get_activated_abilities()[0]

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 4},
        )
        p1.choose = lambda options, description: ManaType.WHITE

        _activate_mana_ability(game, p1, hall, 1)

        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(
                game,
                p1,
                ActivatedAbilityInstance(
                    source=hall,
                    controller=p1,
                    cost=ability.cost,
                    effect=ability.effect,
                    description=ability.description,
                ),
            )

        assert len(game.stack) == 0
        assert CardType.CREATURE not in hall.card_types
        assert p1.mana_pool.get_unrestricted(ManaType.COLORLESS) == 4
        assert p1.mana_pool.get_instant_or_sorcery_only(ManaType.WHITE) == 1


class TestGreatHallOfTheBiblioplexAnimation:
    """The five-mana ability should animate the land and grant the printed trigger."""

    def test_animation_makes_it_a_two_four_wizard_creature_thats_still_a_land(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )

        _activate_animation_ability(game, p1, hall)

        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_spell_cast_trigger_does_not_fire_before_the_land_has_become_a_creature(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Study Break", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[hall])
        hall.register_triggers(game)

        _fire_spell_cast(game, p1, spell)

        assert len(game.stack) == 0

    def test_your_instant_or_sorcery_spell_triggers_plus_one_power_after_animation(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Pop Quiz", owner=p1, controller=p1, mana_cost=ManaCost.parse("{1}{U}"))

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)
        _fire_spell_cast(game, p1, spell)

        assert len(game.stack) == 1
        trigger = game.stack.pop()
        assert trigger.source is hall

        trigger.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4

    def test_opponents_spells_do_not_trigger_the_bonus(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        p2 = game.players[1]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Enemy Lecture", owner=p2, controller=p2, mana_cost=ManaCost.parse("{U}"))

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)
        _fire_spell_cast(game, p2, spell)

        assert len(game.stack) == 0
        assert hall.power == 2

    def test_your_creature_spells_do_not_trigger_the_bonus(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Campus Familiar",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{U}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)
        _fire_spell_cast(game, p1, creature_spell)

        assert len(game.stack) == 0
        assert hall.power == 2

    def test_spell_cast_bonus_expires_at_end_of_turn_but_the_animation_remains(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Fractal Insight", owner=p1, controller=p1, mana_cost=ManaCost.parse("{U}"))

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)
        _fire_spell_cast(game, p1, spell)
        trigger = game.stack.pop()
        trigger.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 3

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert hall.power == 2
        assert hall.toughness == 4

    def test_second_animation_activation_while_already_a_creature_does_not_create_an_extra_bonus_trigger(self) -> None:
        game = _main_phase_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = Instant(name="Expanded Anatomy", owner=p1, controller=p1, mana_cost=ManaCost.parse("{2}{U}"))

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 10},
        )
        hall.register_triggers(game)

        _activate_animation_ability(game, p1, hall)
        _activate_animation_ability(game, p1, hall)
        _fire_spell_cast(game, p1, spell)

        assert len(game.stack) == 1
        trigger = game.stack.pop()
        trigger.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4
