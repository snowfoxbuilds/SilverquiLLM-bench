"""Public casting, targeting and temporary flying coverage for Fleeting Flight.

"Put a +1/+1 counter on target creature. It gains flying until end of turn.
Prevent all combat damage that would be dealt to it this turn." The counter,
the flying and the prevention each show in combat."""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.fdn.fdn_50.card_impl import SkyshipBuccaneer
from cards.fdn.fdn_130.card_impl import QuickDrawKatana
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import Instant, printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, life, moves, taps

_W = {ManaType.WHITE: 1}


class TestFleetingFlightProperties:
    """Static card data should match the FDN 13 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(FleetingFlight(owner=None), Instant)

    def test_name(self) -> None:
        assert printed_class(FleetingFlight(owner=None)) is FleetingFlight

    def test_mana_cost(self) -> None:
        assert FleetingFlight(owner=None).mana_cost == ManaCost.parse("{W}")


class TestFleetingFlightTargeting:
    """Only creatures are legal cast targets."""

    def test_artifact_is_not_a_legal_creature_target(self) -> None:
        flight, katana = card(FleetingFlight), card(QuickDrawKatana)
        game = create_game(
            Side(hand=[flight], battlefield=[katana], mana=_W),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act_illegal(
            0, flight, choices=[katana], note="an artifact is no target for Fleeting Flight"
        )
        t.run()


def _flight_on_lions(p1_battlefield, *, p0_library=(), p1_library=()):
    """Turn 1: player 0 casts Fleeting Flight on their Savannah Lions."""
    flight, lions = card(FleetingFlight), card(SavannahLions)
    game = create_game(
        Side(hand=[flight], battlefield=[lions], mana=_W, library=list(p0_library)),
        Side(battlefield=list(p1_battlefield), library=list(p1_library)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, flight, choices=[lions], then=[moves(flight, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(flight, Zone.GRAVEYARD)])
    return t, lions


def _attack(t, lions, *, block=None, illegal_block=None, then=()):
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    if illegal_block is not None:
        t.act_illegal(1, illegal_block, scoped={illegal_block: lions})
    if block is not None:
        t.act(1, block, scoped={block: lions})
    else:
        t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=list(then))


class TestFleetingFlightResolution:
    """Targeting and resolution run through normal casting."""

    def test_missing_required_target_rejects_before_payment(self) -> None:
        flight, lions = card(FleetingFlight), card(SavannahLions)
        game = create_game(
            Side(hand=[flight, lions], mana=_W), Side(), start=(Phase.PRECOMBAT_MAIN, 0)
        )
        t = Table(game)
        t.act_illegal(0, flight, note="no creature to target")
        t.act(
            0,
            lions,
            then=[moves(lions, Zone.STACK)],
            note="the {W} is still there to pay for the Lions",
        )
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD)])
        t.run()

    def test_chosen_target_receives_counter_and_flying(self) -> None:
        """The 2/1 Lions attacks as a flying 3/2 that the Elves cannot block;
        on its next turn it has lost flying but keeps the counter, so the Elves
        blocks it and dies while it survives."""
        elves = card(LlanowarElves)
        t, lions = _flight_on_lions([elves], p0_library=[card(Plains)], p1_library=[card(Plains)])
        _attack(t, lions, illegal_block=elves, then=[life(1, 17)])
        t.pass_to(Step.UPKEEP, 0)
        _attack(t, lions, block=elves, then=[moves(elves, Zone.GRAVEYARD)])
        t.run()

    def test_targeted_creature_survives_combat_with_a_four_power_flyer(self) -> None:
        """It gets a +1/+1 counter and "prevent all combat damage that would be
        dealt to it this turn" (rule 615.1): the 2/1 target becomes a flying
        3/2 and survives a block by a 4/3 flyer, which its 3 damage kills."""
        buccaneer = card(SkyshipBuccaneer)
        t, lions = _flight_on_lions([buccaneer])
        _attack(t, lions, block=buccaneer, then=[moves(buccaneer, Zone.GRAVEYARD)])
        t.run()
