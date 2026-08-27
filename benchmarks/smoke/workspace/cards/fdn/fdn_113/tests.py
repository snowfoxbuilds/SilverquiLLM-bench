"""Reference test for FDN 113 — Sylvan Scavenging (token identity).

At the beginning of your end step, choose one — the "token" mode creates a 3/3
green Raccoon creature token if you control a creature with power 4 or greater.
The mint routes through the shared ``make_creature_token`` factory. This test
drives the end-step trigger, answers the mode choice with "token" via an
intent, and pins the minted token's identity (subtypes, explicit green colour,
base P/T, ``is_token``).
"""
from __future__ import annotations

from cards.fdn.fdn_113.card_impl import SylvanScavenging
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.events import EndStepTriggeredEvent
from engine.intent_player import Intent
from engine.protection import get_colors
from engine.stack import priority_loop
from engine.types import Color
from test_utils import create_game, set_board_state


def _raccoon_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and getattr(o, "name", None) == "Raccoon"
    ]


class TestSylvanScavengingToken:
    def test_end_step_token_mode_mints_green_raccoon(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scavenging = SylvanScavenging(owner=p1, controller=p1)
        behemoth = Creature(
            name="Grizzly Behemoth", base_power=4, base_toughness=4
        )
        set_board_state(game, 0, battlefield=[scavenging, behemoth])
        game.active_player_index = 0
        scavenging.register_triggers(game)

        # Both modes are legal (a creature is present and it has power >= 4),
        # so the mode is chosen via an intent answering "token".
        p1.start_intent(
            "scav",
            Intent(
                pattern=GameRef(card=frozenset({("name", "Sylvan Scavenging")})),
                preferences=(Decision.mode("token"),),
            ),
        )
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        priority_loop(game)
        p1.end_intent("scav")

        tokens = _raccoon_tokens(game, p1)
        assert len(tokens) == 1
        tok = tokens[0]
        assert tok.subtypes == {"Raccoon"}
        assert get_colors(tok) == {Color.GREEN}
        assert (tok.base_power, tok.base_toughness) == (3, 3)
        assert tok.is_token is True
