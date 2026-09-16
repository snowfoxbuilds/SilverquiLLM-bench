"""Benchmark-owned implementation proposal schema; historical comparison fields preserved."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

from silverquillm.decisions import Decision, DecisionsSection, process_issues_from

jobdir = SimpleNamespace(MODE_RUN="run")


def fields_for(mode):
    if mode != "run":
        raise ProposalError("benchmark proposal requires run mode")
    return RUN_FIELDS


SCHEMA_VERSION = 1

PROPOSAL_FILE = "output/proposal.json"

LINE = "line"  # single-line non-empty string

TEXT = "text"  # multi-line non-empty string

ENUM = "enum"  # one of spec.choices

STRINGS = "strings"  # JSON list of non-empty strings

DECISION_ENTRIES = "decisions"  # JSON list of {"what": ..., "why": ...}

PROCESS_ENTRIES = "process-issues"  # JSON list of {"friction": ..., "suggested_fix": ...}


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str
    choices: tuple[str, ...] = ()
    hint: str = ""


RUN_FIELDS: dict[str, FieldSpec] = {
    spec.name: spec
    for spec in (
        FieldSpec("pr-title", LINE, hint="descriptive PR title (the pipeline adds the #N: prefix)"),
        FieldSpec("pr-description", TEXT, hint="PR narrative (the pipeline composes the body)"),
        FieldSpec("commit-message", TEXT, hint="rich commit message; subject line + body"),
        FieldSpec("decisions", DECISION_ENTRIES, hint='[{"what": "...", "why": "..."}]'),
        FieldSpec("open-questions", STRINGS, hint="calls only a human can make"),
        FieldSpec("remaining-work", STRINGS, hint="what a follow-up round still needs"),
        FieldSpec("dead-ends", STRINGS, hint="approaches tried and abandoned"),
        FieldSpec(
            "process-issues",
            PROCESS_ENTRIES,
            hint='[{"friction": "...", "suggested_fix": "..."}] (advisory)',
        ),
    )
}


class ProposalError(ValueError):
    """A proposal write or read that violates the schema."""


def pending_fields(raw: dict | None) -> dict:
    fields = (raw or {}).get("fields")
    return fields if isinstance(fields, dict) else {}


def _list_shape_error(spec: FieldSpec, value: object) -> str | None:
    if not isinstance(value, list):
        return f"{spec.name} must be a JSON array ({spec.hint})"
    if spec.kind == STRINGS:
        if any(not isinstance(item, str) or not item.strip() for item in value):
            return f"{spec.name} must be an array of non-empty strings"
        return None
    key = "what" if spec.kind == DECISION_ENTRIES else "friction"
    optional = "why" if spec.kind == DECISION_ENTRIES else "suggested_fix"
    for item in value:
        if not isinstance(item, dict):
            return f"{spec.name} entries must be objects ({spec.hint})"
        if not isinstance(item.get(key), str) or not item[key].strip():
            return f"{spec.name} entries need a non-empty {key!r}"
        if not isinstance(item.get(optional, ""), str):
            return f"{spec.name} entry {optional!r} must be a string"
        unknown = set(item) - {key, optional}
        if unknown:
            return f"{spec.name} entries take only {key!r}/{optional!r}, not {sorted(unknown)}"
    return None


def required_fields(mode: str, round_number: int) -> tuple[str, ...]:
    """The unconditionally required fields. commit-message on every round;
    pr-title/pr-description only on the round that creates the PR (on resume
    rounds an absent field means keep-what-exists, ADR-0046). Conditional
    requirements (approve needs grades, revise needs a plan) live in
    :func:`validate_review`."""
    if mode == jobdir.MODE_RUN:
        if round_number <= 1:
            return ("pr-title", "pr-description", "commit-message")
        return ("commit-message",)
    return ("verdict", "evidence")


def _document_errors(raw: dict | None, mode: str) -> list[str]:
    """Structural refusals that apply to the document as a whole."""
    if raw is None:
        return [
            ("no output proposal was written (write the declared proposal file before finishing)")
        ]
    errors = []
    version = raw.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(f"proposal schema_version {version!r} is not {SCHEMA_VERSION}")
    stamped = raw.get("mode")
    if stamped != mode:
        errors.append(f"proposal mode {stamped!r} is not {mode!r}")
    if not isinstance(raw.get("fields"), dict):
        errors.append("proposal carries no fields object")
    unknown_keys = set(raw) - {"schema_version", "mode", "fields"}
    if unknown_keys:
        errors.append(f"unknown proposal keys {sorted(unknown_keys)}")
    return errors


def field_errors(fields: dict, mode: str, round_number: int) -> list[str]:
    """Missing required fields plus shape errors on whatever is present —
    the driver-side check and the completion-retry appendix source alike.
    process-issues stays lenient (advisory content must never invalidate a
    proposal — malformed entries are dropped at composition, never errors)."""
    specs = fields_for(mode)
    errors = []
    for name in sorted(set(fields) - set(specs)):
        errors.append(f"unknown field {name!r} (the {mode} schema allows: {', '.join(specs)})")
    for name in required_fields(mode, round_number):
        if name not in fields:
            errors.append(f"{name} (missing)")
    for name, value in fields.items():
        spec = specs.get(name)
        if spec is None or spec.kind == PROCESS_ENTRIES:
            continue
        if spec.kind in (LINE, TEXT, ENUM):
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{name} (must be a non-empty string)")
            elif spec.kind == LINE and "\n" in value:
                errors.append(f"{name} (must be a single line)")
            elif spec.kind == ENUM and value not in spec.choices:
                errors.append(f"{name} (must be one of {', '.join(spec.choices)})")
        else:
            shape = _list_shape_error(spec, value)
            if shape:
                errors.append(f"{name} ({shape})")
    return errors


@dataclass(frozen=True)
class RunProposal:
    """The validated Implementer proposal, ready for the driver to apply."""

    commit_message: str
    pr_title: str = ""  # "" on resume rounds: keep the existing title
    pr_description: str = ""  # "" on resume rounds: keep the existing body
    section: DecisionsSection = field(default_factory=DecisionsSection)


def _section_from(fields: dict) -> DecisionsSection:
    return DecisionsSection(
        decisions=[
            Decision(what=item["what"], why=item.get("why", ""))
            for item in fields.get("decisions", [])
        ],
        open_questions=list(fields.get("open-questions", [])),
        remaining_work=list(fields.get("remaining-work", [])),
        dead_ends=list(fields.get("dead-ends", [])),
        process_issues=process_issues_from(fields.get("process-issues")),
    )


def validate_run(raw: dict | None, *, round_number: int) -> tuple[RunProposal | None, list[str]]:
    """Strict driver-side validation of an Implementer proposal. Returns
    (proposal, []) or (None, errors) — the error list is what the
    completion-retry appendix quotes (ADR-0016 as amended)."""
    errors = _document_errors(raw, jobdir.MODE_RUN)
    if errors:
        return None, errors
    fields = pending_fields(raw)
    errors = field_errors(fields, jobdir.MODE_RUN, round_number)
    if errors:
        return None, errors
    return (
        RunProposal(
            commit_message=fields["commit-message"],
            pr_title=fields.get("pr-title", ""),
            pr_description=fields.get("pr-description", ""),
            section=_section_from(fields),
        ),
        [],
    )
