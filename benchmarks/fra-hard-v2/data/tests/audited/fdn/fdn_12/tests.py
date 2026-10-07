"""Reference test for FDN 12 — Felidar Savior.

"When this creature enters, put a +1/+1 counter on each of up to two other
target creatures you control." The enters ability is a triggered ability whose
up to two targets are chosen as it goes on the stack. A Savannah Lions (2/1)
with a counter is a 3/2, so it survives the 1 damage a blocking Spectral
Sailor deals it; without one it dies.
"""

from __future__ import annotations

from cards.fdn.fdn_12.card_impl import FelidarSavior, FelidarSaviorAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_164.card_impl import SpectralSailor
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from table import Table, moves, off_stack, on_stack, taps


def _savior_enters(mine, theirs, targets):
    """Player 0 casts Felidar Savior with ``mine`` on the battlefield; its
    trigger targets ``targets`` and resolves."""
    savior = card(FelidarSavior)
    game = create_game(
        Side(hand=[savior], battlefield=list(mine), mana={ManaType.WHITE: 4}),
        Side(battlefield=list(theirs)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, savior, then=[moves(savior, Zone.STACK)])
    t.pass_(0, choices=list(targets))
    t.pass_(1, then=[moves(savior, Zone.BATTLEFIELD), on_stack(FelidarSaviorAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(FelidarSaviorAbility2)])
    return t


def _attack_into_sailors(t, blocks, *, dead):
    """The Lions attack; each Sailor blocks the Lions ``blocks`` maps it to,
    and ``dead`` go to their graveyards."""
    attackers = list(blocks.values())
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, *attackers, then=[taps(a) for a in attackers])
    t.pass_(0)
    t.pass_(1)
    t.act(1, *blocks, scoped=blocks)
    t.pass_(0)
    t.pass_(1, then=[moves(d, Zone.GRAVEYARD) for d in dead])


class TestFelidarSaviorProperties:
    def test_static_data(self):
        fs = FelidarSavior(owner=None)
        assert printed_class(fs) is FelidarSavior
        assert fs.mana_cost == ManaCost.parse("{3}{W}")


class TestFelidarSaviorETB:
    def test_castable_with_no_other_creatures(self):
        """No other creature to target: the Savior still enters, and its
        trigger, with zero of its up to two targets, does nothing."""
        t = _savior_enters([], [], [])
        t.run()

    def test_one_other_creature_gets_a_counter(self):
        lions, sailor = card(SavannahLions), card(SpectralSailor)
        t = _savior_enters([lions], [sailor], [lions])
        _attack_into_sailors(t, {sailor: lions}, dead=[sailor])
        t.run()

    def test_two_other_creatures_both_get_distinct_counters(self):
        """Each Lions gets one counter, so both survive their blocks."""
        first, second = card(SavannahLions), card(SavannahLions)
        s1, s2 = card(SpectralSailor), card(SpectralSailor)
        t = _savior_enters([first, second], [s1, s2], [first, second])
        _attack_into_sailors(t, {s1: first, s2: second}, dead=[s1, s2])
        t.run()
