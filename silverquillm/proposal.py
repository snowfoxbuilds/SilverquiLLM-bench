"""Output Proposal handling — validation delegated to TheOzolith's validator.

The bench does not reimplement the Output Proposal schema.  Per the Bench
Contract (``docs/specs/BENCH-CONTRACT.md``), proposal validation is
``schema_version`` surface consumed from the published API
(:func:`theozolith_worker.api.validate_run`), never copied — a hand-rolled
allowlist would drift silently as production's schema evolves.

This module is a thin bench adapter: locate ``output/proposal.json``, run the
*production* driver-side validator at round one, and map the result to a bench
``proposal_status`` (``applied`` / ``missing`` / ``invalid``).  It never raises
through the driver — a missing or invalid proposal is recorded as a status and
the checkout is committed and graded regardless (the workspace is the evidence).

Public API
----------
- :class:`LoadedProposal` — the :func:`load_proposal` result.
- :func:`load_proposal` — read + validate via the production validator.
- :func:`fallback_commit_message` — the driver's commit body when no valid
  proposal shipped (a deliberate bench deviation; production ships none).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from theozolith_worker import api

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
    :class:`~theozolith_worker.api.RunProposal` on success, else ``None``;
    ``errors`` carries the production validator's messages on failure.
    """

    status: str
    proposal: object | None
    errors: list[str]


def load_proposal(job_dir: Path) -> LoadedProposal:
    """Load ``job_dir/output/proposal.json`` and validate it with production's
    :func:`theozolith_worker.api.validate_run` (round one).  Never raises."""
    path = Path(job_dir) / api.PROPOSAL_FILE
    if not path.is_file():
        return LoadedProposal(PROPOSAL_MISSING, None, [f"no Output Proposal at {path}"])
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
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
