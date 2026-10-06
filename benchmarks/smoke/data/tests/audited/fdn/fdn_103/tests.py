"""Reference test for FDN 103 — Elfsworn Giant (landfall token).

Landfall — "Whenever a land you control enters, create a 1/1 green Elf Warrior
creature token." Playing a land puts the trigger on the stack, and the token
appears as it resolves.
"""

from __future__ import annotations

from cards.fdn.fdn_103.card_impl import ElfswornGiant, ElfswornGiantAbility2
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Phase, Side, Zone, card, create_game

from silverquillm.table import Table, appears, moves, off_stack, on_stack


class TestElfswornGiantToken:
    def test_landfall_mints_green_elf_warrior_token(self) -> None:
        forest = card(Forest)
        game = create_game(
            Side(hand=[forest], battlefield=[card(ElfswornGiant)]), Side(), start=(Phase.PRECOMBAT_MAIN, 0)
        )
        t = Table(game)
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD), on_stack(ElfswornGiantAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ElfswornGiantAbility2), appears(0)], note="an Elf Warrior token")
        t.run()
