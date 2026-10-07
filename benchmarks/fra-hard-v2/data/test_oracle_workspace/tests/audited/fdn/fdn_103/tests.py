"""Reference test for FDN 103 — Elfsworn Giant (landfall token).

Landfall — "Whenever a land you control enters, create a 1/1 green Elf Warrior
creature token." Playing a land puts the trigger on the stack, and the token
appears as it resolves.
"""

from __future__ import annotations

from cards.fdn.fdn_103.card_impl import ElfswornGiant, ElfswornGiantAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, ceases, life, moves, off_stack, on_stack, taps


class TestElfswornGiantToken:
    def test_landfall_mints_green_elf_warrior_token(self) -> None:
        forest, elves = card(Forest), card(LlanowarElves)
        game = create_game(
            Side(hand=[forest], battlefield=[card(ElfswornGiant)], library=[card(Forest)]),
            Side(battlefield=[elves], library=[card(Forest)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD), on_stack(ElfswornGiantAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ElfswornGiantAbility2), appears(0)], note="an Elf Warrior token")
        # Next turn the token attacks and player 1's 1/1 Llanowar Elves blocks
        # it: they trade, so the token has power at least 1 and toughness 1.
        t.pass_to(Step.UPKEEP, 1)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, token(1), then=[taps(token(1))])
        t.pass_(0)
        t.pass_(1)
        t.act(1, elves, scoped={elves: token(1)})
        t.pass_(0)
        t.pass_(1, then=[ceases(token(1)), moves(elves, Zone.GRAVEYARD)])
        t.run()

    def test_the_elf_warrior_token_attacks_for_one(self) -> None:
        forest = card(Forest)
        game = create_game(
            Side(hand=[forest], battlefield=[card(ElfswornGiant)], library=[card(Forest)]),
            Side(library=[card(Forest)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD), on_stack(ElfswornGiantAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ElfswornGiantAbility2), appears(0)])
        t.pass_to(Step.UPKEEP, 1)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, token(1), then=[taps(token(1))])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 19)], note="the Elf Warrior token deals 1")
        t.run()
