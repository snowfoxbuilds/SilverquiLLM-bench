"""Reference test for FDN 38 — Faebloom Trick.

"Create two 1/1 blue Faerie creature tokens with flying. When you do, tap
target creature an opponent controls." The spell always makes the Faeries;
its reflexive "when you do" ability is a triggered ability whose target is
chosen as it goes on the stack, so with no opponent creature it is removed
(rule 603.3d) and the spell still makes its tokens.
"""

from __future__ import annotations

from cards.fdn.fdn_38.card_impl import FaebloomTrick, FaebloomTrickAbility1
from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import CardType, ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, gains_control, life, moves, off_stack, on_stack, taps


def _trick_at(lions, *, mine=(), hand=()):
    """Player 0 casts Faebloom Trick, aiming its reflexive tap at player 1's
    ``lions``: the spell makes two Faeries, and the reflexive trigger goes on
    the stack targeting the Lions."""
    trick = card(FaebloomTrick)
    game = create_game(
        Side(hand=[trick, *hand], battlefield=list(mine), mana={ManaType.BLUE: 3}),
        Side(battlefield=[lions]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, trick, then=[moves(trick, Zone.STACK)])
    t.pass_(0, choices=[lions])
    t.pass_(1, then=[moves(trick, Zone.GRAVEYARD), appears(0), appears(0), on_stack(FaebloomTrickAbility1, 0)])
    return t


def _trick_without_target(trick, *, extra_hand=(), p0_library=(), p1=None):
    """Turn 1: player 0 casts Faebloom Trick while player 1 controls no
    creature, and it makes two Faerie tokens."""
    p1 = p1 or Side()
    game = create_game(
        Side(hand=[trick, *extra_hand], mana={ManaType.BLUE: 3}, library=list(p0_library)),
        p1,
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, trick, then=[moves(trick, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(trick, Zone.GRAVEYARD), appears(0), appears(0)])
    return t


class TestFaebloomTrickProperties:
    def test_static_data(self):
        c = FaebloomTrick(owner=None)
        assert printed_class(c) is FaebloomTrick
        assert c.mana_cost == ManaCost.parse("{2}{U}")
        assert CardType.INSTANT in c.card_types


class TestFaebloomTrickResolve:
    def test_creates_two_flying_faeries_and_taps_target(self):
        """The reflexive "when you do" trigger taps the opponent's Lions."""
        lions = card(SavannahLions)
        t = _trick_at(lions)
        t.pass_(0)
        t.pass_(1, then=[off_stack(FaebloomTrickAbility1), taps(lions)])
        t.run()

    def test_cost_is_paid(self):
        """The three blue mana pay for one Trick, so a second is unaffordable."""
        trick, second = card(FaebloomTrick), card(FaebloomTrick)
        t = _trick_without_target(trick, extra_hand=[second])
        t.act_illegal(0, second, note="the mana pool is empty")
        t.run()

    def test_castable_with_no_target_still_makes_tokens(self):
        """With no opponent creature the spell still resolves and makes both
        tokens; the reflexive tap has no target, so nothing else happens."""
        t = _trick_without_target(card(FaebloomTrick))
        t.run()


class TestFaebloomTrickRevalidation:
    """Rule 608.2b: the reflexive tap revalidates the FULL predicate ("a
    creature an opponent controls") at resolution, not merely presence."""

    def test_no_tap_when_target_leaves_opponent_control(self):
        """With the reflexive trigger on the stack, player 0, whose High Fae
        Trickster lets them cast Involuntary Employment at instant speed,
        takes the Lions: no longer "a creature an opponent controls", it is
        not tapped."""
        lions, employment = card(SavannahLions), card(InvoluntaryEmployment)
        mountains = [card(Mountain) for _ in range(4)]
        t = _trick_at(lions, mine=[HighFaeTrickster, *mountains], hand=[employment])
        for mountain in mountains:
            t.act(0, mountain, then=[taps(mountain)])
        t.act(0, employment, choices=[lions], then=[moves(employment, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(employment, Zone.GRAVEYARD), gains_control(lions, 0), appears(0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(FaebloomTrickAbility1)], note="the Lions stays untapped")
        t.run()


class TestFaebloomTrickTokenIdentity:
    """The two minted tokens are 1/1 flying Faeries: on player 0's next turn
    they attack over the Savannah Lions player 1 cast meanwhile, for 1 each."""

    def test_tokens_are_blue_flying_faeries(self):
        lions, plains = card(SavannahLions), card(Plains)
        t = _trick_without_target(
            card(FaebloomTrick),
            p0_library=[card(Island)],
            p1=Side(hand=[lions], battlefield=[plains], library=[card(Plains)]),
        )
        t.pass_(0)
        t.pass_(1)
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        t.act(1, plains, then=[taps(plains)])
        t.act(1, lions, then=[moves(lions, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(lions, Zone.BATTLEFIELD)])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, token(1), token(2), then=[taps(token(1)), taps(token(2))])
        t.pass_(0)
        t.pass_(1)
        t.act_illegal(1, lions, scoped={lions: token(1)}, note="the Lions cannot block a flier")
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 18)])
        t.run()
