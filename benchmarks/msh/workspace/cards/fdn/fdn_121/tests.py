"""Reference test for FDN 121 — Koma, World-Eater (token identity).

"Whenever Koma deals combat damage to a player, create four 3/3 blue Serpent
creature tokens named Koma's Coil." The per-token mint routes through the
shared ``make_creature_token`` factory while keeping the named-token name.
This test drives a combat-damage event through the registered trigger and pins
the count (four) and each minted token's identity (name, subtypes, explicit
blue colour, base P/T, ``is_token``).
"""
from __future__ import annotations

from cards.fdn.fdn_121.card_impl import KomaWorldEater
from engine.events import DealsDamageTriggeredEvent
from engine.protection import get_colors
from engine.stack import priority_loop
from engine.types import Color
from test_utils import create_game, set_board_state


def _coil_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and getattr(o, "name", None) == "Koma's Coil"
    ]


class TestKomaToken:
    def test_combat_damage_mints_four_blue_serpents(self) -> None:
        game = create_game()
        p1, p2 = game.players
        koma = KomaWorldEater(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[koma])
        koma.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            DealsDamageTriggeredEvent(
                source=koma, target=p2, amount=8, is_combat=True
            ),
        )
        priority_loop(game)

        tokens = _coil_tokens(game, p1)
        assert len(tokens) == 4
        for tok in tokens:
            assert tok.subtypes == {"Serpent"}
            assert get_colors(tok) == {Color.BLUE}
            assert (tok.base_power, tok.base_toughness) == (3, 3)
            assert tok.is_token is True
