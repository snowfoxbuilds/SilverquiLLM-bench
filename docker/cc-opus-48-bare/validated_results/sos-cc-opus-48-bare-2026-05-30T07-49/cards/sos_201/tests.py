"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


class _DamageInstant(Instant):
    """Test instant that deals 2 damage to its controller's opponent."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        controller = self.controller
        opp = game.players[1] if controller is game.players[0] else game.players[0]
        deal_damage(game, self, opp, 2)


def _resolve_all(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _add_to_library(game, player, card) -> None:
    card.owner = player
    card.controller = player
    game.get_library(player).add(card)


class TestLoreholdProperties:
    def test_name_and_stats(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_keywords_and_types(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestLoreholdMiracle:
    def test_first_instant_drawn_can_be_cast_for_two(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        zap = _DamageInstant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        _add_to_library(game, p1, zap)
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        p1._script.append(True)  # accept miracle
        draw_card(game, p1)
        _resolve_all(game)

        assert p2.life == 20 - 2
        assert p1.mana_pool.total() == 0  # paid the {2} miracle cost
        assert zap in game.get_graveyard(p1).get_all()

    def test_decline_miracle_keeps_card_in_hand(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        zap = _DamageInstant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        _add_to_library(game, p1, zap)
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        p1._script.append(False)  # decline miracle
        draw_card(game, p1)
        _resolve_all(game)

        assert p2.life == 20
        assert p1.mana_pool.total() == 2
        assert zap in game.get_hand(p1).get_all()

    def test_no_miracle_for_second_draw(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        zap = _DamageInstant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore], mana={ManaType.COLORLESS: 2})
        _add_to_library(game, p1, zap)
        lore.register_triggers(game)
        # Pretend a card was already drawn this turn — this is the 2nd draw.
        p1.cards_drawn_this_turn = 1

        draw_card(game, p1)
        # No miracle trigger placed on the stack.
        assert game.stack.is_empty()
        assert zap in game.get_hand(p1).get_all()

    def test_no_miracle_when_lorehold_not_in_play(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        zap = _DamageInstant(owner=p1, controller=p1)
        # Lorehold is in hand, not on the battlefield.
        set_board_state(game, 0, hand=[lore], mana={ManaType.COLORLESS: 2})
        _add_to_library(game, p1, zap)
        lore.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        draw_card(game, p1)
        assert game.stack.is_empty()
        assert zap in game.get_hand(p1).get_all()


class TestLoreholdLoot:
    def test_opponent_upkeep_discard_then_draw(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lore], hand=[junk])
        fresh = Creature(name="Fresh", base_power=2, base_toughness=2)
        _add_to_library(game, p1, fresh)
        lore.register_triggers(game)

        # It is the opponent's (p2's) upkeep.
        game.active_player_index = 1
        p1._script.append(True)   # yes, discard
        p1._script.append(junk)   # which card to discard

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert junk in game.get_graveyard(p1).get_all()
        assert fresh in game.get_hand(p1).get_all()

    def test_no_loot_on_controllers_own_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lore], hand=[junk])
        lore.register_triggers(game)

        # Controller's own upkeep — the ability only triggers on opponents'.
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()
        assert junk in game.get_hand(p1).get_all()
