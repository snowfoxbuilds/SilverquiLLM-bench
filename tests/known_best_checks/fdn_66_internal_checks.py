"""Known-Best checks moved out of fdn_66's FDN Audited Tests: moving the card out of the graveyard at instant speed before its trigger resolves takes an effect no FDN card has,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_66.card_impl import NineLivesFamiliar
from engine.types import Zone as _Zone
from engine.zones import move_to_zone
from test_interface import Phase, Step
from test_utils import advance_game_to_phase, resolve_stack
from test_utils import create_game as _create_game


def _place_on_stack(game, player, card_):
    card_.owner = player
    card_.controller = player
    player.zones[_Zone.STACK].add(card_)


class TestNineLivesDiesReturn:
    @staticmethod
    def _dies_with_eight_revival():
        game = _create_game()
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        p1 = game.players[0]
        card_ = NineLivesFamiliar(owner=p1, controller=p1)
        _place_on_stack(game, p1, card_)
        move_to_zone(game, card_, _Zone.STACK, _Zone.BATTLEFIELD)
        assert card_.counters.get("revival", 0) == 8

        # Killing it (battlefield -> graveyard) fires the dies-trigger, whose
        # resolution sets up the return at the beginning of the next end step.
        move_to_zone(game, card_, _Zone.BATTLEFIELD, _Zone.GRAVEYARD)
        resolve_stack(game)
        return game, p1, card_

    def test_does_not_return_if_it_left_the_graveyard_first(self) -> None:
        game, p1, card_ = self._dies_with_eight_revival()
        # Leaving the graveyard makes it a new object (rule 400.7), even if it
        # comes back before the end step.
        move_to_zone(game, card_, _Zone.GRAVEYARD, _Zone.EXILE)
        move_to_zone(game, card_, _Zone.EXILE, _Zone.GRAVEYARD)

        advance_game_to_phase(game, Phase.ENDING, Step.END)
        resolve_stack(game)
        assert game.get_graveyard(p1).contains(card_)
        assert not game.get_battlefield(p1).contains(card_)
