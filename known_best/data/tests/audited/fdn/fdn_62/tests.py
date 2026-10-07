"""Reference test for FDN 62 — Hungry Ghoul.

The "Sacrifice another creature" cost is chosen when the cost is paid, by a
Player Query: the pattern for a non-mana cost that names a permanent. The
+1/+1 counter shows in the Ghoul's combat damage.
"""

from __future__ import annotations

from cards.fdn.fdn_62.card_impl import HungryGhoul, HungryGhoulAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from table import Table, life, moves, off_stack, on_stack, taps

_ONE = {ManaType.BLACK: 1}


class TestHungryGhoulProperties:
    def test_static_data(self):
        ghoul = HungryGhoul(owner=None)
        assert printed_class(ghoul) is HungryGhoul
        assert ghoul.mana_cost == ManaCost.parse("{1}{B}")
        assert (ghoul.base_power, ghoul.base_toughness) == (2, 2)


class TestHungryGhoulSacrifice:
    def test_sacrifice_pays_cost_and_adds_counter(self):
        """The Lions is sacrificed as the cost; the counter makes the Ghoul
        hit for 3."""
        ghoul, fodder = card(HungryGhoul), card(SavannahLions)
        game = create_game(
            Side(battlefield=[ghoul, fodder], mana=_ONE), Side(), start=(Phase.PRECOMBAT_MAIN, 0)
        )
        t = Table(game)
        t.act(
            0,
            HungryGhoulAbility1,
            choices=[fodder],
            then=[moves(fodder, Zone.GRAVEYARD), on_stack(HungryGhoulAbility1, 0)],
        )
        t.pass_(0)
        t.pass_(1, then=[off_stack(HungryGhoulAbility1)])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, ghoul, then=[taps(ghoul)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 17)])
        t.run()

    def test_no_other_creature_cannot_pay(self):
        """With no *other* creature to sacrifice, the cost cannot be paid and the
        activation is rejected (Ghoul cannot sacrifice itself)."""
        ghoul = card(HungryGhoul)
        game = create_game(
            Side(battlefield=[ghoul], mana=_ONE), Side(), start=(Phase.PRECOMBAT_MAIN, 0)
        )
        t = Table(game)
        t.act_illegal(0, HungryGhoulAbility1, choices=[ghoul])
        t.run()

    def test_opponent_creature_not_a_valid_sacrifice(self):
        """The sacrifice must be a creature *you* control, so with only the
        opponent's creature the cost cannot be paid."""
        ghoul, theirs = card(HungryGhoul), card(SavannahLions)
        game = create_game(
            Side(battlefield=[ghoul], mana=_ONE),
            Side(battlefield=[theirs]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act_illegal(0, HungryGhoulAbility1, choices=[theirs])
        t.run()
