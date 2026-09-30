"""Re-grade retained Karn runs against the checkout's current grading inputs.

Run Records are immutable, so a re-grade never replaces one: each run's new scores go to a
separate output directory, tagged with the grading-inputs digest they were graded against.
Scores from different digests are not comparable without re-grading both.

A run's graded workspace comes from its local run artifacts when this host ran it, else it
is rebuilt from the results repository's workspace archive (ADR-015), so any host can
re-grade any archived run.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import secrets
import stat
import statistics
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from silverquillm.results_repo import InvalidRunRecordError, iter_run_dirs

from .benchmark import Benchmark, load_benchmark
from .definition import KarnError
from .execution import _scores
from .grader import (
    DEFAULT_GRADING_TIMEOUT,
    LEGACY_PYTHON,
    ContainerGrader,
    DockerRunner,
    GraderError,
    grader_tag,
)
from .grading_inputs import grading_inputs
from .records import DIMENSIONS, KarnRunRecord, read_record, validate_scores
from .workspace_archive import ArchiveRefused, graded_path, materialize

SUMMARY = "summary.json"
CANDIDATE_HASH = re.compile(r"[0-9a-f]{64}")
OUTPUT_LIMIT = 16 * 1024 * 1024
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
#: Every key of a successful per-run output; a reused output carries exactly these.
OUTPUT_KEYS = frozenset(
    {
        "run_id",
        "candidate_hash",
        "candidate_name",
        "benchmark",
        "grading_inputs_digest",
        "grading_code_digest",
        "benchmark_configuration_changed",
        "source",
        "grading_isolation",
        "scores",
        "graded_at",
    }
)
#: Present only when this host's grader stood in for an absent recorded image.
OPTIONAL_OUTPUT_KEYS = frozenset({"grader_substituted_for"})
WORKSPACE_SOURCES = frozenset({"run_artifacts", "results_repo"})
STOP_SECONDS = 30
PACKAGE = Path(__file__).resolve().parents[1]


class Skip(Exception):
    """A run that cannot be re-graded here; the batch continues without it."""


class LiveContainers:
    """The Docker client, tracking running grader containers so an interrupt can remove them."""

    def __init__(self, docker):
        self.docker = docker
        self.names: set[str] = set()
        self.stopped = False
        self.lock = threading.Lock()

    def run(self, arguments, **options):
        name = arguments[arguments.index("--name") + 1] if "--name" in arguments else None
        with self.lock:
            if self.stopped:
                raise GraderError("regrade_interrupted")
            if name:
                self.names.add(name)
        try:
            return self.docker.run(arguments, **options)
        finally:
            with self.lock:
                self.names.discard(name)
                stopped = self.stopped
            if stopped and name:
                # The daemon may have created the container after the last removal.
                self.docker.remove(name)

    def stop(self, seconds: float = STOP_SECONDS) -> None:
        """Remove every running grader, repeating while a client may still be starting one."""
        with self.lock:
            self.stopped = True
        deadline = time.monotonic() + seconds
        while True:
            with self.lock:
                names = list(self.names)
            if not names or time.monotonic() >= deadline:
                return
            for name in names:
                self.docker.remove(name)
            time.sleep(0.5)

    def __getattr__(self, name):
        return getattr(self.docker, name)


def select_records(
    results_repo: Path, benchmark_id: str, runs=(), candidates=()
) -> tuple[list[KarnRunRecord], list[dict]]:
    """Every record of the benchmark matching the run and candidate prefixes, and the unreadable."""
    selected, skipped = [], []
    for run_dir in iter_run_dirs(results_repo):
        if runs and not any(run_dir.name.startswith(run) for run in runs):
            continue
        if candidates and not any(run_dir.parent.name.startswith(c) for c in candidates):
            continue
        try:
            manifest = json.loads((run_dir / "manifest.json").read_text())
        except (OSError, ValueError):
            skipped.append({"run_id": run_dir.name, "reason": "invalid_record"})
            continue
        if not isinstance(manifest, dict) or manifest.get("benchmark") != benchmark_id:
            continue
        if manifest.get("schema_version") != 2:
            skipped.append({"run_id": run_dir.name, "reason": "not_a_karn_record"})
            continue
        try:
            selected.append(read_record(run_dir))
        except InvalidRunRecordError:
            skipped.append({"run_id": run_dir.name, "reason": "invalid_record"})
    return selected, skipped


def graded_workspace(record: KarnRunRecord, results_dir: Path) -> Path:
    """The workspace the run was graded from, in its run artifacts under ``results_dir``.

    Artifact pointers are not followed: a record may come from another host, and its
    paths must never choose what is mounted into the grader.
    """
    try:
        return graded_path(record, results_dir)
    except ArchiveRefused as refused:
        raise Skip(str(refused)) from None


def archived_workspace(record: KarnRunRecord, results_repo: Path, scratch: Path) -> Path:
    """The run's graded workspace rebuilt from the results repository under ``scratch``."""
    try:
        return materialize(results_repo, record, scratch / record.run_id / "workspace")
    except ArchiveRefused as refused:
        if str(refused) == "workspace_not_archived":
            raise Skip("workspace_unavailable") from None
        raise Skip("workspace_archive_refused:" + str(refused)) from None


