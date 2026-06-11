"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    activate_ability,
)
from engine.card import Creature, Instant
from engine.casting import CastingError, cast_spell as engine_cast, resolve_top
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _activate_mana(game, player, land, index):
    ability = land.get_mana_abilities()[index]
    activate_ability(game, player, ActivatedAbilityInstance(
        source=land, controller=player,
        cost=ability.cost, effect=ability.mana_produced,
        is_mana_ability=True, description=ability.description,
    ))


def _activate(game, player, land, index):
    ability = land.get_activated_abilities()[index]
    activate_ability(game, player, ActivatedAbilityInstance(
        source=land, controller=player,
        cost=ability.cost, effect=ability.effect,
        description=ability.description,
    ))
    while not game.stack.is_empty():
        resolve_top(game)


class TestGreatHallManaAbilities:
    def test_tap_for_colorless(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall])
        _activate_mana(game, p1, hall, 0)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped
        with pytest.raises(AbilityError):
            _activate_mana(game, p1, hall, 0)  # already tapped

    def test_restricted_mana_pays_only_instants_and_sorceries(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        zap = Instant(name="Zap", mana_cost=ManaCost.parse("{U}"))
        wolf = Creature(name="Wolf", base_power=1, base_toughness=1,
                        mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[hall], hand=[zap, wolf])
        p1._script.append(ManaType.BLUE)  # color choice
        _activate_mana(game, p1, hall, 1)

        assert p1.life == 19, "paid 1 life"
        assert hall.is_tapped
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 1
        assert p1.mana_pool.get(ManaType.BLUE) == 0

        # The restricted blue cannot pay for a creature spell.
        game.active_player_index = 0
        with pytest.raises(CastingError):
            engine_cast(game, p1, wolf)

        # But it pays for an instant.
        cast_spell(game, 0, "Zap")
        assert p1.zones[Zone.GRAVEYARD].contains(zap)
        assert p1.mana_pool.total() == 0


class TestGreatHallAnimation:
    def test_five_mana_animates_to_2_4_wizard_still_land(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 5})
        _activate(game, p1, hall, 0)

        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert p1.mana_pool.total() == 0

    def test_unanimated_land_has_no_power_toughness(self):
        hall = GreatHallOfTheBiblioplex(owner=None)
        assert not hasattr(hall, "power")
        assert not hasattr(hall, "toughness")
        assert CardType.CREATURE not in hall.card_types

    def test_animating_twice_is_a_noop_second_time(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall],
                        mana={ManaType.COLORLESS: 10})
        _activate(game, p1, hall, 0)
        _activate(game, p1, hall, 0)  # already a creature — no effect
        assert hall.power == 2 and hall.toughness == 4
        # Only one pump trigger may be registered.
        assert len(game.trigger_manager.get_triggers_for_source(hall)) == 1

    def test_pump_on_instant_cast_stacks_and_expires(self):
        game = create_game()
        p1 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        zap1 = Instant(name="Zap1", mana_cost=ManaCost.parse("{U}"))
        zap2 = Instant(name="Zap2", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[hall], hand=[zap1, zap2],
                        mana={ManaType.COLORLESS: 5})
        _activate(game, p1, hall, 0)
        set_board_state(game, 0, mana={ManaType.BLUE: 2})

        cast_spell(game, 0, "Zap1")
        assert hall.power == 3, "+1/+0 from the first instant"
        assert hall.toughness == 4

        cast_spell(game, 0, "Zap2")
        assert hall.power == 4, "pump stacks per spell"

        # End-of-turn cleanup sweeps the until-EOT effects.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 2 and hall.toughness == 4

    def test_pump_ignores_creature_spells_and_opponents(self):
        game = create_game()
        p1, p2 = game.players
        hall = GreatHallOfTheBiblioplex(owner=None)
        wolf = Creature(name="Wolf", base_power=1, base_toughness=1,
                        mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[hall], hand=[wolf],
                        mana={ManaType.COLORLESS: 6})
        _activate(game, p1, hall, 0)
        cast_spell(game, 0, "Wolf")
        assert hall.power == 2, "creature spells don't pump"

        opp_zap = Instant(name="Opp Zap", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 1, hand=[opp_zap], mana={ManaType.BLUE: 1})
        cast_spell(game, 1, "Opp Zap")
        assert hall.power == 2, "opponent's instants don't pump"
