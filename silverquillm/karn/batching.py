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
from .execution import NATIVE_TELEMETRY, run_benchmark
from .grader import DEFAULT_GRADER_IMAGE, DEFAULT_GRADING_TIMEOUT
from .login import LoginInUseError
from .records import RecordWritePendingError

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
    allowed = {
        "build_output",
        "construct",
        "benchmark",
        "login",
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
            or ("login" in spec and not isinstance(spec["login"], str))
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


def _flag_unsettled_login(row: dict, record) -> None:
    """A harvest the host could not finish is settled by a later pass or the login's next run."""
    errors = record.run_metadata["execution"].get("observation_errors", [])
    unsettled = sorted({"login_harvest_failed", "login_harvest_pending"}.intersection(errors))
    if unsettled:
        row["login_settlement_pending"] = ",".join(unsettled)


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
        grader_image: str = DEFAULT_GRADER_IMAGE,
        grading_timeout: int = DEFAULT_GRADING_TIMEOUT,
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
            "grader_image": grader_image,
            "grading_timeout": grading_timeout,
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

    def _warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)
            logging.getLogger(__name__).warning("%s", message)

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

        for state_path in sorted((self.directory / "state").glob("*.json")):
            try:
                header = json.loads(state_path.read_text())
            except (OSError, ValueError):
                raise KarnError("queue_state_unreadable:" + state_path.name) from None
            if not isinstance(header, dict) or header.get("schema_version") != 2:
                self._warn("unsupported_legacy_state:" + state_path.name)
                continue
            state = read_state(state_path, state_path.stem)
            if self.recoverer is None:
                from .recovery import recover_benchmark

                self.recoverer = recover_benchmark
            for row in state["runs"]:
                if row.get("record_write_pending") or row.get("login_settlement_pending"):
                    self._retry_pending(state_path, state, row)
            if not state["runs"] or state["runs"][-1]["status"] != "running":
                continue
            row = state["runs"][-1]
            try:
                record = self.recoverer(run_id=row["run_id"], spec=row["spec"], **self.options)
            except RunNeverLaunchedError as error:
                row.update(
                    status="failed",
                    error=str(error),
                    recovered_at=datetime.now(UTC).isoformat(),
                )
                self._save(state_path, state)
                continue
            except LoginInUseError:
                self._warn(f"{state_path.stem}: login_in_use; recovery deferred")
                continue
            except RecordWritePendingError as error:
                # The recovered record is retained; later passes publish that same record.
                _recovered(row, error.record)
                row["record_write_pending"] = True
            except LoginSettlementPendingError as error:
                _recovered(row, error.record)
                row["login_settlement_pending"] = str(error)
            except Exception as error:  # noqa: BLE001 -- one unrecoverable row must not stop every scheduler start.
                row.update(
                    status="failed",
                    error="recovery_failed:" + _failure_reason(error),
                    recovered_at=datetime.now(UTC).isoformat(),
                )
            else:
                _recovered(row, record)
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
            if state is not None and state["runs"] and state["runs"][-1]["status"] == "running":
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
                        native_telemetry=spec.get("native_telemetry", "auto"),
                        run_id=row["run_id"],
                        **self.options,
                    )
                    status = record.run_metadata["execution"]["status"]
                    row.update(
                        status="done" if status == "completed" else "failed",
                        execution_status=status,
                        candidate=record.candidate.to_dict(),
                    )
                    _flag_unsettled_login(row, record)
                except LoginInUseError:
                    # Nothing was created; the entry stays pending for the next pass.
                    state["runs"].pop()
                    self._save(state_path, state)
                    self._warn(f"{path.stem}: login_in_use; run deferred")
                    break
                except RecordWritePendingError as error:
                    status = error.record.run_metadata["execution"]["status"]
                    row.update(
                        status="done" if status == "completed" else "failed",
                        execution_status=status,
                        candidate=error.record.candidate.to_dict(),
                        record_write_pending=True,
                        error=str(error),
                    )
                    _flag_unsettled_login(row, error.record)
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
