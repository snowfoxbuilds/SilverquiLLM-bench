"""Reference test for FDN 64 — Infestation Sage.

"When this creature dies, create a 1/1 black and green Insect creature token
with flying." The Sage dies to Burst Lightning, and the Insect attacks on the
next turn as a 1-power flier the Aegis Turtle cannot block.
"""

from __future__ import annotations

from cards.fdn.fdn_64.card_impl import InfestationSage, InfestationSageAbility1
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, life, moves, off_stack, on_stack, taps


class TestInfestationSageProperties:
    def test_static_data(self) -> None:
        c = InfestationSage(owner=None)
        assert printed_class(c) is InfestationSage
        assert c.mana_cost == ManaCost.parse("{B}")


class TestInfestationSageDeathToken:
    def test_death_mints_flying_black_green_insect(self) -> None:
        sage, bolt, turtle = card(InfestationSage), card(BurstLightning), card(AegisTurtle)
        game = create_game(
            Side(battlefield=[sage], hand=[bolt], mana={ManaType.RED: 1}, library=[card(Plains)]),
            Side(battlefield=[turtle], library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, bolt, choices=[sage], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(
            1,
            then=[
                moves(bolt, Zone.GRAVEYARD),
                moves(sage, Zone.GRAVEYARD),
                on_stack(InfestationSageAbility1, 0),
            ],
        )
        t.pass_(0)
        t.pass_(1, then=[off_stack(InfestationSageAbility1), appears(0)])
        t.pass_to(Step.UPKEEP, 0)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, token(1), then=[taps(token(1))])
        t.pass_(0)
        t.pass_(1)
        t.act_illegal(1, turtle, scoped={turtle: token(1)}, note="the Insect flies")
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 19)])
        t.run()
