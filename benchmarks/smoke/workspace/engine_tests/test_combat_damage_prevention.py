"""Combat damage that would be dealt to a creature whose combat damage is
prevented this turn is not dealt (rules 615.1, 510.2).

Fleeting Flight prevents all combat damage that would be dealt to its target
this turn and puts a +1/+1 counter on it, so the Savannah Lions it targets
attacks as a 3/2; it is cast once blockers are declared, so the flying it
also grants does not change the blocks.
"""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import Side, Step, Zone, card, create_game

from silverquillm.table import Table, moves, taps


def _protected_attack(blocker, *, p1_library=()):
    """Turn 1: player 0's Savannah Lions attacks, ``blocker`` blocks it, and
    player 0 casts Fleeting Flight on the Lions before combat damage."""
    lions, flight, plains = card(SavannahLions), card(FleetingFlight), card(Plains)
    ceratops = card(QuakestriderCeratops)
    game = create_game(
        Side(hand=[flight], battlefield=[lions, plains], library=[card(Plains)]),
        Side(battlefield=[blocker, ceratops], library=list(p1_library)),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.act(1, blocker, scoped={blocker: lions})
    t.act(0, plains, then=[taps(plains)])
    t.act(0, flight, choices=[lions], then=[moves(flight, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(flight, Zone.GRAVEYARD)])
    return t, lions, ceratops


def test_prevented_creature_survives_a_lethal_block():
    scourge = card(BrazenScourge)
    t, _lions, _ceratops = _protected_attack(scourge)
    t.pass_(0)
    t.pass_(1, then=[moves(scourge, Zone.GRAVEYARD)], note="the Lions takes no damage from the 3/3")
    t.run()


def test_prevented_creature_still_deals_its_damage():
    elves = card(LlanowarElves)
    t, _lions, _ceratops = _protected_attack(elves)
    t.pass_(0)
    t.pass_(1, then=[moves(elves, Zone.GRAVEYARD)], note="the Lions' 3 damage kills the Elves")
    t.run()


def test_prevention_ends_at_cleanup():
    scourge = card(BrazenScourge)
    t, lions, ceratops = _protected_attack(scourge, p1_library=[card(Plains)])
    t.pass_(0)
    t.pass_(1, then=[moves(scourge, Zone.GRAVEYARD)])
    # Player 0's next turn: the Lions attacks again, and the 12/8 blocks it.
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.act(1, ceratops, scoped={ceratops: lions})
    t.pass_(0)
    t.pass_(1, then=[moves(lions, Zone.GRAVEYARD)], note="the damage is no longer prevented")
    t.run()
