"""Write a Contract Run's :class:`RunRecord` into the results repo.

Kept out of :mod:`silverquillm.contract` so the driver has no hard dependency
on the results-repo schema — the record is written only when a repo is
configured. The interim plain-image candidate carries a legacy identity;
verified Candidate-Bundle identity lands with #65.
"""

from __future__ import annotations

import re
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

__all__ = ["image_candidate_segment", "write_contract_run_record"]

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


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
        },
        proposal_status=proposal_status,
        scores=_contract_scores(eval_result),
    )
    return write_run_record(Path(results_repo), record)
