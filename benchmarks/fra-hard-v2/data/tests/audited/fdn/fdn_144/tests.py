"""Reference test for FDN 144 — Mischievous Pup.

"When this creature enters, return up to one other target permanent you
control to its owner's hand." The enters ability is a triggered ability whose
up to one target is chosen as it goes on the stack, so the trigger goes on
the stack even with no target chosen; the target is checked again as it
resolves (rule 608.2b).
"""

from __future__ import annotations

from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_144.card_impl import MischievousPup, MischievousPupAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import Keyword, ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game

from table import Table, appears, gains_control, moves, off_stack, on_stack, taps


def _pup_enters(targets, *, mine=(), theirs=None):
    """Player 0 casts Mischievous Pup; its trigger goes on the stack with its
    target, if any, chosen from ``targets``."""
    pup = card(MischievousPup)
    game = create_game(
        Side(hand=[pup], battlefield=list(mine), mana={ManaType.WHITE: 3}),
        theirs or Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, pup, then=[moves(pup, Zone.STACK)])
    t.pass_(0, choices=list(targets))
    t.pass_(1, then=[moves(pup, Zone.BATTLEFIELD), on_stack(MischievousPupAbility2, 0)])
    return t


def _resolve(t, *then, note=None):
    t.pass_(0)
    t.pass_(1, then=[off_stack(MischievousPupAbility2), *then], note=note)


class TestMischievousPupProperties:
    def test_static_data(self):
        pup = MischievousPup(owner=None)
        assert printed_class(pup) is MischievousPup
        assert pup.mana_cost == ManaCost.parse("{2}{W}")
        assert (pup.base_power, pup.base_toughness) == (3, 1)
        assert "Dog" in pup.subtypes
        assert Keyword.FLASH in pup.keywords


class TestMischievousPupETB:
    def test_bounces_chosen_permanent(self):
        lions = card(SavannahLions)
        t = _pup_enters([lions], mine=[lions])
        _resolve(t, moves(lions, Zone.HAND))
        t.run()

    def test_castable_with_no_legal_target(self):
        """'Up to one' with no other permanent: the trigger has no target and
        does nothing."""
        t = _pup_enters([])
        _resolve(t)
        t.run()

    def test_optional_target_can_be_declined(self):
        """A legal target exists but the controller declines: nothing is
        bounced."""
        lions = card(SavannahLions)
        t = _pup_enters([], mine=[lions])
        _resolve(t, note="the Lions stays")
        t.run()

    def test_target_control_change_before_resolution_no_bounce(self):
        """With the trigger on the stack, player 1, whose High Fae Trickster
        lets them cast Involuntary Employment at instant speed, takes the
        Lions: no longer 'a permanent you control', it is not bounced."""
        lions, employment = card(SavannahLions), card(InvoluntaryEmployment)
        mountains = [card(Mountain) for _ in range(4)]
        t = _pup_enters(
            [lions], mine=[lions], theirs=Side(hand=[employment], battlefield=[HighFaeTrickster, *mountains])
        )
        t.pass_(0)
        for mountain in mountains:
            t.act(1, mountain, then=[taps(mountain)])
        t.act(1, employment, choices=[lions], then=[moves(employment, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(employment, Zone.GRAVEYARD), gains_control(lions, 1), appears(1)])
        _resolve(t, note="the Lions, now player 1's, is not bounced")
        t.run()
