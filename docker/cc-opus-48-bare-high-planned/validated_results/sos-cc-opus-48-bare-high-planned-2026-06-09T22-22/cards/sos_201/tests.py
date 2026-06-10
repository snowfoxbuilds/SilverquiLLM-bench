"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


class MarkerInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Spark")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))  # normal cost high
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 7


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _to_lib_top(game, pi, card):
    p = game.players[pi]
    card.owner = p
    card.controller = p
    game.get_library(p).add(card)  # appended → top


def _names(zone):
    return [getattr(c, "name", "?") for c in zone.get_all()]


def _setup(scripts_p0):
    game = create_game(scripts=(scripts_p0, []))
    p0 = game.players[0]
    lore = LoreholdTheHistorian(owner=None)
    set_board_state(game, 0, battlefield=[lore])
    lore.register_triggers(game)
    return game, p0, lore


class TestProperties:
    def test_basics(self):
        c = LoreholdTheHistorian(owner=None)
        assert c.name == "Lorehold, the Historian"
        assert c.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert c.base_power == 5 and c.base_toughness == 5
        assert Keyword.FLYING in c.keywords and Keyword.HASTE in c.keywords
        assert Supertype.LEGENDARY in c.supertypes


class TestMiracle:
    def test_first_draw_instant_castable_for_two(self):
        game, p0, lore = _setup([True])
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        _to_lib_top(game, 0, MarkerInstant(owner=None))
        draw_card(game, p0)
        _drain(game)
        # Cast for miracle {2}: resolved (life +7), in graveyard, mana spent.
        assert p0.life == 27
        assert "Spark" in _names(game.get_graveyard(p0))
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_declined_stays_in_hand(self):
        game, p0, lore = _setup([False])
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        _to_lib_top(game, 0, MarkerInstant(owner=None))
        draw_card(game, p0)
        _drain(game)
        assert "Spark" in _names(game.get_hand(p0))
        assert p0.life == 20

    def test_not_first_draw_no_miracle(self):
        game, p0, lore = _setup([])  # no choices should be consumed
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        # First draw = a creature (stamps the turn), second = the instant.
        _to_lib_top(game, 0, MarkerInstant(owner=None))  # added first → lower
        _to_lib_top(game, 0, Creature(name="Dummy", base_power=1, base_toughness=1))  # top
        draw_card(game, p0)   # draws Dummy (first)
        _drain(game)
        draw_card(game, p0)   # draws Spark (second, not first)
        _drain(game)
        assert "Spark" in _names(game.get_hand(p0))  # not cast
        assert p0.life == 20


class TestLoot:
    def test_opponent_upkeep_loot(self):
        game, p0, lore = _setup([True, None])
        discard_me = Creature(name="Trash", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lore], hand=[discard_me])
        _to_lib_top(game, 0, Creature(name="Fresh", base_power=1, base_toughness=1))
        p0._script.clear()
        p0._script.extend([True, discard_me])
        # Opponent's upkeep.
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _drain(game)
        assert "Trash" in _names(game.get_graveyard(p0))
        assert "Fresh" in _names(game.get_hand(p0))

    def test_own_upkeep_does_not_loot(self):
        game, p0, lore = _setup([])
        set_board_state(game, 0, battlefield=[lore],
                        hand=[Creature(name="Keep", base_power=1, base_toughness=1)])
        # Active player is p0 (its own upkeep) → trigger should not fire.
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _drain(game)
        assert "Keep" in _names(game.get_hand(p0))
