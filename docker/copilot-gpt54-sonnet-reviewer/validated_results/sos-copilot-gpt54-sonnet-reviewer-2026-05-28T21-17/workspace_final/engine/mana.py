"""Mana pool and cost payment logic."""

from __future__ import annotations

from engine.types import Color, HybridManaSymbol, ManaCost, ManaType

# Map colored ManaTypes to their corresponding Color enum values.
_MANA_TO_COLOR: dict[ManaType, Color] = {
    ManaType.WHITE: Color.WHITE,
    ManaType.BLUE: Color.BLUE,
    ManaType.BLACK: Color.BLACK,
    ManaType.RED: Color.RED,
    ManaType.GREEN: Color.GREEN,
}


class ManaPool:
    """Tracks available mana for a player.

    Internal storage uses a ``dict[ManaType, int]`` mapping each mana type
    to its current count.
    """

    def __init__(self) -> None:
        self._pool: dict[ManaType, int] = {mt: 0 for mt in ManaType}
        self._last_payment_colors: list[Color] = []
        self._restricted_mana: list[dict[str, object]] = []

    # ------------------------------------------------------------------
    # Basic operations
    # ------------------------------------------------------------------

    def add(self, mana_type: ManaType, amount: int = 1) -> None:
        """Add *amount* mana of the given type to the pool.

        Parameters:
            mana_type: The type of mana to add.
            amount: How many mana to add (must be non-negative).
        """
        if amount < 0:
            raise ValueError(f"Cannot add negative mana: {amount}")
        self._pool[mana_type] = self._pool.get(mana_type, 0) + amount

    def add_restricted(
        self,
        mana_type: ManaType,
        amount: int = 1,
        *,
        can_spend: object | None = None,
    ) -> None:
        """Add restricted mana tracked separately from unrestricted pool mana.

        The optional ``can_spend`` callable is consulted only when a caller
        passes ``spend_context=...`` to :meth:`can_pay` or :meth:`pay`.
        """
        if amount < 0:
            raise ValueError(f"Cannot add negative mana: {amount}")
        self.add(mana_type, amount)
        for _ in range(amount):
            self._restricted_mana.append({
                "mana_type": mana_type,
                "can_spend": can_spend,
            })

    def empty(self) -> None:
        """Clear the pool — happens at phase/step transitions."""
        for mt in self._pool:
            self._pool[mt] = 0
        self._restricted_mana.clear()
        self._last_payment_colors = []

    def total(self) -> int:
        """Return the total amount of mana in the pool across all types."""
        return sum(self._pool.values())

    def get(self, mana_type: ManaType) -> int:
        """Return the amount of a specific mana type in the pool."""
        return self._pool.get(mana_type, 0)

    @property
    def last_payment_colors(self) -> list[Color]:
        """Return the distinct colors of mana spent in the last :meth:`pay` call.

        Colorless mana is not a color and is excluded.  The list is sorted
        by Color enum order for determinism.  Empty if no payment has been
        made or if all mana spent was colorless.
        """
        return list(self._last_payment_colors)

    # ------------------------------------------------------------------
    # Cost payment
    # ------------------------------------------------------------------

    def can_pay(self, cost: ManaCost, *, spend_context: object | None = None) -> bool:
        """Check whether the pool can satisfy *cost*.

        Generic mana can be paid by any type.  X is treated as 0 for
        ``can_pay`` unless explicitly set in the cost's generic component.
        Hybrid symbols can be paid with either option; this method uses
        backtracking to find a valid assignment.

        Returns:
            True if the pool has enough mana to pay the cost.
        """
        remaining: dict[ManaType, int] = self._available_pool(spend_context)

        # Pay colored/colorless pips first.
        for mana_type, count in cost.pips.items():
            if remaining.get(mana_type, 0) < count:
                return False
            remaining[mana_type] = remaining.get(mana_type, 0) - count

        # Solve hybrid symbols with backtracking.
        if cost.hybrid:
            if not self._can_pay_hybrid(remaining, list(cost.hybrid), 0, cost.generic):
                return False
            return True

        # Then check generic — sum of all remaining mana must cover it.
        return sum(remaining.values()) >= cost.generic

    def pay(
        self,
        cost: ManaCost,
        choices: dict[ManaType, int] | None = None,
        *,
        spend_context: object | None = None,
    ) -> bool:
        """Deduct mana from the pool to pay *cost*.

        Parameters:
            cost: The mana cost to pay.
            choices: How to split the generic portion across mana types.
                If ``None``, auto-pay greedily: pay colored pips first,
                then hybrid symbols, then generic using colorless first,
                then excess colored.

        Returns:
            True if payment succeeded, False if the pool has insufficient mana.
        """
        if not self.can_pay(cost, spend_context=spend_context):
            return False

        # Work on a copy so we can roll back on failure.
        available_working: dict[ManaType, int] = self._available_pool(spend_context)

        # 1. Pay colored/colorless pips.
        for mana_type, count in cost.pips.items():
            available_working[mana_type] -= count

        # 2. When explicit generic choices are provided, reserve that mana
        #    *before* solving hybrids so the solver doesn't steal it.
        generic_remaining = cost.generic
        if generic_remaining > 0 and choices is not None:
            # Reject negative choice amounts — they would create mana.
            if any(v < 0 for v in choices.values()):
                return False
            # Validate choices sum to generic cost.
            if sum(choices.values()) != generic_remaining:
                return False
            for mana_type, amount in choices.items():
                if available_working.get(mana_type, 0) < amount:
                    return False
                available_working[mana_type] -= amount

        # 3. Pay hybrid symbols using backtracking to find a valid assignment.
        #    Generic choices (if any) have already been reserved above,
        #    so _solve_hybrid sees only the genuinely available mana.
        if cost.hybrid:
            generic_for_solver = generic_remaining if choices is None else 0
            hybrid_assignment = self._solve_hybrid(
                available_working, list(cost.hybrid), 0, generic_for_solver,
            )
            if hybrid_assignment is None:
                return False  # pragma: no cover – should not happen after can_pay
            for mt in hybrid_assignment:
                available_working[mt] = available_working.get(mt, 0) - 1

        # 4. Pay generic cost (auto-pay path — choices already deducted above).
        if generic_remaining > 0 and choices is None:
            generic_remaining = self._auto_pay_generic(available_working, generic_remaining)
            if generic_remaining > 0:
                return False  # pragma: no cover – should not happen after can_pay

        # Commit the payment.
        # Compute colors of mana spent by comparing old pool to new working pool.
        colors_spent: set[Color] = set()
        spent_by_type: dict[ManaType, int] = {}
        for mt, old_amount in self._available_pool(spend_context).items():
            new_amount = available_working.get(mt, 0)
            if new_amount < old_amount:
                spent_by_type[mt] = old_amount - new_amount
            if new_amount < old_amount and mt in _MANA_TO_COLOR:
                colors_spent.add(_MANA_TO_COLOR[mt])
        for mt, spent in spent_by_type.items():
            self._commit_spend(mt, spent, spend_context)
        self._last_payment_colors = sorted(colors_spent, key=lambda c: c.value)
        return True

    def _available_pool(self, spend_context: object | None) -> dict[ManaType, int]:
        """Return mana counts available for the given spending context."""
        remaining: dict[ManaType, int] = dict(self._pool)
        if spend_context is None:
            return remaining

        for entry in self._restricted_mana:
            mana_type = entry["mana_type"]
            can_spend = entry["can_spend"]
            if callable(can_spend) and not bool(can_spend(spend_context)):
                remaining[mana_type] = remaining.get(mana_type, 0) - 1
        return remaining

    def _commit_spend(self, mana_type: ManaType, amount: int, spend_context: object | None) -> None:
        """Deduct committed mana spend from total and restricted tracked mana."""
        if amount <= 0:
            return

        total_restricted = sum(
            1 for entry in self._restricted_mana if entry["mana_type"] is mana_type
        )
        unrestricted_available = self._pool.get(mana_type, 0) - total_restricted
        restricted_to_remove = max(0, amount - unrestricted_available)

        if restricted_to_remove > 0:
            updated_entries: list[dict[str, object]] = []
            for entry in self._restricted_mana:
                if (
                    restricted_to_remove > 0
                    and entry["mana_type"] is mana_type
                    and self._restricted_entry_is_spendable(entry, spend_context)
                ):
                    restricted_to_remove -= 1
                    continue
                updated_entries.append(entry)
            self._restricted_mana = updated_entries

        self._pool[mana_type] = self._pool.get(mana_type, 0) - amount

    @staticmethod
    def _restricted_entry_is_spendable(entry: dict[str, object], spend_context: object | None) -> bool:
        """Return whether the tracked restricted mana entry may be spent now."""
        if spend_context is None:
            return True
        can_spend = entry["can_spend"]
        if not callable(can_spend):
            return True
        return bool(can_spend(spend_context))

    @staticmethod
    def _can_pay_hybrid(
        remaining: dict[ManaType, int],
        hybrids: list[HybridManaSymbol],
        idx: int,
        generic: int,
    ) -> bool:
        """Recursively check if hybrid symbols + generic can be satisfied.

        Uses backtracking: for each hybrid symbol, try option_a then option_b.
        After all hybrids are assigned, check that remaining mana covers generic.
        """
        if idx >= len(hybrids):
            return sum(remaining.values()) >= generic

        sym = hybrids[idx]
        for option in (sym.option_a, sym.option_b):
            if remaining.get(option, 0) > 0:
                remaining[option] -= 1
                if ManaPool._can_pay_hybrid(remaining, hybrids, idx + 1, generic):
                    remaining[option] += 1
                    return True
                remaining[option] += 1
        return False

    @staticmethod
    def _solve_hybrid(
        remaining: dict[ManaType, int],
        hybrids: list[HybridManaSymbol],
        idx: int,
        generic: int,
    ) -> list[ManaType] | None:
        """Find a valid assignment for hybrid symbols.

        Returns a list of ManaType choices (one per hybrid symbol) or None
        if no valid assignment exists.
        """
        if idx >= len(hybrids):
            if sum(remaining.values()) >= generic:
                return []
            return None

        sym = hybrids[idx]
        for option in (sym.option_a, sym.option_b):
            if remaining.get(option, 0) > 0:
                remaining[option] -= 1
                result = ManaPool._solve_hybrid(remaining, hybrids, idx + 1, generic)
                if result is not None:
                    remaining[option] += 1
                    return [option] + result
                remaining[option] += 1
        return None

    @staticmethod
    def _auto_pay_generic(working: dict[ManaType, int], amount: int) -> int:
        """Deduct *amount* generic mana from *working*, preferring colorless.

        Returns the remaining unpaid generic amount (0 on success).
        """
        # Pay with colorless first.
        if working.get(ManaType.COLORLESS, 0) > 0:
            take = min(working[ManaType.COLORLESS], amount)
            working[ManaType.COLORLESS] -= take
            amount -= take

        # Then pay with each colored type in enum order.
        for mt in ManaType:
            if mt is ManaType.COLORLESS:
                continue
            if amount <= 0:
                break
            if working.get(mt, 0) > 0:
                take = min(working[mt], amount)
                working[mt] -= take
                amount -= take

        return amount

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        non_zero = {mt.name: v for mt, v in self._pool.items() if v > 0}
        return f"ManaPool({non_zero})"
