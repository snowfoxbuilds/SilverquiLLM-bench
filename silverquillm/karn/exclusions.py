"""Exclusions: which retained runs an analysis leaves out, and why, as write-once files.

Records are immutable, so a run is excluded by a file beside the records,
``exclusions/<candidate-hash>/<run-id>.json``, never by editing its record. The run writer
adds one when a mechanical rule fires; an operator adds one for anything a rule cannot
see. One file per run keeps hosts that share the results repository from editing the same
file. Deleting the file restores the run; git history keeps the trail.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from silverquillm.results_repo import InvalidRunRecordError, iter_run_dirs

from .definition import KarnError, canonical, read_regular, strict_json
from .records import KarnRunRecord, read_record

FORMAT_VERSION = 1
EXCLUSIONS = "exclusions"
REASONS = {
    "subagents_used": "the agent delegated to subagent threads",
    "subagents_uncounted": "recorded before subagent threads were counted; subagents may have run",
    "never_executed": "the agent took no turns",
    "host_failed": "the host failed the run",
    "superseded": "a later recovery or rerun of the same attempt replaces it",
    "benchmark_defect": "a benchmark defect makes the score meaningless",
    "pilot": "a pipeline validation run, not a measurement",
    "other": "see the note",
}
RULE_SOURCE, OPERATOR_SOURCE = "rule", "operator"
RULE_AUTHOR = "silverquillm"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
CANDIDATE_HASH = re.compile(r"[0-9a-f]{64}")
FIELDS = {
    "format_version",
    "run_id",
    "candidate_hash",
    "reason",
    "note",
    "source",
    "superseded_by",
    "excluded_by",
    "excluded_at",
}


class ExclusionError(KarnError):
    """An exclusion that cannot be written or read; the message is a stable code."""


@dataclass(frozen=True)
class Exclusion:
    run_id: str
    candidate_hash: str
    reason: str
    note: str
    source: str
    superseded_by: str | None
    excluded_by: str
    excluded_at: str

    def to_dict(self) -> dict:
        return {"format_version": FORMAT_VERSION, **self.__dict__}

    @classmethod
    def from_dict(cls, value) -> Exclusion:
        if (
            not isinstance(value, dict)
            or set(value) != FIELDS
            or value["format_version"] != FORMAT_VERSION
        ):
            raise ExclusionError("exclusion_invalid")
        fields = {key: value[key] for key in FIELDS - {"format_version"}}
        exclusion = cls(**fields)
        exclusion.validate()
        return exclusion

    def validate(self) -> None:
        if (
            not isinstance(self.run_id, str)
            or not RUN_ID.fullmatch(self.run_id)
            or not isinstance(self.candidate_hash, str)
            or not CANDIDATE_HASH.fullmatch(self.candidate_hash)
            or self.reason not in REASONS
            or self.source not in (RULE_SOURCE, OPERATOR_SOURCE)
            or not isinstance(self.note, str)
            or not self.note.strip()
            or not isinstance(self.excluded_by, str)
            or not self.excluded_by.strip()
            or not isinstance(self.excluded_at, str)
        ):
            raise ExclusionError("exclusion_invalid")
        if (self.reason == "superseded") != (self.superseded_by is not None):
            raise ExclusionError("exclusion_superseded_by_required_only_for_superseded")
        if self.superseded_by is not None and (
            not isinstance(self.superseded_by, str) or not RUN_ID.fullmatch(self.superseded_by)
        ):
            raise ExclusionError("exclusion_invalid")
        try:
            if datetime.fromisoformat(self.excluded_at).tzinfo is None:
                raise ValueError
        except ValueError:
            raise ExclusionError("exclusion_invalid") from None


def exclusion_path(results_repo: Path, candidate_hash: str, run_id: str) -> Path:
    if not CANDIDATE_HASH.fullmatch(candidate_hash) or not RUN_ID.fullmatch(run_id):
        raise ExclusionError("exclusion_identity_invalid")
    return Path(results_repo) / EXCLUSIONS / candidate_hash / f"{run_id}.json"


def rule_exclusion(record: KarnRunRecord) -> tuple[str, str] | None:
    """The first mechanical rule the record meets, as ``(reason, note)``, else None.

    Only observed facts count. A host failure is an observed status, whatever the
    measurements hold. Absent, null or empty measurements are unknown and never exclude;
    only a populated measurement object that lacks ``subagent_threads`` shows the run was
    measured before threads were counted.
    """
    metadata = record.run_metadata
    if metadata["execution"]["status"] == "host_failed":
        return "host_failed", "execution status host_failed"
    measurements = metadata.get("measurements")
    if not isinstance(measurements, dict) or not measurements:
        return None
    turns = ((measurements.get("agent_turns") or {}).get("total") or {}).get("value")
    if turns == 0:
        return "never_executed", "observed zero agent turns"
    threads = measurements.get("subagent_threads")
    if isinstance(threads, int) and threads > 0:
        return "subagents_used", f"observed {threads} subagent thread(s)"
    if "subagent_threads" not in measurements:
        return "subagents_uncounted", "measurements predate subagent thread counting"
    return None


def write_exclusion(results_repo: Path, exclusion: Exclusion) -> Path:
    """Write once; an existing exclusion for the run is never replaced."""
    exclusion.validate()
    path = exclusion_path(results_repo, exclusion.candidate_hash, exclusion.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".exclusion-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical(exclusion.to_dict()) + b"\n")
        # A hard link fails if the target exists, so a concurrent writer can never be overwritten.
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise ExclusionError("run_already_excluded") from None
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def _now() -> str:
    return datetime.now(UTC).isoformat()


def exclude_by_rule(results_repo: Path, record: KarnRunRecord) -> Exclusion | None:
    """Write the rule exclusion the record meets, if any and if the run is not excluded yet."""
    matched = rule_exclusion(record)
    if matched is None:
        return None
    if exclusion_path(results_repo, record.candidate.hash, record.run_id).exists():
        return None
    exclusion = Exclusion(
        record.run_id,
        record.candidate.hash,
        matched[0],
        matched[1],
        RULE_SOURCE,
        None,
        RULE_AUTHOR,
        _now(),
    )
    write_exclusion(results_repo, exclusion)
    return exclusion


def exclude(
    results_repo: Path,
    run_id: str,
    *,
    reason: str,
    note: str,
    excluded_by: str,
    superseded_by: str | None = None,
) -> Exclusion:
    """An operator exclusion of a recorded run; a superseding run must be recorded too."""
    records = {record.run_id: record for record in _records(results_repo)}
    if run_id not in records:
        raise ExclusionError("run_not_recorded:" + run_id)
    if superseded_by is not None and superseded_by not in records:
        raise ExclusionError("superseding_run_not_recorded:" + superseded_by)
    if superseded_by == run_id:
        raise ExclusionError("run_cannot_supersede_itself")
    exclusion = Exclusion(
        run_id,
        records[run_id].candidate.hash,
        reason,
        note,
        OPERATOR_SOURCE,
        superseded_by,
        excluded_by,
        _now(),
    )
    write_exclusion(results_repo, exclusion)
    return exclusion


def _records(results_repo: Path) -> list[KarnRunRecord]:
    records = []
    for run_dir in iter_run_dirs(results_repo):
        try:
            records.append(read_record(run_dir))
        except InvalidRunRecordError:
            continue  # Schema 1 records have no Karn measurements to apply rules to.
    return records


def load_exclusions(results_repo: Path) -> dict[str, Exclusion]:
    """Every exclusion by run id; any malformed or misplaced file is refused loudly."""
    found = {}
    root = Path(results_repo) / EXCLUSIONS
    if not root.is_dir():
        return found
    for path in sorted(root.glob("*/*.json")):
        try:
            exclusion = Exclusion.from_dict(strict_json(read_regular(path)))
        except (KarnError, TypeError):
            raise ExclusionError(
                "exclusion_invalid:" + str(path.relative_to(results_repo))
            ) from None
        if path != exclusion_path(results_repo, exclusion.candidate_hash, exclusion.run_id):
            raise ExclusionError("exclusion_misplaced:" + str(path.relative_to(results_repo)))
        found[exclusion.run_id] = exclusion
    return found


def check(results_repo: Path, *, write_rules: bool = False) -> dict:
    """Records meeting a rule without an exclusion, and exclusions without their records.

    With *write_rules*, the missing rule exclusions are written instead of reported.
    """
    records = _records(results_repo)
    by_id = {record.run_id: record for record in records}
    exclusions = load_exclusions(results_repo)
    unexcluded, written = [], []
    for record in records:
        if record.run_id in exclusions or (matched := rule_exclusion(record)) is None:
            continue
        if write_rules:
            written.append(exclude_by_rule(results_repo, record).to_dict())
        else:
            unexcluded.append(
                {
                    "run_id": record.run_id,
                    "candidate_hash": record.candidate.hash,
                    "rule": matched[0],
                }
            )
    orphans = [
        {"run_id": e.run_id, "candidate_hash": e.candidate_hash}
        for e in exclusions.values()
        if by_id.get(e.run_id) is None or by_id[e.run_id].candidate.hash != e.candidate_hash
    ]
    dangling = [
        {"run_id": e.run_id, "superseded_by": e.superseded_by}
        for e in exclusions.values()
        if e.superseded_by is not None and e.superseded_by not in by_id
    ]
    return {
        "unexcluded_rule_matches": unexcluded,
        "written": written,
        "orphaned_exclusions": orphans,
        "missing_superseding_runs": dangling,
    }