def recorded_grader(
    record: KarnRunRecord, docker, timeout: int, *, substitute: bool = False
) -> tuple[ContainerGrader, str | None]:
    """The grader image the run was graded with, and the image substituted for it, if any.

    Grader images are built per host, so another host's recorded image is normally absent.
    With ``substitute`` this host's grader for the recorded Python grades instead, and the
    output names both images.
    """
    isolation = record.run_metadata.get("grading_isolation")
    if not isolation:
        raise Skip("grader_unrecorded")
    image_id = isolation["grader_image_id"]
    python = isolation.get("candidate_python")
    minor = isolation["grader_python"] if python is not None else LEGACY_PYTHON
    used = image_id
    if docker.image_id(image_id) != image_id:
        if not substitute:
            raise Skip("grader_image_unavailable")
        used = docker.image_id(grader_tag(minor))
        if used is None:
            raise Skip("grader_image_unavailable")
    if (python is not None or used != image_id) and docker.image_python(used) != minor:
        raise Skip("grader_python_mismatch")
    grader = ContainerGrader(used, docker=docker, candidate_python=python, timeout=timeout)
    return grader, (used if used != image_id else None)


def _dimensions(scores: dict) -> dict:
    return {
        name: {key: scores[name].get(key) for key in ("tests_passed", "tests_total", "pass_rate")}
        for name in DIMENSIONS
    }


class UnsafeOutput(KarnError):
    """An output location that could redirect a write, so nothing is written there."""


