"""Karn run observations, schema 3 and the schema 2 records before it; historical schema 1
remains unchanged.

Schema 3 differs from schema 2 only in naming (ADR-021): its scores name the suites
``target``, ``fdn`` and ``engine``, and its run metadata carries the ``baseline_comparison``
where schema 2 carried ``combined_regression``. Readers dispatch on the schema version.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
import posixpath
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from silverquillm.results_repo import (
    RETIRED_SUITE_KEYS,
    SUITES,
    InvalidRunRecordError,
    RunRecordExistsError,
    suite_keys,
)

from .definition import DIGEST, SCHEMES, KarnError, canonical, decode_definition, digest
from .observations import (
    SUBAGENT_EFFORTS_MAX,
    SUBAGENT_LABEL_MAX,
    SUBAGENT_MODELS_MAX,
    SUBAGENT_ROWS_MAX,
)
from .provenance import valid as provenance_valid

SCHEMA_VERSION = 3
SCHEMA_VERSIONS = (2, 3)
#: The suites the baseline comparison compares with the unmodified Workspace.
COMPARED_SUITES = ("fdn", "engine")
RECORD_LOCK_SECONDS = 120
# Records from before grading followed the candidate's Python carry no versions.
ISOLATION_FIELDS = (
    {"mode", "grader_image_id", "network"},
    {"mode", "grader_image_id", "network", "candidate_python", "grader_python"},
)
PYTHON_RELEASE = re.compile(r"(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})")


def _graded_python(isolation: dict) -> bool:
    """A recorded candidate version is a release, and its grader shares its minor version."""
    if "candidate_python" not in isolation:
        return True
    python, grader = isolation["candidate_python"], isolation["grader_python"]
    return (
        isinstance(python, str)
        and bool(PYTHON_RELEASE.fullmatch(python))
        and grader == python.rpartition(".")[0]
    )


class RecordWritePendingError(KarnError):
    """The results repository stayed locked; the record is retained locally for recovery."""

    def __init__(self, record: KarnRunRecord | None = None):
        super().__init__("record_write_pending")
        self.record = record


@dataclass(frozen=True)
class KarnIdentity:
    definition_id: str
    definition_digest: str
    image: str
    image_id: str
    scheme: str
    definition_version: int

    def validate(self):
        if (
            type(self.definition_version) is not int
            or self.definition_version not in SCHEMES
            or SCHEMES[self.definition_version] != self.scheme
            or not isinstance(self.definition_id, str)
            or str(uuid.UUID(self.definition_id)) != self.definition_id
            or not DIGEST.fullmatch(self.definition_digest)
            or not DIGEST.fullmatch(self.image_id)
            or not re.fullmatch(r"(?:[a-z0-9][a-z0-9._:/-]*@)?sha256:[0-9a-f]{64}", self.image)
        ):
            raise InvalidRunRecordError("invalid Karn candidate identity")

    def to_dict(self):
        return {
            "scheme": self.scheme,
            "definition_version": self.definition_version,
            "definition_id": self.definition_id,
            "definition_digest": self.definition_digest,
            "image": self.image,
            "image_id": self.image_id,
        }

    @property
    def hash(self):
        self.validate()
        return digest(canonical(self.to_dict())).split(":", 1)[1]

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {
            "scheme",
            "definition_version",
            "definition_id",
            "definition_digest",
            "image",
            "image_id",
        }:
            raise InvalidRunRecordError("invalid Karn identity fields")
        try:
            result = cls(**value)
            result.validate()
        except (ValueError, TypeError):
            raise InvalidRunRecordError("invalid Karn identity") from None
        return result


@dataclass
class KarnRunRecord:
    manifest: dict
    scores: dict

    @property
    def run_id(self):
        return self.manifest["run_id"]

    @property
    def candidate(self):
        return KarnIdentity.from_dict(self.manifest["candidate"])

    @property
    def benchmark(self):
        return self.manifest["benchmark"]

    @property
    def run_metadata(self):
        return self.manifest["run_metadata"]

    @property
    def artifact_pointers(self):
        return self.manifest["artifact_pointers"]

    @property
    def suites(self) -> dict:
        """Each suite's score by its current name, whatever the record's schema version."""
        return {
            suite: self.scores[key]
            for suite, key in suite_keys(self.manifest["schema_version"]).items()
        }

    def validate(self):
        required = {
            "schema_version",
            "run_id",
            "candidate",
            "candidate_hash",
            "benchmark",
            "budget_seconds",
            "run_metadata",
            "artifact_pointers",
        }
        if (
            set(self.manifest) != required
            or type(self.manifest["schema_version"]) is not int
            or self.manifest["schema_version"] not in SCHEMA_VERSIONS
        ):
            raise InvalidRunRecordError("invalid Karn run manifest")
        if not isinstance(self.run_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", self.run_id
        ):
            raise InvalidRunRecordError("invalid Karn run id")
        if self.manifest["candidate_hash"] != self.candidate.hash:
            raise InvalidRunRecordError("Karn candidate hash mismatch")
        if not isinstance(self.benchmark, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.benchmark
        ):
            raise InvalidRunRecordError("invalid Karn benchmark")
        if type(self.manifest["budget_seconds"]) is not int or self.manifest["budget_seconds"] < 1:
            raise InvalidRunRecordError("invalid Karn execution budget")
        if not isinstance(self.run_metadata, dict) or not isinstance(self.artifact_pointers, list):
            raise InvalidRunRecordError("invalid Karn observations")
        required_metadata = {
            "run_date",
            "benchmark_input",
            "candidate_definition",
            "login_profile",
            "grading_source",
            "measurements",
            "execution",
        }
        if not required_metadata <= self.run_metadata.keys():
            raise InvalidRunRecordError("missing Karn run observations")
        date = self.run_metadata["run_date"]
        try:
            if not isinstance(date, str) or datetime.fromisoformat(date).tzinfo is None:
                raise ValueError
        except (TypeError, ValueError):
            raise InvalidRunRecordError("run_date must be a timestamp with a timezone") from None
        try:
            definition = decode_definition(canonical(self.run_metadata["candidate_definition"]))
        except KarnError:
            raise InvalidRunRecordError("invalid recorded definition") from None
        identity = self.candidate
        if (
            digest(canonical(definition)) != identity.definition_digest
            or definition["definition_id"] != identity.definition_id
            or definition["image"] != identity.image
            or definition["definition_version"] != identity.definition_version
        ):
            raise InvalidRunRecordError("recorded definition does not match candidate identity")
        execution = self.run_metadata["execution"]
        if (
            not isinstance(execution, dict)
            or type(execution.get("workspace_stopped")) is not bool
            or execution.get("status")
            not in ("completed", "failed", "deadline", "interrupted", "host_failed")
        ):
            raise InvalidRunRecordError("invalid recorded execution outcome")
        isolation = self.run_metadata.get("grading_isolation")
        if isolation is not None and (
            not isinstance(isolation, dict)
            or set(isolation) not in ISOLATION_FIELDS
            or isolation["mode"] != "container"
            or isolation["network"] != "none"
            or not DIGEST.fullmatch(str(isolation["grader_image_id"]))
            or not _graded_python(isolation)
        ):
            raise InvalidRunRecordError("invalid grading isolation")
        # Records before the toolchain omit the key; an explicit null is never written.
        if "test_toolchain" in self.run_metadata:
            toolchain = self.run_metadata["test_toolchain"]
            if (
                not isinstance(toolchain, dict)
                or set(toolchain) != {"digest", "target"}
                or not DIGEST.fullmatch(str(toolchain["digest"]))
                or not isinstance(toolchain["target"], str)
                or not toolchain["target"].startswith("/run/silverquillm/")
                or posixpath.normpath(toolchain["target"]) != toolchain["target"]
            ):
                raise InvalidRunRecordError("invalid test toolchain")
        # Records before provenance omit the key; an explicit null is never written.
        if "provenance" in self.run_metadata and not provenance_valid(
            self.run_metadata["provenance"]
        ):
            raise InvalidRunRecordError("invalid run provenance")
        failure = self.run_metadata.get("grading_failure")
        if failure is not None and (
            not isinstance(failure, dict)
            or set(failure) != {"reason", "stderr_tail"}
            or not all(isinstance(value, str) for value in failure.values())
        ):
            raise InvalidRunRecordError("invalid grading failure")
        validate_subagents(self.run_metadata["measurements"])
        for pointer in self.artifact_pointers:
            if (
                not isinstance(pointer, dict)
                or set(pointer) != {"kind", "location"}
                or not all(isinstance(value, str) for value in pointer.values())
            ):
                raise InvalidRunRecordError("invalid artifact pointer")
        version = self.manifest["schema_version"]
        current, retired = (
            ("baseline_comparison", "combined_regression")
            if version >= 3
            else ("combined_regression", "baseline_comparison")
        )
        if retired in self.run_metadata:
            raise InvalidRunRecordError(f"schema {version} records carry no {retired}")
        if current in self.run_metadata:
            if version >= 3:
                validate_baseline_comparison(self.run_metadata[current])
            else:
                _validate_schema_2_comparison(self.run_metadata[current])
        validate_scores(self.scores, version)


def validate_subagents(measurements) -> None:
    """Bound the subagent rows, which the workload's own telemetry shapes (#230). Records
    written before them omit the keys."""
    if not isinstance(measurements, dict):
        return
    rows = measurements.get("subagents")
    unlisted = measurements.get("subagents_truncated")
    if unlisted is not None and (type(unlisted) is not int or unlisted < 0):
        raise InvalidRunRecordError("invalid subagent count")
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) > SUBAGENT_ROWS_MAX:
        raise InvalidRunRecordError("invalid subagent rows")
    for row in rows:
        if (
            not isinstance(row, dict)
            # Rows written before requested efforts were kept omit that key.
            or set(row) - {"requested_efforts"} != {"thread_id", "models", "requests"}
            or not _bounded_label(row["thread_id"])
            or not isinstance(row["models"], list)
            or len(row["models"]) > SUBAGENT_MODELS_MAX
            or not all(_bounded_label(model) for model in row["models"])
            or type(row["requests"]) is not int
            or row["requests"] < 0
            or not _efforts(row.get("requested_efforts"))
        ):
            raise InvalidRunRecordError("invalid subagent rows")


def _efforts(value) -> bool:
    return value is None or (
        isinstance(value, list)
        and 0 < len(value) <= SUBAGENT_EFFORTS_MAX
        and all(_bounded_label(effort) for effort in value)
    )


def _bounded_label(value) -> bool:
    return isinstance(value, str) and 0 < len(value) <= SUBAGENT_LABEL_MAX


def validate_scores(scores, schema_version: int = SCHEMA_VERSION) -> None:
    """Enforce the record score invariants on a ``scores.json``-shaped value."""
    if not isinstance(scores, dict) or set(scores) != set(suite_keys(schema_version).values()):
        raise InvalidRunRecordError("invalid Karn score suites")
    for score in scores.values():
        if (
            not isinstance(score, dict)
            or type(score.get("evaluated")) is not bool
            or type(score.get("complete")) is not bool
        ):
            raise InvalidRunRecordError("invalid Karn suite observation")
        reasons = score.get("missing_reasons")
        if not isinstance(reasons, list) or not all(
            isinstance(reason, str) and reason for reason in reasons
        ):
            raise InvalidRunRecordError("invalid grading explanation")
        passed, total, rate = (
            score.get(key) for key in ("tests_passed", "tests_total", "pass_rate")
        )
        if not score["evaluated"]:
            if (
                any(value is not None for value in (passed, total, rate))
                or not reasons
                or score["complete"]
            ):
                raise InvalidRunRecordError("absent grading must remain null with an explanation")
        elif (
            type(passed) is not int
            or type(total) is not int
            or total <= 0
            or not 0 <= passed <= total
            or type(rate) not in (int, float)
            # The range check comes first: math.isfinite converts, and a huge int overflows.
            or not 0 <= rate <= 1
            or not math.isfinite(rate)
            or not math.isclose(rate, passed / total, rel_tol=1e-9, abs_tol=1e-12)
        ):
            raise InvalidRunRecordError("impossible grading counts or rate")


BASELINE_COMPARISON_KEYS = frozenset({"available", "fixed", "broken", "baseline"})
BASELINE_KEY_FIELDS = frozenset(
    {"grading_inputs_digest", "grading_code_digest", "workspace_digest", "grader_image_id"}
)


def _valid_baseline_key(baseline) -> bool:
    return (
        isinstance(baseline, dict)
        and set(baseline) == BASELINE_KEY_FIELDS
        and all(
            isinstance(baseline[name], str) and DIGEST.fullmatch(baseline[name])
            for name in ("grading_inputs_digest", "grading_code_digest", "workspace_digest")
        )
        and isinstance(baseline["grader_image_id"], str)
        and bool(baseline["grader_image_id"])
    )


def _sorted_ids(listed) -> bool:
    return (
        isinstance(listed, list)
        and all(isinstance(node, str) and node for node in listed)
        and listed == sorted(set(listed))
    )


def _moved(value, suites) -> dict:
    if not isinstance(value, dict) or set(value) != set(suites):
        raise InvalidRunRecordError("invalid baseline comparison")
    if not all(_sorted_ids(listed) for listed in value.values()):
        raise InvalidRunRecordError("invalid baseline comparison")
    return value


def validate_baseline_comparison(value) -> None:
    """Enforce the baseline comparison's shape (``SCORING.md`` → Run Record results)."""
    if not isinstance(value, dict) or type(value.get("available")) is not bool:
        raise InvalidRunRecordError("invalid baseline comparison")
    if value["available"] is False:
        if set(value) != {"available", "reason"} or not (
            isinstance(value["reason"], str) and value["reason"]
        ):
            raise InvalidRunRecordError("invalid baseline comparison")
        return
    if set(value) != BASELINE_COMPARISON_KEYS:
        raise InvalidRunRecordError("invalid baseline comparison")
    fixed = _moved(value["fixed"], COMPARED_SUITES)
    broken = _moved(value["broken"], COMPARED_SUITES)
    if any(set(fixed[suite]) & set(broken[suite]) for suite in COMPARED_SUITES):
        raise InvalidRunRecordError("invalid baseline comparison")
    if not _valid_baseline_key(value["baseline"]):
        raise InvalidRunRecordError("invalid baseline comparison")


