"""Re-grade retained Karn runs against the checkout's current grading inputs.

Run Records are immutable, so a re-grade never replaces one: each run's new scores go to a
separate output directory, tagged with the grading-inputs digest they were graded against.
Scores from different digests are not comparable without re-grading both.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import statistics
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from silverquillm.results_repo import InvalidRunRecordError, iter_run_dirs

from .benchmark import Benchmark, load_benchmark
from .definition import KarnError
from .execution import _scores
from .grader import DEFAULT_GRADING_TIMEOUT, ContainerGrader, DockerRunner, GraderError
from .grading_inputs import grading_inputs
from .records import DIMENSIONS, KarnRunRecord, read_record

SUMMARY = "summary.json"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
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
    selected = (record.run_metadata.get("grading_source") or {}).get("selected")
    if not isinstance(selected, str) or not selected:
        raise Skip("no_graded_workspace")
    run_id = record.run_metadata.get("execution_run_id", record.run_id)
    relative = PurePosixPath(selected)
    if (
        not isinstance(run_id, str)
        or not RUN_ID.fullmatch(run_id)
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        raise Skip("grading_source_invalid")
    directory = Path(results_dir).resolve() / run_id
    workspace = directory / relative
    if not workspace.is_dir():
        raise Skip("workspace_unavailable")
    if not workspace.resolve().is_relative_to(directory):
        raise Skip("grading_source_invalid")
    return workspace.resolve()


def recorded_grader(record: KarnRunRecord, docker, timeout: int) -> ContainerGrader:
    """The grader image the run was graded with, which must still be present locally."""
    isolation = record.run_metadata.get("grading_isolation")
    if not isolation:
        raise Skip("grader_unrecorded")
    image_id = isolation["grader_image_id"]
    if docker.image_id(image_id) != image_id:
        raise Skip("grader_image_unavailable")
    python = isolation.get("candidate_python")
    if python is not None and docker.image_python(image_id) != isolation["grader_python"]:
        raise Skip("grader_python_mismatch")
    return ContainerGrader(image_id, docker=docker, candidate_python=python, timeout=timeout)


def _dimensions(scores: dict) -> dict:
    return {
        name: {key: scores[name].get(key) for key in ("tests_passed", "tests_total", "pass_rate")}
        for name in DIMENSIONS
    }


def _write(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".regrade-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def grading_code_digest() -> str:
    """Fingerprint of the package that grades; the grading-inputs digest does not cover it."""
    hashed = hashlib.sha256()
    for path in sorted(PACKAGE.rglob("*.py")):
        hashed.update(str(path.relative_to(PACKAGE)).encode() + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + hashed.hexdigest()


def _reusable(path: Path, record: KarnRunRecord, digests: dict) -> dict | None:
    """A previous output of this run graded on the same inputs and code, if well formed."""
    try:
        previous = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if (
        isinstance(previous, dict)
        and previous.get("run_id") == record.run_id
        and previous.get("candidate_hash") == record.candidate.hash
        and all(previous.get(key) == value for key, value in digests.items())
        and isinstance(previous.get("scores"), dict)
        and set(previous["scores"]) == set(DIMENSIONS)
        and isinstance(previous.get("source"), dict)
        and isinstance(previous["source"].get("scores"), dict)
        and set(previous["source"]["scores"]) == set(DIMENSIONS)
    ):
        return previous
    return None


def output_path(out: Path, record: KarnRunRecord) -> Path:
    return out / record.candidate.hash / f"{record.run_id}.json"


def _regrade_one(
    record: KarnRunRecord,
    benchmark: Benchmark,
    digests: dict,
    *,
    out: Path,
    results_dir: Path,
    docker: LiveContainers,
    timeout: int,
    force: bool,
) -> dict:
    path = output_path(out, record)
    if not force and (previous := _reusable(path, record, digests)):
        return {**previous, "reused": True}
    source = record.run_metadata
    result = {
        "run_id": record.run_id,
        "candidate_hash": record.candidate.hash,
        "candidate_name": source["candidate_definition"].get("name"),
        "benchmark": benchmark.id,
        **digests,
        "benchmark_configuration_changed": source["benchmark_input"].get("configuration_digest")
        != benchmark.identity["configuration_digest"],
        "source": {
            "grading_inputs_digest": (source.get("grading_inputs") or {}).get("digest"),
            "workspace_digest": source["benchmark_input"].get("workspace_digest"),
            "execution_status": source["execution"]["status"],
            "scores": _dimensions(record.scores),
        },
    }
    try:
        workspace = graded_workspace(record, results_dir)
        grader = recorded_grader(record, docker, timeout)
        result["grading_isolation"] = grader.isolation()
        evaluated = grader.evaluate_run(workspace.parent, benchmark, workspace_source=workspace)
        result["scores"] = _scores(evaluated, benchmark)
    except Skip as skip:
        return {**result, "skipped": str(skip)}
    except GraderError as error:
        result["error"] = error.to_dict()
    except Exception as error:  # noqa: BLE001 -- one run's failure must not abort the batch.
        result["error"] = {"reason": type(error).__name__, "stderr_tail": ""}
    if docker.stopped:
        return {**result, "interrupted": True}
    result["graded_at"] = datetime.now(UTC).isoformat()
    path.parent.mkdir(exist_ok=True)
    _write(path, result)
    return result


def _means(pairs) -> tuple[float | None, float | None]:
    """Mean before and after over the runs graded both times, so both cover the same runs."""
    pairs = [(before, after) for before, after in pairs if None not in (before, after)]
    if not pairs:
        return None, None
    return statistics.fmean(p[0] for p in pairs), statistics.fmean(p[1] for p in pairs)


def summarize(results: list[dict], digests: dict, benchmark_id: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for result in results:
        if "scores" in result:
            groups.setdefault(result["candidate_hash"], []).append(result)
    candidates = []
    for candidate_hash, rows in sorted(groups.items()):
        entry = {
            "candidate_hash": candidate_hash,
            "name": rows[0]["candidate_name"],
            "runs": len(rows),
        }
        for name in DIMENSIONS:
            before, after = _means(
                (r["source"]["scores"][name].get("pass_rate"), r["scores"][name].get("pass_rate"))
                for r in rows
            )
            entry[name] = {"before_mean_pass_rate": before, "after_mean_pass_rate": after}
        candidates.append(entry)
    return {
        "benchmark": benchmark_id,
        **digests,
        "candidates": candidates,
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
    inputs = grading_inputs(benchmark)
    digests = {
        "grading_inputs_digest": inputs["digest"],
        "grading_code_digest": grading_code_digest(),
    }
    live = LiveContainers(docker or DockerRunner())
    results = [{**row, "skipped": row.pop("reason")} for row in unreadable]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        try:
            for record in records:
                future = pool.submit(
                    _regrade_one,
                    record,
                    benchmark,
                    digests,
                    out=out,
                    results_dir=results_dir,
                    docker=live,
                    timeout=grading_timeout,
                    force=force,
                )
                futures[future] = record
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as error:  # noqa: BLE001 -- e.g. the output could not be written.
                    record = futures[future]
                    results.append(
                        {
                            "run_id": record.run_id,
                            "error": {"reason": type(error).__name__, "stderr_tail": ""},
                        }
                    )
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)
            live.stop()
            raise
    summary = summarize(results, digests, benchmark_id)
    if inputs["problems"]:
        summary["grading_inputs_problems"] = inputs["problems"]
    if grading_inputs(benchmark)["digest"] != inputs["digest"]:
        summary["grading_inputs_changed_during_regrade"] = True
    _write(out / SUMMARY, summary)
    return summary
