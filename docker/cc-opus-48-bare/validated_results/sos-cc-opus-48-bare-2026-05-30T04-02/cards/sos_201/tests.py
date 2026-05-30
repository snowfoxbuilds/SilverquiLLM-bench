"""Tests for SOS 201 — Lorehold, the Historian (miracle + loot)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


def _lorehold(player: Any) -> LoreholdTheHistorian:
    return LoreholdTheHistorian(owner=player, controller=player)


def _instant(player: Any, name: str = "Bolt", cmc: int = 1) -> Instant:
    return Instant(
        name=name, owner=player, controller=player, mana_cost=ManaCost(generic=cmc)
    )


def _sorcery(player: Any, name: str = "Quake", cmc: int = 3) -> Sorcery:
    return Sorcery(
        name=name, owner=player, controller=player, mana_cost=ManaCost(generic=cmc)
    )


def _creature(player: Any, name: str = "Bear") -> Creature:
    return Creature(
        name=name, owner=player, controller=player, base_power=2, base_toughness=2
    )


def _set_library(player: Any, cards: list[Any]) -> None:
    """Replace a player's library; the last item is the top card."""
    library = player.zones[Zone.LIBRARY]
    for obj in library.get_all():
        library.remove(obj)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _resolve_stack(game: Any) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestLoreholdProperties:
    def test_name(self) -> None:
        assert LoreholdTheHistorian().name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian().mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_toughness(self) -> None:
        c = LoreholdTheHistorian()
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_types_and_subtypes(self) -> None:
        c = LoreholdTheHistorian()
        assert CardType.CREATURE in c.card_types
        assert {"Elder", "Dragon"} <= c.subtypes

    def test_legendary(self) -> None:
        assert Supertype.LEGENDARY in LoreholdTheHistorian().supertypes

    def test_keywords(self) -> None:
        c = LoreholdTheHistorian()
        assert Keyword.FLYING in c.keywords
        assert Keyword.HASTE in c.keywords

    def test_colors(self) -> None:
        assert LoreholdTheHistorian().colors == ["R", "W"]


class TestMiracle:
    def _setup(
        self, game: Any, p1: Any, *, drawn_before: int = 0, mana: int = 2
    ) -> LoreholdTheHistorian:
        lorehold = _lorehold(p1)
        mana_dict = {ManaType.RED: mana} if mana > 0 else {}
        set_board_state(game, 0, battlefield=[lorehold], mana=mana_dict)
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = drawn_before
        return lorehold

    def test_first_drawn_instant_can_be_cast_for_two(self) -> None:
        game = create_game(scripts=([True], []))  # accept the miracle cast
        p1, _ = game.players
        self._setup(game, p1, drawn_before=0, mana=2)
        bolt = _instant(p1, "Bolt", 1)
        _set_library(p1, [bolt])

        draw_card(game, p1)
        _resolve_stack(game)

        assert not p1.zones[Zone.HAND].contains(bolt)
        assert p1.zones[Zone.GRAVEYARD].contains(bolt)
        assert p1.mana_pool.get(ManaType.RED) == 0  # paid the {2} miracle cost

    def test_sorcery_also_qualifies(self) -> None:
        game = create_game(scripts=([True], []))
        p1, _ = game.players
        self._setup(game, p1, drawn_before=0, mana=2)
        quake = _sorcery(p1, "Quake", 3)
        _set_library(p1, [quake])

        draw_card(game, p1)
        _resolve_stack(game)

        assert p1.zones[Zone.GRAVEYARD].contains(quake)

    def test_declined_miracle_keeps_card_in_hand(self) -> None:
        game = create_game(scripts=([False], []))  # decline the cast
        p1, _ = game.players
        self._setup(game, p1, drawn_before=0, mana=2)
        bolt = _instant(p1)
        _set_library(p1, [bolt])

        draw_card(game, p1)
        _resolve_stack(game)

        assert p1.zones[Zone.HAND].contains(bolt)
        assert p1.mana_pool.get(ManaType.RED) == 2  # nothing was paid

    def test_no_miracle_on_second_draw(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        # This turn already saw one draw; the next draw is the second.
        self._setup(game, p1, drawn_before=1, mana=2)
        bolt = _instant(p1)
        _set_library(p1, [bolt])

        draw_card(game, p1)
        _resolve_stack(game)

        assert p1.zones[Zone.HAND].contains(bolt)

    def test_no_miracle_for_noncastable_type(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        self._setup(game, p1, drawn_before=0, mana=2)
        bear = _creature(p1)
        _set_library(p1, [bear])

        draw_card(game, p1)
        _resolve_stack(game)

        assert p1.zones[Zone.HAND].contains(bear)

    def test_no_miracle_without_mana(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        self._setup(game, p1, drawn_before=0, mana=0)
        bolt = _instant(p1)
        _set_library(p1, [bolt])

        draw_card(game, p1)
        _resolve_stack(game)

        assert p1.zones[Zone.HAND].contains(bolt)

    def test_no_miracle_when_lorehold_not_on_battlefield(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        lorehold = _lorehold(p1)
        set_board_state(game, 0, hand=[lorehold], mana={ManaType.RED: 2})
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        bolt = _instant(p1)
        _set_library(p1, [bolt])

        draw_card(game, p1)
        _resolve_stack(game)

        assert p1.zones[Zone.HAND].contains(bolt)


class TestLoot:
    def _setup(
        self, game: Any, p1: Any, *, hand: list[Any], library: list[Any]
    ) -> LoreholdTheHistorian:
        lorehold = _lorehold(p1)
        set_board_state(game, 0, battlefield=[lorehold], hand=hand)
        _set_library(p1, library)
        lorehold.register_triggers(game)
        return lorehold

    def test_loots_on_opponent_upkeep(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        to_discard = _creature(p1, "Discard")
        to_draw = _creature(p1, "Draw")
        self._setup(game, p1, hand=[to_discard], library=[to_draw])
        p1._script.append(True)  # accept the loot
        p1._script.append(to_discard)  # choose the card to discard

        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent(player=p2)
        )
        _resolve_stack(game)

        assert p1.zones[Zone.GRAVEYARD].contains(to_discard)
        assert p1.zones[Zone.HAND].contains(to_draw)

    def test_no_loot_on_own_upkeep(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        to_discard = _creature(p1, "Discard")
        to_draw = _creature(p1, "Draw")
        self._setup(game, p1, hand=[to_discard], library=[to_draw])

        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent(player=p1)
        )
        _resolve_stack(game)

        assert p1.zones[Zone.HAND].contains(to_discard)
        assert p1.zones[Zone.LIBRARY].contains(to_draw)

    def test_declined_loot_does_nothing(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        to_discard = _creature(p1, "Discard")
        to_draw = _creature(p1, "Draw")
        self._setup(game, p1, hand=[to_discard], library=[to_draw])
        p1._script.append(False)  # decline the loot

        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent(player=p2)
        )
        _resolve_stack(game)

        assert p1.zones[Zone.HAND].contains(to_discard)
        assert p1.zones[Zone.LIBRARY].contains(to_draw)

    def test_no_loot_with_empty_hand(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        to_draw = _creature(p1, "Draw")
        self._setup(game, p1, hand=[], library=[to_draw])

        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent(player=p2)
        )
        _resolve_stack(game)

        # Nothing in hand to discard → no draw happens.
        assert p1.zones[Zone.LIBRARY].contains(to_draw)
        assert len(p1.zones[Zone.HAND]) == 0
