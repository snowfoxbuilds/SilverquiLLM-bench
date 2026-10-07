"""Reference test for FDN 258 — Swiftfoot Boots.

Equipped creature has hexproof and haste. These tests judge haste, by
when the equipped creature can attack.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_258.card_impl import SwiftfootBoots, SwiftfootBootsAbility2
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import Equipment, printed_class
from engine.types import ManaCost
from test_interface import Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, life, moves, off_stack, on_stack, taps


class TestSwiftfootBootsProperties:
    def test_static_data(self):
        boots = SwiftfootBoots(owner=None)
        assert printed_class(boots) is SwiftfootBoots
        assert boots.mana_cost == ManaCost.parse("{2}")
        assert boots.equip_cost == ManaCost.parse("{1}")
        assert isinstance(boots, Equipment) and boots.is_equipment is True


def _equip(t: Table, plains, creature) -> None:
    t.act(0, plains, then=[taps(plains)])
    t.act(0, SwiftfootBootsAbility2, choices=[creature], then=[on_stack(SwiftfootBootsAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(SwiftfootBootsAbility2)])


def _lions_cast_this_turn(*others, extra_plains=0):
    """Player 0 casts Savannah Lions and equips Swiftfoot Boots to it."""
    lions, boots = card(SavannahLions), card(SwiftfootBoots)
    plains = [card(Plains) for _ in range(2 + extra_plains)]
    game = create_game(
        Side(hand=[lions], battlefield=[boots, *others, *plains]),
        Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, plains[0], then=[taps(plains[0])])
    t.act(0, lions, then=[moves(lions, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD)])
    _equip(t, plains[1], lions)
    return t, lions, plains[2:]


class TestSwiftfootBootsBehaviour:
    def test_grants_haste(self):
        """The Lions cast this turn attacks at once."""
        t, lions, _ = _lions_cast_this_turn()
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, lions, then=[taps(lions)], note="haste")
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 18)])
        t.run()

    def test_moving_the_boots_ends_haste(self):
        """Equipped to another creature, the Boots no longer give the Lions
        haste, so it cannot attack the turn it was cast."""
        elves = card(LlanowarElves)
        t, lions, (plains,) = _lions_cast_this_turn(elves, extra_plains=1)
        _equip(t, plains, elves)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act_illegal(0, lions, note="the Lions is summoning sick again")
        t.pass_(0)
        t.pass_to(Step.END, 0)
        t.run()
