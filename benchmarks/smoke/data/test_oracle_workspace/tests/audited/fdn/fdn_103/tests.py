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
from engine.protection import get_colors
from engine.types import Color
from test_utils import scenario_game as create_game


def _elf_warrior_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and getattr(o, "name", None) == "Elf Warrior"
    ]


class TestElfswornGiantToken:
    def test_landfall_mints_green_elf_warrior_token(self) -> None:
        from engine.casting import play_land
        from engine.types import Phase
        from test_utils import enter_permanent, resolve_stack

        game = create_game()
        p1 = game.players[0]
        enter_permanent(game, p1, ElfswornGiant())
        land = Land(name="Forest", owner=p1)
        game.get_hand(p1).add(land)
        game.phase, game.step = Phase.PRECOMBAT_MAIN, None
        play_land(game, p1, land)
        resolve_stack(game)
        tokens = _elf_warrior_tokens(game, p1)
        assert len(tokens) == 1
        token = tokens[0]
        assert token.subtypes == {"Elf", "Warrior"}
        assert get_colors(token) == {Color.GREEN}
        assert (token.power, token.toughness) == (1, 1) and token.is_token
