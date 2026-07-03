"""Tests for Great Hall of the Biblioplex (sos_257)."""

from __future__ import annotations

import pytest

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


class DamageInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Damage Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        deal_damage(game, self, game.non_active_player, 1)


def _resolve_stack(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _activate_mana(game, player, hall, index):
    ab = hall.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(source=hall, controller=player,
                                    cost=ab.cost, effect=ab.mana_produced,
                                    is_mana_ability=True)
    activate_ability(game, player, inst)


def _activate_animate(game, player, hall):
    ab = hall.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(source=hall, controller=player,
                                    cost=ab.cost, effect=ab.effect,
                                    is_mana_ability=False)
    activate_ability(game, player, inst)
    _resolve_stack(game)


class TestManaAbilities:
    def test_colorless(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall])
        _activate_mana(game, p0, hall, 0)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert hall.is_tapped is True

    def test_restricted_cannot_pay_creature(self):
        game = create_game(scripts=([ManaType.RED], []))
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[hall], hand=[bear])
        _activate_mana(game, p0, hall, 1)  # {T}, pay 1 life: add restricted R
        assert p0.life == 19
        assert p0.mana_pool.get(ManaType.RED) == 1
        with pytest.raises(Exception):
            cast_spell(game, 0, "Bear")  # restricted mana can't pay a creature

    def test_restricted_can_pay_instant(self):
        game = create_game(scripts=([ManaType.RED], []))
        p0, p1 = game.players
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall], hand=[DamageInstant(owner=None)])
        _activate_mana(game, p0, hall, 1)
        cast_spell(game, 0, "Damage Instant")  # restricted R pays for the instant
        assert p1.life == 19


class TestAnimation:
    def test_becomes_2_4_wizard_still_land(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _activate_animate(game, p0, hall)
        assert CardType.CREATURE in hall.card_types
        assert CardType.LAND in hall.card_types
        assert "Wizard" in hall.subtypes
        assert hall.power == 2 and hall.toughness == 4
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_animate_only_if_not_creature(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 10})
        _activate_animate(game, p0, hall)
        # Second activation: already a creature → no change, but mana still paid
        # only if affordable; here we just confirm idempotent state.
        hall.power = 5  # pretend pumped
        _activate_animate(game, p0, hall)
        assert hall.power == 5  # _animate did nothing (already a creature)


class TestPump:
    def test_pump_on_instant_cast(self):
        game = create_game()
        p0, p1 = game.players
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _activate_animate(game, p0, hall)
        set_board_state(game, 0, hand=[DamageInstant(owner=None), DamageInstant(owner=None)],
                        mana={ManaType.RED: 2})
        cast_spell(game, 0, "Damage Instant")
        assert hall.power == 3
        cast_spell(game, 0, "Damage Instant")
        assert hall.power == 4

    def test_pump_resets_end_of_turn(self):
        game = create_game()
        p0 = game.players[0]
        hall = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[hall], mana={ManaType.COLORLESS: 5})
        _activate_animate(game, p0, hall)
        set_board_state(game, 0, hand=[DamageInstant(owner=None)], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Damage Instant")
        assert hall.power == 3
        # Mimic the cleanup step's continuous-effect sweep.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert hall.power == 2
        assert CardType.CREATURE in hall.card_types  # animation persists
