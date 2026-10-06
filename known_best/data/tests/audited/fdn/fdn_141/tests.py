"""Reference tests for FDN 141 — Giada, Font of Hope.

"Each other Angel you control enters with an additional +1/+1 counter on it for
each Angel you already control." This is a third-party enters-with-counters
*replacement* (rule 614.1c): as another Angel you control enters, Giada adds
one +1/+1 counter for each Angel you already control, on it *as* it enters.

The counters show in combat: the creature that entered blocks on player 1's
turn, and which creatures die shows its size.
"""

from __future__ import annotations

from cards.fdn.fdn_103.card_impl import ElfswornGiant
from cards.fdn.fdn_141.card_impl import GiadaFontOfHope
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_147.card_impl import SerraAngel
from cards.fdn.fdn_149.card_impl import YouthfulValkyrie
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, moves, taps


class TestGiadaProperties:
    def test_name_and_cost(self) -> None:
        card = GiadaFontOfHope(owner=None)
        assert printed_class(card) is GiadaFontOfHope
        assert card.mana_cost == ManaCost.parse("{1}{W}")


def _cast_then_block(entering, attacker, *, battlefield=()):
    """Player 0 casts ``entering`` from a {W}{W} pool beside ``battlefield``;
    on player 1's turn ``attacker`` attacks and ``entering`` blocks it."""
    game = create_game(
        Side(hand=[entering], battlefield=list(battlefield), mana={ManaType.WHITE: 2}),
        Side(battlefield=[attacker], library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, entering, then=[moves(entering, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(entering, Zone.BATTLEFIELD)])
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, attacker, then=[taps(attacker)])
    t.pass_(1)
    t.pass_(0)
    t.act(0, entering, scoped={entering: attacker})
    t.pass_(1)
    return t


class TestGiadaThirdPartyEntryCounters:
    def test_entering_angel_gets_counter_per_existing_angel(self) -> None:
        """Two Angels already controlled (Giada + Serra Angel) => +2: the 1/3
        Youthful Valkyrie is a 3/5, so it and the 5/3 Elfsworn Giant it blocks
        both die (a 2/4 or a 4/6 would survive or not kill)."""
        valkyrie, giant = card(YouthfulValkyrie), card(ElfswornGiant)
        t = _cast_then_block(valkyrie, giant, battlefield=[GiadaFontOfHope, SerraAngel])
        t.pass_(0, then=[moves(valkyrie, Zone.GRAVEYARD), moves(giant, Zone.GRAVEYARD)])
        t.run()

    def test_giada_does_not_buff_itself(self) -> None:
        """Giada enters as a 2/2 even with an Angel already out: blocking the
        2/1 Savannah Lions, both die."""
        giada, lions = card(GiadaFontOfHope), card(SavannahLions)
        t = _cast_then_block(giada, lions, battlefield=[SerraAngel])
        t.pass_(0, then=[moves(giada, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
        t.run()

    def test_non_angel_gets_nothing(self) -> None:
        """Savannah Lions enters as a 2/1 beside Giada: blocking the 1/1
        Llanowar Elves, both die."""
        lions, elves = card(SavannahLions), card(LlanowarElves)
        t = _cast_then_block(lions, elves, battlefield=[GiadaFontOfHope])
        t.pass_(0, then=[moves(lions, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD)])
        t.run()

    def test_opponent_angel_gets_nothing(self) -> None:
        """"Each other Angel *you* control": player 1's Youthful Valkyrie
        enters as a 1/3 beside player 0's Giada, so it dies blocking the 3/3
        Brazen Scourge."""
        valkyrie, scourge = card(YouthfulValkyrie), card(BrazenScourge)
        game = create_game(
            Side(battlefield=[GiadaFontOfHope, scourge], library=[card(Plains)]),
            Side(hand=[valkyrie], mana={ManaType.WHITE: 2}),
            start=(Phase.PRECOMBAT_MAIN, 1),
        )
        t = Table(game)
        t.act(1, valkyrie, then=[moves(valkyrie, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(valkyrie, Zone.BATTLEFIELD)])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, scourge, then=[taps(scourge)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, valkyrie, scoped={valkyrie: scourge})
        t.pass_(0)
        t.pass_(1, then=[moves(valkyrie, Zone.GRAVEYARD)])
        t.run()
