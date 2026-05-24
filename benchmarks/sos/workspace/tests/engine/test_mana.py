"""Tests for engine/mana.py — ManaPool and cost payment logic.

Verifies:
- ManaPool construction starts empty.
- add() increases mana of specified type; get() and total() reflect changes.
- add() with amount=0 is a no-op (no error).
- add() with negative amount raises ValueError.
- empty() clears all mana in the pool back to zero.
- can_pay returns True for exact colored cost match.
- can_pay returns False for insufficient colored mana.
- can_pay returns True when generic cost can be satisfied by colored mana.
- can_pay returns False when total mana is insufficient.
- can_pay treats X as 0 (cost with X portion is payable if non-X portion covered).
- pay with exact cost deducts correctly and returns True.
- pay with insufficient mana returns False and pool is unchanged.
- pay with generic cost and explicit choices dict.
- pay with generic cost and auto-pay (choices=None) prefers colorless for generic.
- pay deducts colored pips first, then generic.
- Pool state after pay reflects deductions.
- Multiple sequential pays draining pool.
- Edge: pay zero cost always succeeds.
- Edge: add zero amount.
- Player.mana_pool is a ManaPool instance.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType


# ---------------------------------------------------------------------------
# ManaPool — construction
# ---------------------------------------------------------------------------
class TestManaPoolConstruction:
    """Tests for ManaPool initial state."""

    def test_new_pool_total_is_zero(self) -> None:
        """A freshly constructed ManaPool should have total() == 0."""
        pool = ManaPool()
        assert pool.total() == 0

    def test_new_pool_get_returns_zero_for_all_types(self) -> None:
        """get() should return 0 for every ManaType on a new pool."""
        pool = ManaPool()
        for mt in ManaType:
            assert pool.get(mt) == 0


# ---------------------------------------------------------------------------
# ManaPool — add, get, total
# ---------------------------------------------------------------------------
class TestManaPoolAdd:
    """Tests for ManaPool.add(), get(), and total()."""

    def test_add_single_type(self) -> None:
        """Adding mana of one type should be reflected by get() and total()."""
        pool = ManaPool()
        pool.add(ManaType.RED, 3)
        assert pool.get(ManaType.RED) == 3
        assert pool.total() == 3

    def test_add_multiple_types(self) -> None:
        """Adding mana of different types should be tracked independently."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 2)
        pool.add(ManaType.BLUE, 1)
        assert pool.get(ManaType.WHITE) == 2
        assert pool.get(ManaType.BLUE) == 1
        assert pool.get(ManaType.RED) == 0
        assert pool.total() == 3

    def test_add_same_type_accumulates(self) -> None:
        """Multiple add() calls for the same type should accumulate."""
        pool = ManaPool()
        pool.add(ManaType.GREEN, 2)
        pool.add(ManaType.GREEN, 3)
        assert pool.get(ManaType.GREEN) == 5
        assert pool.total() == 5

    def test_add_colorless(self) -> None:
        """Adding colorless mana should work the same as colored."""
        pool = ManaPool()
        pool.add(ManaType.COLORLESS, 4)
        assert pool.get(ManaType.COLORLESS) == 4
        assert pool.total() == 4

    def test_add_zero_amount_is_noop(self) -> None:
        """Adding 0 mana should not raise and should not change totals."""
        pool = ManaPool()
        pool.add(ManaType.RED, 0)
        assert pool.get(ManaType.RED) == 0
        assert pool.total() == 0

    def test_add_default_amount_is_one(self) -> None:
        """add() without an explicit amount should add 1."""
        pool = ManaPool()
        pool.add(ManaType.BLACK)
        assert pool.get(ManaType.BLACK) == 1

    def test_add_negative_raises_value_error(self) -> None:
        """Adding a negative amount should raise ValueError."""
        pool = ManaPool()
        with pytest.raises(ValueError):
            pool.add(ManaType.RED, -1)


