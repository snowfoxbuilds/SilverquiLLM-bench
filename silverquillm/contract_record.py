"""Write a Contract Run's :class:`RunRecord` into the results repo.

Kept out of :mod:`silverquillm.contract` so the driver has no hard dependency
on the results-repo schema — the record is written only when a repo is
configured.  The interim plain-image candidate carries a legacy identity;
verified Candidate-Bundle identity (and genuine harness-as-PID-1 runs) land with
#65.  The record captures the execution outcome (agent outcome, gate result,
contract schema version, product/adapter versions, run date) so a run can be
diagnosed, plus an artifact pointer locating its on-disk workspace/job/logs.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from theozolith_worker import api

from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import BenchmarkRef
from silverquillm.modes import BenchmarkMode
from silverquillm.results_repo import (
    CandidateIdentity,
    RunRecord,
    write_run_record,
)

__all__ = ["image_candidate_segment", "write_contract_run_record"]

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")

#: Non-legacy artifact-pointer kind naming the on-disk run directory (holding
#: ``workspace_final/``, ``job/`` output, transcript, and container logs).
RUN_ARTIFACTS_KIND = "run-artifacts"


def image_candidate_segment(image: str | None) -> str:
    """A safe results-repo candidate segment derived from a plain image name.

    Mirrors the CLI's ``_image_dir`` shortening, then sanitizes to the one
    safe path segment :meth:`CandidateIdentity.legacy` requires.
    """
    short = (image or "unknown-image").rsplit("/", 1)[-1].split(":")[0]
    short = short.removeprefix("silverquillm-")
    safe = _UNSAFE.sub("-", short).lstrip(".")
    return safe or "unknown-image"


def _worker_version() -> str:
    try:
        return metadata.version("theozolith-worker")
    except metadata.PackageNotFoundError:  # pragma: no cover - always installed
        return "unknown"


def _dimension_score(results: dict[str, Any], pass_rate: float) -> dict[str, Any]:
    passed = sum(r.tests_passed for r in results.values())
    total = sum(r.tests_total for r in results.values())
    return {
        "pass_rate": pass_rate,
        "tests_passed": passed,
        "tests_total": total,
        "cards": len(results),
    }


def _contract_scores(eval_result: FullEvalResult) -> dict[str, dict[str, Any]]:
    """The neutral three-dimension scores block for a Contract Run."""
    return {
        "card_correctness": _dimension_score(
            eval_result.sos_results, eval_result.sos_pass_rate
        ),
        "fdn_regression": _dimension_score(
            eval_result.fdn_results, eval_result.fdn_pass_rate
        ),
        "engine_regression": {
            "pass_rate": eval_result.engine_pass_rate,
            "tests_passed": eval_result.engine_result.tests_passed,
            "tests_total": eval_result.engine_result.tests_total,
            "cards": 0,
        },
    }


def _outcome_metadata(outcome: api.AgentOutcome) -> dict[str, Any]:
    return {
        "state": outcome.describe(),
        "completed": outcome.completed,
        "timed_out": outcome.timed_out,
        "session_died": outcome.session_died,
        "exit_code": outcome.exit_code,
    }


def _gate_metadata(gate: api.GateResult) -> dict[str, Any]:
    return {
        "steps_run": list(gate.steps_run),
        "clean": gate.clean,
        "findings": [
            {
                "step": f.step,
                "severity": f.severity,
                "summary": f.summary,
                "fixed": f.fixed,
            }
            for f in gate.findings
        ],
    }


def write_contract_run_record(
    *,
    results_repo: Path,
    run_id: str,
    image: str | None,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    budget_seconds: int,
    proposal_status: str,
    eval_result: FullEvalResult,
    agent_outcome: api.AgentOutcome,
    gate: api.GateResult,
    run_dir: Path,
) -> Path:
    """Build and persist the RunRecord for a Contract Run; return its directory.

    Interim plain-image runs are never leaderboard-valid — the candidate
    identity is unverified until #65 recomputes it from a Candidate Bundle.
    """
    candidate = CandidateIdentity.legacy(image_candidate_segment(image))
    record = RunRecord(
        run_id=run_id,
        candidate=candidate,
        mode=mode.name,
        benchmark=benchmark.id,
        budget_seconds=budget_seconds,
        leaderboard_valid=False,
        resumed_from=None,
        run_metadata={
            "driver_ref": mode.driver_ref,
            "evaluation_method": mode.evaluation_method,
            "contract_schema_version": api.SCHEMA_VERSION,
            "adapter": "claude",
            "product_version": _worker_version(),
            "run_date": datetime.now(UTC).isoformat(),
            "agent_outcome": _outcome_metadata(agent_outcome),
            "gate": _gate_metadata(gate),
        },
        proposal_status=proposal_status,
        scores=_contract_scores(eval_result),
        artifact_pointers=[{"kind": RUN_ARTIFACTS_KIND, "location": str(run_dir)}],
    )
    return write_run_record(Path(results_repo), record)
