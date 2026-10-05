"""Reference test for FDN 256 — Meteor Golem.

When Meteor Golem enters, it destroys target nonland permanent an opponent
controls. Player 0 casts it from a pool of seven mana in their main phase.
"""

from __future__ import annotations

from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_162.card_impl import RunAwayTogether
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_256.card_impl import MeteorGolem, MeteorGolemAbility1
from cards.fdn.fdn_258.card_impl import SwiftfootBoots
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game

from silverquillm.table import Table, appears, gains_control, moves, off_stack, on_stack, taps


def _golem_game(mine=(), theirs=(), their_hand=(), their_mana=None, mine_hand=()):
    golem = card(MeteorGolem)
    game = create_game(
        Side(hand=[golem, *mine_hand], battlefield=list(mine), mana={ManaType.COLORLESS: 7}),
        Side(hand=list(their_hand), battlefield=list(theirs), mana=their_mana or {}),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), golem


def _cast(t: Table, golem, targets) -> None:
    """Player 0 casts Meteor Golem; as it enters, its trigger goes on the
    stack with its target chosen from ``targets`` (rule 603.3d)."""
    t.act(0, golem, then=[moves(golem, Zone.STACK)])
    t.pass_(0, choices=targets)
    t.pass_(1, then=[moves(golem, Zone.BATTLEFIELD), on_stack(MeteorGolemAbility1, 0)])


def _resolve(t: Table, *then, note=None) -> None:
    t.pass_(0)
    t.pass_(1, then=[off_stack(MeteorGolemAbility1), *then], note=note)


class TestMeteorGolemProperties:
    def test_static_data(self):
        golem = MeteorGolem(owner=None)
        assert printed_class(golem) is MeteorGolem
        assert golem.mana_cost == ManaCost.parse("{7}")
        assert (golem.base_power, golem.base_toughness) == (3, 3)
        assert "Golem" in golem.subtypes


class TestMeteorGolemETB:
    def test_destroys_opponents_creature(self):
        lions = card(SavannahLions)
        t, golem = _golem_game(theirs=[lions])
        _cast(t, golem, [lions])
        _resolve(t, moves(lions, Zone.GRAVEYARD))
        t.run()

    def test_destroys_opponents_artifact(self):
        boots = card(SwiftfootBoots)
        t, golem = _golem_game(theirs=[boots])
        _cast(t, golem, [boots])
        _resolve(t, moves(boots, Zone.GRAVEYARD))
        t.run()

    def test_option_set_excludes_lands_and_own_permanents(self):
        """Player 0 would rather destroy the opponent's Forest, or their own
        Elves, but only the opponent's nonland permanent can be targeted."""
        elves, lions, forest = card(LlanowarElves), card(SavannahLions), card(Forest)
        t, golem = _golem_game(mine=[elves], theirs=[lions, forest])
        _cast(t, golem, [forest, elves, lions])
        _resolve(t, moves(lions, Zone.GRAVEYARD))
        t.run()

    def test_target_becomes_caster_controlled_before_resolution_not_destroyed(self):
        """Negative revalidation: with the trigger on the stack, player 0,
        whose High Fae Trickster lets them cast Involuntary Employment at
        instant speed, takes the target, so it is no longer 'a permanent an
        opponent controls' and is not destroyed."""
        lions, employment = card(SavannahLions), card(InvoluntaryEmployment)
        mountains = [card(Mountain) for _ in range(4)]
        t, golem = _golem_game(mine=[HighFaeTrickster, *mountains], theirs=[lions], mine_hand=[employment])
        _cast(t, golem, [lions])
        for mountain in mountains:
            t.act(0, mountain, then=[taps(mountain)])
        t.act(0, employment, choices=[lions], then=[moves(employment, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(employment, Zone.GRAVEYARD), gains_control(lions, 0), appears(0)])
        _resolve(t, note="the Lions, now player 0's, is not destroyed")
        t.run()

    def test_target_leaves_and_returns_before_resolution_not_destroyed(self):
        """The target leaves the battlefield and returns before Meteor Golem's
        destruction happens: the returned Spectral Sailor is a new object, so
        it is not destroyed."""
        lions, sailor, together = card(SavannahLions), card(SpectralSailor), card(RunAwayTogether)
        t, golem = _golem_game(
            mine=[lions], theirs=[sailor], their_hand=[together], their_mana={ManaType.BLUE: 3}
        )
        _cast(t, golem, [sailor])
        t.pass_(0)
        t.act(1, together, choices=[sailor, lions], then=[moves(together, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(together, Zone.GRAVEYARD), moves(sailor, Zone.HAND), moves(lions, Zone.HAND)])
        t.pass_(0)
        t.act(1, sailor, then=[moves(sailor, Zone.STACK)], note="Spectral Sailor has flash")
        t.pass_(1)
        t.pass_(0, then=[moves(sailor, Zone.BATTLEFIELD)])
        _resolve(t, note="the returned Sailor is not destroyed")
        t.run()
