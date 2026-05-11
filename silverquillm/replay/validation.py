"""Divergence detection and reporting for replay validation.

Records structured divergences when the engine can't execute a replay action
or produces different state, and produces a ValidationReport summarizing
all divergences after execution.
"""

from __future__ import annotations

import enum
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from silverquillm.replay.executor import ReplayExecutor, StateMismatch, StepResult
from silverquillm.replay.types import GameSnapshot, ReplayAction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Divergence types
# ---------------------------------------------------------------------------


class DivergenceType(enum.Enum):
    """Classification of divergences between engine and GRE replay."""

    MISSING_CARD = "MISSING_CARD"
    ILLEGAL_ACTION = "ILLEGAL_ACTION"
    STATE_MISMATCH = "STATE_MISMATCH"
    ENGINE_ERROR = "ENGINE_ERROR"


# ---------------------------------------------------------------------------
# Divergence record
# ---------------------------------------------------------------------------


@dataclass
class Divergence:
    """A single divergence between engine state and GRE replay."""

    game_state_id: int
    divergence_type: DivergenceType
    description: str
    expected_state: Any = None
    actual_state: Any = None
    action: ReplayAction | None = None
    severity: DivergenceType | None = None  # alias for divergence_type
    involved_grp_ids: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        # severity mirrors divergence_type for backward compat
        if self.severity is None:
            self.severity = self.divergence_type

    def __str__(self) -> str:
        grp_str = f" grpIds={self.involved_grp_ids}" if self.involved_grp_ids else ""
        return (
            f"[{self.divergence_type.value}] gsId={self.game_state_id}: "
            f"{self.description}{grp_str}"
        )


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------


@dataclass
class ValidationReport:
    """Summary report of a replay validation run."""

    total_snapshots: int = 0
    successful_comparisons: int = 0
    divergences: list[Divergence] = field(default_factory=list)
    card_appearances: dict[int, int] = field(default_factory=dict)

    @property
    def divergence_count(self) -> int:
        """Total number of divergences."""
        return len(self.divergences)

    @property
    def divergences_by_type(self) -> dict[DivergenceType, int]:
        """Count of divergences grouped by type."""
        counts: dict[DivergenceType, int] = {}
        for d in self.divergences:
            counts[d.divergence_type] = counts.get(d.divergence_type, 0) + 1
        return counts

    @property
    def per_card_divergence_rates(self) -> dict[int, float]:
        """Divergence rate per grpId (divergences / appearances)."""
        counts: dict[int, int] = Counter()
        for d in self.divergences:
            for grp_id in d.involved_grp_ids:
                counts[grp_id] += 1
        rates: dict[int, float] = {}
        for grp_id, count in counts.items():
            appearances = self.card_appearances.get(grp_id, count)
            rates[grp_id] = count / appearances if appearances else 0.0
        return rates

    @property
    def first_divergence_point(self) -> Divergence | None:
        """The first divergence encountered, for debugging."""
        return self.divergences[0] if self.divergences else None

    def summary(self) -> str:
        """Human-readable summary string."""
        lines = [
            f"Validation Report: {self.total_snapshots} snapshots processed",
            f"  Successful: {self.successful_comparisons}",
            f"  Divergences: {self.divergence_count}",
        ]
        for dtype, count in self.divergences_by_type.items():
            lines.append(f"    {dtype.value}: {count}")
        if self.first_divergence_point:
            lines.append(f"  First divergence: {self.first_divergence_point}")
        top_cards = sorted(
            self.per_card_divergence_rates.items(), key=lambda x: x[1], reverse=True
        )[:5]
        if top_cards:
            lines.append("  Top divergent cards:")
            for grp_id, rate in top_cards:
                lines.append(f"    grpId {grp_id}: {rate:.2f} divergence rate")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validating executor (wraps ReplayExecutor)
# ---------------------------------------------------------------------------


