"""Local Karn batches, filling available login slots under one queue owner."""

from __future__ import annotations

import contextlib
import json
import logging
import re
import signal
import time
import tomllib
import uuid
from datetime import UTC, datetime
from multiprocessing.connection import wait
from pathlib import Path

from silverquillm.queue_state import SchedulerLock, _write_atomically

from . import provenance
from .definition import KarnError
from .execution import NATIVE_TELEMETRY, run_benchmark
from .grader import DEFAULT_GRADING_TIMEOUT
from .login import LoginInUseError
from .login_pool import LoginPool, LoginPoolUnavailableError, logins_root
from .records import RecordWritePendingError
from .scheduler_worker import SpawnWorker, owner_alive

# New batch files declare FORMAT; earlier karn-v4 files keep loading unchanged. The batch
# format is independent of its candidates' Construct Definition versions.
FORMAT = "karn-v5"
FORMATS = ("karn-v4", FORMAT)


def load_batch(path: Path) -> dict | None:
    try:
        value = tomllib.loads(path.read_text())
    except (OSError, ValueError):
        raise KarnError("batch_unreadable:" + path.name) from None
    if value.get("format") not in FORMATS:
        return None
    if set(value) - {"format", "not_before", "runs"} or not isinstance(value.get("runs"), list):
        raise KarnError("invalid_karn_batch:" + path.name)
    allowed = {
        "build_output",
        "construct",
        "benchmark",
        "budget_seconds",
        "native_telemetry",
    }
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
            or spec.get("native_telemetry", "auto") not in NATIVE_TELEMETRY
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
        batch = None
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
                    "format": batch["format"],
                    "status": status,
                    "started": started,
                    "total": len(batch["runs"]),
                    "runs": state["runs"] if state else [],
                }
            )
        except KarnError as error:
            rows.append(
                {
                    "batch": path.stem,
                    "format": batch["format"] if batch else FORMAT,
                    "status": "error",
                    "error": str(error),
                }
            )
    return rows


def _failure_reason(error: Exception) -> str:
    """A KarnError's code, else only the exception type: messages can carry paths or secrets."""
    return str(error) if isinstance(error, KarnError) else type(error).__name__


def _recovered(row: dict, record) -> None:
    """Close a running row from its recovery record, keeping the link to the original execution."""
    status = record.run_metadata["execution"]["status"]
    if record.run_id != row["run_id"]:
        row["recovery_record"] = record.run_id
    row["execution_run_id"] = record.run_metadata.get("execution_run_id", row["run_id"])
    row["recovery_of"] = record.run_metadata.get("recovery_of")
    row.update(
        status="done" if status == "completed" else "failed",
        execution_status=status,
        candidate=record.candidate.to_dict(),
    )
    row.setdefault("recovered_at", datetime.now(UTC).isoformat())
    if status != "completed":
        row["error"] = "prior_runner_interrupted"


def _link_recovery(row: dict, record) -> None:
    """Record a linked recovery of the row's own observation; the original row stays as it was."""
    if record is not None and record.run_id != row["run_id"]:
        _recovered(row, record)


