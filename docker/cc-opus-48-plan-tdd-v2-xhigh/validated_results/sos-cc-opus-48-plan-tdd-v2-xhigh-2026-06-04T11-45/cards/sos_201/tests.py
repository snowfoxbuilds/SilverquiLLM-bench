"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class _Bolt(Sorcery):
    """A simple sorcery that deals 3 damage to a fixed victim on resolve."""

    def __init__(self, victim: Any = None, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)
        self._victim = victim

    def on_resolve(self, game: Any) -> None:
        if self._victim is not None:
            self._victim.life -= 3


def _drain(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestLoreholdProperties:
    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_cost(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert c.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_pt(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert c.base_power == 5 and c.base_toughness == 5

    def test_keywords(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.HASTE in c.keywords

    def test_legendary_elder_dragon(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in c.supertypes
        assert {"Elder", "Dragon"} <= c.subtypes


class TestLoreholdMiracle:
    def test_miracle_first_draw_inst_sorc(self) -> None:
        game = create_game(scripts=([True], []))
        p1, p2 = game.players
        lh = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lh], mana={ManaType.RED: 2})
        lh.register_triggers(game)

        bolt = _Bolt(victim=p2)
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.LIBRARY].add(bolt)

        game.active_player_index = 0
        draw_card(game, p1)
        _drain(game)

        assert p2.life == 17
        assert game.get_graveyard(p1).contains(bolt)
        assert p1.mana_pool.total() == 0

    def test_miracle_not_on_second_draw(self) -> None:
        game = create_game(scripts=([True], []))
        p1, p2 = game.players
        lh = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lh], mana={ManaType.RED: 2})
        lh.register_triggers(game)

        bolt = _Bolt(victim=p2)
        bolt.owner = p1
        bolt.controller = p1
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        bear.owner = p1
        bear.controller = p1
        lib = p1.zones[Zone.LIBRARY]
        lib.add(bolt)   # drawn second
        lib.add(bear)   # on top, drawn first

        game.active_player_index = 0
        draw_card(game, p1)   # bear — first draw, not inst/sorc
        _drain(game)
        draw_card(game, p1)   # bolt — second draw, miracle must NOT fire
        _drain(game)

        assert p2.life == 20

    def test_miracle_not_for_noncaster(self) -> None:
        # An opponent's draw should never trigger our miracle.
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        lh = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lh], mana={ManaType.RED: 2})
        lh.register_triggers(game)

        bolt = _Bolt(victim=p1)
        bolt.owner = p2
        bolt.controller = p2
        p2.zones[Zone.LIBRARY].add(bolt)

        game.active_player_index = 1
        draw_card(game, p2)
        _drain(game)

        assert p1.life == 20


class TestLoreholdLoot:
    def test_loot_on_opponent_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lh = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lh])

        discardable = Creature(name="Discardable", base_power=1, base_toughness=1)
        discardable.owner = p1
        discardable.controller = p1
        p1.zones[Zone.HAND].add(discardable)
        drawn = Creature(name="Drawn", base_power=2, base_toughness=2)
        drawn.owner = p1
        drawn.controller = p1
        p1.zones[Zone.LIBRARY].add(drawn)

        lh.register_triggers(game)
        game.active_player_index = 1  # p2's upkeep
        p1._script.append(True)
        p1._script.append(discardable)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _drain(game)

        assert game.get_graveyard(p1).contains(discardable)
        assert game.get_hand(p1).contains(drawn)

    def test_decline_loot(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lh = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lh])

        card = Creature(name="Keep", base_power=1, base_toughness=1)
        card.owner = p1
        card.controller = p1
        p1.zones[Zone.HAND].add(card)

        lh.register_triggers(game)
        game.active_player_index = 1
        p1._script.append(False)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _drain(game)

        assert game.get_hand(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)

    def test_no_loot_on_own_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lh = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lh])

        card = Creature(name="Held", base_power=1, base_toughness=1)
        card.owner = p1
        card.controller = p1
        p1.zones[Zone.HAND].add(card)

        lh.register_triggers(game)
        game.active_player_index = 0  # p1's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _drain(game)

        assert game.get_hand(p1).contains(card)
        assert not game.get_graveyard(p1).contains(card)
