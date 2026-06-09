"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class _GainThree(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spark")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))  # real cost high
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _setup_lorehold(scripts_p0=None):
    game = create_game(scripts=(scripts_p0 or [], []))
    p0 = game.players[0]
    lore = LoreholdTheHistorian(owner=p0, controller=p0)
    set_board_state(game, 0, battlefield=[lore], life=20)
    lore.register_triggers(game)
    return game, p0, lore


class TestProperties:
    def test_keywords_stats(self):
        c = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in c.keywords and Keyword.HASTE in c.keywords
        assert c.base_power == 5 and c.base_toughness == 5
        assert Supertype.LEGENDARY in c.supertypes
        assert c.mana_cost == ManaCost.parse("{3}{R}{W}")


class TestMiracle:
    def test_first_drawn_instant_cast_for_two(self):
        game, p0, lore = _setup_lorehold([True])
        spell = _GainThree(owner=p0)
        p0.zones[Zone.LIBRARY].add(spell)
        p0.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p0)  # first draw this turn → miracle
        _resolve_stack(game)
        assert game.get_graveyard(p0).contains(spell)
        assert p0.life == 23
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_decline_miracle_keeps_card(self):
        game, p0, lore = _setup_lorehold([False])
        spell = _GainThree(owner=p0)
        p0.zones[Zone.LIBRARY].add(spell)
        p0.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p0)
        _resolve_stack(game)
        assert game.get_hand(p0).contains(spell)
        assert p0.life == 20
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

    def test_not_first_draw_no_miracle(self):
        game, p0, lore = _setup_lorehold([])
        dud = Creature(name="Dud", base_power=1, base_toughness=1, owner=p0)
        spell = _GainThree(owner=p0)
        # Add spell then dud so top (drawn first) = dud, then spell.
        p0.zones[Zone.LIBRARY].add(spell)
        p0.zones[Zone.LIBRARY].add(dud)
        p0.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p0)  # draws dud (not instant) → no miracle
        draw_card(game, p0)  # draws spell, but not first → no miracle
        _resolve_stack(game)
        assert game.get_hand(p0).contains(spell)
        assert p0.life == 20


class TestLoot:
    def test_loots_on_opponent_upkeep(self):
        game, p0, lore = _setup_lorehold([True])  # will append discard target
        junk = Creature(name="Junk", base_power=1, base_toughness=1, owner=p0)
        drawn = Creature(name="Drawn", base_power=2, base_toughness=2, owner=p0)
        set_board_state(game, 0, battlefield=[lore], hand=[junk])
        p0.zones[Zone.LIBRARY].add(drawn)
        p0._script.append(junk)  # choose_card after the yes
        # Opponent's (p1's) upkeep, fired the same way the turn loop fires it.
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert game.get_graveyard(p0).contains(junk)
        assert game.get_hand(p0).contains(drawn)

    def test_no_loot_on_own_upkeep(self):
        game, p0, lore = _setup_lorehold([])
        junk = Creature(name="Junk", base_power=1, base_toughness=1, owner=p0)
        set_board_state(game, 0, battlefield=[lore], hand=[junk])
        game.active_player_index = 0  # own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        # Nothing happened; junk still in hand, no script consumed.
        assert game.get_hand(p0).contains(junk)
        assert p0.remaining_choices == 0
