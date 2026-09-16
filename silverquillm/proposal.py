"""Benchmark-owned Output Proposal schema validation and fallback provenance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from silverquillm import workflow as api

__all__ = [
    "PROPOSAL_APPLIED",
    "PROPOSAL_INVALID",
    "PROPOSAL_MISSING",
    "LoadedProposal",
    "fallback_commit_message",
    "load_proposal",
]

#: The round every bench implementer run stamps (BENCH-CONTRACT.md: round one).
ROUND_NUMBER = 1

#: ``proposal_status`` values recorded on the run record.
PROPOSAL_MISSING = "missing"
PROPOSAL_INVALID = "invalid"
PROPOSAL_APPLIED = "applied"


@dataclass(frozen=True)
class LoadedProposal:
    """The outcome of loading + validating ``output/proposal.json``.

    ``status`` is one of :data:`PROPOSAL_APPLIED` / :data:`PROPOSAL_MISSING` /
    :data:`PROPOSAL_INVALID`.  ``proposal`` is the validated
    benchmark RunProposal on success, else ``None``;
    ``errors`` carries the benchmark validator's messages on failure.
    """

    status: str
    proposal: object | None
    errors: list[str]


def load_proposal(job_dir: Path, *, path: Path | None = None) -> LoadedProposal:
    """Load ``job_dir/output/proposal.json`` and validate it with the benchmark's
    benchmark validate_run (round one).  Never raises."""
    path = path or Path(job_dir) / api.PROPOSAL_FILE
    if not path.exists() and not path.is_symlink():
        return LoadedProposal(PROPOSAL_MISSING, None, [f"no Output Proposal at {path}"])
    try:
        from silverquillm.safe_files import read_regular

        raw = json.loads(read_regular(path).decode("utf-8"))
    except (OSError, ValueError) as exc:
        return LoadedProposal(PROPOSAL_INVALID, None, [f"proposal is not valid JSON: {exc}"])
    if not isinstance(raw, dict):
        return LoadedProposal(PROPOSAL_INVALID, None, ["proposal must be a JSON object"])
    proposal, errors = api.validate_run(raw, round_number=ROUND_NUMBER)
    if proposal is None:
        return LoadedProposal(PROPOSAL_INVALID, None, list(errors))
    return LoadedProposal(PROPOSAL_APPLIED, proposal, [])


def fallback_commit_message(run_id: str, *, issue_number: int = 0) -> str:
    """The driver's commit message when no valid proposal shipped.

    Production ships no fallback (a completed session without a valid proposal
    is retried/escalated); the bench instead commits the checkout as-left with
    this message so the run is still harvested and graded — a deliberate bench
    deviation.  The provenance trailer comes from the production composer.
    """
    body = (
        "Contract run with no valid Output Proposal\n\n"
        "The Output Proposal was missing or invalid; the checkout is committed "
        "as left so the run is still harvested and evaluated."
    )
    return api.commit_message_with_trailer(body, run_id, issue_number, ROUND_NUMBER)
