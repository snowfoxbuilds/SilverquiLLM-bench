"""Local serial Karn batches, using the shared queue lock and atomic writer."""

from __future__ import annotations

import json
import logging
import re
import time
import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from silverquillm.queue_state import SchedulerLock, _write_atomically

from .definition import KarnError
from .execution import run_benchmark

FORMAT = "karn-v4"


def load_batch(path: Path) -> dict | None:
    try:
        value = tomllib.loads(path.read_text())
    except (OSError, ValueError):
        raise KarnError("batch_unreadable:" + path.name) from None
    if value.get("format") != FORMAT:
        return None
    if set(value) - {"format", "not_before", "runs"} or not isinstance(value.get("runs"), list):
        raise KarnError("invalid_karn_batch:" + path.name)
    allowed = {"build_output", "construct", "benchmark", "login", "budget_seconds"}
    for spec in value["runs"]:
        if (
            not isinstance(spec, dict)
            or set(spec) - allowed
            or any(
                not isinstance(spec.get(key), str) or not spec[key]
                for key in ("build_output", "construct", "benchmark")
            )
            or type(spec.get("budget_seconds", 86400)) is not int
            or spec.get("budget_seconds", 86400) < 1
            or ("login" in spec and not isinstance(spec["login"], str))
        ):
            raise KarnError("invalid_karn_run_spec:" + path.name)
    due = value.get("not_before")
    if due is not None and (not isinstance(due, datetime) or due.tzinfo is None):
        raise KarnError("batch_not_before_requires_timezone")
    return value


def read_state(path: Path, batch_id: str) -> dict | None:
    if not path.exists():
        return None
    if path.is_symlink():
        raise KarnError("batch_state_symlink")
    try:
        value = json.loads(path.read_text())
        if (
            value.get("schema_version") != 2
            or value.get("batch") != batch_id
            or not isinstance(value["runs"], list)
        ):
            raise ValueError
        for index, row in enumerate(value["runs"]):
            if row["index"] != index or row["status"] not in ("running", "done", "failed"):
                raise ValueError
            if row["status"] == "running" and index != len(value["runs"]) - 1:
                raise ValueError
            if not isinstance(row["run_id"], str) or not isinstance(row["spec"], dict):
                raise TypeError
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", row["run_id"]):
                raise ValueError
        return value
    except (OSError, ValueError, KeyError, TypeError):
        raise KarnError("batch_state_invalid:" + batch_id) from None


def queue_rows(directory: Path) -> list[dict]:
    rows = []
    for path in sorted(Path(directory).glob("*.toml")):
        try:
            batch = load_batch(path)
            if batch is None:
                rows.append(
                    {"batch": path.stem, "format": "legacy", "status": "unsupported_legacy_batch"}
                )
                continue
            state = read_state(Path(directory) / "state" / (path.stem + ".json"), path.stem)
            started = len(state["runs"]) if state else 0
            status = (
                "missing_state"
                if state is None
                else "running"
                if any(r["status"] == "running" for r in state["runs"])
                else "pending"
                if started < len(batch["runs"])
                else "done"
            )
            rows.append(
                {
                    "batch": path.stem,
                    "format": FORMAT,
                    "status": status,
                    "started": started,
                    "total": len(batch["runs"]),
                    "runs": state["runs"] if state else [],
                }
            )
        except KarnError as error:
            rows.append(
                {"batch": path.stem, "format": FORMAT, "status": "error", "error": str(error)}
            )
    return rows