def _same(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


class OutputDir:
    """``--out``, written only through directory descriptors that never follow a link.

    Checking the resolved ``--out`` against the records and run artifacts is not enough: a
    candidate directory inside it could be a link into either. Every read, temporary file
    and replacement below goes through descriptors opened with ``O_NOFOLLOW``, and each
    directory is checked again right before a replacement, so a directory swapped for a
    link while a run grades is refused rather than written through.
    """

    def __init__(self, path: Path):
        self.path = path
        try:
            self.root = os.open(path, DIRECTORY)
        except OSError as error:
            raise UnsafeOutput(f"regrade_output_unsafe:{error.strerror}") from None
        self.children: dict[str, int] = {}
        self.lock = threading.Lock()

    def close(self) -> None:
        for descriptor in [*self.children.values(), self.root]:
            os.close(descriptor)
        self.children.clear()

    def _check_root(self) -> None:
        try:
            current = os.stat(self.path, follow_symlinks=False)
        except OSError:
            raise UnsafeOutput("regrade_output_unsafe:out_replaced") from None
        if not _same(current, os.fstat(self.root)):
            raise UnsafeOutput("regrade_output_unsafe:out_replaced")

    def directory(self, name: str | None) -> int:
        """The descriptor of ``--out`` itself, or of its candidate directory ``name``."""
        if name is None:
            return self.root
        if not CANDIDATE_HASH.fullmatch(name):
            raise UnsafeOutput("regrade_output_unsafe:candidate_hash")
        with self.lock:
            if name in self.children:
                return self.children[name]
            try:
                os.mkdir(name, 0o755, dir_fd=self.root)
            except FileExistsError:
                pass
            try:
                descriptor = os.open(name, DIRECTORY, dir_fd=self.root)
            except OSError:
                raise UnsafeOutput("regrade_output_unsafe:candidate_directory") from None
            self.children[name] = descriptor
            return descriptor

    def _check(self, name: str | None, descriptor: int) -> None:
        self._check_root()
        if name is None:
            return
        try:
            current = os.stat(name, dir_fd=self.root, follow_symlinks=False)
        except OSError:
            raise UnsafeOutput("regrade_output_unsafe:candidate_replaced") from None
        if not stat.S_ISDIR(current.st_mode) or not _same(current, os.fstat(descriptor)):
            raise UnsafeOutput("regrade_output_unsafe:candidate_replaced")

    def read(self, name: str | None, filename: str) -> dict | list | None:
        """A regular file's JSON, or None when it is absent, not a regular file, or invalid."""
        directory = self.directory(name)
        try:
            descriptor = os.open(
                filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory
            )
        except OSError:
            return None
        with os.fdopen(descriptor, "rb") as handle:
            status = os.fstat(handle.fileno())
            if not stat.S_ISREG(status.st_mode) or status.st_size > OUTPUT_LIMIT:
                return None
            try:
                return json.loads(handle.read(OUTPUT_LIMIT + 1))
            except ValueError:
                return None

    def write(self, name: str | None, filename: str, value: dict) -> None:
        """Replace ``filename`` atomically, never through a link and never outside ``--out``."""
        directory = self.directory(name)
        self._check(name, directory)
        data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        temporary = f".regrade-{secrets.token_hex(8)}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        descriptor = os.open(temporary, flags, 0o644, dir_fd=directory)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self._check(name, directory)
            os.replace(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory)
        except BaseException:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
            raise


def grading_code_digest() -> str:
    """Fingerprint of the package that grades; the grading-inputs digest does not cover it."""
    hashed = hashlib.sha256()
    for path in sorted(PACKAGE.rglob("*.py")):
        hashed.update(str(path.relative_to(PACKAGE)).encode() + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + hashed.hexdigest()


def _source(record: KarnRunRecord) -> dict:
    """What the record itself says, kept beside the new scores so the two are never mixed."""
    metadata = record.run_metadata
    return {
        "grading_inputs_digest": (metadata.get("grading_inputs") or {}).get("digest"),
        "workspace_digest": metadata["benchmark_input"].get("workspace_digest"),
        "execution_status": metadata["execution"]["status"],
        "scores": _dimensions(record.scores),
    }


def _identity(record: KarnRunRecord, benchmark: Benchmark, digests: dict) -> dict:
    metadata = record.run_metadata
    return {
        "run_id": record.run_id,
        "candidate_hash": record.candidate.hash,
        "candidate_name": metadata["candidate_definition"].get("name"),
        "benchmark": benchmark.id,
        **digests,
        "benchmark_configuration_changed": metadata["benchmark_input"].get("configuration_digest")
        != benchmark.identity["configuration_digest"],
        "source": _source(record),
    }


def _reusable(previous, identity: dict) -> dict | None:
    """A previous successful output of this run on the same inputs and code, fully checked.

    Anything else is a miss that re-grades only this run: an output is reused only when its
    identity and source projection equal what the current record and inputs produce, its
    scores satisfy the record score invariants, and it carries exactly a success's fields.
    """
    if not isinstance(previous, dict) or not OUTPUT_KEYS <= set(previous) <= (
        OUTPUT_KEYS | OPTIONAL_OUTPUT_KEYS
    ):
        return None
    if any(previous[key] != value for key, value in identity.items() if key != "source"):
        return None
    source = previous["source"]
    if (
        not isinstance(source, dict)
        or source.get("workspace") not in WORKSPACE_SOURCES
        or {k: v for k, v in source.items() if k != "workspace"} != identity["source"]
    ):
        return None
    if "grader_substituted_for" in previous and not isinstance(
        previous["grader_substituted_for"], str
    ):
        return None
    isolation = previous["grading_isolation"]
    if (
        not isinstance(isolation, dict)
        or not isinstance(isolation.get("grader_image_id"), str)
        or not isinstance(previous["graded_at"], str)
    ):
        return None
    try:
        validate_scores(previous["scores"])
        datetime.fromisoformat(previous["graded_at"])
    except (InvalidRunRecordError, ValueError):
        return None
    return previous


def _regrade_one(
    record: KarnRunRecord,
    benchmark: Benchmark,
    digests: dict,
    *,
    out: OutputDir,
    results_dir: Path,
    results_repo: Path,
    docker: LiveContainers,
    timeout: int,
    force: bool,
    substitute_grader: bool,
) -> dict:
    candidate, filename = record.candidate.hash, f"{record.run_id}.json"
    result = _identity(record, benchmark, digests)
    if not force and (previous := _reusable(out.read(candidate, filename), result)):
        return {**previous, "reused": True}
    try:
        # The archive is rebuilt outside --out, which is written only through descriptors.
        with tempfile.TemporaryDirectory(prefix="sq-regrade-workspace-") as scratch:
            try:
                workspace = graded_workspace(record, results_dir)
                result["source"]["workspace"] = "run_artifacts"
            except Skip as skip:
                if str(skip) != "workspace_unavailable":
                    raise
                workspace = archived_workspace(record, results_repo, Path(scratch))
                result["source"]["workspace"] = "results_repo"
            grader, substituted = recorded_grader(
                record, docker, timeout, substitute=substitute_grader
            )
            result["grading_isolation"] = grader.isolation()
            if substituted is not None:
                result["grader_substituted_for"] = record.run_metadata["grading_isolation"][
                    "grader_image_id"
                ]
            evaluated = grader.evaluate_run(workspace.parent, benchmark, workspace_source=workspace)
            scores = _scores(evaluated, benchmark)
        try:
            validate_scores(scores)
        except InvalidRunRecordError:
            raise GraderError("regrade_scores_invalid") from None
        result["scores"] = scores
    except Skip as skip:
        return {**result, "skipped": str(skip)}
    except GraderError as error:
        result["error"] = error.to_dict()
    except Exception as error:  # noqa: BLE001 -- one run's failure must not abort the batch.
        result["error"] = {"reason": type(error).__name__, "stderr_tail": ""}
    if docker.stopped:
        return {**result, "interrupted": True}
    result["graded_at"] = datetime.now(UTC).isoformat()
    out.write(candidate, filename, result)
    return result


def _means(pairs) -> tuple[float | None, float | None, int]:
    """Mean before and after over the runs observed both times, so both cover the same runs."""
    pairs = [(before, after) for before, after in pairs if None not in (before, after)]
    if not pairs:
        return None, None, 0
    before = statistics.fmean(p[0] for p in pairs)
    return before, statistics.fmean(p[1] for p in pairs), len(pairs)


def summarize(results: list[dict], digests: dict, benchmark_id: str) -> dict:
    """Before/after means per cohort: one candidate graded originally on one inputs digest.

    Original scores from different grading-inputs digests are never averaged together, and
    a run whose original digest is unknown forms a cohort of its own.
    """
    groups: dict[tuple, list[dict]] = {}
    for result in results:
        if "scores" in result:
            original = result["source"]["grading_inputs_digest"]
            key = (result["candidate_hash"], original or "", "" if original else result["run_id"])
            groups.setdefault(key, []).append(result)
    cohorts = []
    for (candidate_hash, original, unknown_run), rows in sorted(groups.items()):
        entry = {
            "candidate_hash": candidate_hash,
            "name": rows[0]["candidate_name"],
            "source_grading_inputs_digest": original or None,
            "runs": len(rows),
        }
        if unknown_run:
            entry["run_id"] = unknown_run
        for name in DIMENSIONS:
            before, after, paired = _means(
                (r["source"]["scores"][name].get("pass_rate"), r["scores"][name].get("pass_rate"))
                for r in rows
            )
            entry[name] = {
                "before_mean_pass_rate": before,
                "after_mean_pass_rate": after,
                "paired_runs": paired,
            }
        cohorts.append(entry)
    return {
        "benchmark": benchmark_id,
        **digests,
        "cohorts": cohorts,
        "skipped": sorted(
            ({"run_id": r["run_id"], "reason": r["skipped"]} for r in results if "skipped" in r),
            key=lambda row: row["run_id"],
        ),
        "errors": sorted(
            ({"run_id": r["run_id"], **r["error"]} for r in results if "error" in r),
            key=lambda row: row["run_id"],
        ),
    }


def regrade(
    *,
    bench_root: Path,
    benchmark_id: str,
    results_repo: Path,
    out: Path,
    results_dir: Path,
    runs=(),
    candidates=(),
    workers: int = 2,
    force: bool = False,
    grading_timeout: int = DEFAULT_GRADING_TIMEOUT,
    substitute_grader: bool = False,
    docker=None,
) -> dict:
    """Re-grade the selected runs into ``out`` and return the summary written beside them."""
    out = Path(out).resolve()
    for name, kept in (("results_repo", results_repo), ("results_dir", results_dir)):
        kept = Path(kept).resolve()
        if out.is_relative_to(kept) or kept.is_relative_to(out):
            raise KarnError(f"regrade_output_overlaps_{name}")
    benchmark = load_benchmark(bench_root, benchmark_id)
    records, unreadable = select_records(
        Path(results_repo).resolve(), benchmark_id, runs, candidates
    )
    for prefixes, key in ((runs, lambda r: r.run_id), (candidates, lambda r: r.candidate.hash)):
        for prefix in prefixes:
            if not any(key(record).startswith(prefix) for record in records):
                raise KarnError("regrade_selection_matched_nothing:" + prefix)
    out.mkdir(parents=True, exist_ok=True)
    output = OutputDir(out)
    try:
        inputs = grading_inputs(benchmark)
        digests = {
            "grading_inputs_digest": inputs["digest"],
            "grading_code_digest": grading_code_digest(),
        }
        results = _grade_all(
            records,
            benchmark,
            digests,
            LiveContainers(docker or DockerRunner()),
            workers,
            out=output,
            results_dir=results_dir,
            results_repo=Path(results_repo).resolve(),
            timeout=grading_timeout,
            force=force,
            substitute_grader=substitute_grader,
        )
        results += [{**row, "skipped": row["reason"]} for row in unreadable]
        summary = summarize(results, digests, benchmark_id)
        if inputs["problems"]:
            summary["grading_inputs_problems"] = inputs["problems"]
        if grading_inputs(benchmark)["digest"] != inputs["digest"]:
            summary["grading_inputs_changed_during_regrade"] = True
        output.write(None, SUMMARY, summary)
        return summary
    finally:
        output.close()


def _grade_all(records, benchmark, digests, live, workers, **options) -> list[dict]:
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        try:
            for record in records:
                future = pool.submit(
                    _regrade_one, record, benchmark, digests, docker=live, **options
                )
                futures[future] = record
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as error:  # noqa: BLE001 -- e.g. the output could not be written.
                    reason = str(error) if isinstance(error, KarnError) else type(error).__name__
                    results.append(
                        {
                            "run_id": futures[future].run_id,
                            "error": {"reason": reason, "stderr_tail": ""},
                        }
                    )
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)
            live.stop()
            raise
    return results
