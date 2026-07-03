"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature
from engine.game import draw_card
from engine.turn import run_turn
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Zone
from test_utils import (
    _resolve_top_of_stack,
    advance_to_phase,
    cast_spell,
    create_game,
    set_board_state,
)

LOREHOLD_MANA = {ManaType.COLORLESS: 3, ManaType.RED: 1, ManaType.WHITE: 1}


def _game_with_lorehold():
    game = create_game()
    p1 = game.players[0]
    set_board_state(
        game, 0,
        hand=[LoreholdTheHistorian(owner=None)],
        mana=dict(LOREHOLD_MANA),
    )
    cast_spell(game, 0, "Lorehold, the Historian")
    p1.cards_drawn_this_turn = 0  # test setup: no draws yet this turn
    return game, p1


def _put_on_library(player, card):
    card.owner = card.controller = player
    player.zones[Zone.LIBRARY].add(card)


class TestLoreholdStatics:
    def test_card_data(self):
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords


class TestLoreholdMiracle:
    def test_first_drawn_instant_can_be_miracle_cast(self):
        game, p1 = _game_with_lorehold()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        bear.owner = bear.controller = p1
        flight = FleetingFlight(owner=None)
        _put_on_library(p1, flight)
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        drawn = draw_card(game, p1)
        assert drawn is flight
        p1._script.append(True)   # cast for miracle {2}
        p1._script.append(bear)   # the spell's target
        _resolve_top_of_stack(game)
        assert bear.plus_one_counters == 1
        assert game.get_graveyard(p1).contains(flight)
        assert p1.mana_pool.total() == 0  # the {2} miracle cost was paid

    def test_second_draw_gets_no_miracle(self):
        game, p1 = _game_with_lorehold()
        flight = FleetingFlight(owner=None)
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        # Top of library: Filler first, then Fleeting Flight underneath.
        _put_on_library(p1, flight)
        _put_on_library(p1, filler)
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        draw_card(game, p1)  # creature — no miracle window
        draw_card(game, p1)  # instant, but it's the second draw
        _resolve_top_of_stack(game)
        assert p1.zones[Zone.HAND].contains(flight)
        assert p1.mana_pool.total() == 2

    def test_decline_miracle_keeps_card_in_hand(self):
        game, p1 = _game_with_lorehold()
        flight = FleetingFlight(owner=None)
        _put_on_library(p1, flight)
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        draw_card(game, p1)
        p1._script.append(False)  # decline
        _resolve_top_of_stack(game)
        assert p1.zones[Zone.HAND].contains(flight)
        assert p1.mana_pool.total() == 2

    def test_no_mana_no_miracle_prompt(self):
        game, p1 = _game_with_lorehold()
        flight = FleetingFlight(owner=None)
        _put_on_library(p1, flight)
        assert p1.mana_pool.total() == 0

        draw_card(game, p1)
        _resolve_top_of_stack(game)  # no scripted answers — no prompt
        assert p1.zones[Zone.HAND].contains(flight)


class TestLoreholdUpkeepLoot:
    def _run_opponent_turn(self, game):
        """Advance to the opponent's turn and run it through the engine."""
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()  # wraps to turn 2 — opponent active, untap
        assert game.active_player is game.players[1]
        run_turn(game)

    def test_discard_to_draw_on_opponent_upkeep(self):
        game, p1 = _game_with_lorehold()
        p2 = game.players[1]
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[fodder])
        replacement = Creature(name="Fresh", base_power=1, base_toughness=1)
        _put_on_library(p1, replacement)
        _put_on_library(p2, Creature(name="P2Card", base_power=1, base_toughness=1))

        p2._script.append("pass")   # priority over the upkeep trigger
        p1._script.append("pass")
        p1._script.append(fodder)   # loot: discard Fodder
        self._run_opponent_turn(game)

        assert game.get_graveyard(p1).contains(fodder)
        assert p1.zones[Zone.HAND].contains(replacement)

    def test_decline_loot(self):
        game, p1 = _game_with_lorehold()
        p2 = game.players[1]
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[fodder])
        _put_on_library(p2, Creature(name="P2Card", base_power=1, base_toughness=1))

        p2._script.append("pass")
        p1._script.append("pass")
        p1._script.append(None)     # decline the loot
        self._run_opponent_turn(game)

        assert p1.zones[Zone.HAND].contains(fodder)
        assert len(game.get_graveyard(p1)) == 0

    def test_no_trigger_on_own_upkeep(self):
        game, p1 = _game_with_lorehold()
        p2 = game.players[1]
        set_board_state(game, 0, hand=[])
        _put_on_library(p1, Creature(name="P1Card", base_power=1, base_toughness=1))
        _put_on_library(p2, Creature(name="P2Card", base_power=1, base_toughness=1))

        # Opponent's turn first (decline the loot)…
        p2._script.append("pass")
        p1._script.append("pass")
        self._run_opponent_turn(game)
        # …then the controller's own turn: the only prompt is declare
        # attackers (Lorehold is on the battlefield) — script "no attackers".
        # An upkeep-loot prompt would exhaust the script and raise.
        assert game.active_player is p1
        p1._script.append(None)
        run_turn(game)
        assert len(game.get_graveyard(p1)) == 0  # no loot happened
