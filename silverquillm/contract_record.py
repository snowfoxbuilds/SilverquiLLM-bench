"""Write a Contract Run's :class:`RunRecord` into the results repo.

Kept out of :mod:`silverquillm.contract` so the driver has no hard dependency
on the results-repo schema — the record is written only when a repo is
configured.  The candidate identity is the ``ozolith-v1`` triple
:mod:`silverquillm.candidate` recomputed from the Candidate Bundle through
TheOzolith's verifier (``verified: true`` — the only way such an identity
exists); adapter and product versions, the export timestamp, the built image
and the run date are recorded as run metadata only, never identity-bearing.

The record is *attempted for every run that reached a verified identity*,
however it ended: ``run_metadata`` carries the whole ``contract_run.json``
evidence — phase reached, classified failures, the harness-authored status,
the agent outcome, the gate result, the pinned packages — and an unevaluated
run records zeroed scores marked ``evaluated: false`` so it can never be
mistaken for a legitimate zero.  ``leaderboard_valid`` comes from its one
owner, :func:`silverquillm.results_repo.derive_leaderboard_valid`, over the
scored card set (an unevaluated run is never valid).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import BenchmarkRef
from silverquillm.modes import BenchmarkMode
from silverquillm.results_repo import (
    CANDIDATE_DIRNAME,
    RESULTS_DIRNAME,
    CandidateIdentity,
    RunRecord,
    candidate_hash,
    derive_leaderboard_valid,
    write_run_record,
)

__all__ = [
    "CANDIDATE_BUNDLE_KIND",
    "EVIDENCE_KIND",
    "RUN_ARTIFACTS_KIND",
    "write_contract_run_record",
]

#: Artifact-pointer kind naming the on-disk run directory (holding the job dir
#: — status, transcript, proposal, jobs channel, checkout — the driver
#: repository, ``workspace_final/``, and the trusted input snapshot).
RUN_ARTIFACTS_KIND = "run-artifacts"
#: Artifact-pointer kind naming the run's ``contract_run.json`` evidence file.
EVIDENCE_KIND = "contract-run-evidence"
#: Artifact-pointer kind naming the vendored Candidate Bundle inside the
#: results repo itself (``results/<candidate-hash>/candidate/``, relative to
#: the repo root) — present when the run vendored or re-verified it.
CANDIDATE_BUNDLE_KIND = "candidate-bundle"

#: ``run_metadata`` keys copied verbatim from the ``contract_run.json`` evidence.
_EVIDENCE_KEYS = (
    "contract_schema_version",
    "contract_bundle_format_version",
    "contract_identity_spec_version",
    "worker",
    "contract_packages",
    "phase",
    "phases_run",
    "failure",
    "failures",
    "warnings",
    "container",
    "image",
    "secret_slots",
    "agent_outcome",
    "harness_status",
    "transcript",
    "gate",
    "proposal_errors",
    "commit_sha",
    "timing",
)

#: ``candidate`` evidence keys recorded as run metadata (never identity).
_CANDIDATE_METADATA_KEYS = (
    "path",
    "worker_type",
    "adapter",
    "model",
    "effort",
    "product_version",
    "exported_at",
    "bundle_format_version",
    "identity_spec_version",
    "tag",
)


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
    candidate: CandidateIdentity,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    budget_seconds: int,
    proposal_status: str | None,
    eval_result: FullEvalResult | None,
    evidence: Mapping[str, Any],
) -> Path:
    """Build and persist the RunRecord for a Contract Run; return its directory.

    *candidate* is the identity :mod:`silverquillm.candidate` recomputed from
    the bundle (``ozolith-v1``, verified); *evidence* is the run's
    ``contract_run.json`` payload
    (:meth:`silverquillm.contract.ContractRunResult.evidence`).
    """
    candidate.validate()
    run_dir = Path(evidence["run_dir"]) if evidence.get("run_dir") else None
    candidate_evidence = evidence.get("candidate") or {}
    run_metadata: dict[str, Any] = {
        "driver_ref": mode.driver_ref,
        "evaluation_method": mode.evaluation_method,
        "run_date": (evidence.get("timing") or {}).get("started_at"),
        "evaluated": eval_result is not None,
    }
    for key in _CANDIDATE_METADATA_KEYS:
        run_metadata[key] = candidate_evidence.get(key)
    for key in _EVIDENCE_KEYS:
        run_metadata[key] = evidence.get(key)
    pointers = []
    if run_dir is not None:
        pointers.append({"kind": RUN_ARTIFACTS_KIND, "location": str(run_dir)})
        pointers.append({"kind": EVIDENCE_KIND, "location": str(run_dir / "contract_run.json")})
    if evidence.get("vendored_candidate"):
        pointers.append(
            {
                "kind": CANDIDATE_BUNDLE_KIND,
                "location": f"{RESULTS_DIRNAME}/{candidate_hash(candidate)}/{CANDIDATE_DIRNAME}/",
            }
        )
    scored = list(eval_result.sos_results) if eval_result is not None else []
    leaderboard_valid = (
        derive_leaderboard_valid(benchmark.config, None, None, scored)
        if eval_result is not None
        else False
    )
    record = RunRecord(
        run_id=run_id,
        candidate=candidate,
        mode=mode.name,
        benchmark=benchmark.id,
        budget_seconds=budget_seconds,
        leaderboard_valid=leaderboard_valid,
        resumed_from=None,
        run_metadata=run_metadata,
        proposal_status=proposal_status,
        scores=_contract_scores(eval_result),
        artifact_pointers=pointers,
    )
    return write_run_record(Path(results_repo), record)
