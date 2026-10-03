"""The baseline reference grade and the Combined Regression block reported against it.

The unmodified Workspace of a benchmark with a Known Defect manifest is graded through the
same grader as a run, at most once per cache key, and its per-test outcomes are kept in a
host-side store. Combined Regression pools the FDN and engine regression Audited Tests and
reports a run against that grade (``docs/specs/KNOWN-BEST-ENGINE.md``, ``SCORING.md``).

This module must not import ``execution`` or ``regrade``: both import it.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from silverquillm.known_defects import (
    REGRESSION_DIMENSIONS,
    has_known_defects_manifest,
    regression_outcomes,
)

from .definition import KarnError, canonical
from .grader import GraderError
from .grading_inputs import grading_inputs
from .snapshots import copy_workspace

PACKAGE = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
GRADE_KEYS = frozenset({"schema_version", "key", "graded_at", "dimensions"})
DIMENSION_KEYS = frozenset(
    {"complete", "tests_passed", "tests_total", "missing_reasons", "test_nodes"}
)
# Only about a third of the FDN cards have Audited Tests, so this reason describes the
# population a run and its baseline share, never a grading failure.
COVERAGE_REASON = "some_cards_have_no_executed_audited_tests"
INPUTS_CHANGED = "grading_inputs_changed_during_grading"
# A comparison that is unavailable only for this reason reflects the candidate's own
# grading, so a regrade may reuse it; every other unavailable comparison is retried.
STABLE_UNAVAILABLE = frozenset({"regression_not_evaluated"})
GRADE_LIMIT = 64 * 1024 * 1024


def grading_code_digest() -> str:
    """Fingerprint of the package that grades; the grading-inputs digest does not cover it."""
    hashed = hashlib.sha256()
    for path in sorted(PACKAGE.rglob("*.py")):
        hashed.update(str(path.relative_to(PACKAGE)).encode() + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + hashed.hexdigest()


@dataclass(frozen=True)
class StagedBaseline:
    path: Path
    digest: str


def stage_baseline(benchmark, scratch: Path) -> StagedBaseline:
    """Copy the unmodified Workspace exactly as ``stage_benchmark`` copies it for a run."""
    copied = copy_workspace(benchmark.root / "workspace", Path(scratch) / "workspace")
    if copied["errors"] or copied["omissions"]:
        raise KarnError("baseline_workspace_incomplete")
    return StagedBaseline(Path(scratch) / "workspace", copied["digest"])


def baseline_key(
    benchmark, *, grading_inputs_digest: str, workspace_digest: str, grader_image_id: str
) -> dict:
    return {
        "benchmark": benchmark.identity,
        "grading_inputs_digest": grading_inputs_digest,
        "grading_code_digest": grading_code_digest(),
        "workspace_digest": workspace_digest,
        "grader_image_id": grader_image_id,
    }


class BaselineStore:
    """Baseline reference grades under ``<state_root>/baseline-grades``, one file per key."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, key: dict) -> Path:
        name = hashlib.sha256(canonical(key)).hexdigest() + ".json"
        return self.root / key["benchmark"]["id"] / name

    def get_or_grade(self, key: dict, grade: Callable[[], dict]) -> dict:
        """The stored grade for ``key``, grading and storing it first on a miss.

        The lock serializes threads and processes alike, so concurrent runs and regrade
        workers grade one key once. A failed grade raises and stores nothing, and an
        incomplete one is returned for this attempt but never stored, so the next request
        grades again.
        """
        path = self.path(key)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        descriptor = os.open(path.parent / ".lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            stored = _read(path, key)
            if stored is not None:
                return stored
            graded = grade()
            if _reusable(graded):
                _write(path, graded)
            return graded
        finally:
            os.close(descriptor)


def _read(path: Path, key: dict) -> dict | None:
    """A stored grade that is fully valid for ``key``; anything else is a miss."""
    try:
        with open(path, "rb") as handle:
            value = json.loads(handle.read(GRADE_LIMIT + 1))
        return value if _valid_grade(value, key) else None
    except Exception:  # noqa: BLE001 -- an unreadable stored grade is graded again.
        return None


def _write(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".baseline-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def _count(value) -> bool:
    return type(value) is int and value >= 0


def _valid_grade(value, key: dict) -> bool:
    if (
        not isinstance(value, dict)
        or set(value) != GRADE_KEYS
        or type(value["schema_version"]) is not int
        or value["schema_version"] != SCHEMA_VERSION
        or value["key"] != key
        or not isinstance(value["graded_at"], str)
        or not isinstance(value["dimensions"], dict)
        or set(value["dimensions"]) != set(REGRESSION_DIMENSIONS)
    ):
        return False
    datetime.fromisoformat(value["graded_at"])
    for dimension in value["dimensions"].values():
        if not isinstance(dimension, dict) or set(dimension) != DIMENSION_KEYS:
            return False
        passed, total = dimension["tests_passed"], dimension["tests_total"]
        counts = (passed is None and total is None) or (
            _count(passed) and _count(total) and passed <= total
        )
        reasons, nodes = dimension["missing_reasons"], dimension["test_nodes"]
        if (
            type(dimension["complete"]) is not bool
            or not counts
            or not isinstance(reasons, list)
            or not all(isinstance(reason, str) for reason in reasons)
            or not isinstance(nodes, dict)
            or not all(outcome in ("pass", "fail") for outcome in nodes.values())
        ):
            return False
    return _reusable(value)


def _reusable(grade: dict) -> bool:
    """Only a grade complete but for the shared FDN coverage gap is reference data.

    Failing Audited Tests are what a baseline records; a timeout, collection error or
    unexecuted suite is a failed attempt and must not outlive it.
    """
    return all(_baseline_complete(dimension) for dimension in grade["dimensions"].values())


def _stored(key: dict, evaluated, scores: dict) -> dict:
    outcomes = regression_outcomes(evaluated)
    dimensions = {}
    for name in REGRESSION_DIMENSIONS:
        score = scores[name]
        dimensions[name] = {
            "complete": score["complete"],
            "tests_passed": score["tests_passed"],
            "tests_total": score["tests_total"],
            "missing_reasons": list(score["missing_reasons"]),
            "test_nodes": dict(outcomes[name].nodes) if score["evaluated"] else {},
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "key": key,
        "graded_at": datetime.now(UTC).isoformat(),
        "dimensions": dimensions,
    }


class GradingInputsChanged(KarnError):
    """The grading inputs differ from the digest the baseline was requested for."""


@dataclass(frozen=True)
class Baseline:
    grade: dict | None
    """The stored baseline reference grade."""
    unavailable: str | None
    """Why there is no grade, when ``grade`` is None."""


def baseline_reference_grade(
    benchmark,
    *,
    evaluate,
    score,
    grading_inputs_digest: str,
    grader_image_id: str,
    store: BaselineStore,
    staged: StagedBaseline | None = None,
) -> Baseline | None:
    """The benchmark's baseline reference grade, or None when it has no manifest.

    ``evaluate`` is the callable that grades the run, so the baseline goes through the
    identical grading path. Never raises ``Exception``: a failure is an unavailable baseline.
    """
    if not has_known_defects_manifest(benchmark.root):
        return None
    try:
        with contextlib.ExitStack() as cleanup:
            if staged is None:
                scratch = cleanup.enter_context(tempfile.TemporaryDirectory(prefix="sq-baseline-"))
                staged = stage_baseline(benchmark, Path(scratch))
            key = baseline_key(
                benchmark,
                grading_inputs_digest=grading_inputs_digest,
                workspace_digest=staged.digest,
                grader_image_id=grader_image_id,
            )

            def unchanged_inputs() -> None:
                if grading_inputs(benchmark)["digest"] != grading_inputs_digest:
                    raise GradingInputsChanged(INPUTS_CHANGED)

            def grade() -> dict:
                # A grade is stored under the requested digest, so it must be graded on it.
                unchanged_inputs()
                evaluated = evaluate(staged.path.parent, benchmark, workspace_source=staged.path)
                unchanged_inputs()
                return _stored(key, evaluated, score(evaluated, benchmark))

            return Baseline(store.get_or_grade(key, grade), None)
    except GraderError as error:
        return Baseline(None, "baseline_grading_failed:" + error.reason)
    except GradingInputsChanged:
        return Baseline(None, INPUTS_CHANGED)
    except KarnError as error:
        if str(error) == "baseline_workspace_incomplete":
            return Baseline(None, "baseline_workspace_incomplete")
        return Baseline(None, "baseline_grading_failed:" + type(error).__name__)
    except Exception as error:  # noqa: BLE001 -- a run is still recorded without its reference scores.
        return Baseline(None, "baseline_grading_failed:" + type(error).__name__)


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


def _baseline_complete(dimension: dict) -> bool:
    """Complete but for the FDN coverage gap the run shares."""
    return dimension["tests_total"] is not None and not (
        set(dimension["missing_reasons"]) - {COVERAGE_REASON}
    )


def combined_regression(
    scores: dict, evaluated, baseline: Baseline | None, *, inputs_changed: bool = False
) -> dict | None:
    """The Combined Regression block for a graded run, or None without a manifest.

    ``scores`` is never changed: ``fdn_regression`` and ``engine_regression`` keep their own
    raw pass/total for diagnosis.
    """
    if baseline is None:
        return None
    if inputs_changed:
        return _unavailable(INPUTS_CHANGED)
    if not all(scores[name]["evaluated"] for name in REGRESSION_DIMENSIONS):
        return _unavailable("regression_not_evaluated")
    if baseline.unavailable is not None:
        return _unavailable(baseline.unavailable)
    reference = baseline.grade["dimensions"]
    if not all(_baseline_complete(reference[name]) for name in REGRESSION_DIMENSIONS):
        return _unavailable("baseline_incomplete")
    outcomes = regression_outcomes(evaluated)
    fixed, regressed = {}, {}
    for name in REGRESSION_DIMENSIONS:
        before, after = reference[name]["test_nodes"], outcomes[name].nodes
        fixed[name] = sorted(
            node
            for node, outcome in before.items()
            if outcome == "fail" and after.get(node) == "pass"
        )
        regressed[name] = sorted(
            node
            for node, outcome in before.items()
            if outcome == "pass" and after.get(node) != "pass"
        )
    passed = sum(scores[name]["tests_passed"] for name in REGRESSION_DIMENSIONS)
    total = sum(scores[name]["tests_total"] for name in REGRESSION_DIMENSIONS)
    baseline_passed = sum(reference[name]["tests_passed"] for name in REGRESSION_DIMENSIONS)
    baseline_total = sum(reference[name]["tests_total"] for name in REGRESSION_DIMENSIONS)
    return {
        "available": True,
        "tests_passed": passed,
        "tests_total": total,
        "pass_rate": passed / total,
        "baseline_score": {"tests_passed": baseline_passed, "tests_total": baseline_total},
        "known_best_score": {"tests_passed": baseline_total, "tests_total": baseline_total},
        "fixed": {"count": sum(map(len, fixed.values())), "test_nodes": fixed},
        "regressed": {"count": sum(map(len, regressed.values())), "test_nodes": regressed},
        "baseline": {
            name: value for name, value in baseline.grade["key"].items() if name != "benchmark"
        },
    }
