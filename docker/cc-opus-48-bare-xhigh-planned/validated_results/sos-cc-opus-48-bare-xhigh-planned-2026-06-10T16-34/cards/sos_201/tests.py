"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class LifeGain(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "LifeGain")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))  # high real cost
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 7


def _resolve_all(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _lib_add(player, card):
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)


class TestProperties:
    def test_static(self):
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestLoot:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        return game, p1, p2, lore

    def test_opponent_upkeep_discard_and_draw(self):
        game, p1, p2, lore = self._setup()
        discard_me = Creature(name="HandCard", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lore], hand=[discard_me])
        drawn = Creature(name="Drawn", base_power=2, base_toughness=2)
        _lib_add(p1, drawn)
        game.active_player_index = 1  # opponent's turn
        p1._script.append(discard_me)  # choose to discard
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)
        assert game.get_graveyard(p1).contains(discard_me)
        assert game.get_hand(p1).contains(drawn)  # drew a card

    def test_own_upkeep_does_not_trigger(self):
        game, p1, p2, lore = self._setup()
        hand_card = Creature(name="HandCard", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lore], hand=[hand_card])
        game.active_player_index = 0  # p1's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)
        assert game.get_hand(p1).contains(hand_card)  # nothing discarded

    def test_decline_loot(self):
        game, p1, p2, lore = self._setup()
        hand_card = Creature(name="HandCard", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lore], hand=[hand_card])
        game.active_player_index = 1
        p1._script.append(None)  # decline
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)
        assert game.get_hand(p1).contains(hand_card)

    def test_empty_hand_loot_noop(self):
        game, p1, p2, lore = self._setup()
        set_board_state(game, 0, battlefield=[lore], hand=[])
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)  # must not raise / ask for a choice
        assert len(game.get_hand(p1).get_all()) == 0


class TestMiracle:
    def _setup(self, mana=None):
        game = create_game()
        p1 = game.players[0]
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore],
                        mana=mana if mana is not None else {ManaType.COLORLESS: 2})
        lore.register_triggers(game)
        game.active_player_index = 0
        game.turn_number = 1
        return game, p1, lore

    def test_first_draw_instant_cast_for_miracle(self):
        game, p1, lore = self._setup()
        inst = LifeGain(owner=None)
        _lib_add(p1, inst)
        p1._script.append(True)  # yes, cast for miracle
        draw_card(game, p1)
        _resolve_all(game)
        # Cast for its {2} miracle cost (not its {5} real cost): mana drained,
        # life gained, card resolved to graveyard.
        assert p1.mana_pool.total() == 0
        assert p1.life == 27
        assert game.get_graveyard(p1).contains(inst)

    def test_decline_miracle(self):
        game, p1, lore = self._setup()
        inst = LifeGain(owner=None)
        _lib_add(p1, inst)
        p1._script.append(False)  # decline
        draw_card(game, p1)
        _resolve_all(game)
        assert game.get_hand(p1).contains(inst)  # still in hand
        assert p1.mana_pool.total() == 2  # not spent

    def test_cannot_afford_no_miracle(self):
        game, p1, lore = self._setup(mana={ManaType.COLORLESS: 1})  # only 1
        inst = LifeGain(owner=None)
        _lib_add(p1, inst)
        draw_card(game, p1)
        _resolve_all(game)
        assert game.get_hand(p1).contains(inst)  # couldn't pay {2}

    def test_second_draw_not_eligible(self):
        game, p1, lore = self._setup()
        first = Creature(name="FirstDraw", base_power=1, base_toughness=1)
        inst = LifeGain(owner=None)
        _lib_add(p1, inst)    # bottom
        _lib_add(p1, first)   # top → drawn first
        draw_card(game, p1)   # first draw: a creature (marks first-draw)
        _resolve_all(game)
        draw_card(game, p1)   # second draw: the instant — NOT first
        _resolve_all(game)
        assert game.get_hand(p1).contains(inst)  # no miracle on 2nd draw

    def test_first_draw_noninstant_then_instant_no_miracle(self):
        game, p1, lore = self._setup()
        creature = Creature(name="C", base_power=1, base_toughness=1)
        _lib_add(p1, creature)
        p1._script.append(True)  # would say yes, but should never be asked
        draw_card(game, p1)  # first draw is a creature → no miracle
        _resolve_all(game)
        assert game.get_hand(p1).contains(creature)
        # the scripted True was not consumed (no miracle prompt)
        assert p1.remaining_choices == 1
