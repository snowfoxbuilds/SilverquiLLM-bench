"""Audited tests for FDN 117 — Ashroot Animist.

"Whenever this creature attacks, another target creature you control gains
trample and gets +X/+X until end of turn, where X is this creature's power."
X is read when the ability resolves: from the Animist while it remains on the
battlefield, otherwise as it last existed there (rule 608.2h).

The Animist (4/4) attacks beside Savannah Lions (2/1), its trigger targets the
Lions, and player 1's Llanowar Elves (1/1) blocks the Lions: the damage that
tramples over the Elves shows the Lions' new power.
"""

from __future__ import annotations

from cards.fdn.fdn_117.card_impl import AshrootAnimist, AshrootAnimistAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_162.card_impl import RunAwayTogether
from cards.fdn.fdn_174.card_impl import FakeYourOwnDeath, FakeYourOwnDeathAbility1
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Decision, Side, Step, Zone, card, create_game

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps

ANIMIST = AshrootAnimistAbility2


def _attacking(*, p0_hand=(), p0_lands=(), p1_hand=(), p1_lands=()):
    """The Animist and the Lions attack; the Animist's trigger, targeting the
    Lions, is on the stack and player 0 has priority."""
    animist, lions, elves = card(AshrootAnimist), card(SavannahLions), card(LlanowarElves)
    game = create_game(
        Side(hand=list(p0_hand), battlefield=[animist, lions, *p0_lands]),
        Side(hand=list(p1_hand), battlefield=[elves, *p1_lands]),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    # The declared creatures also answer the trigger's target: an engine that
    # offers the Animist itself and rejects it is answered with the Lions first.
    t.act(0, branches=[[animist, lions], [lions, animist]], choices=[lions],
          then=[taps(animist), taps(lions), on_stack(ANIMIST, 0)])
    return t, animist, lions, elves


def _resolve_and_block(t, lions, elves, *, damage):
    """The trigger resolves; the Elves blocks the trampling Lions, takes 1 and
    dies, and player 1 takes ``damage``."""
    t.pass_(0, choices=[lions])
    t.pass_(1, then=[off_stack(ANIMIST)])
    t.pass_(0)
    t.pass_(1)
    t.act(1, elves, scoped={elves: lions})
    t.pass_(0, per_query={elves: [Decision.number(1)]})
    t.pass_(1, then=[moves(elves, Zone.GRAVEYARD), life(1, 20 - damage)])


def _tap(t, seat, *lands):
    for land in lands:
        t.act(seat, land, then=[taps(land)])


def _cast(t, seat, spell, *, choices, then=()):
    """``seat`` casts ``spell`` and both players pass, so it resolves."""
    t.act(seat, spell, choices=choices, then=[moves(spell, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(spell, Zone.GRAVEYARD), *then])


class TestAshrootAnimistAttack:
    def test_another_creature_gets_plus_x_and_trample(self) -> None:
        t, _animist, lions, elves = _attacking()
        _resolve_and_block(t, lions, elves, damage=4 + 5)
        t.run()

    def test_power_gained_after_triggering_counts_while_it_stays(self) -> None:
        """Giant Growth on the Animist in response makes X 7: the 9/8 Lions
        tramples 8 over the Elves, beside the Animist's 7."""
        growth, forest = card(GiantGrowth), card(Forest)
        t, animist, lions, elves = _attacking(p0_hand=[growth], p0_lands=[forest])
        _tap(t, 0, forest)
        _cast(t, 0, growth, choices=[animist])
        _resolve_and_block(t, lions, elves, damage=7 + 8)
        t.run()

    def test_uses_its_power_as_it_last_existed_if_it_left(self) -> None:
        """Giant Growth makes the Animist a 7/7, then Hero's Downfall destroys
        it before its trigger resolves: X is 7, its power as it last existed,
        not the 4 of the card in the graveyard."""
        growth, forest = card(GiantGrowth), card(Forest)
        downfall, swamps = card(HerosDownfall), [card(Swamp) for _ in range(3)]
        t, animist, lions, elves = _attacking(p0_hand=[growth], p0_lands=[forest], p1_hand=[downfall], p1_lands=swamps)
        _tap(t, 0, forest)
        _cast(t, 0, growth, choices=[animist])
        t.pass_(0)
        _tap(t, 1, *swamps)
        _cast(t, 1, downfall, choices=[animist], then=[moves(animist, Zone.GRAVEYARD)])
        _resolve_and_block(t, lions, elves, damage=8)
        t.run()

    def test_a_later_return_and_departure_do_not_change_the_pending_power(self) -> None:
        """Fake Your Own Death makes the Animist a 6/4; destroyed, it returns
        tapped as a new 4/4 object, which Run Away Together then returns to
        hand. X is still 6, the power of the Animist that attacked, as it
        last existed."""
        fake, swamps0 = card(FakeYourOwnDeath), [card(Swamp) for _ in range(2)]
        downfall, swamps1 = card(HerosDownfall), [card(Swamp) for _ in range(3)]
        bounce, islands, other = card(RunAwayTogether), [card(Island) for _ in range(2)], card(SavannahLions)
        t, animist, lions, elves = _attacking(
            p0_hand=[fake], p0_lands=swamps0, p1_hand=[downfall, bounce], p1_lands=[other, *swamps1, *islands],
        )
        _tap(t, 0, *swamps0)
        _cast(t, 0, fake, choices=[animist])
        t.pass_(0)
        _tap(t, 1, *swamps1)
        _cast(t, 1, downfall, choices=[animist], then=[moves(animist, Zone.GRAVEYARD), on_stack(FakeYourOwnDeathAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(FakeYourOwnDeathAbility1), moves(animist, Zone.BATTLEFIELD), taps(animist), appears(0)])
        t.pass_(0)
        _tap(t, 1, *islands)
        _cast(t, 1, bounce, choices=[animist, other], then=[moves(animist, Zone.HAND), moves(other, Zone.HAND)])
        _resolve_and_block(t, lions, elves, damage=7)
        t.run()
