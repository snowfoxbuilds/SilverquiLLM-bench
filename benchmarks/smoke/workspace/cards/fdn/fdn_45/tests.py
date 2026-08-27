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
from engine.events import AttacksTriggeredEvent
from engine.intent_player import Intent
from engine.protection import get_colors
from engine.stack import priority_loop
from engine.types import Color, Supertype
from test_utils import create_game, set_board_state


def _scion_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and getattr(o, "name", None) == "Scion of the Deep"
    ]


class TestKioraToken:
    def test_threshold_attack_mints_blue_legendary_octopus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kiora = KioraTheRisingTide(owner=p1, controller=p1)
        graveyard = [
            Creature(name=f"Milled {i}", base_power=1, base_toughness=1)
            for i in range(7)
        ]
        set_board_state(game, 0, battlefield=[kiora], graveyard=graveyard)
        game.active_player_index = 0
        kiora.register_triggers(game)

        p1.start_intent(
            "kiora",
            Intent(
                pattern=GameRef(
                    card=frozenset({("name", "Kiora, the Rising Tide")})
                ),
                preferences=(Decision.yes(),),
            ),
        )
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(attacker=kiora, creature=kiora)
        )
        priority_loop(game)
        p1.end_intent("kiora")

        tokens = _scion_tokens(game, p1)
        assert len(tokens) == 1
        tok = tokens[0]
        assert tok.subtypes == {"Octopus"}
        assert get_colors(tok) == {Color.BLUE}
        assert (tok.base_power, tok.base_toughness) == (8, 8)
        assert tok.is_token is True
        assert Supertype.LEGENDARY in tok.supertypes
