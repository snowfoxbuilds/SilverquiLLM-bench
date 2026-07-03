"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _mana_instance(land, player, index):
    ma = land.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=land, controller=player, cost=ma.cost,
        effect=ma.mana_produced, is_mana_ability=True,
    )


def _activated_instance(land, player, index):
    ab = land.get_activated_abilities()[index]
    return ActivatedAbilityInstance(
        source=land, controller=player, cost=ab.cost,
        effect=ab.effect, is_mana_ability=False,
    )


def _animate(game, land, player_index=0):
    """Activate the {5} ability through the real ability/stack path."""
    player = game.players[player_index]
    player.mana_pool.add(ManaType.COLORLESS, 5)
    activate_ability(game, player, _activated_instance(land, player, 0))
    player._script.extend(["pass", "pass", "pass"])
    game.players[1 - player_index]._script.extend(["pass", "pass", "pass"])
    priority_loop(game)


class TestManaAbilities:
    def test_tap_adds_colorless(self):
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land])
        activate_ability(game, p1, _mana_instance(land, p1, 0))
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped
        with pytest.raises(AbilityError):
            activate_ability(game, p1, _mana_instance(land, p1, 0))

    def test_pay_life_adds_restricted_color_usable_for_instant(self):
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=None)
        inst = Instant(name="Trick", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[land], hand=[inst])
        p1._script.append(ManaType.BLUE)  # chosen color
        activate_ability(game, p1, _mana_instance(land, p1, 1))
        assert p1.life == 19
        assert p1.mana_pool.get_restricted(ManaType.BLUE) == 1
        assert p1.mana_pool.get(ManaType.BLUE) == 0

        cast_spell(game, 0, "Trick")
        assert p1.zones[Zone.GRAVEYARD].contains(inst)
        assert p1.mana_pool.total() == 0

    def test_restricted_mana_cannot_pay_for_creature(self):
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=None)
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[land], hand=[bear])
        p1._script.append(ManaType.GREEN)
        activate_ability(game, p1, _mana_instance(land, p1, 1))
        assert p1.mana_pool.get_restricted(ManaType.GREEN) == 1
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Bear")


class TestAnimation:
    def test_five_mana_animates_to_2_4_wizard_still_land(self):
        game = create_game()
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land])
        _animate(game, land)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4
        assert game.players[0].mana_pool.total() == 0

    def test_pump_on_instant_cast_resets_at_cleanup(self):
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=None)
        i1 = Instant(name="T1", mana_cost=ManaCost.parse("{U}"))
        i2 = Instant(name="T2", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[land], hand=[i1, i2])
        _animate(game, land)

        p1.mana_pool.add(ManaType.BLUE, 2)
        cast_spell(game, 0, "T1")
        assert land.power == 3
        cast_spell(game, 0, "T2")
        assert land.power == 4
        assert land.toughness == 4

        from engine.turn import _do_cleanup_step
        _do_cleanup_step(game)
        assert land.power == 2  # pump expired, animation persists
        assert CardType.CREATURE in land.card_types

    def test_opponent_spell_does_not_pump(self):
        game = create_game()
        land = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[land])
        _animate(game, land)
        opp_spell = Instant(name="Opp Trick", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 1, hand=[opp_spell], mana={ManaType.RED: 1})
        cast_spell(game, 1, "Opp Trick")
        assert land.power == 2

    def test_unanimated_land_does_not_pump(self):
        game = create_game()
        p1 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=None)
        inst = Instant(name="T", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[land], hand=[inst],
                        mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "T")
        assert CardType.CREATURE not in land.card_types
        assert land.power == 0
