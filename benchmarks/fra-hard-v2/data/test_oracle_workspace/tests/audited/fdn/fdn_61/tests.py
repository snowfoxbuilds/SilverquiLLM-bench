"""Audited tests for FDN 61 — High-Society Hunter.

"Whenever another nontoken creature dies, draw a card." The card is drawn by
the player who controlled the Hunter when the ability triggered (rule 603.3a),
even if the Hunter leaves the battlefield before the ability resolves and
returns as a new object (400.7).
"""

from __future__ import annotations

from cards.fdn.fdn_61.card_impl import HighSocietyHunter
from engine.card import Creature
from engine.game import destroy
from engine.types import Zone
from engine.zones import move_to_zone
from test_utils import behavioral_game, enter_permanent, resolve_stack


def _hand_sizes(game):
    return tuple(len(game.get_hand(player).get_all()) for player in game.players)


class TestHighSocietyHunterDraw:
    def test_draws_when_another_nontoken_creature_dies(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        enter_permanent(game, player, HighSocietyHunter())
        victim = enter_permanent(game, player, Creature(name="Victim", base_power=1, base_toughness=1))
        destroy(game, victim)
        resolve_stack(game)
        assert _hand_sizes(game) == (1, 0)

    def test_pending_draw_stays_with_its_controller_after_the_hunter_leaves(self) -> None:
        game = behavioral_game()
        controller, owner = game.players
        hunter = enter_permanent(game, controller, HighSocietyHunter())
        hunter.owner = owner  # a Hunter the controller does not own
        victim = enter_permanent(game, controller, Creature(name="Victim", base_power=1, base_toughness=1))
        destroy(game, victim)
        destroy(game, hunter)  # in response; it is not "another" creature
        resolve_stack(game)
        assert _hand_sizes(game) == (1, 0)

    def test_pending_draw_ignores_the_hunter_returning_under_its_owner(self) -> None:
        game = behavioral_game()
        controller, owner = game.players
        hunter = enter_permanent(game, controller, HighSocietyHunter())
        hunter.owner = owner
        victim = enter_permanent(game, controller, Creature(name="Victim", base_power=1, base_toughness=1))
        destroy(game, victim)
        destroy(game, hunter)
        move_to_zone(game, hunter, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        assert game.get_battlefield(owner).contains(hunter)
        resolve_stack(game)
        assert _hand_sizes(game) == (1, 0)
