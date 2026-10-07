"""Reference test for FDN 142 — Healer's Hawk.

Illustrative test covering **blocker declaration / blocking restrictions**.
Healer's Hawk is a 1/1 with Flying + Lifelink. The flying keyword
restricts which creatures can legally block it: per the rules, a flying
attacker can only be blocked by creatures with flying or reach. The
tests play the attack at the table: Healer's Hawk attacks, player 1 tries
to block it, and the life totals and the graveyard show what happened.
"""

from __future__ import annotations

from cards.fdn.fdn_52.card_impl import StrixLookout
from cards.fdn.fdn_114.card_impl import TreetopSnarespinner
from cards.fdn.fdn_142.card_impl import HealersHawk
from cards.fdn.fdn_146.card_impl import SavannahLions
from engine.card import Creature, printed_class
from engine.types import Keyword, ManaCost
from test_interface import Side, Step, Zone, card, create_game

from table import Table, life, moves, taps


class TestHealersHawkProperties:
    """Static card data should match the FDN 142 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HealersHawk(owner=None), Creature)

    def test_name(self) -> None:
        assert printed_class(HealersHawk(owner=None)) is HealersHawk

    def test_mana_cost(self) -> None:
        assert HealersHawk(owner=None).mana_cost == ManaCost.parse("{W}")

    def test_power_toughness(self) -> None:
        card = HealersHawk(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_has_flying_and_lifelink(self) -> None:
        kw = HealersHawk(owner=None).keywords
        assert Keyword.FLYING in kw
        assert Keyword.LIFELINK in kw


class TestHealersHawkBlockerRules:
    """Flying restricts which creatures can legally block this attacker."""

    @staticmethod
    def _attack(blocker):
        """Player 0's Healer's Hawk attacks into player 1's ``blocker``."""
        hawk = card(HealersHawk)
        game = create_game(Side(battlefield=[hawk]), Side(battlefield=[blocker]), start=(Step.BEGIN_COMBAT, 0))
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, hawk, then=[taps(hawk)])
        t.pass_(0)
        t.pass_(1)
        return t, hawk

    @staticmethod
    def _unblocked(t):
        t.pass_(1, note="no block")
        t.pass_(0)
        t.pass_(1, then=[life(1, 19), life(0, 21)], note="1 damage, and lifelink gains 1")
        t.run()

    def test_ground_creature_cannot_block_flying_attacker(self) -> None:
        lions = card(SavannahLions)
        t, hawk = self._attack(lions)
        t.act_illegal(1, lions, scoped={lions: hawk})
        self._unblocked(t)

    def test_flying_blocker_can_block_flying_attacker(self) -> None:
        strix = card(StrixLookout)
        t, hawk = self._attack(strix)
        t.act(1, strix, scoped={strix: hawk})
        t.pass_(0)
        t.pass_(1, then=[moves(hawk, Zone.GRAVEYARD), life(0, 21)], note="the 1/2 flier survives and kills the Hawk")
        t.run()

    def test_reach_blocker_can_block_flying_attacker(self) -> None:
        spider = card(TreetopSnarespinner)
        t, hawk = self._attack(spider)
        t.act(1, spider, scoped={spider: hawk})
        t.pass_(0)
        t.pass_(1, then=[moves(hawk, Zone.GRAVEYARD), life(0, 21)], note="the reach blocker kills the Hawk")
        t.run()

    def test_tapped_creature_cannot_block(self) -> None:
        strix = card(StrixLookout, tapped=True)
        t, hawk = self._attack(strix)
        t.act_illegal(1, strix, scoped={strix: hawk})
        self._unblocked(t)
