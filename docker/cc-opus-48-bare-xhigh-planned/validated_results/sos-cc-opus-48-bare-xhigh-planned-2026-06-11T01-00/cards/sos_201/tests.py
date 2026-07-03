"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


class _GainLifeInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Heal")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))  # normal cost high
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 3


def _set_library(game, idx, cards):
    lib = game.get_library(game.players[idx])
    for o in lib.get_all():
        lib.remove(o)
    for c in cards:
        c.owner = game.players[idx]
        c.controller = game.players[idx]
        lib.add(c)


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_static(self):
        c = LoreholdTheHistorian(owner=None)
        assert c.name == "Lorehold, the Historian"
        assert c.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert c.base_power == 5 and c.base_toughness == 5
        assert Keyword.FLYING in c.keywords
        assert Keyword.HASTE in c.keywords
        assert Supertype.LEGENDARY in c.supertypes


class TestMiracle:
    def test_first_drawn_instant_can_be_cast_for_two(self):
        game = create_game()
        lore = LoreholdTheHistorian(owner=None)
        heal = _GainLifeInstant(name="Heal")
        set_board_state(game, 0, battlefield=[lore],
                        mana={ManaType.COLORLESS: 2})
        _set_library(game, 0, [heal])  # top card
        lore.register_triggers(game)
        p0 = game.players[0]
        p0._script.append(True)  # yes, cast for miracle
        draw_card(game, p0)  # first draw of the turn
        _drain(game)
        # Cast for {2}: instant resolved (+3 life), mana spent, now in graveyard.
        assert p0.life == 23
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
        assert game.get_graveyard(p0).contains(heal)

    def test_second_draw_not_miracle(self):
        game = create_game()
        lore = LoreholdTheHistorian(owner=None)
        first = Creature(name="Dud", base_power=1, base_toughness=1)
        heal = _GainLifeInstant(name="Heal")
        set_board_state(game, 0, battlefield=[lore],
                        mana={ManaType.COLORLESS: 2})
        # top of library is drawn first: 'first' (creature), then 'heal'.
        _set_library(game, 0, [heal, first])  # 'first' is top
        lore.register_triggers(game)
        p0 = game.players[0]
        draw_card(game, p0)  # first draw: creature → no miracle
        draw_card(game, p0)  # second draw: instant, but not first → no miracle
        _drain(game)
        # Heal still in hand (not cast); no life gained; mana untouched.
        assert game.get_hand(p0).contains(heal)
        assert p0.life == 20
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

    def test_decline_miracle_keeps_card_in_hand(self):
        game = create_game()
        lore = LoreholdTheHistorian(owner=None)
        heal = _GainLifeInstant(name="Heal")
        set_board_state(game, 0, battlefield=[lore],
                        mana={ManaType.COLORLESS: 2})
        _set_library(game, 0, [heal])
        lore.register_triggers(game)
        p0 = game.players[0]
        p0._script.append(False)  # decline miracle
        draw_card(game, p0)
        _drain(game)
        assert game.get_hand(p0).contains(heal)
        assert p0.life == 20
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2


class TestLoot:
    def test_loot_on_opponent_upkeep(self):
        game = create_game()
        lore = LoreholdTheHistorian(owner=None)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lore], hand=[junk])
        _set_library(game, 0, [Creature(name="Top", base_power=1, base_toughness=1)])
        lore.register_triggers(game)
        p0 = game.players[0]
        # Make it the opponent's (p1's) turn/upkeep.
        game.active_player_index = 1
        p0._script.append(junk)  # discard 'junk'
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _drain(game)
        assert game.get_graveyard(p0).contains(junk)  # discarded
        assert len(game.get_hand(p0)) == 1  # drew 'Top'
        assert game.get_hand(p0).get_all()[0].name == "Top"

    def test_no_loot_on_own_upkeep(self):
        game = create_game()
        lore = LoreholdTheHistorian(owner=None)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lore], hand=[junk])
        lore.register_triggers(game)
        p0 = game.players[0]
        game.active_player_index = 0  # p0's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _drain(game)
        # No loot on your own upkeep.
        assert game.get_hand(p0).contains(junk)