#: The block schema 2 records carried in place of the baseline comparison.
SCHEMA_2_COMPARISON_KEYS = frozenset(
    {
        "available",
        "tests_passed",
        "tests_total",
        "pass_rate",
        "baseline_score",
        "known_best_score",
        "fixed",
        "regressed",
        "baseline",
    }
)
SCHEMA_2_COMPARED_KEYS = tuple(RETIRED_SUITE_KEYS[suite] for suite in COMPARED_SUITES)


def _schema_2_counts(value) -> tuple[int, int]:
    if not isinstance(value, dict) or set(value) != {"tests_passed", "tests_total"}:
        raise InvalidRunRecordError("invalid schema 2 comparison")
    passed, total = value["tests_passed"], value["tests_total"]
    if type(passed) is not int or type(total) is not int or total <= 0 or not 0 <= passed <= total:
        raise InvalidRunRecordError("invalid schema 2 comparison")
    return passed, total


def _schema_2_changed(value) -> int:
    if not isinstance(value, dict) or set(value) != {"count", "test_nodes"}:
        raise InvalidRunRecordError("invalid schema 2 comparison")
    try:
        nodes = _moved(value["test_nodes"], SCHEMA_2_COMPARED_KEYS)
    except InvalidRunRecordError:
        raise InvalidRunRecordError("invalid schema 2 comparison") from None
    count = value["count"]
    if type(count) is not int or count != sum(len(listed) for listed in nodes.values()):
        raise InvalidRunRecordError("invalid schema 2 comparison")
    return count


