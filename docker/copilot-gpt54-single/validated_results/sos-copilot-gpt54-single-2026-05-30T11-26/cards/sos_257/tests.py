"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.casting import CastingError, cast_spell as cast_spell_to_stack
from engine.card import Creature, Instant, Land, Sorcery
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


def _set_precombat_main(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)
    game.effect_manager.apply_all(game)


def _get_activated_abilities(card, game):
    try:
        return card.get_activated_abilities(game)
    except TypeError:
        return card.get_activated_abilities()


def _activate_ability(game, source, ability_index: int = 0) -> None:
    ability = _get_activated_abilities(source, game)[ability_index]
    assert ability.cost(game, source) is True
    ability.effect(game)
    game.effect_manager.apply_all(game)


def _mana_ability_index_producing(game, player, desired_mana: ManaType, expected_life_loss: int) -> int:
    original_choose = player.choose

    for index in range(len(GreatHallOfTheBiblioplex(owner=player, controller=player).get_mana_abilities())):
        probe = GreatHallOfTheBiblioplex(owner=player, controller=player)
        player.mana_pool.empty()
        player.life = 20
        probe.is_tapped = False
        player.choose = lambda _options, _description, mt=desired_mana: mt

        ability = probe.get_mana_abilities()[index]
        if not ability.cost(game, probe):
            continue
        ability.mana_produced(game)

        if player.mana_pool.get(desired_mana) == 1 and 20 - player.life == expected_life_loss:
            player.choose = original_choose
            player.mana_pool.empty()
            player.life = 20
            return index

    player.choose = original_choose
    raise AssertionError(f"Could not find a mana ability that produces {desired_mana}")


def _activate_mana_ability(game, hall, mana_type: ManaType, expected_life_loss: int) -> None:
    controller = hall.controller
    assert controller is not None
    index = _mana_ability_index_producing(game, controller, mana_type, expected_life_loss)
    original_choose = controller.choose
    controller.choose = lambda _options, _description, mt=mana_type: mt
    ability = hall.get_mana_abilities()[index]
    assert ability.cost(game, hall) is True
    ability.mana_produced(game)
    controller.choose = original_choose


class _CampusInstant(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Campus Insight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class _CampusSorcery(Sorcery):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Campus Lecture")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)


class _CampusCreature(Creature):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Campus Apprentice")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)


class TestGreatHallOfTheBiblioplexProperties:
    def test_is_a_land_named_great_hall_of_the_biblioplex_with_no_mana_cost(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert isinstance(card, Land)
        assert card.name == "Great Hall of the Biblioplex"
        assert card.mana_cost == ManaCost()
        assert CardType.LAND in card.card_types

    def test_starts_as_a_noncreature_colorless_land(self) -> None:
        card = GreatHallOfTheBiblioplex(owner=None)

        assert CardType.CREATURE not in card.card_types
        assert card.colors == set()


class TestGreatHallOfTheBiblioplexManaAbilities:
    def test_has_a_tap_ability_that_adds_colorless_without_costing_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], life=20)
        _activate_mana_ability(game, hall, ManaType.COLORLESS, expected_life_loss=0)

        assert hall.is_tapped is True
        assert p1.life == 20
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    @pytest.mark.parametrize(
        "mana_type",
        [
            ManaType.WHITE,
            ManaType.BLUE,
            ManaType.BLACK,
            ManaType.RED,
            ManaType.GREEN,
        ],
    )
    def test_pay_life_mana_ability_can_add_each_color_for_instants_and_sorceries(self, mana_type: ManaType) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], life=20)
        _activate_mana_ability(game, hall, mana_type, expected_life_loss=1)

        assert hall.is_tapped is True
        assert p1.life == 19
        assert p1.mana_pool.get(mana_type) == 1

    def test_restricted_colored_mana_can_cast_an_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = _CampusInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], hand=[spell], life=20)
        _set_precombat_main(game)
        _activate_mana_ability(game, hall, ManaType.BLUE, expected_life_loss=1)

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert p1.life == 19
        assert game.get_graveyard(p1).contains(spell)

    def test_restricted_colored_mana_can_cast_a_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = _CampusSorcery(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], hand=[spell], life=20)
        _set_precombat_main(game)
        _activate_mana_ability(game, hall, ManaType.BLUE, expected_life_loss=1)

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert p1.life == 19
        assert game.get_graveyard(p1).contains(spell)

    def test_restricted_colored_mana_cannot_be_spent_to_cast_a_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = _CampusCreature(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[hall], hand=[creature_spell], life=20)
        _set_precombat_main(game)
        _activate_mana_ability(game, hall, ManaType.BLUE, expected_life_loss=1)

        with pytest.raises(CastingError):
            cast_spell_to_stack(game, p1, creature_spell)

        assert p1.life == 19
        assert game.get_hand(p1).contains(creature_spell)


class TestGreatHallOfTheBiblioplexAnimation:
    def test_five_mana_ability_turns_it_into_a_two_four_wizard_creature_thats_still_a_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            mana={ManaType.COLORLESS: 5},
        )
        _activate_ability(game, hall)

        assert CardType.LAND in hall.card_types
        assert CardType.CREATURE in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4

    def test_after_animation_casting_an_instant_gives_it_plus_one_power_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = _CampusInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[spell],
            mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1},
        )
        _set_precombat_main(game)
        hall.register_triggers(game)
        _activate_ability(game, hall)

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert hall.power == 3
        assert hall.toughness == 4

    def test_after_animation_casting_a_creature_spell_does_not_buff_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        creature_spell = _CampusCreature(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[creature_spell],
            mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1},
        )
        _set_precombat_main(game)
        hall.register_triggers(game)
        _activate_ability(game, hall)

        cast_spell_to_stack(game, p1, creature_spell)
        _resolve_all(game)

        assert hall.power == 2
        assert hall.toughness == 4

    def test_animating_it_again_while_already_a_creature_does_not_create_an_extra_spell_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=p1, controller=p1)
        spell = _CampusInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[hall],
            hand=[spell],
            mana={ManaType.COLORLESS: 10, ManaType.BLUE: 1},
        )
        _set_precombat_main(game)
        hall.register_triggers(game)
        _activate_ability(game, hall)
        _activate_ability(game, hall)

        cast_spell_to_stack(game, p1, spell)
        _resolve_all(game)

        assert hall.power == 3
        assert hall.toughness == 4
