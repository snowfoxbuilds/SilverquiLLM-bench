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
    # MSH Player Query protocol (intent-driven seat): a query that no
    # replay-derived intent could answer, and an engine-side boundary-validation
    # failure. Both are recorded divergences — never a crash of the run.
    QUERY_UNANSWERED = "QUERY_UNANSWERED"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    # Simulate mode: an executor-side impossibility (engine library empty on
    # a GRE-observed draw, step-event plumbing failure) — replay-harness
    # signal, kept separate from the engine/card-bug ENGINE_ERROR count.
    REPLAY_INFRA = "REPLAY_INFRA"


# Module-qualified names of the MSH protocol exceptions (engine/decisions.py).
# Qualified matching keeps this shared code import-free while ruling out a
# same-named third-party exception classifying as a protocol failure.
_PROTOCOL_ERROR_QUALNAME = ("engine.decisions", "ProtocolError")
_UNMATCHED_QUERY_QUALNAME = ("engine.decisions", "UnmatchedQueryError")


def classify_step_exception(exc: BaseException) -> "DivergenceType":
    """Classify an exception raised while executing a replay step.

    Engine-agnostic — matches on module-qualified class names in the MRO so
    this shared code need not import the MSH-only exception classes:
      - ``engine.decisions.ProtocolError`` (boundary-validation failure) -> PROTOCOL_ERROR
      - ``engine.decisions.UnmatchedQueryError`` (no intent matched) -> QUERY_UNANSWERED
      - anything else (including a same-named foreign class) -> ENGINE_ERROR
    An unanswerable query is thus a recorded divergence, never a crash.
    """
    mro_qualnames = {(cls.__module__, cls.__name__) for cls in type(exc).__mro__}
    if _PROTOCOL_ERROR_QUALNAME in mro_qualnames:
        return DivergenceType.PROTOCOL_ERROR
    if _UNMATCHED_QUERY_QUALNAME in mro_qualnames:
        return DivergenceType.QUERY_UNANSWERED
    return DivergenceType.ENGINE_ERROR


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
        # Simulate mode: missing-card identities already recorded — the
        # counting unit is one divergence per (game, identity), not per
        # action or snapshot.
        self._missing_identities: set[str] = set()

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

        # Check for missing cards before executing. Simulate mode counts the
        # full unimplemented surface (parser actions + battlefield arrivals
        # here, executor-synthesized actions after execution), deduplicated
        # per (game, identity); observer mode keeps the original
        # per-occurrence, mapped-actions-only behavior.
        simulate = getattr(self.executor, "simulate", False)
        if simulate:
            missing = self._check_missing_cards_simulate(
                prev_snapshot, curr_snapshot
            )
        else:
            missing = self._check_missing_cards(curr_snapshot)
        has_missing = len(missing) > 0
        for div in missing:
            self.divergences.append(div)

        # Try executing through the engine
        try:
            result = self.executor.execute_step(prev_snapshot, curr_snapshot)
        except Exception as exc:
            div_type = classify_step_exception(exc)
            action = (
                curr_snapshot.actions[0] if curr_snapshot.actions else None
            )
            grp_ids = [action.grp_id] if action and action.grp_id else []
            div = Divergence(
                game_state_id=curr_snapshot.game_state_id,
                divergence_type=div_type,
                description=f"Engine raised {type(exc).__name__}: {exc}",
                expected_state=self._snapshot_state_summary(curr_snapshot),
                actual_state=None,
                action=action,
                involved_grp_ids=grp_ids,
            )
            self.divergences.append(div)
            # Simulate mode: resync engine state to GRE truth so the failed
            # step doesn't cascade into every later comparison.
            if getattr(self.executor, "simulate", False):
                try:
                    self.executor._resync_to_snapshot(curr_snapshot)
                except Exception:
                    logger.exception("post-failure resync failed")
            return StepResult(
                snapshot_id=curr_snapshot.game_state_id,
                success=False,
            )

        # Simulate mode: engine API failures are recorded divergences,
        # never silent fallbacks. Executor-side impossibilities are
        # recorded under REPLAY_INFRA so the ENGINE_ERROR count stays a
        # clean engine/card-bug signal.
        engine_failures = getattr(result, "engine_failures", [])
        infra_failures = getattr(result, "infra_failures", [])
        for div_type, failures in (
            (DivergenceType.ENGINE_ERROR, engine_failures),
            (DivergenceType.REPLAY_INFRA, infra_failures),
        ):
            for failure in failures:
                self.divergences.append(Divergence(
                    game_state_id=curr_snapshot.game_state_id,
                    divergence_type=div_type,
                    description=failure,
                    action=curr_snapshot.actions[0] if curr_snapshot.actions else None,
                    involved_grp_ids=[
                        a.grp_id for a in curr_snapshot.actions if a.grp_id
                    ][:1],
                ))

        # Simulate mode: hidden-origin actions are synthesized inside the
        # executor, after the pre-execution check ran — count their missing
        # cards from the StepResult.
        if simulate:
            synth_missing = self._check_missing_synthesized(result, curr_snapshot)
            for div in synth_missing:
                self.divergences.append(div)
            has_missing = has_missing or bool(synth_missing)

        # Classify mismatches from the result
        if result.mismatches:
            self._classify_mismatches(result, curr_snapshot)
        elif not has_missing and not engine_failures and not infra_failures:
            # Only count as successful if no mismatches, missing cards,
            # or engine failures
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

    # Basic-land names the executor resolves from GRE subtypes for grpIds
    # outside the card map (arbitrary 17lands printings) — those become
    # real registered cards, not misses.
    _BASIC_LAND_NAMES = {"Plains", "Island", "Swamp", "Mountain", "Forest"}

    def _missing_card_identity(self, grp_id: int, obj: Any = None) -> str | None:
        """Resolve a grpId to its missing-card identity.

        The mapped card name when the grpId maps; else the executor's
        basic-land subtype resolution (mirroring ``_create_card_from_object``,
        so an alt-printing Forest is 'Forest', not an unknown); else
        ``grpId_<n>``. ``None`` for grp_id 0 (nothing to identify).
        """
        if not grp_id:
            return None
        name = self.card_id_map.get(grp_id, "")
        if (
            not name
            and obj is not None
            and "CardType_Land" in getattr(obj, "card_types", [])
        ):
            for subtype in getattr(obj, "subtypes", []):
                basic = subtype.removeprefix("SubType_")
                if basic in self._BASIC_LAND_NAMES:
                    name = basic
                    break
        return name or f"grpId_{grp_id}"

    def _identity_is_missing(self, identity: str) -> bool:
        """True if *identity* has no implementation in the engine registry."""
        if identity.startswith("grpId_"):
            return True  # unmapped grpId: nothing to look up in the registry
        return identity not in self.executor.registry

    def _record_missing(
        self,
        snapshot: GameSnapshot,
        grp_id: int,
        obj: Any = None,
        action: ReplayAction | None = None,
    ) -> Divergence | None:
        """Dedup-record one missing identity; None if known/implemented."""
        identity = self._missing_card_identity(grp_id, obj)
        if identity is None or identity in self._missing_identities:
            return None
        if not self._identity_is_missing(identity):
            return None
        self._missing_identities.add(identity)
        return Divergence(
            game_state_id=snapshot.game_state_id,
            divergence_type=DivergenceType.MISSING_CARD,
            description=(
                f"Card '{identity}' (grpId={grp_id}) not implemented in engine"
            ),
            expected_state=self._snapshot_state_summary(snapshot),
            actual_state=None,
            action=action,
            involved_grp_ids=[grp_id],
        )

    def _check_missing_cards_simulate(
        self,
        prev_snapshot: GameSnapshot,
        curr_snapshot: GameSnapshot,
    ) -> list[Divergence]:
        """Simulate-mode missing-card check: parser actions + battlefield
        arrivals, one divergence per (game, identity)."""
        missing: list[Divergence] = []
        if self.executor.registry is None:
            return missing  # Can't check without a registry

        # (a) parser-inferred actions.
        for action in curr_snapshot.actions:
            obj = curr_snapshot.game_objects.get(action.instance_id)
            div = self._record_missing(
                curr_snapshot, action.grp_id, obj=obj, action=action
            )
            if div is not None:
                missing.append(div)

        # (c) battlefield arrivals — makes cards the parser and the
        # hidden-origin synthesis never surface (tokens above all) visible.
        prev_bf = self._battlefield_instance_ids(prev_snapshot)
        for iid in self._battlefield_instance_ids(curr_snapshot) - prev_bf:
            obj = curr_snapshot.game_objects.get(iid)
            if obj is None:
                continue
            if obj.type not in ("GameObjectType_Card", "GameObjectType_Token"):
                continue
            div = self._record_missing(curr_snapshot, obj.grp_id, obj=obj)
            if div is not None:
                missing.append(div)

        return missing

    def _check_missing_synthesized(
        self,
        result: StepResult,
        curr_snapshot: GameSnapshot,
    ) -> list[Divergence]:
        """(b) executor-synthesized hidden-origin actions (opponent casts
        and land plays the parser can't see)."""
        missing: list[Divergence] = []
        if self.executor.registry is None:
            return missing
        for action in getattr(result, "synthesized_actions", []):
            obj = curr_snapshot.game_objects.get(action.instance_id)
            div = self._record_missing(
                curr_snapshot, action.grp_id, obj=obj, action=action
            )
            if div is not None:
                missing.append(div)
        return missing

    @staticmethod
    def _battlefield_instance_ids(snapshot: GameSnapshot) -> set[int]:
        ids: set[int] = set()
        for zone in snapshot.zones.values():
            if zone.type == "ZoneType_Battlefield":
                ids.update(zone.object_instance_ids)
        return ids

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
