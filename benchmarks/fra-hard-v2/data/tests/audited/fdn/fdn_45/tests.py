"""Reference test for FDN 45 — Kiora, the Rising Tide (token identity).

Threshold — "Whenever Kiora attacks, if there are seven or more cards in your
graveyard, you may create Scion of the Deep, a legendary 8/8 blue Octopus
creature token." The mint routes through the shared ``make_creature_token``
factory and reinstates the legendary supertype afterwards (the factory does not
take supertypes). This test drives the attack trigger above threshold, answers
the optional "you may" with yes via an intent, and pins the minted token's
identity (name, subtypes, explicit blue colour, base P/T, legendary,
``is_token``).
"""

from __future__ import annotations

from cards.fdn.fdn_45.card_impl import KioraTheRisingTide
from engine.card import Creature
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.protection import get_colors
from engine.types import Color, Supertype
from test_utils import scenario_game as create_game
from test_utils import set_board_state


def _scion_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and getattr(o, "name", None) == "Scion of the Deep"
    ]


class TestKioraToken:
    def test_threshold_attack_mints_blue_legendary_octopus(self) -> None:
        from test_utils import declare_attackers, enter_permanent, resolve_stack

        game = create_game()
        p1 = game.players[0]
        kiora = enter_permanent(game, p1, KioraTheRisingTide())
        kiora.summoning_sick = False
        graveyard = [Creature(name=f"Milled {i}", base_power=1, base_toughness=1) for i in range(7)]
        set_board_state(game, 0, graveyard=graveyard)
        p1.set_baseline(Intent(pattern=GameRef(), preferences=(Decision.yes(),)))
        declare_attackers(game, [kiora])
        resolve_stack(game)
        tokens = _scion_tokens(game, p1)
        assert len(tokens) == 1
        token = tokens[0]
        assert token.subtypes == {"Octopus"} and get_colors(token) == {Color.BLUE}
        assert (token.power, token.toughness) == (8, 8) and token.is_token
        assert Supertype.LEGENDARY in token.supertypes