def _validate_schema_2_comparison(value) -> None:
    """Enforce the shape of the block a schema 2 record carries under its retired name."""
    if not isinstance(value, dict) or type(value.get("available")) is not bool:
        raise InvalidRunRecordError("invalid schema 2 comparison")
    if value["available"] is False:
        if set(value) != {"available", "reason"} or not (
            isinstance(value["reason"], str) and value["reason"]
        ):
            raise InvalidRunRecordError("invalid schema 2 comparison")
        return
    if set(value) != SCHEMA_2_COMPARISON_KEYS:
        raise InvalidRunRecordError("invalid schema 2 comparison")
    passed, total = _schema_2_counts(
        {"tests_passed": value["tests_passed"], "tests_total": value["tests_total"]}
    )
    rate = value["pass_rate"]
    if (
        type(rate) not in (int, float)
        # The range check comes first: math.isclose converts, and a huge int overflows.
        or not 0 <= rate <= 1
        or not math.isfinite(rate)
        or not math.isclose(rate, passed / total, rel_tol=1e-9, abs_tol=1e-12)
    ):
        raise InvalidRunRecordError("invalid schema 2 comparison")
    baseline_passed, baseline_total = _schema_2_counts(value["baseline_score"])
    best_passed, best_total = _schema_2_counts(value["known_best_score"])
    if not best_passed == best_total == baseline_total:
        raise InvalidRunRecordError("invalid schema 2 comparison")
    if _schema_2_changed(value["fixed"]) > baseline_total - baseline_passed:
        raise InvalidRunRecordError("invalid schema 2 comparison")
    if _schema_2_changed(value["regressed"]) > baseline_passed:
        raise InvalidRunRecordError("invalid schema 2 comparison")
    if not _valid_baseline_key(value["baseline"]):
        raise InvalidRunRecordError("invalid schema 2 comparison")


