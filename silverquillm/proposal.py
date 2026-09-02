"""Output Proposal: load, validate, and turn into a driver commit.

The Output Proposal is the sole policy boundary (ADR-0046): the agent writes
``output/proposal.json`` describing what it did, and the *driver* — never the
agent — validates it post-exit and commits the workspace. The proposal is
narrative; the workspace filesystem is the evidence. An absent or invalid
proposal therefore never aborts harvest or evaluation — it is recorded as a
``proposal_status`` and the run is scored from the filesystem regardless.

Wire shape (substrate parity): ``{"schema_version": 1, "mode": "run",
"fields": {...}}`` with kebab-case field names. The bench consumes the
Implementer field set; ``pr-title`` / ``pr-description`` are accepted and
recorded verbatim as metadata but never applied (bench runs open no PRs).

Allowlist by schema (the trust boundary): unknown top-level keys and unknown
field names are rejected; an absent optional field is a no-op, never a clear.

Public API
----------
- :class:`Proposal` / :class:`ProposalError` — the ``load_proposal`` result.
- :func:`load_proposal` — read + strictly validate; returns, never raises.
- :func:`commit_message_with_trailer` / :func:`fallback_commit_message`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "PROPOSAL_APPLIED",
    "PROPOSAL_INVALID",
    "PROPOSAL_MISSING",
    "SCHEMA_VERSION",
    "Proposal",
    "ProposalError",
    "commit_message_with_trailer",
    "fallback_commit_message",
    "load_proposal",
]

#: The Output Proposal schema version — also stamped into the job manifest.
SCHEMA_VERSION = 1

#: ``proposal_status`` values recorded on the run record.
PROPOSAL_MISSING = "missing"
PROPOSAL_INVALID = "invalid"
PROPOSAL_APPLIED = "applied"

#: Allowed top-level keys of a proposal document.
_TOP_LEVEL_KEYS = frozenset({"schema_version", "mode", "fields"})

#: Implementer (``mode: "run"``) fields the bench consumes — kebab-case on disk.
#: ``commit-message`` is required; everything else is optional narrative.
_LIST_OF_STR_FIELDS = ("open-questions", "remaining-work", "dead-ends")
_STR_FIELDS = ("commit-message", "pr-title", "pr-description")
#: kebab field -> the allowed keys of each object in the list.
_LIST_OF_OBJ_FIELDS = {
    "decisions": frozenset({"what", "why"}),
    "process-issues": frozenset({"friction", "suggested_fix"}),
}
_ALLOWED_FIELDS = frozenset(
    (*_STR_FIELDS, *_LIST_OF_STR_FIELDS, *_LIST_OF_OBJ_FIELDS)
)


@dataclass(frozen=True)
class Proposal:
    """A validated Implementer Output Proposal.

    ``pr_title`` / ``pr_description`` are recorded verbatim as metadata and
    never applied by the bench (bench runs open no PRs).
    """

    commit_message: str
    decisions: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    remaining_work: list[str] = field(default_factory=list)
    dead_ends: list[str] = field(default_factory=list)
    process_issues: list[dict[str, Any]] = field(default_factory=list)
    pr_title: str | None = None
    pr_description: str | None = None


@dataclass(frozen=True)
class ProposalError:
    """A typed load failure. ``status`` is :data:`PROPOSAL_MISSING` or
    :data:`PROPOSAL_INVALID`; it is returned, never raised, so it can never
    abort the driver."""

    status: str
    message: str


def _err(status: str, message: str) -> ProposalError:
    return ProposalError(status=status, message=message)


def _manifest_schema_version(job_dir: Path) -> int | None:
    """The ``schema_version`` stamped in the job manifest, or ``None`` if it
    cannot be read (the proposal's own value is then the only check)."""
    try:
        manifest = json.loads(
            (job_dir / "input" / "manifest.json").read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return None
    value = manifest.get("schema_version") if isinstance(manifest, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def load_proposal(job_dir: Path) -> Proposal | ProposalError:
    """Load and strictly validate ``job_dir/output/proposal.json``.

    Returns a :class:`Proposal` on success or a typed :class:`ProposalError`
    (status ``missing`` for an absent file, ``invalid`` for anything else) —
    it never raises through the driver. ``schema_version`` is asserted against
    the job manifest when the manifest is readable.
    """
    job_dir = Path(job_dir)
    path = job_dir / "output" / "proposal.json"
    if not path.is_file():
        return _err(PROPOSAL_MISSING, f"no Output Proposal at {path}")

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return _err(PROPOSAL_INVALID, f"proposal is not valid JSON: {exc}")

    if not isinstance(doc, dict):
        return _err(PROPOSAL_INVALID, "proposal must be a JSON object")

    unknown_top = set(doc) - _TOP_LEVEL_KEYS
    if unknown_top:
        return _err(
            PROPOSAL_INVALID,
            f"unknown top-level key(s): {', '.join(sorted(unknown_top))}",
        )

    version = doc.get("schema_version")
    if version != SCHEMA_VERSION:
        return _err(
            PROPOSAL_INVALID,
            f"schema_version must be {SCHEMA_VERSION}, got {version!r}",
        )
    manifest_version = _manifest_schema_version(job_dir)
    if manifest_version is not None and manifest_version != version:
        return _err(
            PROPOSAL_INVALID,
            f"schema_version {version!r} != job manifest {manifest_version!r}",
        )

    if doc.get("mode") != "run":
        return _err(
            PROPOSAL_INVALID,
            f"mode must be 'run' (implementer), got {doc.get('mode')!r}",
        )

    fields = doc.get("fields")
    if not isinstance(fields, dict):
        return _err(PROPOSAL_INVALID, "'fields' must be a JSON object")

    unknown_fields = set(fields) - _ALLOWED_FIELDS
    if unknown_fields:
        return _err(
            PROPOSAL_INVALID,
            f"unknown proposal field(s): {', '.join(sorted(unknown_fields))}",
        )

    # commit-message is required and non-empty.
    commit_message = fields.get("commit-message")
    if not isinstance(commit_message, str) or not commit_message.strip():
        return _err(PROPOSAL_INVALID, "'commit-message' is required and must be non-empty")

    for key in _STR_FIELDS:
        if key in fields and not isinstance(fields[key], str):
            return _err(PROPOSAL_INVALID, f"{key!r} must be a string")

    for key in _LIST_OF_STR_FIELDS:
        value = fields.get(key)
        if key in fields and not _is_list_of_str(value):
            return _err(PROPOSAL_INVALID, f"{key!r} must be a list of strings")

    for key, allowed_keys in _LIST_OF_OBJ_FIELDS.items():
        value = fields.get(key)
        if key in fields:
            problem = _validate_obj_list(value, allowed_keys)
            if problem is not None:
                return _err(PROPOSAL_INVALID, f"{key!r} {problem}")

    return Proposal(
        commit_message=commit_message,
        decisions=list(fields.get("decisions", [])),
        open_questions=list(fields.get("open-questions", [])),
        remaining_work=list(fields.get("remaining-work", [])),
        dead_ends=list(fields.get("dead-ends", [])),
        process_issues=list(fields.get("process-issues", [])),
        pr_title=fields.get("pr-title"),
        pr_description=fields.get("pr-description"),
    )


def _is_list_of_str(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def _validate_obj_list(value: Any, allowed_keys: frozenset[str]) -> str | None:
    """Return a problem description, or ``None`` if *value* is a valid list of
    objects whose keys are a subset of *allowed_keys* with string values."""
    if not isinstance(value, list):
        return "must be a list"
    for entry in value:
        if not isinstance(entry, dict):
            return "entries must be objects"
        extra = set(entry) - allowed_keys
        if extra:
            return f"entry has unknown key(s): {', '.join(sorted(extra))}"
        for k, v in entry.items():
            if not isinstance(v, str):
                return f"entry {k!r} must be a string"
    return None


# ---------------------------------------------------------------------------
# Commit-message composition (driver-side)
# ---------------------------------------------------------------------------


def commit_message_with_trailer(
    body: str, run_id: str, benchmark: str, mode: str
) -> str:
    """Return *body* with the bench provenance trailer appended.

    Trailer: ``Silverquillm-Run: <run-id> / <benchmark> / <mode>``. The driver
    commits with this message; the agent never runs git.
    """
    trailer = f"Silverquillm-Run: {run_id} / {benchmark} / {mode}"
    return f"{body.rstrip()}\n\n{trailer}\n"


def fallback_commit_message(run_id: str, benchmark: str, mode: str) -> str:
    """A generated commit message for when the proposal is missing/invalid."""
    body = (
        f"Contract run of {benchmark} ({mode}) with no valid Output Proposal\n\n"
        "The Output Proposal was missing or invalid; the workspace is committed "
        "as left so the run is still harvested and evaluated."
    )
    return commit_message_with_trailer(body, run_id, benchmark, mode)