class ValidatingExecutor:
    """Wraps a ReplayExecutor and records structured Divergences.

    Extends the executor's step execution with divergence classification
    and produces a ValidationReport after execution.
    """

    def __init__(
        self,
        executor: ReplayExecutor,
        card_id_map: dict[int, str] | None = None,
    ) -> None:
        self.executor = executor
        self.card_id_map = card_id_map or executor.card_id_map
        self.divergences: list[Divergence] = []
        self._snapshots_processed: int = 0
        self._successful: int = 0
        self._card_appearances: dict[int, int] = Counter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_step(
        self,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
    ) -> StepResult:
        """Execute a single step and classify any divergences."""
        self._snapshots_processed += 1

        # Track card appearances for this snapshot comparison
        for action in curr_snapshot.actions:
            if action.grp_id and action.grp_id != 0:
                self._card_appearances[action.grp_id] += 1

        # Check for missing cards before executing
        missing = self._check_missing_cards(curr_snapshot)
        has_missing = len(missing) > 0
        for div in missing:
            self.divergences.append(div)

        # Try executing through the engine
        try:
            result = self.executor.execute_step(prev_snapshot, curr_snapshot)
        except Exception as exc:
            # ENGINE_ERROR: unhandled exception
            action = (
                curr_snapshot.actions[0] if curr_snapshot.actions else None
            )
            grp_ids = [action.grp_id] if action and action.grp_id else []
            div = Divergence(
                game_state_id=curr_snapshot.game_state_id,
                divergence_type=DivergenceType.ENGINE_ERROR,
                description=f"Engine raised {type(exc).__name__}: {exc}",
                expected_state=self._snapshot_state_summary(curr_snapshot),
                actual_state=None,
                action=action,
                involved_grp_ids=grp_ids,
            )
            self.divergences.append(div)
            return StepResult(
                snapshot_id=curr_snapshot.game_state_id,
                success=False,
            )

        # Classify mismatches from the result
        if result.mismatches:
            self._classify_mismatches(result, curr_snapshot)
        elif not has_missing:
            # Only count as successful if no mismatches AND no missing cards
            self._successful += 1

        return result

    def execute_all(
        self,
        stop_on_first: bool = False,
        step_callback: Any = None,
    ) -> list[StepResult]:
        """Execute all snapshot transitions and collect divergences.

        Args:
            stop_on_first: If True, stop after the first divergence is recorded.
            step_callback: Optional callback(step_index, snapshot_id, action_desc, result_desc)
                called after each step for verbose output.
        """
        if not self.executor._initialized:
            if self.executor.replay.snapshots:
                self.executor.initialize(self.executor.replay.snapshots[0])
            else:
                return []

        results = []
        snapshots = self.executor.replay.snapshots
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            result = self.execute_step(prev, curr)
            results.append(result)

            # Verbose callback
            if step_callback is not None:
                actions = curr.actions
                action_desc = str(actions[0]) if actions else "no-action"
                if result.mismatches:
                    result_desc = f"DIVERGED ({len(result.mismatches)} mismatches)"
                elif result.success:
                    result_desc = "OK"
                else:
                    result_desc = "FAILED"
                step_callback(i, curr.game_state_id, action_desc, result_desc)

            # Stop on first divergence within this replay
            if stop_on_first and self.divergences:
                break

        return results

    def report(self) -> ValidationReport:
        """Produce a ValidationReport summarizing the execution."""
        return ValidationReport(
            total_snapshots=self._snapshots_processed,
            successful_comparisons=self._successful,
            divergences=list(self.divergences),
            card_appearances=dict(self._card_appearances),
        )

    def record_divergence(self, divergence: Divergence) -> None:
        """Manually record a divergence."""
        self.divergences.append(divergence)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_missing_cards(self, snapshot: GameSnapshot) -> list[Divergence]:
        """Check for cards in the snapshot that aren't implemented in the engine."""
        missing: list[Divergence] = []
        if self.executor.registry is None:
            return missing  # Can't check without a registry

        for action in snapshot.actions:
            if action.grp_id == 0:
                continue
            card_name = self.card_id_map.get(action.grp_id, "")
            if not card_name:
                continue
            # Check if card is in the registry
            if card_name not in self.executor.registry:
                missing.append(Divergence(
                    game_state_id=snapshot.game_state_id,
                    divergence_type=DivergenceType.MISSING_CARD,
                    description=f"Card '{card_name}' (grpId={action.grp_id}) not implemented in engine",
                    expected_state=self._snapshot_state_summary(snapshot),
                    actual_state=None,
                    action=action,
                    involved_grp_ids=[action.grp_id],
                ))
        return missing

    def _classify_mismatches(
        self,
        result: StepResult,
        snapshot: GameSnapshot,
    ) -> None:
        """Classify StateMismatch objects into Divergence records."""
        for mismatch in result.mismatches:
            # Determine involved grpIds
            grp_ids = self._extract_grp_ids(result, snapshot)

            # Check if this looks like an illegal action (engine rejected)
            if self._is_illegal_action(mismatch, result):
                div_type = DivergenceType.ILLEGAL_ACTION
            else:
                div_type = DivergenceType.STATE_MISMATCH

            div = Divergence(
                game_state_id=snapshot.game_state_id,
                divergence_type=div_type,
                description=str(mismatch),
                expected_state=mismatch.snapshot_value,
                actual_state=mismatch.engine_value,
                action=snapshot.actions[0] if snapshot.actions else None,
                involved_grp_ids=grp_ids,
            )
            self.divergences.append(div)

    def _is_illegal_action(self, mismatch: StateMismatch, result: StepResult) -> bool:
        """Check if this represents an illegal action (engine rejected)."""
        # Primary: use StepResult.skipped with skip_reason
        if result.skipped and result.skip_reason:
            return True
        # Fallback: keyword matching in mismatch description
        desc = mismatch.description.lower()
        return "rejected" in desc or "illegal" in desc or "cannot" in desc

    def _extract_grp_ids(
        self, result: StepResult, snapshot: GameSnapshot
    ) -> list[int]:
        """Extract involved grpIds from a step result and snapshot."""
        grp_ids: list[int] = []

        # From snapshot actions
        for action in snapshot.actions:
            if action.grp_id and action.grp_id not in grp_ids:
                grp_ids.append(action.grp_id)

        # From card name lookup
        if result.card_name and not grp_ids:
            for gid, name in self.card_id_map.items():
                if name == result.card_name:
                    grp_ids.append(gid)
                    break

        return grp_ids

    def _snapshot_state_summary(self, snapshot: GameSnapshot) -> dict[str, Any]:
        """Build a summary dict of the snapshot state for divergence records."""
        summary: dict[str, Any] = {"game_state_id": snapshot.game_state_id}
        if hasattr(snapshot, "players") and snapshot.players:
            summary["players"] = [
                {"seat_id": p.seat_id, "life": p.life_total}
                for p in snapshot.players.values()
            ]
        if hasattr(snapshot, "zones") and snapshot.zones:
            summary["zone_count"] = len(snapshot.zones)
        return summary


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def validate_replay(
    executor: ReplayExecutor,
    card_id_map: dict[int, str] | None = None,
    stop_on_first: bool = False,
    step_callback: Any = None,
) -> ValidationReport:
    """Run a full replay validation and return the report.

    Args:
        executor: An initialized (or initializable) ReplayExecutor.
        card_id_map: Optional grpId->name map (defaults to executor's map).
        stop_on_first: If True, halt execution at the first divergence.
        step_callback: Optional callback for per-step verbose output.

    Returns:
        A ValidationReport summarizing all divergences.
    """
    validator = ValidatingExecutor(executor, card_id_map)
    validator.execute_all(stop_on_first=stop_on_first, step_callback=step_callback)
    return validator.report()
