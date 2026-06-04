"""Tests for SOS 201 — Lorehold, the Historian (5/5 Elder Dragon)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.turn import _do_untap_step
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state

_NAME = "Lorehold, the Historian"


def _lorehold() -> LoreholdTheHistorian:
    return LoreholdTheHistorian(owner=None)


def _put_on_battlefield(game, lorehold, player_index: int) -> None:
    """Register Lorehold's triggers by entering it via the real zone move."""
    set_board_state(game, player_index, hand=[lorehold])
    move_to_zone(game, lorehold, Zone.HAND, Zone.BATTLEFIELD)


def _owned_sorcery(owner) -> Sorcery:
    spell = Sorcery(name="Reconstruct History", mana_cost=ManaCost.parse("{4}"))
    spell.owner = owner
    spell.controller = owner
    return spell


class TestLoreholdProperties:
    def test_name(self) -> None:
        assert _lorehold().name == _NAME

    def test_mana_cost(self) -> None:
        assert _lorehold().mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_legendary_elder_dragon_5_5(self) -> None:
        card = _lorehold()
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert card.base_power == 5 and card.base_toughness == 5

    def test_flying_and_haste(self) -> None:
        card = _lorehold()
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords


class TestLoreholdUpkeepLoot:
    def test_discards_then_draws_on_opponent_upkeep(self) -> None:
        lorehold = _lorehold()
        game = create_game()
        p1, p2 = game.players
        _put_on_battlefield(game, lorehold, 0)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        drawn = Creature(name="Fresh", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[junk])
        p1.zones[Zone.LIBRARY].add(drawn)
        # p1 chooses to loot, then discards "junk".
        p1._script.append(True)
        p1._script.append(junk)
        # Opponent's (p2) upkeep.
        game.active_player_index = 1
        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent(player=p2)
        )
        _resolve_top_of_stack(game)
        assert junk in p1.zones[Zone.GRAVEYARD].get_all()
        assert drawn in p1.zones[Zone.HAND].get_all()

    def test_may_decline_loot(self) -> None:
        lorehold = _lorehold()
        game = create_game()
        p1, p2 = game.players
        _put_on_battlefield(game, lorehold, 0)
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        keep = Creature(name="Keep", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[junk])
        p1.zones[Zone.LIBRARY].add(keep)
        p1._script.append(False)  # decline
        game.active_player_index = 1
        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent(player=p2)
        )
        _resolve_top_of_stack(game)
        assert junk in p1.zones[Zone.HAND].get_all()
        assert keep in p1.zones[Zone.LIBRARY].get_all()

    def test_does_not_trigger_on_own_upkeep(self) -> None:
        lorehold = _lorehold()
        game = create_game()
        p1, p2 = game.players
        _put_on_battlefield(game, lorehold, 0)
        set_board_state(game, 0, hand=[Creature(name="Junk")])
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent(player=p1)
        )
        # Controller's own upkeep — no loot trigger should be on the stack.
        assert game.stack.is_empty()


class TestLoreholdMiracle:
    def _setup_main_phase(self, game) -> None:
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

    def test_first_instant_or_sorcery_draw_can_be_cast_for_two(self) -> None:
        lorehold = _lorehold()
        game = create_game()
        p1 = game.players[0]
        _put_on_battlefield(game, lorehold, 0)
        spell = _owned_sorcery(p1)
        p1.zones[Zone.LIBRARY].add(spell)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p1.cards_drawn_this_turn = 0
        self._setup_main_phase(game)
        p1._script.append(True)  # cast for miracle
        draw_card(game, p1)
        _resolve_top_of_stack(game)
        # Cast for {2}, resolved sorcery -> graveyard, pool emptied.
        assert spell in p1.zones[Zone.GRAVEYARD].get_all()
        assert spell not in p1.zones[Zone.HAND].get_all()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_may_decline_miracle(self) -> None:
        lorehold = _lorehold()
        game = create_game()
        p1 = game.players[0]
        _put_on_battlefield(game, lorehold, 0)
        spell = _owned_sorcery(p1)
        p1.zones[Zone.LIBRARY].add(spell)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p1.cards_drawn_this_turn = 0
        self._setup_main_phase(game)
        p1._script.append(False)  # decline
        draw_card(game, p1)
        _resolve_top_of_stack(game)
        assert spell in p1.zones[Zone.HAND].get_all()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_only_first_draw_qualifies(self) -> None:
        lorehold = _lorehold()
        game = create_game()
        p1 = game.players[0]
        _put_on_battlefield(game, lorehold, 0)
        first = Creature(name="FirstDraw", base_power=1, base_toughness=1)
        first.owner = p1
        spell = _owned_sorcery(p1)
        # Library bottom->top: [spell, first] so "first" is drawn first.
        p1.zones[Zone.LIBRARY].add(spell)
        p1.zones[Zone.LIBRARY].add(first)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p1.cards_drawn_this_turn = 0
        self._setup_main_phase(game)
        draw_card(game, p1)  # first (non-I/S) — no miracle
        draw_card(game, p1)  # spell, but it's the 2nd draw — no miracle
        assert game.stack.is_empty()
        assert spell in p1.zones[Zone.HAND].get_all()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_instant_miracle_works_off_main_phase(self) -> None:
        lorehold = _lorehold()
        game = create_game()
        p1 = game.players[0]
        _put_on_battlefield(game, lorehold, 0)
        bolt = Instant(name="Sudden Insight", mana_cost=ManaCost.parse("{3}"))
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.LIBRARY].add(bolt)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p1.cards_drawn_this_turn = 0
        # Off main phase: instants bypass sorcery-speed timing.
        game.active_player_index = 0
        game.phase = Phase.COMBAT
        p1._script.append(True)
        draw_card(game, p1)
        _resolve_top_of_stack(game)
        assert bolt in p1.zones[Zone.GRAVEYARD].get_all()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_miracle_when_lorehold_absent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Lorehold never enters the battlefield -> no triggers registered.
        spell = _owned_sorcery(p1)
        p1.zones[Zone.LIBRARY].add(spell)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p1.cards_drawn_this_turn = 0
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        draw_card(game, p1)
        assert game.stack.is_empty()
        assert spell in p1.zones[Zone.HAND].get_all()


class TestCardsDrawnReset:
    def test_untap_step_resets_draw_counter(self) -> None:
        game = create_game()
        p1, p2 = game.players
        p1.cards_drawn_this_turn = 5
        p2.cards_drawn_this_turn = 3
        game.active_player_index = 0
        _do_untap_step(game)
        assert p1.cards_drawn_this_turn == 0
        assert p2.cards_drawn_this_turn == 0
