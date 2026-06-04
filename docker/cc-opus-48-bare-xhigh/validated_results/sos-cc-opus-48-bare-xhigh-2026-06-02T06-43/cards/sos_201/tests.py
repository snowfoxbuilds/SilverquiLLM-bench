"""Tests for Lorehold, the Historian (SOS 201)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import (
    MIRACLE_COST,
    LoreholdTheHistorian,
    cast_for_miracle,
)
from engine.card import Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import card_colors, create_game, set_board_state


class _Bolt(Instant):
    def __init__(self, name: str = "Bolt", **kwargs: Any) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        game._resolved = getattr(game, "_resolved", 0) + 1


def _vanilla(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _resolve_stack(game: Any) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


def _to_library(player: Any, card: Any) -> None:
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)


class TestLoreholdProperties:
    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.power == 5 and card.toughness == 5

    def test_flying_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_legendary_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes and "Dragon" in card.subtypes

    def test_red_white(self) -> None:
        assert card_colors(LoreholdTheHistorian(owner=None)) == {"R", "W"}

    def test_registers_two_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lore = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        assert len(game.trigger_manager.get_triggers_for_source(lore)) == 2


class TestMiracle:
    def _setup(self, scripts, mana=None):
        game = create_game(scripts=(scripts, []))
        p1 = game.players[0]
        lore = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lore], mana=mana or {})
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        return game, p1, lore

    def test_first_drawn_instant_castable_for_miracle(self) -> None:
        game, p1, lore = self._setup([True], mana={ManaType.COLORLESS: 2})
        bolt = _Bolt()
        _to_library(p1, bolt)
        draw_card(game, p1)
        _resolve_stack(game)
        assert game._resolved == 1
        assert p1.zones[Zone.GRAVEYARD].contains(bolt)
        assert p1.mana_pool.total() == 0

    def test_decline_keeps_card_in_hand(self) -> None:
        game, p1, lore = self._setup([False], mana={ManaType.COLORLESS: 2})
        bolt = _Bolt()
        _to_library(p1, bolt)
        draw_card(game, p1)
        _resolve_stack(game)
        assert getattr(game, "_resolved", 0) == 0
        assert p1.zones[Zone.HAND].contains(bolt)
        assert p1.mana_pool.total() == 2  # nothing spent

    def test_no_miracle_when_cannot_pay(self) -> None:
        game, p1, lore = self._setup([True], mana={})  # no mana
        bolt = _Bolt()
        _to_library(p1, bolt)
        draw_card(game, p1)
        _resolve_stack(game)
        assert getattr(game, "_resolved", 0) == 0
        assert p1.zones[Zone.HAND].contains(bolt)

    def test_no_miracle_for_noninstant(self) -> None:
        game, p1, lore = self._setup([], mana={ManaType.COLORLESS: 2})
        bear = _vanilla()
        _to_library(p1, bear)
        draw_card(game, p1)
        _resolve_stack(game)
        assert p1.zones[Zone.HAND].contains(bear)
        assert game.stack.is_empty()

    def test_no_miracle_when_not_first_draw(self) -> None:
        game, p1, lore = self._setup([], mana={ManaType.COLORLESS: 2})
        p1.cards_drawn_this_turn = 3  # already drew earlier this turn
        bolt = _Bolt()
        _to_library(p1, bolt)
        draw_card(game, p1)
        _resolve_stack(game)
        assert p1.zones[Zone.HAND].contains(bolt)
        assert game.stack.is_empty()

    def test_cast_for_miracle_helper(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bolt = _Bolt()
        set_board_state(game, 0, hand=[bolt], mana={ManaType.COLORLESS: 2})
        assert cast_for_miracle(game, p1, bolt, MIRACLE_COST) is True
        _resolve_stack(game)
        assert game._resolved == 1
        assert p1.mana_pool.total() == 0


class TestLoot:
    def _setup(self, scripts):
        game = create_game(scripts=(scripts, []))
        p1, p2 = game.players
        lore = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lore])
        lore.register_triggers(game)
        return game, p1, p2, lore

    def test_loots_on_opponent_upkeep(self) -> None:
        game, p1, p2, lore = self._setup([True])
        to_discard = _vanilla("Discard")
        set_board_state(game, 0, battlefield=[lore], hand=[to_discard])
        drawn = _vanilla("Drawn")
        _to_library(p1, drawn)
        game.active_player_index = 1  # opponent's turn
        game.players[0]._script.append(to_discard)  # choose_card answer
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(to_discard)
        assert p1.zones[Zone.HAND].contains(drawn)

    def test_no_loot_on_own_upkeep(self) -> None:
        game, p1, p2, lore = self._setup([])
        set_board_state(game, 0, battlefield=[lore], hand=[_vanilla("H")])
        game.active_player_index = 0  # your own turn
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()

    def test_decline_loot(self) -> None:
        game, p1, p2, lore = self._setup([False])
        keep = _vanilla("Keep")
        set_board_state(game, 0, battlefield=[lore], hand=[keep])
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert p1.zones[Zone.HAND].contains(keep)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0

    def test_loot_empty_hand_no_crash(self) -> None:
        game, p1, p2, lore = self._setup([])
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_stack(game)
        assert len(p1.zones[Zone.HAND]) == 0
