"""Reference test for FDN 145 — Resolute Reinforcements (Phase H token minter).

"When this creature enters, create a 1/1 white Soldier creature token." The
mint fires from a self-ETB trigger, so casting the creature drives it
directly. The token shows what it is in play: on player 1's turn it blocks a
1/1 Llanowar Elves, and both die.
"""
from __future__ import annotations

from cards.fdn.fdn_145.card_impl import ResoluteReinforcements, ResoluteReinforcementsAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from silverquillm.table import Table, appears, ceases, moves, off_stack, on_stack, taps


class TestResoluteReinforcementsMint:
    def test_etb_mints_11_white_soldier_token(self) -> None:
        reinforcements, elves = card(ResoluteReinforcements), card(LlanowarElves)
        game = create_game(
            Side(hand=[reinforcements], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1}),
            Side(battlefield=[elves], library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, reinforcements, then=[moves(reinforcements, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(reinforcements, Zone.BATTLEFIELD), on_stack(ResoluteReinforcementsAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ResoluteReinforcementsAbility2), appears(0)])
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act(1, elves, then=[taps(elves)])
        t.pass_(1)
        t.pass_(0)
        soldier = token(1)
        t.act(0, soldier, scoped={soldier: elves})
        t.pass_(1)
        t.pass_(0, then=[ceases(soldier), moves(elves, Zone.GRAVEYARD)], note="a 1/1 creature trades with the 1/1")
        t.run()
