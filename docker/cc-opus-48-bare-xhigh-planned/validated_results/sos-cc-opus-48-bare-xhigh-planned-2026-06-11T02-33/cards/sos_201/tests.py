"""Tests for SOS 201 — Lorehold, the Historian (miracle + opponent-upkeep loot)."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Land
from engine.casting import resolve_top
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class Bolt(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        opp = [p for p in game.players if p is not self.controller][0]
        deal_damage(game, self, opp, 3)


def _lorehold(game):
    lh = LoreholdTheHistorian(owner=None)
    set_board_state(game, 0, battlefield=[lh])
    lh.register_triggers(game)
    return lh


def _lib_push(game, idx, card):
    game.players[idx].zones[Zone.LIBRARY].add(card)


class TestProperties:
    def test_basic(self):
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords and Keyword.HASTE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestMiracle:
    def test_first_draw_instant_castable_for_two(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold(game)
        _lib_push(game, 0, Bolt(owner=None))
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p0._script.append(True)  # yes, miracle-cast
        draw_card(game, p0)
        resolve_top(game)  # miracle trigger → casts Bolt
        resolve_top(game)  # Bolt resolves
        assert p1.life == 17
        assert any(c.name == "Bolt" for c in game.get_graveyard(p0).get_all())
        assert p0.mana_pool.total() == 0  # paid {2}

    def test_decline_miracle_keeps_card(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold(game)
        _lib_push(game, 0, Bolt(owner=None))
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p0._script.append(False)  # decline
        draw_card(game, p0)
        resolve_top(game)
        assert any(c.name == "Bolt" for c in game.get_hand(p0).get_all())
        assert p1.life == 20

    def test_not_first_draw_no_miracle(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold(game)
        # First draw is a land; second draw is an instant.
        _lib_push(game, 0, Bolt(owner=None))   # bottom (drawn 2nd)
        _lib_push(game, 0, Land(name="Waste"))  # top (drawn 1st)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p0)  # land — consumes the "first draw" slot
        draw_card(game, p0)  # bolt — not the first draw → no miracle
        assert game.stack.is_empty()  # no miracle trigger
        assert any(c.name == "Bolt" for c in game.get_hand(p0).get_all())

    def test_non_instant_first_draw_no_miracle(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold(game)
        _lib_push(game, 0, Creature(name="Dog", base_power=2, base_toughness=2))
        draw_card(game, p0)
        assert game.stack.is_empty()
        assert any(c.name == "Dog" for c in game.get_hand(p0).get_all())

    def test_cannot_afford_miracle(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold(game)
        _lib_push(game, 0, Bolt(owner=None))
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})  # only 1, need 2
        draw_card(game, p0)
        resolve_top(game)  # miracle trigger → can't pay → no cast
        assert any(c.name == "Bolt" for c in game.get_hand(p0).get_all())
        assert p1.life == 20


def _fire_upkeep(game, active_index):
    game.active_player_index = active_index
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())


class TestLoot:
    def test_loot_on_opponent_upkeep(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold(game)
        to_discard = Creature(name="ToDiscard", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[to_discard])
        _lib_push(game, 0, Land(name="ToDraw"))
        p0._script.append(to_discard)  # discard this
        _fire_upkeep(game, 1)          # opponent (p1) upkeep
        resolve_top(game)
        assert game.get_graveyard(p0).contains(to_discard)
        assert any(c.name == "ToDraw" for c in game.get_hand(p0).get_all())

    def test_loot_decline(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold(game)
        keep = Creature(name="Keep", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[keep])
        _lib_push(game, 0, Land(name="ToDraw"))
        p0._script.append(None)  # decline
        _fire_upkeep(game, 1)
        resolve_top(game)
        assert game.get_hand(p0).contains(keep)
        assert not any(c.name == "ToDraw" for c in game.get_hand(p0).get_all())

    def test_no_loot_on_own_upkeep(self):
        game = create_game()
        p0, p1 = game.players
        _lorehold(game)
        set_board_state(game, 0, hand=[Creature(name="X", base_power=1, base_toughness=1)])
        _fire_upkeep(game, 0)  # controller's own upkeep
        assert game.stack.is_empty()  # no loot trigger
