"""Reference test for FDN 92 — Rite of the Dragoncaller.

"Whenever you cast an instant or sorcery spell, create a 5/5 red Dragon
creature token with flying." The Dragon shows in play: it arrives as its
trigger resolves, a creature without flying cannot block it, and it deals 5.
"""

from __future__ import annotations

from cards.fdn.fdn_92.card_impl import RiteOfTheDragoncaller, RiteOfTheDragoncallerAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import ManaCost, ManaType
from test_interface import Phase, Side, Step, Zone, card, create_game, player, token

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps


class TestRiteOfTheDragoncallerProperties:
    def test_static_data(self) -> None:
        c = RiteOfTheDragoncaller(owner=None)
        assert printed_class(c) is RiteOfTheDragoncaller
        assert c.mana_cost == ManaCost.parse("{4}{R}{R}")


class TestRiteOfTheDragoncallerToken:
    def test_casting_instant_mints_flying_red_dragon(self) -> None:
        bolt, lions = card(BurstLightning), card(SavannahLions)
        game = create_game(
            Side(hand=[bolt], battlefield=[card(RiteOfTheDragoncaller)], library=[card(Mountain)],
                 mana={ManaType.RED: 1}),
            Side(battlefield=[lions], library=[card(Mountain)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, bolt, choices=[player(1)], then=[
            moves(bolt, Zone.STACK), on_stack(RiteOfTheDragoncallerAbility1, 0),
        ])
        t.pass_(0)
        t.pass_(1, then=[off_stack(RiteOfTheDragoncallerAbility1), appears(0)], note="a Dragon token")
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        # Player 0's next turn: the Dragon attacks; the Lions cannot block a flier.
        t.pass_to(Step.UPKEEP, 0)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, token(1), then=[taps(token(1))])
        t.pass_(0)
        t.pass_(1)
        t.act_illegal(1, lions, scoped={lions: token(1)}, note="the Dragon has flying")
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 13)], note="the Dragon deals 5")
        t.run()
