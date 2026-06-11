"""Tests for Great Hall of the Biblioplex (sos_257)."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import TestSetupError, create_game, set_board_state, cast_spell


def _mana_ability_instance(hall, index):
    ma = hall.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=hall, controller=hall.controller,
        cost=ma.cost, effect=ma.mana_produced, is_mana_ability=True,
    )


def _activated_instance(hall, index=0):
    ab = hall.get_activated_abilities()[index]
    return ActivatedAbilityInstance(
        source=hall, controller=hall.controller, cost=ab.cost, effect=ab.effect,
    )


def _animate(game, hall, player):
    """Activate {5} through the real ability pipeline and resolve it."""
    activate_ability(game, player, _activated_instance(hall))
    resolve_top(game)


class TestGreatHallManaAbilities:
    def test_tap_for_colorless(self):
        game = create_game()
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall])
        activate_ability(game, game.players[0], _mana_ability_instance(hall, 0))
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped

    def test_restricted_mana_pays_for_instant(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        spell = Instant(name="Blue Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[hall], hand=[spell])
        p0._script.append(ManaType.BLUE)  # color choice
        activate_ability(game, p0, _mana_ability_instance(hall, 1))
        assert p0.life == 19
        assert p0.mana_pool.get_restricted(ManaType.BLUE) == 1
        cast_spell(game, 0, "Blue Trick")
        assert p0.zones[Zone.GRAVEYARD].contains(spell)
        assert p0.mana_pool.get_restricted(ManaType.BLUE) == 0

    def test_restricted_mana_cannot_pay_for_creature(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[hall], hand=[bear])
        p0._script.append(ManaType.GREEN)
        activate_ability(game, p0, _mana_ability_instance(hall, 1))
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Bear")


class TestGreatHallAnimation:
    def test_animates_to_2_4_wizard_still_land(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _animate(game, hall, p0)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert p0.mana_pool.total() == 0

    def test_pump_on_instant_cast_until_end_of_turn(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        spell = Instant(name="Cheap Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[hall],
                        hand=[spell],
                        mana={ManaType.COLORLESS: 5, ManaType.BLUE: 1})
        _animate(game, hall, p0)
        cast_spell(game, 0, "Cheap Trick")
        assert hall.power == 3
        # Cleanup: until-EOT effects expire.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 2

    def test_animation_noop_if_already_creature(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 10})
        _animate(game, hall, p0)
        _animate(game, hall, p0)  # second activation: pays, no further effect
        assert hall.power == 2 and hall.toughness == 4
        assert len(game.trigger_manager.get_triggers_for_source(hall)) == 1

    def test_opponent_spell_does_not_pump(self):
        game = create_game()
        p0, p1 = game.players
        hall = GreatHallOfTheBiblioplex()
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _animate(game, hall, p0)
        spell = Instant(name="Opp Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 1, hand=[spell], mana={ManaType.BLUE: 1})
        cast_spell(game, 1, "Opp Trick")
        assert hall.power == 2
