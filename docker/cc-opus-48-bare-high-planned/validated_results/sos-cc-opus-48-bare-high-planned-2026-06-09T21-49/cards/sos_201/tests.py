"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from engine.state_based_actions import resolve_state_based_actions
from test_utils import create_game, set_board_state


class _Lifer(Instant):
    def __init__(self, name="Lifer"):
        super().__init__(name=name, mana_cost=ManaCost.parse("{R}"))

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 10


def _lib(game, pidx, cards):
    p = game.players[pidx]
    lib = p.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in cards:
        c.owner = p
        c.controller = p
        lib.add(c)


def _resolve(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _setup(game, *, hand=None, mana=None):
    p0 = game.players[0]
    lore = LoreholdTheHistorian(owner=p0, controller=p0)
    set_board_state(game, 0, battlefield=[lore], hand=hand or [], mana=mana or {})
    lore.register_triggers(game)
    return lore


class TestProperties:
    def test_static(self):
        c = LoreholdTheHistorian(owner=None)
        assert c.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert Keyword.FLYING in c.keywords
        assert Keyword.HASTE in c.keywords
        assert Supertype.LEGENDARY in c.supertypes
        assert (c.base_power, c.base_toughness) == (5, 5)


class TestMiracle:
    def test_first_instant_drawn_can_be_cast_for_two(self):
        game = create_game()
        p0 = game.players[0]
        _setup(game, mana={ManaType.COLORLESS: 2})
        _lib(game, 0, [_Lifer("Bolt")])
        p0._script.append(True)  # cast via miracle
        p0.life = 20
        draw_card(game, p0)
        _resolve(game)
        assert p0.life == 30  # bolt cast and resolved
        assert any(getattr(c, "name", "") == "Bolt"
                   for c in p0.zones[Zone.GRAVEYARD].get_all())
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0  # {2} spent

    def test_decline_miracle_keeps_card(self):
        game = create_game()
        p0 = game.players[0]
        _setup(game, mana={ManaType.COLORLESS: 2})
        _lib(game, 0, [_Lifer("Bolt")])
        p0._script.append(False)
        p0.life = 20
        draw_card(game, p0)
        _resolve(game)
        assert p0.life == 20
        assert any(getattr(c, "name", "") == "Bolt"
                   for c in p0.zones[Zone.HAND].get_all())
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

    def test_not_first_draw_no_miracle(self):
        game = create_game()
        p0 = game.players[0]
        _setup(game, mana={ManaType.COLORLESS: 2})
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        # Bear on top (drawn first, not i/s), then Bolt.
        _lib(game, 0, [_Lifer("Bolt"), bear])
        p0.life = 20
        draw_card(game, p0)  # bear — first draw, not i/s
        _resolve(game)
        draw_card(game, p0)  # bolt — second draw, no miracle
        _resolve(game)
        assert p0.life == 20
        assert any(getattr(c, "name", "") == "Bolt"
                   for c in p0.zones[Zone.HAND].get_all())


class TestLoot:
    def _fire_upkeep(self, game, active_index):
        game.active_player_index = active_index
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve(game)

    def test_loot_on_opponent_upkeep(self):
        game = create_game()
        p0 = game.players[0]
        cardA = Creature(name="ToDiscard", base_power=1, base_toughness=1)
        drawn = Creature(name="Drawn", base_power=1, base_toughness=1)
        _setup(game, hand=[cardA])
        _lib(game, 0, [drawn])
        p0._script.extend([True, cardA])  # yes, discard cardA
        self._fire_upkeep(game, 1)  # opponent's (p1) upkeep
        assert p0.zones[Zone.GRAVEYARD].contains(cardA)
        assert p0.zones[Zone.HAND].contains(drawn)

    def test_no_loot_on_own_upkeep(self):
        game = create_game()
        p0 = game.players[0]
        cardA = Creature(name="ToDiscard", base_power=1, base_toughness=1)
        _setup(game, hand=[cardA])
        _lib(game, 0, [Creature(name="Drawn", base_power=1, base_toughness=1)])
        self._fire_upkeep(game, 0)  # own upkeep → no loot
        assert p0.zones[Zone.HAND].contains(cardA)
        assert len(p0.zones[Zone.GRAVEYARD].get_all()) == 0

    def test_loot_decline(self):
        game = create_game()
        p0 = game.players[0]
        cardA = Creature(name="Keep", base_power=1, base_toughness=1)
        _setup(game, hand=[cardA])
        _lib(game, 0, [Creature(name="Drawn", base_power=1, base_toughness=1)])
        p0._script.append(False)
        self._fire_upkeep(game, 1)
        assert p0.zones[Zone.HAND].contains(cardA)
        assert len(p0.zones[Zone.HAND].get_all()) == 1
