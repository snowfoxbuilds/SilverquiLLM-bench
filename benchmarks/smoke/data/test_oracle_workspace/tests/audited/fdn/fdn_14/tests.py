"""Reference test for FDN 14 — Guarded Heir (Phase H token minter).

"When this creature enters, create two 3/3 white Knight creature tokens." The
mint fires from a self-ETB trigger, so casting the creature drives it directly.
That the two tokens are 3/3s shows on the next turn: one hits for 3 unblocked,
and the other survives a 2/1's block and kills it.
"""

from __future__ import annotations

from cards.fdn.fdn_14.card_impl import GuardedHeir, GuardedHeirAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps


class TestGuardedHeirMint:
    def test_etb_mints_two_33_white_knight_tokens(self) -> None:
        heir, lions = card(GuardedHeir), card(SavannahLions)
        game = create_game(
            Side(
                hand=[heir], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 5}, library=[card(Plains)]
            ),
            Side(battlefield=[lions], library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, heir, then=[moves(heir, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(heir, Zone.BATTLEFIELD), on_stack(GuardedHeirAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(GuardedHeirAbility2), appears(0), appears(0)])
        # Player 0's next turn: both Knights attack, and the Lions blocks one.
        t.pass_to(Step.UPKEEP, 0)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, token(1), token(2), then=[taps(token(1)), taps(token(2))])
        t.pass_(0)
        t.pass_(1)
        t.act(1, lions, scoped={lions: token(1)})
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.GRAVEYARD), life(1, 17)])
        t.run()
