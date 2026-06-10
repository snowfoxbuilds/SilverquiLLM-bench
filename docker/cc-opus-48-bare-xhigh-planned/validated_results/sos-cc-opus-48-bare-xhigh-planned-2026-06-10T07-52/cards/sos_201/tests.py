"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import CardImpl, Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.state_based_actions import resolve_state_based_actions
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class _Zap(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))  # 5 normally
        super().__init__(**kwargs)

    def get_targets(self, game):
        players = set(game.players)
        return [TargetRequirement(filter_fn=lambda o: o in players,
                                  description="player", zone=Zone.BATTLEFIELD)]

    def on_resolve(self, game):
        from engine.game import deal_damage

        t = (getattr(self, "chosen_targets", []) or [None])[0]
        if t is not None:
            deal_damage(game, self, t, 3)


def _resolve_all(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _lib_add(game, idx, cards_bottom_to_top):
    lib = game.players[idx].zones[Zone.LIBRARY]
    for c in cards_bottom_to_top:
        c.owner = game.players[idx]
        c.controller = game.players[idx]
        lib.add(c)


class TestProperties:
    def test_static(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")


class TestMiracle:
    def test_first_draw_instant_castable_for_two(self) -> None:
        game = create_game()
        p0, p1 = game.players
        lore = LoreholdTheHistorian(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        lore.register_triggers(game)
        zap = _Zap(owner=p0, controller=p0)
        _lib_add(game, 0, [zap])  # top of library

        drawn = draw_card(game, p0)  # first draw of the turn
        assert drawn is zap
        # Miracle trigger on the stack; resolve: yes-cast, target p1.
        p0._script.extend([True, p1])
        _resolve_all(game)
        assert p1.life == 17  # Zap (3 dmg) cast for the {2} miracle cost
        assert game.get_graveyard(p0).contains(zap)  # cast → graveyard
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0  # paid {2}

    def test_decline_keeps_card(self) -> None:
        game = create_game()
        p0, p1 = game.players
        lore = LoreholdTheHistorian(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        lore.register_triggers(game)
        zap = _Zap(owner=p0, controller=p0)
        _lib_add(game, 0, [zap])
        draw_card(game, p0)
        p0._script.extend([False])  # decline miracle
        _resolve_all(game)
        assert game.get_hand(p0).contains(zap)  # stays in hand
        assert p1.life == 20

    def test_not_first_draw_no_miracle(self) -> None:
        game = create_game()
        p0, p1 = game.players
        lore = LoreholdTheHistorian(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        lore.register_triggers(game)
        dummy = CardImpl(name="Dummy")
        zap = _Zap(owner=p0, controller=p0)
        # top→ dummy drawn first (uses up "first draw"), then zap
        _lib_add(game, 0, [zap, dummy])  # bottom=zap, top=dummy
        draw_card(game, p0)  # draws dummy (first) — not instant/sorcery
        draw_card(game, p0)  # draws zap (second) — no miracle
        _resolve_all(game)
        assert game.get_hand(p0).contains(zap)  # not cast
        assert p1.life == 20


class TestLoot:
    def test_opponent_upkeep_loot(self) -> None:
        game = create_game()
        p0, p1 = game.players
        lore = LoreholdTheHistorian(owner=p0, controller=p0)
        discardable = CardImpl(name="ToDiscard")
        set_board_state(game, 0, battlefield=[lore], hand=[discardable])
        lore.register_triggers(game)
        future = CardImpl(name="ToDraw")
        _lib_add(game, 0, [future])
        # Opponent's (p1) upkeep.
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        p0._script.extend([discardable])  # choose to discard it
        _resolve_all(game)
        assert game.get_graveyard(p0).contains(discardable)
        assert game.get_hand(p0).contains(future)  # drew a card

    def test_not_on_your_own_upkeep(self) -> None:
        game = create_game()
        p0, p1 = game.players
        lore = LoreholdTheHistorian(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[lore], hand=[CardImpl(name="X")])
        lore.register_triggers(game)
        # Your own (p0) upkeep — should not trigger.
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()
