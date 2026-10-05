"""Audited tests for FDN 112 — Spinner of Souls.

"Whenever another nontoken creature you control dies, you may reveal cards
from the top of your library until you reveal a creature card. Put that card
into your hand and the rest on the bottom of your library in a random order."
"You" is the player who controlled Spinner when the ability triggered (rule
603.3a), even if Spinner leaves the battlefield before it resolves.
"""

from __future__ import annotations

from cards.fdn.fdn_112.card_impl import SpinnerOfSouls
from engine.card import Creature
from engine.game import destroy
from test_utils import behavioral_game, enter_permanent, resolve_stack


def _hand_sizes(game):
    return tuple(len(game.get_hand(player).get_all()) for player in game.players)


class TestSpinnerOfSoulsReveal:
    def test_puts_a_creature_card_into_hand_when_another_creature_you_control_dies(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        top = game.get_library(player).top(1)[0]
        enter_permanent(game, player, SpinnerOfSouls())
        victim = enter_permanent(game, player, Creature(name="Victim", base_power=1, base_toughness=1))
        destroy(game, victim)
        resolve_stack(game)
        assert game.get_hand(player).get_all() == [top]

    def test_pending_reveal_stays_with_its_controller_after_spinner_leaves(self) -> None:
        game = behavioral_game()
        controller, owner = game.players
        spinner = enter_permanent(game, controller, SpinnerOfSouls())
        spinner.owner = owner  # a Spinner the controller does not own
        victim = enter_permanent(game, controller, Creature(name="Victim", base_power=1, base_toughness=1))
        destroy(game, victim)
        destroy(game, spinner)  # in response; it is not "another" creature
        resolve_stack(game)
        assert _hand_sizes(game) == (1, 0)
