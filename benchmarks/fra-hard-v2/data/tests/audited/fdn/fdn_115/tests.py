"""Audited tests for FDN 115 — Alesha, Who Laughs at Fate.

"Whenever Alesha attacks, put a +1/+1 counter on it. Raid — At the beginning
of your end step, if you attacked this turn, return target creature card with
mana value less than or equal to Alesha's power from your graveyard to the
battlefield." Alesha's power is read when the raid ability resolves: from
Alesha while it remains on the battlefield, otherwise as it last existed there
(rule 608.2h).

Alesha attacks once, so its attack trigger makes it a 3/3, and the raid
ability returns Inspiring Paladin, a mana value 3 creature card.
"""

from __future__ import annotations

from cards.fdn.fdn_18.card_impl import InspiringPaladin
from cards.fdn.fdn_115.card_impl import (
    AleshaWhoLaughsAtFate,
    AleshaWhoLaughsAtFateAbility2,
    AleshaWhoLaughsAtFateAbility3,
)
from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility2
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Phase, Side, Step, Zone, card, create_game

from table import Table, first_strike_damage, life, moves, off_stack, on_stack, taps

RAID = AleshaWhoLaughsAtFateAbility3


def _raid_pending(p1_hand=(), p1_battlefield=()):
    """Alesha attacks unblocked (its attack trigger makes it a 3/3), and its
    raid trigger goes on the stack at the end step with Inspiring Paladin in
    the graveyard."""
    alesha, paladin = card(AleshaWhoLaughsAtFate), card(InspiringPaladin)
    game = create_game(
        Side(battlefield=[alesha], graveyard=[paladin]),
        Side(hand=list(p1_hand), battlefield=list(p1_battlefield)),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, alesha, then=[taps(alesha), on_stack(AleshaWhoLaughsAtFateAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AleshaWhoLaughsAtFateAbility2)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1, then=[first_strike_damage()])
    t.pass_(0)
    t.pass_(1, then=[life(1, 17)], note="Alesha is a 3/3 with first strike")
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0, choices=[paladin])
    t.pass_(1, then=[on_stack(RAID, 0)])
    return t, alesha, paladin


class TestAleshaRaid:
    def test_returns_a_creature_card_with_mana_value_up_to_its_power(self) -> None:
        t, _alesha, paladin = _raid_pending()
        t.pass_(0, choices=[paladin])
        t.pass_(1, then=[off_stack(RAID), moves(paladin, Zone.BATTLEFIELD)])
        t.run()

    def test_uses_its_power_as_it_last_existed_if_it_left(self) -> None:
        abrade, first, second = card(Abrade), card(Mountain), card(Mountain)
        t, alesha, paladin = _raid_pending(p1_hand=[abrade], p1_battlefield=[first, second])
        t.pass_(0, choices=[paladin])
        # In response, player 1 deals 3 damage to the 3/3 Alesha.
        t.act(1, first, then=[taps(first)])
        t.act(1, second, then=[taps(second)])
        t.act(1, abrade, choices=[AbradeAbility2, alesha], then=[moves(abrade, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(abrade, Zone.GRAVEYARD), moves(alesha, Zone.GRAVEYARD)])
        t.pass_(0, choices=[paladin])
        t.pass_(1, then=[off_stack(RAID), moves(paladin, Zone.BATTLEFIELD)],
                note="Alesha's power as it last existed, 3, still allows mana value 3")
        t.run()