def _published(row: dict) -> None:
    row.pop("record_write_pending", None)
    if row.get("error") == "record_write_pending":
        del row["error"]


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
        grader_image: str | None = None,
        grading_timeout: int = DEFAULT_GRADING_TIMEOUT,
        executor=run_benchmark,
        recoverer=None,
        allow_dirty: bool = False,
        worker_factory=SpawnWorker,
        slot_poll_seconds: float = 5.0,
    ):
        self.directory = Path(batches_dir).resolve()
        self.options = {
            "bench_root": Path(bench_root).resolve(),
            "results_dir": Path(results_dir).resolve(),
            "results_repo": Path(results_repo).resolve(),
            "state_root": Path(state_root).resolve(),
            "collector_host": collector_host,
            "grader_image": grader_image,
            "grading_timeout": grading_timeout,
        }
        self.allow_dirty = allow_dirty
        self.replay = set(replay_without_state)
        self.executor, self.recoverer = executor, recoverer
        self.worker_factory = worker_factory
        self.slot_poll_seconds = slot_poll_seconds
        self.warnings = []
        # Login pools that could serve no entry during the latest pass, by batch.
        self.unavailable_logins: dict[str, str] = {}

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
        """One pass; when nothing ran only because no login could serve it, that is an error."""
        self._require_package()
        with SchedulerLock(self.directory):
            count = self._run_locked()
        if not count and self.unavailable_logins:
            raise LoginPoolUnavailableError(min(self.unavailable_logins.values()))
        return count

    def _retry_pending(self, state_path: Path, state: dict, row: dict) -> None:
        """Publish a retained record or settle the run's login; never execute the task again."""
        from .recovery import LoginSettlementPendingError

        try:
            record = self.recoverer(run_id=row["run_id"], spec=row["spec"], **self.options)
        except RecordWritePendingError as error:
            # An unconfirmed observation may have gained a retained linked recovery meanwhile.
            _link_recovery(row, error.record)
            row["record_write_pending"] = True
            self._save(state_path, state)
            return
        except LoginSettlementPendingError as error:
            _link_recovery(row, error.record)
            _published(row)
            row["login_settlement_pending"] = str(error)
            self._save(state_path, state)
            return
        except Exception as error:  # noqa: BLE001 -- one unrecoverable row must not stop every scheduler start.
            self._warn(f"{state_path.stem}: pending retry failed: {_failure_reason(error)}")
            return
        _link_recovery(row, record)
        _published(row)
        row.pop("login_settlement_pending", None)
        self._save(state_path, state)

    def _recover_running_states(self):
        from .recovery import LoginSettlementPendingError, RunNeverLaunchedError

        states = {}
        for state_path in sorted((self.directory / "state").glob("*.json")):
            try:
                header = json.loads(state_path.read_text())
            except (OSError, ValueError):
                raise KarnError("queue_state_unreadable:" + state_path.name) from None
            if not isinstance(header, dict) or header.get("schema_version") != 2:
                self._warn("unsupported_legacy_state:" + state_path.name)
                continue
            state = read_state(state_path, state_path.stem)
            states[state_path.stem] = state
            if self.recoverer is None:
                from .recovery import recover_benchmark

                self.recoverer = recover_benchmark
            for row in state["runs"]:
                if owner_alive(row.get("worker")):
                    continue
                if row.get("record_write_pending") or row.get("login_settlement_pending"):
                    self._retry_pending(state_path, state, row)
                if row["status"] != "running":
                    continue
                try:
                    record = self.recoverer(run_id=row["run_id"], spec=row["spec"], **self.options)
                except RunNeverLaunchedError as error:
                    row.update(
                        status="failed",
                        error=str(error),
                        recovered_at=datetime.now(UTC).isoformat(),
                    )
                except LoginInUseError:
                    self._warn(f"{state_path.stem}: login_in_use; recovery deferred")
                    continue
                except RecordWritePendingError as error:
                    _recovered(row, error.record)
                    row["record_write_pending"] = True
                except LoginSettlementPendingError as error:
                    _recovered(row, error.record)
                    row["login_settlement_pending"] = str(error)
                except Exception as error:  # noqa: BLE001 -- one row must not stop recovery of the others.
                    if isinstance(error, KarnError) and str(error) == "run_in_progress":
                        self._warn(f"{state_path.stem}: run_in_progress; recovery deferred")
                        continue
                    row.update(
                        status="failed",
                        error="recovery_failed:" + _failure_reason(error),
                        recovered_at=datetime.now(UTC).isoformat(),
                    )
                else:
                    _recovered(row, record)
                self._save(state_path, state)
        return states

    def _require_package(self) -> None:
        """A package from another checkout is a configuration error, not a failed entry: it
        escapes before the queue is locked, recovered or launched, so fixing the environment
        and rerunning resumes the same entries."""
        provenance.require_package_from(self.options["bench_root"])

    def _run_locked(self) -> int:
        self._require_package()
        states = self._recover_running_states()
        self.unavailable_logins = {}
        active = {}
        deferred = {}
        count = 0
        interrupted = None
        draining = False

        def unpooled_live():
            return any(
                row["status"] == "running"
                and "login" in row
                and row["login"] is None
                and (row["run_id"] in active or owner_alive(row.get("worker")))
                for state in states.values()
                for row in state["runs"]
            )

        def retry_claimable(*, retry_dead_workers=False):
            for name, plugin in list(deferred.items()):
                if plugin is None:
                    if retry_dead_workers:
                        del deferred[name]
                    continue
                if (
                    not unpooled_live()
                    if plugin == "unpooled"
                    else LoginPool(
                        logins_root(self.options["state_root"]) / plugin, plugin
                    ).has_claimable_slot()
                ):
                    del deferred[name]

        def save(path, state):
            try:
                self._save(path, state)
            except Exception as error:
                if not draining:
                    raise
                self._warn("queue save failed during shutdown: " + _failure_reason(error))

        def acknowledge(worker, admitted):
            with contextlib.suppress(BrokenPipeError, EOFError, OSError):
                worker.connection.send(admitted)

        def launch(job):
            row, state, state_path = job["row"], job["state"], job["state_path"]
            if not row.get("started_at"):
                row.update(started_at=datetime.now(UTC).isoformat(), worker=job["worker"].owner)
                if "login" in job:
                    row["login"] = job["login"]
                state["runs"].append(row)
                save(state_path, state)

        def events():
            nonlocal count, interrupted
            changed = False
            released = False
            for run_id, job in list(active.items()):
                worker = job["worker"]
                terminal = False
                # Once death is observed, all of this worker's messages are available to drain.
                alive = worker.alive()
                while worker.connection.poll():
                    try:
                        kind, value = worker.connection.recv()
                    except EOFError:
                        break
                    changed = True
                    if kind == "warning":
                        self._warn(f"{job['name']}: {value}")
                    elif kind == "released":
                        released = True
                    elif kind == "selected":
                        job["login"] = value
                        plugin = value.split("/", 1)[0] if value else "unpooled"
                        admitted = not any(
                            name < job["name"] and pool == plugin for name, pool in deferred.items()
                        )
                        if value is None:
                            admitted = admitted and not unpooled_live()
                        acknowledge(worker, admitted and interrupted is None)
                    elif kind == "launch":
                        if interrupted is None:
                            launch(job)
                        acknowledge(worker, interrupted is None)
                        job["probing"] = False
                    elif kind in ("busy", "unavailable"):
                        deferred[job["name"]] = value.rsplit(":", 1)[-1]
                        if kind == "unavailable":
                            self.unavailable_logins[job["name"]] = value
                            self._warn(f"{job['name']}: {value}; entries stay pending")
                        terminal = True
                    elif kind == "interrupt":
                        interrupted = (
                            SystemExit(value) if value is not None else KeyboardInterrupt()
                        )
                        terminal = True
                    elif kind == "result":
                        released = True
                        launch(job)
                        job["row"].update(value, finished_at=datetime.now(UTC).isoformat())
                        save(job["state_path"], job["state"])
                        self.unavailable_logins.pop(job["name"], None)
                        count += 1
                        terminal = True
                        if value.get("execution_status") == "interrupted":
                            interrupted = KeyboardInterrupt()
                if terminal or not alive:
                    changed = True
                    worker.close()
                    del active[run_id]
                    if not terminal:
                        released = True
                        # A dead worker leaves its launched row for ordinary recovery.
                        if job["row"].get("started_at"):
                            self._warn(f"{job['name']}: worker exited; recovery required")
                        else:
                            deferred[job["name"]] = None
            if released:
                retry_claimable()
            return changed

        def dispatch():
            paths = set(self.directory.glob("*.toml")) | {
                self.directory / (name + ".toml") for name in states
            }
            for path in sorted(paths):
                if path.stem in deferred:
                    continue
                try:
                    batch = load_batch(path)
                    if batch is None:
                        self._warn("unsupported_legacy_batch:" + path.name)
                        continue
                    state_path = self.directory / "state" / (path.stem + ".json")
                    if path.stem not in states:
                        state = read_state(state_path, path.stem)
                        if state is None:
                            if path.stem not in self.replay:
                                continue
                            state = {"schema_version": 2, "batch": path.stem, "runs": []}
                            self._save(state_path, state)
                        states[path.stem] = state
                    state = states[path.stem]
                    if len(state["runs"]) >= len(batch["runs"]):
                        continue
                    if batch.get("not_before") and batch["not_before"] > datetime.now(UTC):
                        continue
                    spec = dict(batch["runs"][len(state["runs"])])
                    row = {
                        "index": len(state["runs"]),
                        "run_id": uuid.uuid4().hex,
                        "spec": spec,
                        "status": "running",
                    }
                    build = Path(spec["build_output"])
                    if not build.is_absolute():
                        build = self.options["bench_root"] / build
                    arguments = dict(
                        build_output=build,
                        construct=spec["construct"],
                        benchmark_id=spec["benchmark"],
                        budget_seconds=spec.get("budget_seconds", 86400),
                        native_telemetry=spec.get("native_telemetry", "auto"),
                        run_id=row["run_id"],
                        allow_dirty=self.allow_dirty,
                        **self.options,
                    )
                    blocked = signal.pthread_sigmask(
                        signal.SIG_BLOCK, (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
                    )
                    try:
                        worker = self.worker_factory(self.executor, arguments)
                        active[row["run_id"]] = {
                            "worker": worker,
                            "row": row,
                            "state": state,
                            "state_path": state_path,
                            "name": path.stem,
                            "probing": True,
                        }
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
                    return True
                except KarnError as error:
                    self._warn(str(error))
            return False

        try:
            retry_at = time.monotonic()
            dispatch_needed = True
            while True:
                dispatch_needed = events() or dispatch_needed
                if interrupted is not None:
                    raise interrupted
                if time.monotonic() >= retry_at:
                    retry_claimable(retry_dead_workers=True)
                    dispatch_needed = True
                    retry_at = time.monotonic() + self.slot_poll_seconds
                if dispatch_needed and not any(job["probing"] for job in active.values()):
                    dispatch_needed = False
                    if dispatch():
                        continue
                if not active:
                    break
                wait(
                    [job["worker"].connection for job in active.values()],
                    timeout=max(0, retry_at - time.monotonic()),
                )
        except BaseException:
            draining = True
            previous = {}
            for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                try:
                    previous[number] = signal.signal(number, signal.SIG_IGN)
                except ValueError:
                    pass
            try:
                interrupted = interrupted or KeyboardInterrupt()
                for job in active.values():
                    job["worker"].interrupt()
                while active:
                    events()
                    if active:
                        next(iter(active.values()))["worker"].connection.poll(0.01)
            finally:
                for number, handler in previous.items():
                    signal.signal(number, handler)
            raise
        return count

    def serve(self, poll_seconds: float = 30):
        self._require_package()
        with SchedulerLock(self.directory):
            while True:
                self._run_locked()
                time.sleep(poll_seconds)
