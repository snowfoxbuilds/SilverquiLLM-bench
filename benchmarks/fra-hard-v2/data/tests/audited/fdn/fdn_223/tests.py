"""Audited tests for FDN 223 — Giant Growth.

"Target creature gets +3/+3 until end of turn." The effect is locked onto
that creature when the spell resolves (rule 611.2c); if the creature leaves
the battlefield it returns as a new object the effect no longer applies to
(400.7), so a returned 2/2 dies to 2 damage.
"""

from __future__ import annotations

from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_122.card_impl import (
    KykarZephyrAwakener,
    KykarZephyrAwakenerAbility2,
    KykarZephyrAwakenerAbility3,
    KykarZephyrAwakenerAbility4,
)
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_187.card_impl import Zombify
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_250.card_impl import BurnishedHart
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Phase, Side, Step, Zone, card, create_game, player

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps

FLICKER, SPIRIT = KykarZephyrAwakenerAbility3, KykarZephyrAwakenerAbility4


def _cast(t, land, spell, *choices, then=()):
    """Player 0 taps ``land``, casts ``spell`` with ``choices``, and both
    players pass, resolving it."""
    t.act(0, land, then=[taps(land)])
    t.act(0, spell, choices=list(choices), then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), *then])


def _attack_unblocked(t, *attackers, then=()):
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, *attackers, then=[taps(a) for a in attackers])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=list(then))


def _cast_with_kykar(t, land, spell, *choices, mode, then=()):
    """Like :func:`_cast`, with Kykar's cast trigger resolving first in
    ``mode``. Kykar's mode and target are answered both as the trigger is
    put on the stack and as it resolves, whenever the engine asks."""
    t.act(0, land, then=[taps(land)])
    t.act(0, spell, choices=[*choices, mode], then=[moves(spell, Zone.STACK), on_stack(KykarZephyrAwakenerAbility2, 0)])
    t.pass_(0, choices=[mode, *choices])
    t.pass_(1, then=[off_stack(KykarZephyrAwakenerAbility2), *then])
    t.pass_(0)


class TestGiantGrowth:
    def test_target_gets_plus_three_until_end_of_turn(self) -> None:
        """The pumped 2/1 deals 5 while the other Lions deals 2; on the next
        turn it deals 2 again."""
        target, bystander, forest, growth = card(SavannahLions), card(SavannahLions), card(Forest), card(GiantGrowth)
        game = create_game(
            Side(hand=[growth], battlefield=[target, bystander, forest], library=[Plains]),
            Side(library=[Plains]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast(t, forest, growth, target)
        _attack_unblocked(t, target, bystander, then=[life(1, 13)])
        _attack_unblocked(t, target, then=[life(1, 11)])
        t.run()

    def test_pump_ends_when_the_target_is_exiled_and_returned(self) -> None:
        """Kykar exiles the pumped 2/2; it returns at the end step as a new
        object, and Burst Lightning's 2 damage kills it."""
        hart, growth, bolt, finisher = card(BurnishedHart), card(GiantGrowth), card(BurstLightning), card(BurstLightning)
        forest, mountain, other_mountain = card(Forest), card(Mountain), card(Mountain)
        game = create_game(
            Side(hand=[growth, bolt, finisher], battlefield=[KykarZephyrAwakener, hart, forest, mountain, other_mountain]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast_with_kykar(t, forest, growth, hart, mode=SPIRIT, then=[appears(0)])
        t.pass_(1, then=[moves(growth, Zone.GRAVEYARD)])
        _cast_with_kykar(t, mountain, bolt, player(1), hart, mode=FLICKER, then=[moves(hart, Zone.EXILE)])
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.pass_(0)
        t.pass_(1, then=[on_stack(KykarZephyrAwakenerAbility3, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(KykarZephyrAwakenerAbility3), moves(hart, Zone.BATTLEFIELD)])
        _cast_with_kykar(t, other_mountain, finisher, hart, mode=SPIRIT, then=[appears(0)])
        t.pass_(1, then=[moves(finisher, Zone.GRAVEYARD), moves(hart, Zone.GRAVEYARD)])
        t.run()

    def test_pump_ends_when_the_target_dies_and_returns(self) -> None:
        """The pumped 2/2 dies blocked by a 12/8; Zombify returns it as a new
        2/2, which Burst Lightning kills."""
        hart, growth, zombify, bolt = card(BurnishedHart), card(GiantGrowth), card(Zombify), card(BurstLightning)
        forest, mountain, swamps = card(Forest), card(Mountain), [card(Swamp) for _ in range(4)]
        ceratops = card(QuakestriderCeratops)
        game = create_game(
            Side(hand=[growth, zombify, bolt], battlefield=[hart, forest, mountain, *swamps]),
            Side(battlefield=[ceratops]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, hart, then=[taps(hart)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, ceratops, scoped={ceratops: hart})
        _cast(t, forest, growth, hart)
        t.pass_(0)
        t.pass_(1, then=[moves(hart, Zone.GRAVEYARD)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        for swamp in swamps[1:]:
            t.act(0, swamp, then=[taps(swamp)])
        _cast(t, swamps[0], zombify, hart, then=[moves(hart, Zone.BATTLEFIELD)])
        _cast(t, mountain, bolt, hart, then=[moves(hart, Zone.GRAVEYARD)])
        t.run()