def missing_scores(reason: str) -> dict:
    return {
        name: {
            "evaluated": False,
            "complete": False,
            "pass_rate": None,
            "tests_passed": None,
            "tests_total": None,
            "missing_reasons": [reason],
        }
        for name in SUITES
    }


@contextlib.contextmanager
def _record_lock(results: Path, timeout: float, record: KarnRunRecord):
    # flock the results directory itself, so no lock file ever enters the results repository.
    descriptor = os.open(results, os.O_RDONLY | os.O_DIRECTORY)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RecordWritePendingError(record) from None
                time.sleep(0.1)
        yield
    finally:
        os.close(descriptor)


def write_record(
    repo_root: Path, record: KarnRunRecord, *, lock_seconds: float = RECORD_LOCK_SECONDS
) -> Path:
    """Wait for concurrent writers; on timeout raise :class:`RecordWritePendingError`."""
    record.validate()
    repo_root = Path(repo_root)
    target = repo_root / "results" / record.candidate.hash / record.run_id
    target.parent.mkdir(parents=True, exist_ok=True)
    with _record_lock(repo_root / "results", lock_seconds, record):
        if target.exists():
            raise RunRecordExistsError(str(target))
        temporary = Path(tempfile.mkdtemp(prefix=".record-", dir=target.parent))
        try:
            (temporary / "manifest.json").write_bytes(canonical(record.manifest) + b"\n")
            (temporary / "scores.json").write_bytes(canonical(record.scores) + b"\n")
            os.rename(temporary, target)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return target


def read_record(run_dir: Path) -> KarnRunRecord:
    try:
        record = KarnRunRecord(
            json.loads((run_dir / "manifest.json").read_text()),
            json.loads((run_dir / "scores.json").read_text()),
        )
        record.validate()
    except (ValueError, TypeError, OSError, KeyError):
        raise InvalidRunRecordError("invalid Karn run record") from None
    if record.run_id != run_dir.name or record.candidate.hash != run_dir.parent.name:
        raise InvalidRunRecordError("Karn record identity does not match its location")
    return record
