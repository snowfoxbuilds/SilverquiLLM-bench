"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.casting import resolve_top
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class TestProperties:
    def test_basics(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert c.name == "Lorehold, the Historian"
        assert c.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert c.base_power == 5 and c.base_toughness == 5
        assert Supertype.LEGENDARY in c.supertypes
        assert {"Elder", "Dragon"} <= c.subtypes
        assert c.keywords & Keyword.FLYING
        assert c.keywords & Keyword.HASTE


class TestMiracle:
    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        set_board_state(
            game, 0, battlefield=[lore], hand=[bolt], mana={ManaType.COLORLESS: 2}
        )
        lore.register_triggers(game)
        return game, p1, lore, bolt

    def test_miracle_casts_for_two(self) -> None:
        game, p1, lore, bolt = self._setup()
        p1._script.extend([True])  # cast for miracle cost
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=bolt)
        )
        resolve_top(game)  # resolve the miracle trigger
        assert bolt not in p1.zones[Zone.HAND].get_all()
        assert p1.mana_pool.total() == 0  # paid {2}
        assert not game.stack.is_empty()

    def test_decline_miracle(self) -> None:
        game, p1, lore, bolt = self._setup()
        p1._script.extend([False])  # decline
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=bolt)
        )
        resolve_top(game)
        assert bolt in p1.zones[Zone.HAND].get_all()
        assert p1.mana_pool.total() == 2

    def test_no_miracle_for_noncreature_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[lore], hand=[bear])
        lore.register_triggers(game)
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=bear)
        )
        # A creature draw does not have miracle — no trigger queued.
        assert game.stack.is_empty()


class TestLoot:
    def test_loot_on_opponent_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        keep = Instant(name="Keep", mana_cost=ManaCost.parse("{1}"))
        toss = Instant(name="Toss", mana_cost=ManaCost.parse("{2}"))
        set_board_state(game, 0, battlefield=[lore], hand=[keep, toss])
        # A non-instant/sorcery card to draw so it can't re-trigger miracle.
        top = Creature(name="Top", base_power=1, base_toughness=1)
        top.owner = p1
        p1.zones[Zone.LIBRARY].add(top)
        lore.register_triggers(game)
        # Opponent's turn.
        game.active_player_index = 1
        p1._script.extend([True, toss])  # discard, choose Toss
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        resolve_top(game)
        assert toss in p1.zones[Zone.GRAVEYARD].get_all()
        assert top in p1.zones[Zone.HAND].get_all()  # drew the replacement

    def test_no_loot_on_own_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore], hand=[Instant(name="X")])
        lore.register_triggers(game)
        game.active_player_index = 0  # controller's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()
