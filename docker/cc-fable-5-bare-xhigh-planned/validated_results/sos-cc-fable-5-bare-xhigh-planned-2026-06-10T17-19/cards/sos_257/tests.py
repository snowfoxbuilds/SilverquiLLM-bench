"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.types import CardType, ManaType, Zone
from test_utils import TestSetupError as SetupError
from test_utils import (
    _resolve_top_of_stack,
    cast_spell,
    create_game,
    set_board_state,
)


def _activate_mana(game, land, index, player, extra_script=None):
    """Drive a mana ability through the engine's activation pipeline."""
    if extra_script:
        for item in extra_script:
            player._script.append(item)
    ability = land.get_mana_abilities()[index]
    instance = ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.mana_produced,
        is_mana_ability=True,
        description=ability.description,
    )
    activate_ability(game, player, instance)


def _activate_animation(game, land, player):
    """Drive the {5} ability through the engine and resolve the stack."""
    ability = land.get_activated_abilities()[0]
    instance = ActivatedAbilityInstance(
        source=land,
        controller=player,
        cost=ability.cost,
        effect=ability.effect,
        is_mana_ability=False,
        description=ability.description,
    )
    activate_ability(game, player, instance)
    _resolve_top_of_stack(game)


def _hall_on_battlefield(game, player_index=0):
    hall = GreatHallOfTheBiblioplex(owner=None)
    set_board_state(game, player_index, battlefield=[hall])
    return hall


class TestGreatHallManaAbilities:
    def test_tap_for_colorless(self):
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        _activate_mana(game, hall, 0, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped

    def test_tapped_hall_cannot_activate_again(self):
        from engine.abilities import AbilityError

        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        _activate_mana(game, hall, 0, p1)
        with pytest.raises(AbilityError):
            _activate_mana(game, hall, 0, p1)

    def test_second_ability_pays_life_adds_chosen_color(self):
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        _activate_mana(game, hall, 1, p1, extra_script=[ManaType.RED])
        assert p1.life == 19
        assert p1.mana_pool.get(ManaType.RED) == 1
        assert hall.is_tapped

    def test_restricted_mana_casts_instant_but_not_creature(self):
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        bear_target = Creature(name="Bear", base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear_target)
        _activate_mana(game, hall, 1, p1, extra_script=[ManaType.WHITE])

        # Restricted {W} cannot pay for a {W} creature spell.
        kitten = Creature(
            name="Kitten", base_power=1, base_toughness=1,
        )
        from engine.types import ManaCost

        kitten.mana_cost = ManaCost.parse("{W}")
        p1.zones[Zone.HAND].add(kitten)
        kitten.owner = kitten.controller = p1
        with pytest.raises(SetupError):
            cast_spell(game, 0, "Kitten")

        # …but it pays for an instant just fine.
        ff = FleetingFlight(owner=None)
        p1.zones[Zone.HAND].add(ff)
        ff.owner = ff.controller = p1
        cast_spell(game, 0, "Fleeting Flight", targets=[bear_target])
        assert bear_target.plus_one_counters == 1
        assert p1.mana_pool.total() == 0


class TestGreatHallAnimation:
    def test_five_generic_animates_to_2_4_wizard_land(self):
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        game.get_battlefield(p1).add(hall)
        _activate_animation(game, hall, p1)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types  # still a land
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_pump_on_instant_and_sorcery_casts(self):
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        game.get_battlefield(p1).add(hall)
        _activate_animation(game, hall, p1)

        for expected_power in (3, 4):
            ff = FleetingFlight(owner=None)
            p1.zones[Zone.HAND].add(ff)
            ff.owner = ff.controller = p1
            p1.mana_pool.add(ManaType.WHITE, 1)
            cast_spell(game, 0, "Fleeting Flight", targets=[bear])
            assert hall.power == expected_power

    def test_opponents_spell_does_not_pump(self):
        game = create_game()
        p1, p2 = game.players
        hall = _hall_on_battlefield(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        game.get_battlefield(p1).add(hall)
        _activate_animation(game, hall, p1)

        ff = FleetingFlight(owner=None)
        p2.zones[Zone.HAND].add(ff)
        ff.owner = ff.controller = p2
        p2.mana_pool.add(ManaType.WHITE, 1)
        cast_spell(game, 1, "Fleeting Flight", targets=[bear])
        assert hall.power == 2

    def test_animation_is_not_applied_twice(self):
        game = create_game()
        p1 = game.players[0]
        hall = _hall_on_battlefield(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 10})
        game.get_battlefield(p1).add(hall)
        _activate_animation(game, hall, p1)
        _activate_animation(game, hall, p1)  # "isn't a creature" gate

        ff = FleetingFlight(owner=None)
        p1.zones[Zone.HAND].add(ff)
        ff.owner = ff.controller = p1
        p1.mana_pool.add(ManaType.WHITE, 1)
        cast_spell(game, 0, "Fleeting Flight", targets=[bear])
        # Only one pump trigger registered → +1, not +2.
        assert hall.power == 3
