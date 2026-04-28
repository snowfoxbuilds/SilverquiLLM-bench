"""Mana pool and cost payment logic."""

from __future__ import annotations

from engine.types import Color, ManaCost, ManaType

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

    def empty(self) -> None:
        """Clear the pool — happens at phase/step transitions."""
        for mt in self._pool:
            self._pool[mt] = 0

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

        Returns:
            True if the pool has enough mana to pay the cost.
        """
        # TODO: hybrid/Phyrexian
        # First check that every colored/colorless pip requirement is met.
        remaining: dict[ManaType, int] = dict(self._pool)
        for mana_type, count in cost.pips.items():
            if remaining.get(mana_type, 0) < count:
                return False
            remaining[mana_type] = remaining.get(mana_type, 0) - count

        # Then check generic — sum of all remaining mana must cover it.
        return sum(remaining.values()) >= cost.generic

    def pay(self, cost: ManaCost, choices: dict[ManaType, int] | None = None) -> bool:
        """Deduct mana from the pool to pay *cost*.

        Parameters:
            cost: The mana cost to pay.
            choices: How to split the generic portion across mana types.
                If ``None``, auto-pay greedily: pay colored pips first,
                then generic using colorless first, then excess colored.

        Returns:
            True if payment succeeded, False if the pool has insufficient mana.
        """
        # TODO: hybrid/Phyrexian
        if not self.can_pay(cost):
            return False

        # Work on a copy so we can roll back on failure.
        working: dict[ManaType, int] = dict(self._pool)

        # 1. Pay colored/colorless pips.
        for mana_type, count in cost.pips.items():
            working[mana_type] -= count

        # 2. Pay generic cost.
        generic_remaining = cost.generic
        if generic_remaining > 0:
            if choices is not None:
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
            else:
                # Auto-pay: colorless first, then colored in enum order.
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
