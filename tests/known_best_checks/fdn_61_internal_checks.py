"""Known-Best checks moved out of fdn_61's FDN Audited Tests: returning the Hunter from the graveyard at instant speed before its trigger resolves takes an effect no FDN card has,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_61.card_impl import HighSocietyHunter
from engine.card import Creature
from engine.game import destroy
from engine.types import Zone as _Zone
from engine.zones import move_to_zone
from test_utils import behavioral_game, enter_permanent, resolve_stack


def _hand_sizes(game):
    return tuple(len(game.get_hand(player).get_all()) for player in game.players)


class TestHighSocietyHunterDraw:

    def test_pending_draw_ignores_the_hunter_returning_under_its_owner(self) -> None:
        game = behavioral_game()
        controller, owner = game.players
        hunter = enter_permanent(game, controller, HighSocietyHunter())
        hunter.owner = owner
        victim = enter_permanent(
            game, controller, Creature(name="Victim", base_power=1, base_toughness=1)
        )
        destroy(game, victim)
        destroy(game, hunter)
        move_to_zone(game, hunter, _Zone.GRAVEYARD, _Zone.BATTLEFIELD)
        assert game.get_battlefield(owner).contains(hunter)
        resolve_stack(game)
        assert _hand_sizes(game) == (1, 0)
