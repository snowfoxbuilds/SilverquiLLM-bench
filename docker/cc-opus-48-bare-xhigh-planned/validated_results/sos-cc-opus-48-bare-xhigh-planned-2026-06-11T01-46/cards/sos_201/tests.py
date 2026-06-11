"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class DamageInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Damage Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        deal_damage(game, self, game.non_active_player, 3)


def _lib_add(game, pidx, cards):
    p = game.players[pidx]
    for c in cards:
        c.owner = p
        c.controller = p
        p.zones[Zone.LIBRARY].add(c)


def _resolve_stack(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _fire_upkeep(game):
    # Mirrors engine/turn.py's upkeep step, then resolves resulting triggers.
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _resolve_stack(game)


def _lorehold_in_play(game):
    lh = LoreholdTheHistorian(owner=None)
    set_board_state(game, 0, battlefield=[lh])
    lh.register_triggers(game)
    return lh


class TestProperties:
    def test_static(self):
        c = LoreholdTheHistorian(owner=None)
        assert c.name == "Lorehold, the Historian"
        assert c.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert Keyword.FLYING in c.keywords and Keyword.HASTE in c.keywords
        assert c.base_power == 5 and c.base_toughness == 5
        assert Supertype.LEGENDARY in c.supertypes


class TestMiracle:
    def test_first_instant_can_be_miracled(self):
        game = create_game(scripts=([True], []))
        p0, p1 = game.players
        _lorehold_in_play(game)
        _lib_add(game, 0, [DamageInstant(owner=None)])
        p0.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p0)
        _resolve_stack(game)
        assert p1.life == 17                       # cast via miracle
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0  # paid {2}
        assert any(getattr(c, "name", "") == "Damage Instant"
                   for c in game.get_graveyard(p0).get_all())

    def test_not_first_draw_no_miracle(self):
        game = create_game(scripts=([True], []))
        p0, p1 = game.players
        _lorehold_in_play(game)
        # top = creature (drawn first), then the instant
        _lib_add(game, 0, [DamageInstant(owner=None),
                           Creature(name="Dog", base_power=1, base_toughness=1)])
        p0.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p0)  # draws Dog (first) → not instant
        draw_card(game, p0)  # draws instant (second) → no miracle
        _resolve_stack(game)
        assert p1.life == 20
        assert any(getattr(c, "name", "") == "Damage Instant"
                   for c in game.get_hand(p0).get_all())

    def test_decline_miracle(self):
        game = create_game(scripts=([False], []))
        p0, p1 = game.players
        _lorehold_in_play(game)
        _lib_add(game, 0, [DamageInstant(owner=None)])
        p0.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p0)
        _resolve_stack(game)
        assert p1.life == 20
        assert any(getattr(c, "name", "") == "Damage Instant"
                   for c in game.get_hand(p0).get_all())


class TestLoot:
    def test_opponent_upkeep_loots(self):
        game = create_game()
        p0, p1 = game.players
        game.active_player_index = 1  # opponent's turn/upkeep
        _lorehold_in_play(game)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[junk])
        _lib_add(game, 0, [Creature(name="Fresh", base_power=2, base_toughness=2)])
        p0._script.append(junk)  # discard Junk
        _fire_upkeep(game)
        assert game.get_graveyard(p0).contains(junk)
        assert any(getattr(c, "name", "") == "Fresh" for c in game.get_hand(p0).get_all())
        assert len(game.get_library(p0)) == 0

    def test_decline_loot(self):
        game = create_game()
        p0, p1 = game.players
        game.active_player_index = 1
        _lorehold_in_play(game)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[junk])
        _lib_add(game, 0, [Creature(name="Fresh", base_power=2, base_toughness=2)])
        p0._script.append(None)  # decline
        _fire_upkeep(game)
        assert game.get_hand(p0).contains(junk)
        assert len(game.get_library(p0)) == 1

    def test_own_upkeep_no_loot(self):
        game = create_game()
        p0, p1 = game.players
        game.active_player_index = 0  # your own upkeep
        _lorehold_in_play(game)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[junk])
        _lib_add(game, 0, [Creature(name="Fresh", base_power=2, base_toughness=2)])
        _fire_upkeep(game)  # no choose_card should be requested
        assert game.get_hand(p0).contains(junk)
        assert len(game.get_library(p0)) == 1
