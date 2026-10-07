"""Reference test for FDN 176 — Liliana, Dreadhorde General (+1 Zombie).

Phase H implements Liliana's ``+1: Create a 2/2 black Zombie creature token``
(grpId 94170). Player 0 activates the +1 through the real loyalty-activation
path, and the token shows what it is on player 1's turn: it blocks Strongbox
Raider (5/2), and both die. (The passive dies-trigger draw and the -4/-9
abilities are simplified stubs, out of scope.)
"""

from __future__ import annotations

from cards.fdn.fdn_96.card_impl import StrongboxRaider
from cards.fdn.fdn_176.card_impl import LilianaDreadhordeGeneral, LilianaDreadhordeGeneralAbility2
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import Phase, Side, Step, Zone, card, create_game, player, token

from table import Table, appears, ceases, moves, off_stack, on_stack, taps


class TestLilianaPlusOne:
    def test_plus_one_mints_a_2_2_black_zombie(self) -> None:
        raider = card(StrongboxRaider)
        game = create_game(
            Side(battlefield=[LilianaDreadhordeGeneral]),
            Side(battlefield=[raider], library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, LilianaDreadhordeGeneralAbility2, then=[on_stack(LilianaDreadhordeGeneralAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(LilianaDreadhordeGeneralAbility2), appears(0)])
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act(1, raider, scoped={raider: player(0)}, then=[taps(raider)])
        t.pass_(1)
        t.pass_(0)
        zombie = token(1)
        t.act(0, zombie, scoped={zombie: raider})
        t.pass_(1)
        t.pass_(0, then=[ceases(zombie), moves(raider, Zone.GRAVEYARD)], note="a creature with 2 power kills the 5/2")
        t.run()
