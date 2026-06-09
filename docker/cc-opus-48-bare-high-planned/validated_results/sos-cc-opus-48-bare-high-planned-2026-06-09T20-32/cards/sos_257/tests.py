"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _activate_mana(game, player, land, index, scripts=None):
    ma = land.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(source=land, controller=player,
                                    cost=ma.cost, effect=ma.mana_produced,
                                    is_mana_ability=True)
    activate_ability(game, player, inst)


def _activate_animate(game, player, land):
    ab = land.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(source=land, controller=player,
                                    cost=ab.cost, effect=ab.effect,
                                    is_mana_ability=False)
    activate_ability(game, player, inst)
    _resolve_stack(game)


class TestProperties:
    def test_is_land_not_castable(self):
        c = GreatHallOfTheBiblioplex(owner=None)
        assert CardType.LAND in c.card_types
        assert CardType.CREATURE not in c.card_types
        from test_utils import create_game as cg
        g = cg()
        assert c.can_cast(g) is False


class TestManaAbilities:
    def test_tap_for_colorless(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land])
        _activate_mana(game, p0, land, 0)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped is True

    def test_restricted_color_costs_life(self):
        game = create_game(scripts=([ManaType.RED], []))
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], life=20)
        _activate_mana(game, p0, land, 1)
        assert p0.mana_pool.get(ManaType.RED) == 1
        assert p0.mana_pool.has_restricted() is True
        assert p0.life == 19

    def test_restricted_mana_cannot_cast_creature(self):
        game = create_game(scripts=([ManaType.RED], []))
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        dude = Creature(name="Dude", base_power=1, base_toughness=1,
                        mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[land], hand=[dude], life=20)
        _activate_mana(game, p0, land, 1)
        with pytest.raises(Exception):
            cast_spell(game, 0, "Dude")
        # Mana preserved after the failed cast.
        assert p0.mana_pool.get(ManaType.RED) == 1

    def test_restricted_mana_can_cast_instant(self):
        game = create_game(scripts=([ManaType.RED], []))
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        bolt = Instant(name="Zap", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[land], hand=[bolt], life=20)
        _activate_mana(game, p0, land, 1)
        cast_spell(game, 0, "Zap")
        assert game.get_graveyard(p0).contains(bolt)


class TestAnimation:
    def test_becomes_creature_still_land(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_animate(game, p0, land)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types
        assert "Wizard" in land.subtypes
        assert land.power == 2 and land.toughness == 4
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_animate_only_if_not_creature(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 10})
        _activate_animate(game, p0, land)
        # Second activation: still a creature, _animate is a no-op (no second
        # pump trigger registered).
        before = len(game.trigger_manager.get_triggers_for_source(land))
        _activate_animate(game, p0, land)
        after = len(game.trigger_manager.get_triggers_for_source(land))
        assert before == after == 1


class TestPump:
    def test_pump_per_instant_cast(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_animate(game, p0, land)
        assert land.power == 2

        bolt1 = Instant(name="Z1", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[bolt1], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Z1")
        assert land.power == 3

        bolt2 = Instant(name="Z2", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[bolt2], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Z2")
        assert land.power == 4

    def test_pump_resets_end_of_turn(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_animate(game, p0, land)
        bolt = Instant(name="Z", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[bolt], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Z")
        assert land.power == 3
        # Cleanup's continuous-effect recalculation resets the until-EOT pump.
        game.effect_manager.apply_all(game)
        assert land.power == 2
