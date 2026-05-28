"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.casting import CastingError, cast_spell, play_land, resolve_top
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


class TrainingInstant(Instant):
    """Cheap instant used to trigger the animated Hall."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)
        self.times_resolved = 0

    def on_resolve(self, game) -> None:
        self.times_resolved += 1


def _set_precombat_main(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _mana_ability_instance(source, controller, index: int) -> ActivatedAbilityInstance:
    ability = source.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=source,
        controller=controller,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
        description=ability.description,
    )


def _activated_ability_instance(source, controller, index: int = 0) -> ActivatedAbilityInstance:
    ability = source.get_activated_abilities()[index]
    return ActivatedAbilityInstance(
        source=source,
        controller=controller,
        cost=ability.cost,
        effect=ability.effect,
        description=ability.description,
    )


def _animate_hall(game, hall, player) -> None:
    activate_ability(game, player, _activated_ability_instance(hall, player))
    assert len(game.stack) == 1
    resolve_top(game)
    game.effect_manager.apply_all(game)


class TestGreatHallOfTheBiblioplexProperties:
    """Static card data and printed abilities should match the spec."""

    def test_is_a_land_with_the_expected_name_and_abilities(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert card.mana_cost == ManaCost()
        assert CardType.LAND in card.card_types
        assert CardType.CREATURE not in card.card_types
        assert len(card.get_mana_abilities()) == 2
        assert len(card.get_activated_abilities()) == 1


class TestGreatHallOfTheBiblioplexManaAbilities:
    """The land should produce mana exactly as printed."""

    def test_first_mana_ability_taps_for_colorless(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall])

        activate_ability(game, p1, _mana_ability_instance(hall, p1, 0))

        assert hall.is_tapped is True
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_second_mana_ability_costs_one_life_and_adds_the_chosen_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.choose = lambda options, description: ManaType.BLUE

        set_board_state(game, 0, battlefield=[hall])

        activate_ability(game, p1, _mana_ability_instance(hall, p1, 1))

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.total() == 1
        assert p1.mana_pool.restricted_total() == 1
        assert len(p1.mana_pool.restricted_entries) == 1
        assert p1.mana_pool.restricted_entries[0].mana_type is ManaType.BLUE
        assert (
            p1.mana_pool.restricted_entries[0].description
            == "Spend this mana only to cast an instant or sorcery spell."
        )

    def test_second_mana_ability_cannot_be_activated_if_you_cannot_pay_the_life(self) -> None:
        game = create_game(player1_life=0)
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        p1.choose = lambda options, description: ManaType.WHITE

        set_board_state(game, 0, battlefield=[hall])

        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, p1, _mana_ability_instance(hall, p1, 1))

        assert p1.life == 0
        assert p1.mana_pool.total() == 0
        assert hall.is_tapped is False


class TestGreatHallOfTheBiblioplexAnimation:
    """The five-mana activation should turn the land into the printed creature."""

    def test_animation_makes_it_a_2_4_wizard_creature_thats_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        _set_precombat_main(game)
        set_board_state(game, 0, hand=[hall], mana={ManaType.COLORLESS: 5})
        play_land(game, p1, hall)

        _animate_hall(game, hall, p1)

        assert hall.is_tapped is False
        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_casting_an_instant_after_animation_gives_plus_one_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = TrainingInstant(owner=p1, controller=p1)

        _set_precombat_main(game)
        set_board_state(
            game,
            0,
            hand=[hall, spell],
            mana={
                ManaType.COLORLESS: 5,
                ManaType.BLUE: 1,
            },
        )
        play_land(game, p1, hall)
        _animate_hall(game, hall, p1)

        cast_spell(game, p1, spell)

        assert len(game.stack) == 2

        resolve_top(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4

        resolve_top(game)
        assert spell.times_resolved == 1

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 2
        assert hall.toughness == 4

    def test_animation_does_not_add_duplicate_spell_cast_triggers_once_it_is_already_a_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = TrainingInstant(owner=p1, controller=p1)

        _set_precombat_main(game)
        set_board_state(
            game,
            0,
            hand=[hall, spell],
            mana={
                ManaType.COLORLESS: 10,
                ManaType.BLUE: 1,
            },
        )
        play_land(game, p1, hall)
        _animate_hall(game, hall, p1)
        _animate_hall(game, hall, p1)

        cast_spell(game, p1, spell)

        assert len(game.stack) == 2

        resolve_top(game)
        game.effect_manager.apply_all(game)

        assert hall.power == 3
        assert hall.toughness == 4


class TestGreatHallOfTheBiblioplexRestrictedMana:
    """Restricted colored mana should be publicly tracked and spell-limited."""

    def test_restricted_mana_can_cast_an_instant_and_is_consumed(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = TrainingInstant(owner=p1, controller=p1)
        p1.choose = lambda options, description: ManaType.BLUE

        _set_precombat_main(game)
        set_board_state(game, 0, hand=[hall, spell])
        play_land(game, p1, hall)

        activate_ability(game, p1, _mana_ability_instance(hall, p1, 1))

        assert p1.mana_pool.can_pay_for_spell(spell.mana_cost, spell) is True

        cast_spell(game, p1, spell)

        assert p1.mana_pool.total() == 0
        assert p1.mana_pool.restricted_total() == 0
        assert len(game.stack) == 1

        resolve_top(game)
        assert spell.times_resolved == 1

    def test_restricted_mana_cannot_cast_a_non_instant_or_sorcery_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature = Creature(
            name="Blue Bear",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{U}"),
            base_power=2,
            base_toughness=2,
        )
        p1.choose = lambda options, description: ManaType.BLUE

        _set_precombat_main(game)
        set_board_state(game, 0, hand=[hall, creature])
        play_land(game, p1, hall)

        activate_ability(game, p1, _mana_ability_instance(hall, p1, 1))

        assert p1.mana_pool.can_pay_for_spell(creature.mana_cost, creature) is False

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell(game, p1, creature)

        assert game.get_hand(p1).contains(creature) is True
        assert len(game.stack) == 0
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.restricted_total() == 1
