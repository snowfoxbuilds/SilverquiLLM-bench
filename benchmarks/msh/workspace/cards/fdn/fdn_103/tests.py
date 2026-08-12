"""Reference test for FDN 103 — Elfsworn Giant (landfall token identity).

Landfall — "Whenever a land you control enters, create a 1/1 green Elf Warrior
creature token." The mint routes through the shared ``make_creature_token``
factory; this test drives a land-ETB event through the registered landfall
trigger and pins the minted token's identity (subtypes, explicit green colour,
base P/T, ``is_token``) so replay correlation keys it to the Elf Warrior grpId.
"""
from __future__ import annotations

from cards.fdn.fdn_103.card_impl import ElfswornGiant
from engine.card import Land
from engine.events import EntersBattlefieldTriggeredEvent
from engine.protection import get_colors
from engine.stack import priority_loop
from engine.types import Color
from test_utils import create_game, set_board_state


def _elf_warrior_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and getattr(o, "name", None) == "Elf Warrior"
    ]


class TestElfswornGiantToken:
    def test_landfall_mints_green_elf_warrior_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        giant = ElfswornGiant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[giant])
        giant.register_triggers(game)

        land = Land(name="Forest", owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=land, controller=p1),
        )
        priority_loop(game)

        tokens = _elf_warrior_tokens(game, p1)
        assert len(tokens) == 1
        tok = tokens[0]
        assert tok.subtypes == {"Elf", "Warrior"}
        assert get_colors(tok) == {Color.GREEN}
        assert (tok.base_power, tok.base_toughness) == (1, 1)
        assert tok.is_token is True
