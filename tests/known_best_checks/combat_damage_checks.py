"""Known-Best combat damage follows the creatures in combat wherever their
cards sit, and the regular damage step deals damage only from the
combatants that had neither first nor double strike as the first-strike
step began, or have double strike now (rule 510.4).

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_214.card_impl import BrokenWings
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from cards.fdn.spg_77.card_impl import Embercleave, EmbercleaveAbility3
from engine.types import ManaType, Phase, Step, Zone
from test_interface import Side, card, create_game

from table import (
    Table,
    appears,
    first_strike_damage,
    gains_control,
    life,
    moves,
    off_stack,
    on_stack,
    taps,
)

MAIN = (Phase.PRECOMBAT_MAIN, 0)


def _tap(t, seat, lands):
    for land in lands:
        t.act(seat, land, then=[taps(land)])


def test_a_stolen_attacker_deals_its_combat_damage():
    lions, employment = card(SavannahLions), card(InvoluntaryEmployment)
    t = Table(create_game(Side(hand=[employment], mana={ManaType.RED: 4}), Side(battlefield=[lions]), start=MAIN))
    t.act(0, employment, choices=[lions], then=[moves(employment, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(employment, Zone.GRAVEYARD), gains_control(lions, 0), appears(0)])
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=[life(1, 18)])
    t.run()


def test_a_stolen_blocker_deals_its_combat_damage():
    attacker, stolen, employment = card(SavannahLions), card(SavannahLions), card(InvoluntaryEmployment)
    mountains = [card(Mountain) for _ in range(4)]
    t = Table(create_game(
        Side(battlefield=[attacker, stolen]),
        Side(hand=[employment], battlefield=[HighFaeTrickster, *mountains]),
        start=MAIN,
    ))
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, attacker, then=[taps(attacker)])
    t.pass_(0)
    _tap(t, 1, mountains)
    t.act(1, employment, choices=[stolen], then=[moves(employment, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(employment, Zone.GRAVEYARD), gains_control(stolen, 1), appears(1)])
    t.pass_(0)
    t.pass_(1)
    t.act(1, stolen, scoped={stolen: attacker})
    t.pass_(0)
    t.pass_(1, then=[moves(attacker, Zone.GRAVEYARD), moves(stolen, Zone.GRAVEYARD)], note="they trade")
    t.run()


def test_a_creature_that_lost_double_strike_deals_no_regular_damage():
    lions, cleave, wings = card(SavannahLions), card(Embercleave), card(BrokenWings)
    mountains, forests = [card(Mountain) for _ in range(5)], [card(Forest) for _ in range(3)]
    t = Table(create_game(
        Side(hand=[cleave], battlefield=[lions, *mountains]),
        Side(hand=[wings], battlefield=forests),
        start=MAIN,
    ))
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    _tap(t, 0, mountains)
    t.act(0, cleave, then=[moves(cleave, Zone.STACK)])
    t.pass_(0, choices=[lions])
    t.pass_(1, then=[moves(cleave, Zone.BATTLEFIELD), on_stack(EmbercleaveAbility3, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(EmbercleaveAbility3)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1, then=[first_strike_damage()])  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=[life(1, 17)], note="3 first-strike damage from the equipped Lions")
    t.pass_(0)
    _tap(t, 1, forests)
    t.act(1, wings, choices=[cleave], then=[moves(wings, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(wings, Zone.GRAVEYARD), moves(cleave, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, note="the Lions had double strike as the first-strike step began, and has lost it")
    final = t.run()
    assert final.players[1].life == 17
