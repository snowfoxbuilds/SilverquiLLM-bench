"""Reference test for SPG 74 — Condemn.

Condemn puts target attacking creature on the bottom of its owner's library,
and that creature's controller gains life equal to its toughness. Each test
plays player 1's attack and player 0's Condemn in the declare attackers step.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.spg_74.card_impl import Condemn
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, life, moves, taps


def _attack(*, attackers, others=(), hand=()):
    """Player 1 attacks with ``attackers``; player 0, holding Condemn and a
    Plains, taps the Plains in the declare attackers step."""
    condemn, plains = card(Condemn), card(Plains)
    game = create_game(
        Side(hand=[condemn, *hand], battlefield=[plains]),
        Side(battlefield=[*attackers, *others], library=[card(Plains)]),
        start=(Step.BEGIN_COMBAT, 1),
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, *attackers, then=[taps(a) for a in attackers])
    t.pass_(1)
    t.act(0, plains, then=[taps(plains)])
    return t, condemn


def _condemn(t: Table, condemn, targets, *, then) -> None:
    t.act(0, condemn, choices=targets, then=[moves(condemn, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(condemn, Zone.GRAVEYARD), *then])


class TestCondemnProperties:
    def test_static_data(self):
        c = Condemn(owner=None)
        assert printed_class(c) is Condemn
        assert c.mana_cost == ManaCost.parse("{W}")

    def test_get_targets_requirement_filters_attackers(self):
        """Player 0 would rather condemn the creature that stayed home, but only
        the attacker can be targeted."""
        attacker, idle = card(SavannahLions), card(SavannahLions)
        t, condemn = _attack(attackers=[attacker], others=[idle])
        _condemn(t, condemn, [idle, attacker], then=[moves(attacker, Zone.LIBRARY, bottom=True), life(1, 21)])
        t.run()


class TestCondemnResolve:
    def test_puts_attacker_on_bottom_of_library(self):
        lions = card(SavannahLions)
        t, condemn = _attack(attackers=[lions])
        _condemn(t, condemn, [lions], then=[moves(lions, Zone.LIBRARY, bottom=True), life(1, 21)])
        t.run()

    def test_controller_gains_life_equal_to_toughness(self):
        turtle = card(AegisTurtle)
        t, condemn = _attack(attackers=[turtle])
        _condemn(t, condemn, [turtle], then=[moves(turtle, Zone.LIBRARY, bottom=True), life(1, 25)])
        t.run()

    def test_cost_is_paid(self):
        """Condemn spends the Plains' white mana, so a second Condemn cannot be
        cast."""
        lions, turtle, second = card(SavannahLions), card(AegisTurtle), card(Condemn)
        t, condemn = _attack(attackers=[lions, turtle], hand=[second])
        _condemn(t, condemn, [lions], then=[moves(lions, Zone.LIBRARY, bottom=True), life(1, 21)])
        t.pass_(1)
        t.act_illegal(0, second, choices=[turtle])
        t.pass_(0)
        t.run()

    def test_no_attacking_creature_makes_spell_uncastable(self):
        """Required target: a non-attacking creature is not a legal target, so
        with no attackers the spell cannot be cast."""
        condemn, idle = card(Condemn), card(SavannahLions)
        game = create_game(
            Side(hand=[condemn], mana={ManaType.WHITE: 1}),
            Side(battlefield=[idle]),
            start=(Phase.PRECOMBAT_MAIN, 1),
        )
        t = Table(game)
        t.pass_(1)
        t.act_illegal(0, condemn, choices=[idle])
        t.pass_(0)
        t.run()
