"""Write a Contract Run's :class:`RunRecord` into the results repo.

Kept out of :mod:`silverquillm.contract` so the driver has no hard dependency
on the results-repo schema — the record is written only when a repo is
configured.  The interim plain-image candidate carries a legacy identity;
verified Candidate-Bundle identity lands with #65.

The record is *attempted for every run*, however it ended: ``run_metadata``
carries the whole ``contract_run.json`` evidence — phase reached, classified
failures, the harness-authored status, the agent outcome, the gate result, the
pinned worker — and an unevaluated run records zeroed scores marked
``evaluated: false`` so it can never be mistaken for a legitimate zero.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import BenchmarkRef
from silverquillm.modes import BenchmarkMode
from silverquillm.results_repo import (
    CandidateIdentity,
    RunRecord,
    write_run_record,
)

__all__ = [
    "EVIDENCE_KIND",
    "RUN_ARTIFACTS_KIND",
    "image_candidate_segment",
    "write_contract_run_record",
]

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")

#: Artifact-pointer kind naming the on-disk run directory (holding the job dir
#: — status, transcript, proposal, jobs channel, checkout — the driver
#: repository, ``workspace_final/``, and the trusted input snapshot).
RUN_ARTIFACTS_KIND = "run-artifacts"
#: Artifact-pointer kind naming the run's ``contract_run.json`` evidence file.
EVIDENCE_KIND = "contract-run-evidence"

#: ``run_metadata`` keys copied verbatim from the ``contract_run.json`` evidence.
_EVIDENCE_KEYS = (
    "contract_schema_version",
    "worker",
    "phase",
    "phases_run",
    "failure",
    "failures",
    "warnings",
    "container",
    "agent_outcome",
    "harness_status",
    "transcript",
    "gate",
    "proposal_errors",
    "commit_sha",
    "timing",
)


def image_candidate_segment(image: str | None) -> str:
    """A safe results-repo candidate segment derived from a plain image name.

    Mirrors the CLI's ``_image_dir`` shortening, then sanitizes to the one
    safe path segment :meth:`CandidateIdentity.legacy` requires.
    """
    short = (image or "unknown-image").rsplit("/", 1)[-1].split(":")[0]
    short = short.removeprefix("silverquillm-")
    safe = _UNSAFE.sub("-", short).lstrip(".")
    return safe or "unknown-image"


def _dimension_score(results: dict[str, Any], pass_rate: float) -> dict[str, Any]:
    passed = sum(r.tests_passed for r in results.values())
    total = sum(r.tests_total for r in results.values())
    return {
        "pass_rate": pass_rate,
        "tests_passed": passed,
        "tests_total": total,
        "cards": len(results),
        "evaluated": True,
    }


def _unevaluated() -> dict[str, Any]:
    return {"pass_rate": 0.0, "tests_passed": 0, "tests_total": 0, "cards": 0, "evaluated": False}


def _contract_scores(eval_result: FullEvalResult | None) -> dict[str, dict[str, Any]]:
    """The neutral three-dimension scores block for a Contract Run."""
    if eval_result is None:
        return {
            "card_correctness": _unevaluated(),
            "fdn_regression": _unevaluated(),
            "engine_regression": _unevaluated(),
        }
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
            "evaluated": True,
        },
    }


def write_contract_run_record(
    *,
    results_repo: Path,
    run_id: str,
    image: str | None,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    budget_seconds: int,
    proposal_status: str | None,
    eval_result: FullEvalResult | None,
    evidence: Mapping[str, Any],
) -> Path:
    """Build and persist the RunRecord for a Contract Run; return its directory.

    *evidence* is the run's ``contract_run.json`` payload
    (:meth:`silverquillm.contract.ContractRunResult.evidence`).  Interim
    plain-image runs are never leaderboard-valid — the candidate identity is
    unverified until #65 recomputes it from a Candidate Bundle.
    """
    candidate = CandidateIdentity.legacy(image_candidate_segment(image))
    run_dir = Path(evidence["run_dir"]) if evidence.get("run_dir") else None
    run_metadata: dict[str, Any] = {
        "driver_ref": mode.driver_ref,
        "evaluation_method": mode.evaluation_method,
        "adapter": "claude",
        "run_date": (evidence.get("timing") or {}).get("started_at"),
        "evaluated": eval_result is not None,
    }
    for key in _EVIDENCE_KEYS:
        run_metadata[key] = evidence.get(key)
    pointers = []
    if run_dir is not None:
        pointers.append({"kind": RUN_ARTIFACTS_KIND, "location": str(run_dir)})
        pointers.append({"kind": EVIDENCE_KIND, "location": str(run_dir / "contract_run.json")})
    record = RunRecord(
        run_id=run_id,
        candidate=candidate,
        mode=mode.name,
        benchmark=benchmark.id,
        budget_seconds=budget_seconds,
        leaderboard_valid=False,
        resumed_from=None,
        run_metadata=run_metadata,
        proposal_status=proposal_status,
        scores=_contract_scores(eval_result),
        artifact_pointers=pointers,
    )
    return write_run_record(Path(results_repo), record)
