"""Reference test for FDN 249 — Adventuring Gear.

No static buff; a landfall trigger gives the equipped creature +2/+2 until end
of turn. See fdn_129/tests.py for the canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_249.card_impl import (
    AdventuringGear,
    AdventuringGearAbility1,
    AdventuringGearAbility2,
)
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import Equipment, printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from table import Table, life, moves, off_stack, on_stack, taps


class TestAdventuringGearProperties:
    def test_static_data(self):
        gear = AdventuringGear(owner=None)
        assert printed_class(gear) is AdventuringGear
        assert gear.mana_cost == ManaCost.parse("{1}")
        assert gear.equip_cost == ManaCost.parse("{1}")
        assert isinstance(gear, Equipment) and gear.is_equipment is True


def _equipped(*, hand=()):
    """Player 0's main phase: Adventuring Gear is equipped to Savannah Lions."""
    lions, gear = card(SavannahLions), card(AdventuringGear)
    game = create_game(
        Side(hand=list(hand), battlefield=[lions, gear], library=[card(Plains)], mana={ManaType.COLORLESS: 1}),
        Side(library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, AdventuringGearAbility2, choices=[lions], then=[on_stack(AdventuringGearAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AdventuringGearAbility2)])
    return t, lions


def _attack(t: Table, lions, total: int) -> None:
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, total)])


class TestAdventuringGearBehaviour:
    def test_no_static_buff(self):
        t, lions = _equipped()
        _attack(t, lions, 18)
        t.run()

    def test_landfall_pumps_until_end_of_turn(self):
        forest = card(Forest)
        t, lions = _equipped(hand=[forest])
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD), on_stack(AdventuringGearAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(AdventuringGearAbility1)])
        _attack(t, lions, 16)
        _attack(t, lions, 14)
        t.run()
