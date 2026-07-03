"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.turn import run_turn
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state


def _stock_library(game, player_index, cards):
    player = game.players[player_index]
    for c in cards:
        c.owner = player
        c.controller = player
        player.zones[Zone.LIBRARY].add(c)


def _lorehold_on_battlefield(game, player_index=0):
    lh = LoreholdTheHistorian(owner=None)
    set_board_state(game, player_index, battlefield=[lh])
    lh.register_triggers(game)
    return lh


class TestMiracle:
    def test_first_drawn_instant_may_be_miracle_cast(self):
        game = create_game(scripts=([], ["pass"] * 6))
        p1 = game.players[0]
        _lorehold_on_battlefield(game)
        inst = Instant(name="Bolt of Insight", mana_cost=ManaCost.parse("{4}{R}"))
        _stock_library(game, 0, [inst])
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        draw_card(game, p1)
        # pass, pass -> trigger resolves -> yes to miracle; then drain.
        p1._script.extend(["pass", True] + ["pass"] * 5)
        priority_loop(game)

        assert p1.zones[Zone.GRAVEYARD].contains(inst)   # cast + resolved
        assert p1.mana_pool.total() == 0                  # {2} deducted

    def test_second_draw_no_miracle(self):
        game = create_game(scripts=([], ["pass"] * 6))
        p1 = game.players[0]
        _lorehold_on_battlefield(game)
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        inst = Instant(name="Trick", mana_cost=ManaCost.parse("{4}{R}"))
        _stock_library(game, 0, [inst, filler])  # top: filler, then inst
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        draw_card(game, p1)   # first draw: a creature — no miracle
        draw_card(game, p1)   # second draw: the instant — not first
        priority_loop(game)

        assert p1.zones[Zone.HAND].contains(inst)
        assert game.stack.is_empty()
        assert p1.mana_pool.total() == 2

    def test_miracle_decline_keeps_card_in_hand(self):
        game = create_game(scripts=([], ["pass"] * 6))
        p1 = game.players[0]
        _lorehold_on_battlefield(game)
        inst = Instant(name="Trick", mana_cost=ManaCost.parse("{4}{R}"))
        _stock_library(game, 0, [inst])
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        draw_card(game, p1)
        p1._script.extend(["pass", False] + ["pass"] * 5)
        priority_loop(game)

        assert p1.zones[Zone.HAND].contains(inst)
        assert p1.mana_pool.total() == 2

    def test_no_mana_no_miracle_prompt(self):
        game = create_game(scripts=([], ["pass"] * 6))
        p1 = game.players[0]
        _lorehold_on_battlefield(game)
        inst = Instant(name="Trick", mana_cost=ManaCost.parse("{4}{R}"))
        _stock_library(game, 0, [inst])

        draw_card(game, p1)
        p1._script.extend(["pass"] * 6)
        priority_loop(game)

        assert p1.zones[Zone.HAND].contains(inst)


class TestUpkeepLoot:
    def _turn_setup(self):
        """P2 about to take a turn; P1 controls Lorehold."""
        game = create_game(scripts=(["pass"] * 30, ["pass"] * 30))
        p1, p2 = game.players
        game.active_player_index = 1
        game.priority_player_index = 1
        game._normal_next_index = 0
        keep = Instant(name="Keep", mana_cost=ManaCost.parse("{R}"))
        toss = Creature(name="Toss", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[keep, toss])
        _lorehold_on_battlefield(game, 0)
        _stock_library(game, 0, [Creature(name="Lib1", base_power=1, base_toughness=1)])
        _stock_library(game, 1, [Creature(name="Lib2", base_power=1, base_toughness=1)])
        return game, p1, p2, keep, toss

    def test_discard_to_draw_on_opponent_upkeep(self):
        game, p1, p2, keep, toss = self._turn_setup()
        # During p2's upkeep: p2 passes, p1 passes, trigger asks choose_card.
        from collections import deque
        p1._script = deque(["pass", toss] + ["pass"] * 30)
        run_turn(game)

        assert p1.zones[Zone.GRAVEYARD].contains(toss)
        assert len(p1.zones[Zone.HAND]) == 2          # drew Lib1
        assert p1.zones[Zone.HAND].contains(keep)

    def test_decline_loot(self):
        game, p1, p2, keep, toss = self._turn_setup()
        from collections import deque
        p1._script = deque(["pass", None] + ["pass"] * 30)
        run_turn(game)

        assert len(p1.zones[Zone.GRAVEYARD]) == 0
        assert len(p1.zones[Zone.HAND]) == 2          # unchanged

    def test_no_trigger_on_own_upkeep(self):
        game = create_game(scripts=(["pass"] * 30, ["pass"] * 30))
        p1 = game.players[0]
        toss = Creature(name="Toss", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[toss])
        lh = _lorehold_on_battlefield(game, 0)
        _stock_library(game, 0, [Creature(name="Lib1", base_power=1, base_toughness=1)])
        _stock_library(game, 1, [Creature(name="Lib2", base_power=1, base_toughness=1)])
        run_turn(game)  # p1's own turn

        assert len(p1.zones[Zone.GRAVEYARD]) == 0     # loot never offered
        assert Keyword.HASTE in lh.keywords and Keyword.FLYING in lh.keywords
