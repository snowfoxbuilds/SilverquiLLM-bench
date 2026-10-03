"""Reference test for FDN 218 — Dwynen's Elite (token identity).

Dwynen's Elite's ETB ("if you control another Elf, create a 1/1 green Elf
Warrior creature token") mints through the shared ``make_creature_token``
factory. This test pins the minted token's identity — subtypes, explicit
green colour (a token has no mana cost to derive colour from), base P/T, and
``is_token`` — so replay correlation keys it to the 1/1 green Elf Warrior grpId.
"""
from __future__ import annotations

from cards.fdn.fdn_218.card_impl import DwynensElite
from engine.card import Creature
from engine.protection import get_colors
from engine.types import Color, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _elf_warrior_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and getattr(o, "name", None) == "Elf Warrior"
    ]


class TestDwynensEliteToken:
    def test_etb_mints_green_elf_warrior_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        other_elf = Creature(
            name="Llanowar Elves", subtypes={"Elf"}, base_power=1, base_toughness=1
        )
        set_board_state(game, 0, battlefield=[other_elf])
        dwynen = DwynensElite(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[dwynen],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "Dwynen's Elite")

        tokens = _elf_warrior_tokens(game, p1)
        assert len(tokens) == 1
        tok = tokens[0]
        assert tok.subtypes == {"Elf", "Warrior"}
        assert get_colors(tok) == {Color.GREEN}
        assert (tok.base_power, tok.base_toughness) == (1, 1)
        assert tok.is_token is True
