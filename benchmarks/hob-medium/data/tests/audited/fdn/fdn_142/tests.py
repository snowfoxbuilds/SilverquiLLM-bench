"""Reference test for FDN 142 — Healer's Hawk.

Illustrative test covering **blocker declaration / blocking restrictions**.
Healer's Hawk is a 1/1 with Flying + Lifelink. The flying keyword
restricts which creatures can legally block it: per the rules, a flying
attacker can only be blocked by creatures with flying or reach. The
engine encodes this in :func:`engine.combat._can_block`.
"""

from __future__ import annotations

from cards.fdn.fdn_142.card_impl import HealersHawk
from engine.card import Creature
from engine.combat import _can_block
from engine.types import Keyword, ManaCost


class TestHealersHawkProperties:
    """Static card data should match the FDN 142 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HealersHawk(owner=None), Creature)

    def test_name(self) -> None:
        assert HealersHawk(owner=None).name == "Healer's Hawk"

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
    def _ground_creature() -> Creature:
        c = Creature(name="Ground Bear", base_power=2, base_toughness=2)
        c.keywords = Keyword(0)
        c.is_tapped = False
        return c

    @staticmethod
    def _flying_creature() -> Creature:
        c = Creature(name="Air Bear", base_power=2, base_toughness=2)
        c.keywords = Keyword.FLYING
        c.is_tapped = False
        return c

    @staticmethod
    def _reach_creature() -> Creature:
        c = Creature(name="Spider", base_power=1, base_toughness=4)
        c.keywords = Keyword.REACH
        c.is_tapped = False
        return c

    def test_ground_creature_cannot_block_flying_attacker(self) -> None:
        attacker = HealersHawk(owner=None)
        blocker = self._ground_creature()
        assert _can_block(blocker, attacker) is False

    def test_flying_blocker_can_block_flying_attacker(self) -> None:
        attacker = HealersHawk(owner=None)
        blocker = self._flying_creature()
        assert _can_block(blocker, attacker) is True

    def test_reach_blocker_can_block_flying_attacker(self) -> None:
        attacker = HealersHawk(owner=None)
        blocker = self._reach_creature()
        assert _can_block(blocker, attacker) is True

    def test_tapped_creature_cannot_block(self) -> None:
        """Tapped creatures cannot be declared as blockers at all."""
        attacker = HealersHawk(owner=None)
        blocker = self._flying_creature()
        blocker.is_tapped = True
        assert _can_block(blocker, attacker) is False
