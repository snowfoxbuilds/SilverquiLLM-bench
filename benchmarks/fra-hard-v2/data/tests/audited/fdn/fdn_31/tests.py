"""Reference test for FDN 31 — Bigfin Bouncer.

"When this creature enters, return target creature an opponent controls to
its owner's hand." The enters ability is a triggered ability whose target is
chosen as it goes on the stack (rule 603.3d) and checked again as it resolves
(rule 608.2b).
"""

from __future__ import annotations

from cards.fdn.fdn_31.card_impl import BigfinBouncer, BigfinBouncerAbility1
from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game

from silverquillm.table import Table, appears, gains_control, moves, off_stack, on_stack, taps


def _bouncer_enters(*, hand=(), mine=(), theirs=(), targets=(), fallback=()):
    """Player 0 casts Bigfin Bouncer from four blue mana; its trigger, if it
    has a legal target, goes on the stack targeting one of ``targets`` — or
    of ``fallback`` once the engine has rejected a choice from ``targets``."""
    bouncer = card(BigfinBouncer)
    game = create_game(
        Side(hand=[bouncer, *hand], battlefield=list(mine), mana={ManaType.BLUE: 4}),
        Side(battlefield=list(theirs)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, bouncer, then=[moves(bouncer, Zone.STACK)])
    if fallback:
        t.pass_(0, branches=[list(targets), list(fallback)])
    else:
        t.pass_(0, choices=list(targets))
    t.pass_(1, then=[moves(bouncer, Zone.BATTLEFIELD), *([on_stack(BigfinBouncerAbility1, 0)] if targets else [])])
    return t


def _resolve(t, *then, note=None):
    t.pass_(0)
    t.pass_(1, then=[off_stack(BigfinBouncerAbility1), *then], note=note)


class TestBigfinBouncerProperties:
    def test_static_data(self):
        c = BigfinBouncer(owner=None)
        assert printed_class(c) is BigfinBouncer
        assert c.mana_cost == ManaCost.parse("{3}{U}")
        assert (c.base_power, c.base_toughness) == (3, 2)
        assert {"Shark", "Pirate"} <= c.subtypes


class TestBigfinBouncerBounce:
    def test_bounces_target_to_owner_hand(self):
        lions = card(SavannahLions)
        t = _bouncer_enters(theirs=[lions], targets=[lions])
        _resolve(t, moves(lions, Zone.HAND))
        t.run()

    def test_cost_is_paid(self):
        """The four blue mana is spent: a second Bouncer cannot be cast."""
        lions, second = card(SavannahLions), card(BigfinBouncer)
        t = _bouncer_enters(hand=[second], theirs=[lions], targets=[lions])
        _resolve(t, moves(lions, Zone.HAND))
        t.act_illegal(0, second, note="no mana is left")
        t.run()

    def test_filter_targets_only_opponent_creatures(self):
        """Player 0 would rather bounce their own Lions, which is not a legal
        target: not offered, or offered and rejected, the trigger then
        targeting the opponent's Lions."""
        mine, theirs = card(SavannahLions), card(SavannahLions)
        t = _bouncer_enters(mine=[mine], theirs=[theirs], targets=[mine, theirs], fallback=[theirs])
        _resolve(t, moves(theirs, Zone.HAND))
        t.run()

    def test_no_legal_target_removes_the_trigger(self):
        """Required target with no opponent creature: the Bouncer still
        enters, and its enters trigger is not put on the stack (rule 603.3d)."""
        t = _bouncer_enters()
        t.run()

    def test_target_control_change_before_resolution_no_bounce(self):
        """With the trigger on the stack, player 0, whose High Fae Trickster
        lets them cast Involuntary Employment at instant speed, takes the
        target: no longer 'a creature an opponent controls', it is not
        bounced."""
        lions, employment = card(SavannahLions), card(InvoluntaryEmployment)
        mountains = [card(Mountain) for _ in range(4)]
        t = _bouncer_enters(
            hand=[employment], mine=[HighFaeTrickster, *mountains], theirs=[lions], targets=[lions]
        )
        for mountain in mountains:
            t.act(0, mountain, then=[taps(mountain)])
        t.act(0, employment, choices=[lions], then=[moves(employment, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(employment, Zone.GRAVEYARD), gains_control(lions, 0), appears(0)])
        _resolve(t, note="the Lions, now player 0's, is not bounced")
        t.run()
