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

    Restricted mana is tracked separately via ``_restricted_mana``: a list of
    dicts with keys ``source``, ``restriction`` (str), and ``amount`` (int).
    The casting pipeline should consult these restrictions when paying costs.
    """

    def __init__(self) -> None:
        self._pool: dict[ManaType, int] = {mt: 0 for mt in ManaType}
        self._last_payment_colors: list[Color] = []
        self._restricted_mana: list[dict] = []

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
        restriction: str = "",
        source: object | None = None,
    ) -> None:
        """Add restricted mana to the pool.

        Restricted mana can only be spent on spells matching the restriction.
        The mana is added to the normal pool for total() accounting, and
        metadata is tracked in ``_restricted_mana``.

        Parameters:
            mana_type: The type of mana to add.
            amount: How many mana to add.
            restriction: A string describing the restriction (e.g.
                ``"instant_or_sorcery"``).
            source: The object that produced this mana.
        """
        if amount < 0:
            raise ValueError(f"Cannot add negative restricted mana: {amount}")
        self._pool[mana_type] = self._pool.get(mana_type, 0) + amount
        self._restricted_mana.append({
            "source": source,
            "restriction": restriction,
            "amount": amount,
        })

    @property
    def restricted_mana(self) -> list[dict]:
        """Return the list of restricted-mana entries (read-only view).

        Each entry is a dict with ``source``, ``restriction``, and ``amount``
        keys. Callers should treat the returned list as read-only — use
        :meth:`add_restricted` to add entries.
        """
        return list(self._restricted_mana)

    def empty(self) -> None:
        """Clear the pool — happens at phase/step transitions."""
        for mt in self._pool:
            self._pool[mt] = 0
        self._restricted_mana.clear()

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

    def can_pay(self, cost: ManaCost) -> bool:
        """Check whether the pool can satisfy *cost*.

        Generic mana can be paid by any type.  X is treated as 0 for
        ``can_pay`` unless explicitly set in the cost's generic component.
        Hybrid symbols can be paid with either option; this method uses
        backtracking to find a valid assignment.

        Returns:
            True if the pool has enough mana to pay the cost.
        """
        remaining: dict[ManaType, int] = dict(self._pool)

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

    def pay(self, cost: ManaCost, choices: dict[ManaType, int] | None = None) -> bool:
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
        if not self.can_pay(cost):
            return False

        # Work on a copy so we can roll back on failure.
        working: dict[ManaType, int] = dict(self._pool)

        # 1. Pay colored/colorless pips.
        for mana_type, count in cost.pips.items():
            working[mana_type] -= count

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
                if working.get(mana_type, 0) < amount:
                    return False
                working[mana_type] -= amount

        # 3. Pay hybrid symbols using backtracking to find a valid assignment.
        #    Generic choices (if any) have already been reserved above,
        #    so _solve_hybrid sees only the genuinely available mana.
        if cost.hybrid:
            generic_for_solver = generic_remaining if choices is None else 0
            hybrid_assignment = self._solve_hybrid(
                working, list(cost.hybrid), 0, generic_for_solver,
            )
            if hybrid_assignment is None:
                return False  # pragma: no cover – should not happen after can_pay
            for mt in hybrid_assignment:
                working[mt] = working.get(mt, 0) - 1

        # 4. Pay generic cost (auto-pay path — choices already deducted above).
        if generic_remaining > 0 and choices is None:
            generic_remaining = self._auto_pay_generic(working, generic_remaining)
            if generic_remaining > 0:
                return False  # pragma: no cover – should not happen after can_pay

        # Commit the payment.
        # Compute colors of mana spent by comparing old pool to new working pool.
        colors_spent: set[Color] = set()
        for mt, old_amount in self._pool.items():
            new_amount = working.get(mt, 0)
            if new_amount < old_amount and mt in _MANA_TO_COLOR:
                colors_spent.add(_MANA_TO_COLOR[mt])
        self._last_payment_colors = sorted(colors_spent, key=lambda c: c.value)
        self._pool = working
        return True

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