# ---------------------------------------------------------------------------
# ManaPool — empty
# ---------------------------------------------------------------------------
class TestManaPoolEmpty:
    """Tests for ManaPool.empty()."""

    def test_empty_clears_all_mana(self) -> None:
        """empty() should set all mana types to 0."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 3)
        pool.add(ManaType.BLUE, 2)
        pool.add(ManaType.COLORLESS, 5)
        pool.empty()
        assert pool.total() == 0
        for mt in ManaType:
            assert pool.get(mt) == 0

    def test_empty_on_already_empty_pool(self) -> None:
        """empty() on an already-empty pool should be a safe no-op."""
        pool = ManaPool()
        pool.empty()
        assert pool.total() == 0


# ---------------------------------------------------------------------------
# ManaPool — can_pay
# ---------------------------------------------------------------------------
class TestManaPoolCanPay:
    """Tests for ManaPool.can_pay()."""

    def test_can_pay_exact_colored_cost(self) -> None:
        """can_pay should return True when pool has exactly the colored cost."""
        pool = ManaPool()
        pool.add(ManaType.RED, 2)
        cost = ManaCost(generic=0, pips={ManaType.RED: 2})
        assert pool.can_pay(cost) is True

    def test_can_pay_insufficient_colored(self) -> None:
        """can_pay should return False when pool lacks colored mana."""
        pool = ManaPool()
        pool.add(ManaType.RED, 1)
        cost = ManaCost(generic=0, pips={ManaType.RED: 2})
        assert pool.can_pay(cost) is False

    def test_can_pay_generic_satisfied_by_colored(self) -> None:
        """can_pay should return True when generic cost is covered by excess colored mana."""
        pool = ManaPool()
        pool.add(ManaType.GREEN, 3)
        # Cost: {1}{G} — 1 generic + 1 green pip
        cost = ManaCost(generic=1, pips={ManaType.GREEN: 1})
        assert pool.can_pay(cost) is True

    def test_can_pay_generic_satisfied_by_colorless(self) -> None:
        """can_pay should return True when generic cost is covered by colorless mana."""
        pool = ManaPool()
        pool.add(ManaType.COLORLESS, 3)
        cost = ManaCost(generic=3)
        assert pool.can_pay(cost) is True

    def test_can_pay_insufficient_total(self) -> None:
        """can_pay should return False when total mana is less than total cost."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        # Cost: {3}{W} — needs 4 total
        cost = ManaCost(generic=3, pips={ManaType.WHITE: 1})
        assert pool.can_pay(cost) is False

    def test_can_pay_treats_x_as_zero(self) -> None:
        """can_pay should treat X as 0 — cost is payable if non-X portion is covered."""
        pool = ManaPool()
        pool.add(ManaType.RED, 1)
        # Cost like {X}{R} — X is 0, only need 1 red
        cost = ManaCost(generic=0, pips={ManaType.RED: 1}, x_count=1)
        assert pool.can_pay(cost) is True

    def test_can_pay_x_with_no_extra_mana(self) -> None:
        """X as 0 means even an empty pool can pay a pure-X cost."""
        pool = ManaPool()
        cost = ManaCost(generic=0, pips={}, x_count=2)
        assert pool.can_pay(cost) is True

    def test_can_pay_zero_cost(self) -> None:
        """A zero cost should always be payable, even with an empty pool."""
        pool = ManaPool()
        cost = ManaCost(generic=0, pips={})
        assert pool.can_pay(cost) is True

    def test_can_pay_multi_colored_pips(self) -> None:
        """can_pay with multiple different colored pips."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        pool.add(ManaType.BLUE, 1)
        pool.add(ManaType.BLACK, 1)
        # Cost: {W}{U}{B}
        cost = ManaCost(generic=0, pips={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1})
        assert pool.can_pay(cost) is True

    def test_can_pay_missing_one_color(self) -> None:
        """can_pay should return False if any single colored pip is missing."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        pool.add(ManaType.BLUE, 1)
        # Cost: {W}{U}{B} but pool has no black
        cost = ManaCost(generic=0, pips={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1})
        assert pool.can_pay(cost) is False

    def test_can_pay_generic_plus_colored_just_enough(self) -> None:
        """can_pay with generic + colored where total exactly matches."""
        pool = ManaPool()
        pool.add(ManaType.RED, 2)
        pool.add(ManaType.GREEN, 1)
        # Cost: {1}{R}{R} — 1 generic + 2 red; green covers generic
        cost = ManaCost(generic=1, pips={ManaType.RED: 2})
        assert pool.can_pay(cost) is True


