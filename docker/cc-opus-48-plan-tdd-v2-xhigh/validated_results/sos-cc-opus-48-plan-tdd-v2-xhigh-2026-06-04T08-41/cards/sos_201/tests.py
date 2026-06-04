"""Tests for Lorehold, the Historian (SOS 201)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.events import (
    BeginningOfUpkeepTriggeredEvent,
)
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class _GainLifeInstant(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Surge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _add_to_library(player, card):
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)


class TestProperties:
    def test_static_data(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestLoot:
    def _setup(self, game, p1, *, hand):
        dragon = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[dragon], hand=hand)
        dragon.register_triggers(game)
        return dragon

    def test_loot_on_opponent_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        discard_me = Creature(name="Pitch", base_power=1, base_toughness=1)
        self._setup(game, p1, hand=[discard_me])
        drawn = Creature(name="Drawn", base_power=2, base_toughness=2)
        _add_to_library(p1, drawn)
        game.active_player_index = 1  # opponent's turn
        p1._script.extend([True, discard_me])
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert game.get_graveyard(p1).contains(discard_me)
        assert game.get_hand(p1).contains(drawn)

    def test_no_loot_on_own_upkeep(self) -> None:
        game = create_game()
        p1, _ = game.players
        discard_me = Creature(name="Pitch", base_power=1, base_toughness=1)
        self._setup(game, p1, hand=[discard_me])
        game.active_player_index = 0  # controller's own turn
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert game.get_hand(p1).contains(discard_me)
        assert p1.remaining_choices == 0

    def test_loot_decline(self) -> None:
        game = create_game()
        p1, _ = game.players
        discard_me = Creature(name="Pitch", base_power=1, base_toughness=1)
        self._setup(game, p1, hand=[discard_me])
        game.active_player_index = 1
        p1._script.append(False)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert game.get_hand(p1).contains(discard_me)

    def test_loot_no_cards_in_hand(self) -> None:
        game = create_game()
        p1, _ = game.players
        self._setup(game, p1, hand=[])
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert p1.remaining_choices == 0


class TestMiracle:
    def _setup(self, game, p1):
        dragon = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[dragon])
        dragon.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        game.active_player_index = 0
        return dragon

    def test_miracle_cast_first_instant(self) -> None:
        game = create_game()
        p1, _ = game.players
        self._setup(game, p1)
        p1.life = 20
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        surge = _GainLifeInstant(owner=p1, controller=p1)
        _add_to_library(p1, surge)
        p1._script.append(True)  # yes, cast for miracle
        draw_card(game, p1)
        _resolve_stack(game)
        assert p1.life == 23
        assert p1.mana_pool.total() == 0
        assert game.get_graveyard(p1).contains(surge)

    def test_miracle_decline_keeps_card(self) -> None:
        game = create_game()
        p1, _ = game.players
        self._setup(game, p1)
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        surge = _GainLifeInstant(owner=p1, controller=p1)
        _add_to_library(p1, surge)
        p1._script.append(False)
        draw_card(game, p1)
        _resolve_stack(game)
        assert game.get_hand(p1).contains(surge)
        assert p1.mana_pool.total() == 2

    def test_miracle_only_first_draw(self) -> None:
        game = create_game()
        p1, _ = game.players
        self._setup(game, p1)
        p1.cards_drawn_this_turn = 1  # already drew one this turn
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        surge = _GainLifeInstant(owner=p1, controller=p1)
        _add_to_library(p1, surge)
        draw_card(game, p1)  # this is the second draw
        _resolve_stack(game)
        assert game.get_hand(p1).contains(surge)
        assert p1.remaining_choices == 0

    def test_miracle_only_instant_sorcery(self) -> None:
        game = create_game()
        p1, _ = game.players
        self._setup(game, p1)
        beast = Creature(name="Beast", base_power=2, base_toughness=2)
        _add_to_library(p1, beast)
        draw_card(game, p1)
        _resolve_stack(game)
        assert game.get_hand(p1).contains(beast)
        assert p1.remaining_choices == 0
