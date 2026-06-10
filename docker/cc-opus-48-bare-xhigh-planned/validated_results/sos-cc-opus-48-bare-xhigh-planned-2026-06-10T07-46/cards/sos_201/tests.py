"""Tests for SOS 201 — Lorehold, the Historian (miracle + upkeep loot)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


def _resolve_stack(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class _GainInstant(Instant):
    def __init__(self, name: str = "Gain5", **kwargs: Any) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))  # normal cost is high
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 5


def _lorehold_on_bf(game) -> LoreholdTheHistorian:
    p0 = game.players[0]
    lore = LoreholdTheHistorian(owner=p0, controller=p0)
    set_board_state(game, 0, hand=[lore])
    move_to_zone(game, lore, Zone.HAND, Zone.BATTLEFIELD)
    return lore


def _add_library(game, pidx: int, cards) -> None:
    p = game.players[pidx]
    for c in cards:
        c.owner = p
        c.controller = p
        p.zones[Zone.LIBRARY].add(c)


class TestProperties:
    def test_static_data(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords and Keyword.HASTE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestMiracle:
    def test_first_drawn_instant_can_be_cast_for_two(self) -> None:
        game = create_game(scripts=([True], []))  # yes, cast for miracle
        p0 = game.players[0]
        _lorehold_on_bf(game)
        probe = _GainInstant()
        _add_library(game, 0, [probe])  # top of library
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        before = p0.life
        draw_card(game, p0)
        _resolve_stack(game)
        assert game.get_graveyard(p0).contains(probe)  # cast & resolved
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0  # paid {2}
        assert p0.life == before + 5

    def test_decline_miracle_keeps_in_hand(self) -> None:
        game = create_game(scripts=([False], []))  # decline
        p0 = game.players[0]
        _lorehold_on_bf(game)
        probe = _GainInstant()
        _add_library(game, 0, [probe])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p0)
        _resolve_stack(game)
        assert game.get_hand(p0).contains(probe)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

    def test_not_first_draw_no_miracle(self) -> None:
        game = create_game()
        p0 = game.players[0]
        _lorehold_on_bf(game)
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        probe = _GainInstant()
        _add_library(game, 0, [probe, creature])  # top = creature
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p0)  # creature — first draw, not a spell
        _resolve_stack(game)
        draw_card(game, p0)  # instant — second draw, no miracle
        _resolve_stack(game)
        assert game.get_hand(p0).contains(probe)  # not cast

    def test_cannot_afford_no_miracle(self) -> None:
        game = create_game()
        p0 = game.players[0]
        _lorehold_on_bf(game)
        probe = _GainInstant()
        _add_library(game, 0, [probe])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})  # < {2}
        draw_card(game, p0)
        _resolve_stack(game)
        assert game.get_hand(p0).contains(probe)


class TestLoot:
    def test_loot_on_opponent_upkeep(self) -> None:
        game = create_game()
        p0 = game.players[0]
        _lorehold_on_bf(game)
        a = Creature(name="A", base_power=1, base_toughness=1)
        b = Creature(name="B", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[a, b])
        libCard = Creature(name="Lib", base_power=1, base_toughness=1)
        _add_library(game, 0, [libCard])
        # Opponent's upkeep.
        game.active_player_index = 1
        p0._script.append(a)  # discard A
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert game.get_graveyard(p0).contains(a)  # discarded
        assert game.get_hand(p0).contains(libCard)  # drew
        assert len(game.get_hand(p0).get_all()) == 2  # net even

    def test_no_loot_on_own_upkeep(self) -> None:
        game = create_game()
        p0 = game.players[0]
        _lorehold_on_bf(game)
        a = Creature(name="A", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[a])
        game.active_player_index = 0  # your own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert len(game.get_hand(p0).get_all()) == 1  # unchanged

    def test_decline_loot(self) -> None:
        game = create_game()
        p0 = game.players[0]
        _lorehold_on_bf(game)
        a = Creature(name="A", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[a])
        libCard = Creature(name="Lib", base_power=1, base_toughness=1)
        _add_library(game, 0, [libCard])
        game.active_player_index = 1
        p0._script.append(None)  # decline
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert game.get_hand(p0).contains(a)
        assert not game.get_hand(p0).contains(libCard)