# ---------------------------------------------------------------------------
# ManaPool — pay
# ---------------------------------------------------------------------------
class TestManaPoolPay:
    """Tests for ManaPool.pay()."""

    def test_pay_exact_colored_cost(self) -> None:
        """pay should deduct exact colored mana and return True."""
        pool = ManaPool()
        pool.add(ManaType.RED, 2)
        cost = ManaCost(generic=0, pips={ManaType.RED: 2})
        result = pool.pay(cost)
        assert result is True
        assert pool.get(ManaType.RED) == 0
        assert pool.total() == 0

    def test_pay_insufficient_returns_false(self) -> None:
        """pay should return False when pool cannot cover the cost."""
        pool = ManaPool()
        pool.add(ManaType.RED, 1)
        cost = ManaCost(generic=0, pips={ManaType.RED: 2})
        result = pool.pay(cost)
        assert result is False

    def test_pay_insufficient_does_not_change_pool(self) -> None:
        """pay returning False should leave pool unchanged."""
        pool = ManaPool()
        pool.add(ManaType.RED, 1)
        cost = ManaCost(generic=0, pips={ManaType.RED: 2})
        pool.pay(cost)
        assert pool.get(ManaType.RED) == 1
        assert pool.total() == 1

    def test_pay_generic_with_explicit_choices(self) -> None:
        """pay with choices dict should allocate generic cost as specified."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 2)
        pool.add(ManaType.GREEN, 3)
        # Cost: {2}{W} — 2 generic + 1 white pip
        cost = ManaCost(generic=2, pips={ManaType.WHITE: 1})
        choices = {ManaType.GREEN: 2}
        result = pool.pay(cost, choices=choices)
        assert result is True
        assert pool.get(ManaType.WHITE) == 1  # 2 - 1 pip
        assert pool.get(ManaType.GREEN) == 1  # 3 - 2 generic

    def test_pay_generic_auto_prefers_colorless(self) -> None:
        """Auto-pay (choices=None) should use colorless mana first for generic."""
        pool = ManaPool()
        pool.add(ManaType.COLORLESS, 3)
        pool.add(ManaType.RED, 2)
        # Cost: {2}{R} — 2 generic + 1 red pip
        cost = ManaCost(generic=2, pips={ManaType.RED: 1})
        result = pool.pay(cost)
        assert result is True
        # Auto-pay should use colorless for generic
        assert pool.get(ManaType.COLORLESS) == 1  # 3 - 2
        assert pool.get(ManaType.RED) == 1  # 2 - 1 pip

    def test_pay_generic_auto_falls_back_to_colored(self) -> None:
        """Auto-pay should use colored mana for generic when colorless is insufficient."""
        pool = ManaPool()
        pool.add(ManaType.COLORLESS, 1)
        pool.add(ManaType.BLUE, 3)
        # Cost: {3} — 3 generic
        cost = ManaCost(generic=3)
        result = pool.pay(cost)
        assert result is True
        assert pool.get(ManaType.COLORLESS) == 0  # used 1 for generic
        assert pool.get(ManaType.BLUE) == 1  # used 2 for generic

    def test_pay_colored_pips_first_then_generic(self) -> None:
        """Colored pips should be deducted before generic portion."""
        pool = ManaPool()
        pool.add(ManaType.RED, 3)
        # Cost: {1}{R}{R} — 1 generic + 2 red pips
        cost = ManaCost(generic=1, pips={ManaType.RED: 2})
        result = pool.pay(cost)
        assert result is True
        # 2 red used for pips, 1 red used for generic
        assert pool.get(ManaType.RED) == 0
        assert pool.total() == 0

    def test_pay_zero_cost_succeeds(self) -> None:
        """Paying a zero cost should always return True (even empty pool)."""
        pool = ManaPool()
        cost = ManaCost(generic=0, pips={})
        result = pool.pay(cost)
        assert result is True
        assert pool.total() == 0

    def test_pay_zero_cost_with_mana_in_pool(self) -> None:
        """Paying zero cost should not consume any mana."""
        pool = ManaPool()
        pool.add(ManaType.RED, 5)
        cost = ManaCost(generic=0, pips={})
        result = pool.pay(cost)
        assert result is True
        assert pool.get(ManaType.RED) == 5

    def test_pay_leaves_excess_mana(self) -> None:
        """pay should only deduct what's needed, leaving excess mana."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 5)
        cost = ManaCost(generic=0, pips={ManaType.WHITE: 2})
        result = pool.pay(cost)
        assert result is True
        assert pool.get(ManaType.WHITE) == 3

    def test_multiple_sequential_pays(self) -> None:
        """Multiple sequential pay calls should drain pool incrementally."""
        pool = ManaPool()
        pool.add(ManaType.RED, 3)
        pool.add(ManaType.GREEN, 2)

        cost1 = ManaCost(generic=0, pips={ManaType.RED: 1})
        assert pool.pay(cost1) is True
        assert pool.get(ManaType.RED) == 2

        cost2 = ManaCost(generic=0, pips={ManaType.RED: 1, ManaType.GREEN: 1})
        assert pool.pay(cost2) is True
        assert pool.get(ManaType.RED) == 1
        assert pool.get(ManaType.GREEN) == 1

        # Third pay should drain remaining
        cost3 = ManaCost(generic=1, pips={ManaType.RED: 1})
        assert pool.pay(cost3) is True
        assert pool.total() == 0

    def test_multiple_pays_eventually_fail(self) -> None:
        """Repeated pays should eventually fail when pool runs out."""
        pool = ManaPool()
        pool.add(ManaType.BLUE, 2)
        cost = ManaCost(generic=0, pips={ManaType.BLUE: 1})
        assert pool.pay(cost) is True
        assert pool.pay(cost) is True
        assert pool.pay(cost) is False
        # Pool should still have 0 blue (not negative)
        assert pool.get(ManaType.BLUE) == 0

    def test_pay_generic_choices_wrong_sum_returns_false(self) -> None:
        """pay with choices that don't sum to generic cost should return False."""
        pool = ManaPool()
        pool.add(ManaType.RED, 5)
        cost = ManaCost(generic=3, pips={})
        # Choices sum to 2, but generic is 3
        choices = {ManaType.RED: 2}
        result = pool.pay(cost, choices=choices)
        assert result is False

    def test_pay_generic_choices_exceed_available_returns_false(self) -> None:
        """pay with choices requesting more of a type than available should fail."""
        pool = ManaPool()
        pool.add(ManaType.RED, 1)
        pool.add(ManaType.GREEN, 1)
        cost = ManaCost(generic=2, pips={})
        # Choices ask for 2 red but only 1 available
        choices = {ManaType.RED: 2}
        result = pool.pay(cost, choices=choices)
        assert result is False

    def test_pay_negative_choice_rejected(self) -> None:
        """pay with a negative choice value should be rejected (returns False).

        A negative choice would subtract a negative from the working pool,
        effectively creating mana instead of spending it.
        """
        pool = ManaPool()
        pool.add(ManaType.RED, 5)
        cost = ManaCost(generic=2, pips={})
        # Negative choice: would create mana if not validated
        choices = {ManaType.RED: 4, ManaType.GREEN: -2}
        result = pool.pay(cost, choices=choices)
        assert result is False

    def test_pay_negative_choice_leaves_pool_unchanged(self) -> None:
        """pay rejecting a negative choice must not alter the pool."""
        pool = ManaPool()
        pool.add(ManaType.RED, 5)
        pool.add(ManaType.GREEN, 0)
        cost = ManaCost(generic=2, pips={})
        choices = {ManaType.RED: 4, ManaType.GREEN: -2}
        pool.pay(cost, choices=choices)
        assert pool.get(ManaType.RED) == 5
        assert pool.get(ManaType.GREEN) == 0
        assert pool.total() == 5

    def test_pay_single_negative_choice_rejected(self) -> None:
        """Even a single negative choice value should cause rejection."""
        pool = ManaPool()
        pool.add(ManaType.BLUE, 3)
        cost = ManaCost(generic=1, pips={})
        choices = {ManaType.BLUE: -1}
        result = pool.pay(cost, choices=choices)
        assert result is False
        assert pool.get(ManaType.BLUE) == 3


