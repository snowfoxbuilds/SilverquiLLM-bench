"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.game import draw_card
from engine.turn import run_turn
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state


class ZapBolt(Instant):
    """Targetless instant: deals 2 damage to the opponent of its controller."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Zap Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        for p in game.players:
            if p is not self.controller:
                p.life -= 2


def _filler(player, n=3):
    out = []
    for i in range(n):
        c = Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        c.owner = c.controller = player
        out.append(c)
    return out


def _lorehold_on_battlefield(game, player_index=0):
    lh = LoreholdTheHistorian()
    set_board_state(game, player_index, battlefield=[lh])
    lh.register_triggers(game)  # set_board_state skips ETB hooks
    return lh


class TestLoreholdTheHistorian:
    def test_keywords(self):
        kw = LoreholdTheHistorian().keywords
        assert Keyword.FLYING in kw and Keyword.HASTE in kw

    def test_opponent_upkeep_loot(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold_on_battlefield(game, 0)
        spare = Creature(name="Spare Card", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[spare])
        for c in _filler(p0):
            p0.zones[Zone.LIBRARY].add(c)
        for c in _filler(p1):
            p1.zones[Zone.LIBRARY].add(c)
        # Run the opponent's turn — the loot trigger fires at their upkeep.
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        p1._script.append("pass")
        p0._script.extend(["pass", spare])  # pass priority; discard Spare Card
        run_turn(game)
        assert p0.zones[Zone.GRAVEYARD].contains(spare)
        assert len(p0.zones[Zone.HAND]) == 1  # drew a replacement

    def test_no_loot_on_own_upkeep(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold_on_battlefield(game, 0)
        spare = Creature(name="Spare Card", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[spare])
        for c in _filler(p0):
            p0.zones[Zone.LIBRARY].add(c)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        p0._script.append(None)  # declare no attackers with Lorehold
        run_turn(game)  # own turn: no loot trigger
        assert not p0.zones[Zone.GRAVEYARD].contains(spare)

    def test_miracle_first_drawn_instant(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold_on_battlefield(game, 0)
        bolt = ZapBolt()
        bolt.owner = bolt.controller = p0
        p0.zones[Zone.LIBRARY].add(bolt)  # on top
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p0._script.append(True)  # yes, cast for miracle {2}
        draw_card(game, p0)
        assert len(game.stack) == 1  # miracle trigger
        while not game.stack.is_empty():
            resolve_top(game)
        assert p1.life == 18  # cast off the miracle trigger
        assert p0.mana_pool.total() == 0  # paid {2}
        assert p0.zones[Zone.GRAVEYARD].contains(bolt)

    def test_no_miracle_on_second_draw(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold_on_battlefield(game, 0)
        first = Creature(name="First Drawn", base_power=1, base_toughness=1)
        bolt = ZapBolt()
        for c in (bolt, first):  # 'first' ends up on top
            c.owner = c.controller = p0
            p0.zones[Zone.LIBRARY].add(c)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p0)  # creature: no miracle trigger
        assert game.stack.is_empty()
        draw_card(game, p0)  # bolt, but it's the second draw
        assert game.stack.is_empty()
        assert p1.life == 20

    def test_miracle_declined_card_stays_in_hand(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold_on_battlefield(game, 0)
        bolt = ZapBolt()
        bolt.owner = bolt.controller = p0
        p0.zones[Zone.LIBRARY].add(bolt)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p0._script.append(False)  # decline
        draw_card(game, p0)
        while not game.stack.is_empty():
            resolve_top(game)
        assert p0.zones[Zone.HAND].contains(bolt)
        assert p0.mana_pool.total() == 2  # nothing paid
        assert p1.life == 20
