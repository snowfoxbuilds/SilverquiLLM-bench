"""Reference tests for FDN 66 — Nine-Lives Familiar.

"This creature enters with eight revival counters on it if you cast it." Under
the enters-with-counters primitive the eight revival counters land as the
creature enters *from the stack* (a resolved cast). A return via the
dies-trigger enters from the graveyard and gets no fresh counters — it keeps the
one-fewer count it left with. The dies-and-return mechanic is preserved.
"""

from __future__ import annotations

from cards.fdn.fdn_66.card_impl import NineLivesFamiliar
from engine.types import ManaCost, Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import advance_game_to_phase, create_game, resolve_stack, set_board_state
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
    @staticmethod
    def _dies_with_eight_revival():
        game = create_game()
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        p1 = game.players[0]
        card = NineLivesFamiliar(owner=p1, controller=p1)
        _place_on_stack(game, p1, card)
        move_to_zone(game, card, Zone.STACK, Zone.BATTLEFIELD)
        assert card.counters.get("revival", 0) == 8

        # Killing it (battlefield -> graveyard) fires the dies-trigger, whose
        # resolution sets up the return at the beginning of the next end step.
        move_to_zone(game, card, Zone.BATTLEFIELD, Zone.GRAVEYARD)
        resolve_stack(game)
        return game, p1, card

    def test_dies_returns_with_one_fewer_revival(self) -> None:
        game, p1, card = self._dies_with_eight_revival()
        assert game.get_graveyard(p1).contains(card)

        advance_game_to_phase(game, Phase.ENDING, Step.END)
        resolve_stack(game)
        assert game.get_battlefield(p1).contains(card)
        assert card.counters.get("revival", 0) == 7

    def test_does_not_return_before_the_next_end_step(self) -> None:
        game, p1, card = self._dies_with_eight_revival()
        advance_game_to_phase(game, Phase.POSTCOMBAT_MAIN)
        resolve_stack(game)
        assert game.get_graveyard(p1).contains(card)
        assert not game.get_battlefield(p1).contains(card)

    def test_does_not_return_if_it_left_the_graveyard_first(self) -> None:
        game, p1, card = self._dies_with_eight_revival()
        # Leaving the graveyard makes it a new object (rule 400.7), even if it
        # comes back before the end step.
        move_to_zone(game, card, Zone.GRAVEYARD, Zone.EXILE)
        move_to_zone(game, card, Zone.EXILE, Zone.GRAVEYARD)

        advance_game_to_phase(game, Phase.ENDING, Step.END)
        resolve_stack(game)
        assert game.get_graveyard(p1).contains(card)
        assert not game.get_battlefield(p1).contains(card)