# ---------------------------------------------------------------------------
# ManaPool — repr
# ---------------------------------------------------------------------------
class TestManaPoolRepr:
    """Tests for ManaPool.__repr__()."""

    def test_empty_pool_repr(self) -> None:
        """Empty pool repr should show empty dict."""
        pool = ManaPool()
        r = repr(pool)
        assert "ManaPool" in r

    def test_non_empty_pool_repr(self) -> None:
        """Non-empty pool repr should mention the non-zero mana types."""
        pool = ManaPool()
        pool.add(ManaType.RED, 3)
        r = repr(pool)
        assert "RED" in r


# ---------------------------------------------------------------------------
# Player.mana_pool integration
# ---------------------------------------------------------------------------
class TestPlayerManaPoolIntegration:
    """Verify Player.mana_pool is now a ManaPool instance."""

    def test_player_mana_pool_is_mana_pool_instance(self) -> None:
        """Player.mana_pool should be a ManaPool (not None)."""
        from benchmarks.sos.workspace.engine.player import DeterministicPlayer

        p = DeterministicPlayer("Alice", [])
        assert isinstance(p.mana_pool, ManaPool)

    def test_player_mana_pool_starts_empty(self) -> None:
        """Player's mana pool should start with 0 total mana."""
        from benchmarks.sos.workspace.engine.player import DeterministicPlayer

        p = DeterministicPlayer("Alice", [])
        assert p.mana_pool.total() == 0

    def test_each_player_gets_distinct_mana_pool(self) -> None:
        """Two players should not share the same ManaPool instance."""
        from benchmarks.sos.workspace.engine.player import DeterministicPlayer

        p1 = DeterministicPlayer("P1", [])
        p2 = DeterministicPlayer("P2", [])
        assert p1.mana_pool is not p2.mana_pool

    def test_player_mana_pool_is_functional(self) -> None:
        """Player's mana pool should support add/pay operations."""
        from benchmarks.sos.workspace.engine.player import DeterministicPlayer

        p = DeterministicPlayer("Alice", [])
        p.mana_pool.add(ManaType.RED, 2)
        cost = ManaCost(generic=0, pips={ManaType.RED: 1})
        assert p.mana_pool.pay(cost) is True
        assert p.mana_pool.get(ManaType.RED) == 1
