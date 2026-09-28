"""Schema 2 run observations; historical schema 1 remains unchanged."""

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

from silverquillm.results_repo import InvalidRunRecordError, RunRecordExistsError

from .definition import DIGEST, KarnError, canonical, decode_definition, digest

SCHEMA_VERSION = 2
DIMENSIONS = ("card_correctness", "fdn_regression", "engine_regression")
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
    scheme: str = "karn-v4"
    definition_version: int = 4

    def validate(self):
        if (
            self.scheme != "karn-v4"
            or type(self.definition_version) is not int
            or self.definition_version != 4
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
            or self.manifest["schema_version"] != 2
        ):
            raise InvalidRunRecordError("invalid schema 2 run manifest")
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
        failure = self.run_metadata.get("grading_failure")
        if failure is not None and (
            not isinstance(failure, dict)
            or set(failure) != {"reason", "stderr_tail"}
            or not all(isinstance(value, str) for value in failure.values())
        ):
            raise InvalidRunRecordError("invalid grading failure")
        for pointer in self.artifact_pointers:
            if (
                not isinstance(pointer, dict)
                or set(pointer) != {"kind", "location"}
                or not all(isinstance(value, str) for value in pointer.values())
            ):
                raise InvalidRunRecordError("invalid artifact pointer")
        if not isinstance(self.scores, dict) or set(self.scores) != set(DIMENSIONS):
            raise InvalidRunRecordError("invalid Karn score dimensions")
        for score in self.scores.values():
            if (
                not isinstance(score, dict)
                or type(score.get("evaluated")) is not bool
                or type(score.get("complete")) is not bool
            ):
                raise InvalidRunRecordError("invalid Karn dimension observation")
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
                    raise InvalidRunRecordError(
                        "absent grading must remain null with an explanation"
                    )
            elif (
                type(passed) is not int
                or type(total) is not int
                or total <= 0
                or not 0 <= passed <= total
                or type(rate) not in (int, float)
                or not math.isfinite(rate)
                or not 0 <= rate <= 1
                or not math.isclose(rate, passed / total, rel_tol=1e-9, abs_tol=1e-12)
            ):
                raise InvalidRunRecordError("impossible grading counts or rate")

    def index_row(self):
        return {
            "schema_version": 2,
            "candidate_hash": self.candidate.hash,
            "run_id": self.run_id,
            "benchmark": self.benchmark,
            "run_date": self.run_metadata.get("run_date"),
            "execution_status": self.run_metadata.get("execution", {}).get("status"),
            "recovery_of": self.run_metadata.get("recovery_of"),
            "execution_run_id": self.run_metadata.get("execution_run_id", self.run_id),
            "measurements": self.run_metadata.get("measurements"),
        }


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
        for name in DIMENSIONS
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
        raise InvalidRunRecordError("invalid schema 2 run record") from None
    if record.run_id != run_dir.name or record.candidate.hash != run_dir.parent.name:
        raise InvalidRunRecordError("schema 2 identity does not match record location")
    return record
