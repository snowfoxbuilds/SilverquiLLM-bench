"""Reference test for FDN 218 — Dwynen's Elite (token identity).

"When this creature enters, if you control another Elf, create a 1/1 green
Elf Warrior creature token." The enters ability is a triggered ability with
an intervening "if" (rule 603.4). Colour and subtypes are not visible at the
table, so the token is judged as a 1/1 in combat on the next turn.
"""

from __future__ import annotations

from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_218.card_impl import DwynensElite, DwynensEliteAbility1
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from silverquillm.table import Table, appears, ceases, moves, off_stack, on_stack, taps


def _cast_elite(mine, theirs=()):
    elite = card(DwynensElite)
    game = create_game(
        Side(hand=[elite], battlefield=list(mine), library=[Forest], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1}),
        Side(battlefield=list(theirs), library=[Forest]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, elite, then=[moves(elite, Zone.STACK)])
    t.pass_(0)
    return t, elite


class TestDwynensEliteToken:
    def test_etb_mints_a_one_one_token(self) -> None:
        """With Llanowar Elves in play the Elite makes a token; on player 0's
        next turn it attacks and trades with a blocking Spectral Sailor (1/1)."""
        sailor = card(SpectralSailor)
        t, elite = _cast_elite([LlanowarElves], [sailor])
        t.pass_(1, then=[moves(elite, Zone.BATTLEFIELD), on_stack(DwynensEliteAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(DwynensEliteAbility1), appears(0)])
        warrior = token(1)
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, warrior, then=[taps(warrior)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, sailor, scoped={sailor: warrior})
        t.pass_(0)
        t.pass_(1, then=[ceases(warrior), moves(sailor, Zone.GRAVEYARD)])
        t.run()

    def test_no_other_elf_no_trigger(self) -> None:
        """Without another Elf the ability does not trigger (rule 603.4)."""
        t, elite = _cast_elite([])
        t.pass_(1, then=[moves(elite, Zone.BATTLEFIELD)])
        t.run()