class KarnScheduler:
    def __init__(
        self,
        batches_dir: Path,
        *,
        bench_root: Path,
        results_dir: Path,
        results_repo: Path,
        state_root: Path,
        replay_without_state=(),
        collector_host: str | None = None,
        executor=run_benchmark,
        recoverer=None,
    ):
        self.directory = Path(batches_dir).resolve()
        self.options = {
            "bench_root": Path(bench_root).resolve(),
            "results_dir": Path(results_dir).resolve(),
            "results_repo": Path(results_repo).resolve(),
            "state_root": Path(state_root).resolve(),
            "collector_host": collector_host,
        }
        self.replay = set(replay_without_state)
        self.executor, self.recoverer = executor, recoverer
        self.warnings = []

    def _warn(self, message: str) -> None:
        """Log each distinct problem once per scheduler; the file itself is never rewritten."""
        if message not in self.warnings:
            self.warnings.append(message)
            logging.getLogger(__name__).warning("%s", message)

    def _save(self, path, state):
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_atomically(
            path, json.dumps(state, sort_keys=True, indent=2) + "\n", prefix=".karn-state-"
        )

    def run_until_idle(self) -> int:
        with SchedulerLock(self.directory):
            return self._run_locked()

    def _recover_running_states(self):
        for state_path in sorted((self.directory / "state").glob("*.json")):
            try:
                header = json.loads(state_path.read_text())
            except (OSError, ValueError):
                raise KarnError("queue_state_unreadable:" + state_path.name) from None
            if not isinstance(header, dict) or header.get("schema_version") != 2:
                self._warn("unsupported_legacy_state:" + state_path.name)
                continue
            state = read_state(state_path, state_path.stem)
            if not state["runs"] or state["runs"][-1]["status"] != "running":
                continue
            row = state["runs"][-1]
            if self.recoverer is None:
                from .recovery import recover_benchmark

                self.recoverer = recover_benchmark
            record = self.recoverer(run_id=row["run_id"], spec=row["spec"], **self.options)
            status = record.run_metadata["execution"]["status"]
            if record.run_id != row["run_id"]:
                row["recovery_record"] = record.run_id
            row["execution_run_id"] = record.run_metadata.get("execution_run_id", row["run_id"])
            row["recovery_of"] = record.run_metadata.get("recovery_of")
            row.update(
                status="done" if status == "completed" else "failed",
                execution_status=status,
                candidate=record.candidate.to_dict(),
                recovered_at=datetime.now(UTC).isoformat(),
            )
            if status != "completed":
                row["error"] = "prior_runner_interrupted"
            self._save(state_path, state)

    def _run_locked(self) -> int:
        self._recover_running_states()
        count = 0
        for path in sorted(self.directory.glob("*.toml")):
            try:
                batch = load_batch(path)
                if batch is None:
                    self._warn("unsupported_legacy_batch:" + path.name)
                    continue
                state_path = self.directory / "state" / (path.stem + ".json")
                state = read_state(state_path, path.stem)
            except KarnError as error:
                self._warn(str(error))
                continue
            if state is None:
                if path.stem not in self.replay:
                    continue
                state = {"schema_version": 2, "batch": path.stem, "runs": []}
                self._save(state_path, state)
            while True:
                try:
                    batch = load_batch(path)
                except KarnError as error:
                    self._warn(str(error))
                    break
                if batch is None or len(state["runs"]) >= len(batch["runs"]):
                    break
                if batch.get("not_before") and batch["not_before"] > datetime.now(UTC):
                    break
                spec = dict(batch["runs"][len(state["runs"])])
                row = {
                    "index": len(state["runs"]),
                    "run_id": uuid.uuid4().hex,
                    "spec": spec,
                    "status": "running",
                    "started_at": datetime.now(UTC).isoformat(),
                }
                state["runs"].append(row)
                self._save(state_path, state)
                build = Path(spec["build_output"])
                if not build.is_absolute():
                    build = self.options["bench_root"] / build
                try:
                    record = self.executor(
                        build_output=build,
                        construct=spec["construct"],
                        benchmark_id=spec["benchmark"],
                        login=spec.get("login"),
                        budget_seconds=spec.get("budget_seconds", 86400),
                        run_id=row["run_id"],
                        **self.options,
                    )
                    status = record.run_metadata["execution"]["status"]
                    row.update(
                        status="done" if status == "completed" else "failed",
                        execution_status=status,
                        candidate=record.candidate.to_dict(),
                    )
                except Exception as error:  # noqa: BLE001 -- one failed run does not discard the rest of a batch.
                    row.update(
                        status="failed",
                        error=str(error) if isinstance(error, KarnError) else type(error).__name__,
                    )
                row["finished_at"] = datetime.now(UTC).isoformat()
                self._save(state_path, state)
                count += 1
                if row.get("execution_status") == "interrupted":
                    raise KeyboardInterrupt
        return count

    def serve(self, poll_seconds: float = 30):
        with SchedulerLock(self.directory):
            while True:
                self._run_locked()
                time.sleep(poll_seconds)
