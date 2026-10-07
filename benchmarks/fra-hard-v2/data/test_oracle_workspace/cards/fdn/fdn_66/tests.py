"""Reference tests for FDN 66 — Nine-Lives Familiar.

"This creature enters with eight revival counters on it if you cast it." Under
the enters-with-counters primitive the eight revival counters land as the
creature enters *from the stack* (a resolved cast). A return via the
dies-trigger enters from the graveyard at the beginning of the next end step and
gets no fresh counters — it keeps the one-fewer count it left with.
"""

from __future__ import annotations

from cards.fdn.fdn_66.card_impl import NineLivesFamiliar
from engine.events import EndStepTriggeredEvent
from engine.types import ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import create_game, resolve_stack, set_board_state
from engine.card import printed_class


def _place_on_stack(game, player, card):
    card.owner = player
    card.controller = player
    player.zones[Zone.STACK].add(card)


class TestNineLivesProperties:
    def test_name_and_cost(self) -> None:
        card = NineLivesFamiliar(owner=None)
        assert printed_class(card) is NineLivesFamiliar
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")


class TestNineLivesEntersWithRevival:
    def test_enters_from_stack_gets_eight_revival(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NineLivesFamiliar(owner=p1, controller=p1)
        _place_on_stack(game, p1, card)
        move_to_zone(game, card, Zone.STACK, Zone.BATTLEFIELD)
        assert card.counters.get("revival", 0) == 8
        # Revival counters are generic, not +1/+1 — no P/T change.
        assert card.power == 1
        assert card.toughness == 1

    def test_return_from_graveyard_adds_no_fresh_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NineLivesFamiliar(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[card])
        # Simulate the dies-trigger return path (graveyard -> battlefield).
        move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        assert card.counters.get("revival", 0) == 0


class TestNineLivesDiesReturn:
    def test_dies_returns_with_one_fewer_revival(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = NineLivesFamiliar(owner=p1, controller=p1)
        _place_on_stack(game, p1, card)
        move_to_zone(game, card, Zone.STACK, Zone.BATTLEFIELD)
        assert card.counters.get("revival", 0) == 8

        # Killing it (battlefield -> graveyard) fires the dies-trigger; it
        # resolves into a delayed trigger that returns it at the beginning of
        # the next end step with one fewer revival counter.
        move_to_zone(game, card, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        resolve_stack(game)
        assert game.get_graveyard(p1).contains(card)
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        resolve_stack(game)
        assert game.get_battlefield(p1).contains(card)
        assert card.counters.get("revival", 0) == 7
