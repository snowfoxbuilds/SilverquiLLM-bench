"""Local Karn batches, filling available login slots under one queue owner."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import signal
import stat
import tempfile
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


# The queue ledger: every Batch the scheduler has seen in this directory, in queue order. It is
# not a ``*.json`` file in ``state/`` so that no Batch id can collide with it.
LEDGER_FILENAME = "queue.json"


def read_ledger(directory: Path) -> list[dict] | None:
    """The directory's queue ledger entries in queue order, or None when it has none yet."""
    path = Path(directory) / LEDGER_FILENAME
    if path.is_symlink():
        raise KarnError("queue_ledger_symlink")
    if not path.exists():
        return None
    if not path.is_file():
        raise KarnError("queue_ledger_invalid")
    try:
        value = json.loads(path.read_text())
        entries = value["batches"]
        if value.get("schema_version") != 1 or not isinstance(entries, list):
            raise ValueError
        seen = set()
        for entry in entries:
            queued_at = entry.get("queued_at")
            if (
                not isinstance(entry["batch"], str)
                or entry["batch"] in seen
                or type(entry["acknowledged"]) is not bool
                or not (queued_at is None or isinstance(queued_at, str))
            ):
                raise ValueError
            seen.add(entry["batch"])
        return entries
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise KarnError("queue_ledger_invalid") from None


# The dispatch control: whether the scheduler may launch new runs. Written by the operator's
# ``queue pause|drain|resume``; the scheduler only turns a finished drain into a pause.
CONTROL_FILENAME = "control.json"
DISPATCH_MODES = ("running", "paused", "draining")


CONTROL_LIMIT = 4096
"""A control file is a few dozen bytes; anything larger is not one."""


CONTROL_LOCK_FILENAME = ".control.lock"
CONTROL_LOCK_TIMEOUT = 30.0
CLAIM_GLOB = ".karn-control-claim-*.json"
"""A control file moved aside by an earlier scheduler version that then crashed."""


def read_control(directory: Path) -> dict:
    """The directory's dispatch mode: ``running`` without a control file.

    A control file that cannot be read means someone meant to stop dispatch, so it reads as
    ``paused`` with an ``error``; it never reads as ``running``. Neither does a missing file
    while a moved-aside copy waits to be put back. It never raises: this runs in the
    scheduler's loop, where an exception would interrupt every run in flight.
    """
    directory = Path(directory)
    control = _read_control_path(directory / CONTROL_FILENAME)
    if control["mode"] == "running" and _claims(directory):
        return {"mode": "paused", "since": None, "error": "dispatch_control_claim_unresolved"}
    return control


def _claims(directory: Path) -> list[Path]:
    try:
        return sorted(directory.glob(CLAIM_GLOB))
    except Exception:  # noqa: BLE001 - an unlistable directory is reported by the file read
        return []


def _read_control_path(path: Path) -> dict:
    try:
        # O_NONBLOCK: a FIFO put in its place opens at once instead of blocking the loop.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {"mode": "running", "since": None}
    except Exception as error:  # noqa: BLE001 - a symlink (ELOOP), EACCES, anything: paused
        return {
            "mode": "paused",
            "since": None,
            "error": "dispatch_control_unreadable:" + type(error).__name__,
        }
    try:
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > CONTROL_LIMIT:
                raise ValueError
            data = handle.read(CONTROL_LIMIT + 1)
        if len(data) > CONTROL_LIMIT:
            raise ValueError
        value = json.loads(data)
        if (
            value.get("schema_version") != 1
            or value.get("mode") not in ("paused", "draining")
            or not isinstance(value.get("since"), str)
        ):
            raise ValueError
        return {"mode": value["mode"], "since": value["since"]}
    except Exception:  # noqa: BLE001 - never interrupt the scheduler over this file
        return {"mode": "paused", "since": None, "error": "dispatch_control_invalid"}


def _control_not_a_file(path: Path) -> KarnError:
    return KarnError(f"dispatch_control_not_a_file: remove the directory {path} by hand")


@contextlib.contextmanager
def control_lock(directory: Path, timeout: float = CONTROL_LOCK_TIMEOUT):
    """Serialize every change of the dispatch mode: the ``queue`` commands and a finished drain.

    Separate from the scheduler's lifetime lock, and held only for one read-and-replace, so
    an operator command never waits on a serving scheduler.
    """
    import fcntl

    path = Path(directory) / CONTROL_LOCK_FILENAME
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o644)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise KarnError("dispatch_control_busy") from None
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


def write_control(directory: Path, mode: str, *, only_if: str | None = None) -> dict:
    """Set the dispatch mode; ``running`` removes the control file.

    Under the control lock, the current mode is read and the whole file replaced in one
    rename, never removed first: a failure leaves the previous file, so a stop request is
    never lost. A symlink, FIFO, oversized or garbled file in its place is replaced without
    being read through; only a directory there is refused. With ``only_if``, the file is
    replaced only while it still holds that mode, so an operator's later command wins.
    """
    if mode not in DISPATCH_MODES:
        raise KarnError("dispatch_mode_invalid:" + mode)
    directory = Path(directory)
    path = directory / CONTROL_FILENAME
    if os.path.isdir(path) and not os.path.islink(path):
        raise _control_not_a_file(path)
    if not directory.is_dir():
        raise KarnError("batches_dir_missing")
    with control_lock(directory):
        _reconcile_claims(directory)
        current = read_control(directory)
        if only_if is not None and current["mode"] != only_if:
            return current
        if mode == "running":
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            return read_control(directory)
        # Pausing a drain, or draining again, keeps the time dispatch first stopped.
        since = current["since"] if current["mode"] != "running" and current["since"] else None
        payload = json.dumps(
            {"schema_version": 1, "mode": mode, "since": since or datetime.now(UTC).isoformat()},
            indent=2,
        )
        _write_atomically(path, payload + "\n", prefix=".karn-control-")
        return read_control(directory)


def _reconcile_claims(directory: Path) -> None:
    """Put back a control file an earlier scheduler moved aside, under the control lock.

    A claim is removed only once a control file is in place: either the claim was restored,
    or a file written since supersedes it. If the restore fails the claim stays, and dispatch
    stays closed (``read_control`` reads a lone claim as paused).
    """
    path = Path(directory) / CONTROL_FILENAME
    for claimed in _claims(directory):
        if not os.path.lexists(path):
            with contextlib.suppress(FileExistsError):
                os.link(claimed, path, follow_symlinks=False)
        if os.path.lexists(path):
            claimed.unlink()


def queue_order(names, ledger: list[dict] | None) -> list[str]:
    """Queue order: the ledger's order, then Batches it has not recorded yet in name order."""
    rank = {entry["batch"]: index for index, entry in enumerate(ledger or ())}
    return sorted(names, key=lambda name: (rank.get(name, len(rank)), name))


def stateless_status(batch_id: str, ledger: list[dict] | None) -> str:
    """``pending`` for a Batch the scheduler will acknowledge by itself, else ``missing_state``.

    Only a Batch an existing ledger has never seen is new. Without a ledger nothing tells a
    new Batch from one whose state was lost, so the operator acknowledges it.
    """
    if ledger is not None and all(entry["batch"] != batch_id for entry in ledger):
        return "pending"
    return "missing_state"


def _readable_ledger(directory: Path) -> tuple[list[dict] | None, str | None]:
    """For read-only views: the ledger, or none and the reason it is damaged."""
    try:
        return read_ledger(directory), None
    except KarnError as error:
        return None, str(error)


def queue_rows(directory: Path) -> list[dict]:
    rows = []
    ledger, damaged = _readable_ledger(Path(directory))
    paths = {path.stem: path for path in Path(directory).glob("*.toml")}
    for path in (paths[name] for name in queue_order(paths, ledger)):
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
                stateless_status(path.stem, ledger)
                if state is None
                else "running"
                if any(r["status"] == "running" for r in state["runs"])
                else "pending"
                if started < len(batch["runs"])
                else "done"
            )
            if damaged and status != "done" and status != "running":
                # A damaged ledger stops all dispatch, not only stateless Batches.
                status = "ledger_damaged"
            rows.append(
                {
                    "batch": path.stem,
                    "format": batch["format"],
                    "status": status,
                    "started": started,
                    "total": len(batch["runs"]),
                    "runs": state["runs"] if state else [],
                    **({"error": damaged} if status == "ledger_damaged" else {}),
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
    # Serve's pause between passes, its own so a test can stop it without patching the
    # process-wide time.sleep that a run's worker thread also calls.
    _pause = staticmethod(time.sleep)

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
        # Why the latest pass could dispatch nothing at all, when its queue ledger failed.
        self.dispatch_blocked: str | None = None
        # Replay acknowledgements whose ledger write failed; dispatch stays blocked until saved.
        self.unsaved_acknowledgements: set[str] = set()
        # Set when a pass ends because a drain finished: no run is in flight any more.
        self.drained = False
        self.dispatch_mode = "running"
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

    def _save_ledger(self, entries: list[dict]) -> None:
        _write_atomically(
            self.directory / LEDGER_FILENAME,
            json.dumps({"schema_version": 1, "batches": entries}, indent=2) + "\n",
            prefix=".karn-ledger-",
        )

    def _start_state(self, state_path: Path, batch_id: str) -> dict:
        """Write a Batch's empty state, never replacing a state file that appeared meanwhile."""
        state = {"schema_version": 2, "batch": batch_id, "runs": []}
        state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".karn-state-", suffix=".tmp", dir=state_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(state, sort_keys=True, indent=2) + "\n")
            os.link(tmp, state_path)
        except FileExistsError:
            return read_state(state_path, batch_id)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
        return state

    def _remove_stale_ledger_temps(self) -> None:
        """Temporary ledger files left by a crash; only the lock holder writes them."""
        for path in self.directory.glob(".karn-ledger-*.json"):
            with contextlib.suppress(OSError):
                path.unlink()

    def _sync_ledger(self) -> list[dict]:
        """Record every Batch file the ledger has not seen, and return the ledger.

        Without a ledger, every Batch present is recorded, and one without state stays
        unacknowledged: nothing then tells a new Batch from one whose state was lost. With a
        ledger, a valid Batch it has never seen is new and is acknowledged here. Its empty
        state is written before its entry, so a crash between the two leaves a Batch that
        starts normally, never one that reads as lost.
        """
        state_dir = self.directory / "state"
        self._remove_stale_ledger_temps()
        self._restore_control_claims()
        entries = read_ledger(self.directory)
        changed = entries is None
        if entries is None:
            names = {path.stem for path in self.directory.glob("*.toml")}
            names |= {path.stem for path in state_dir.glob("*.json")}
            entries = [
                {
                    "batch": name,
                    "queued_at": None,
                    "acknowledged": (state_dir / (name + ".json")).exists(),
                }
                for name in sorted(names)
            ]
        known = {entry["batch"] for entry in entries}
        for path in sorted(self.directory.glob("*.toml")):
            if path.stem in known:
                continue
            state_path = state_dir / (path.stem + ".json")
            try:
                if load_batch(path) is None:
                    # Left unrecorded, so correcting it to a Karn Batch admits it then.
                    self._warn("unsupported_legacy_batch:" + path.name)
                    continue
                if read_state(state_path, path.stem) is None:
                    self._start_state(state_path, path.stem)
            except KarnError as error:
                # Not yet a valid Batch, perhaps still being written: it stays unrecorded.
                self._warn(str(error))
                continue
            entries.append(
                {
                    "batch": path.stem,
                    "queued_at": datetime.now(UTC).isoformat(),
                    "acknowledged": True,
                }
            )
            known.add(path.stem)
            changed = True
        if changed:
            self._save_ledger(entries)
        return entries

    def _dispatch_open(self) -> bool:
        """Whether new runs may launch; each change of dispatch mode is logged once."""
        control = read_control(self.directory)
        mode = control["mode"] + (f" ({control['error']})" if control.get("error") else "")
        if mode != self.dispatch_mode:
            self.dispatch_mode = mode
            if control["mode"] != "running" or control.get("error"):
                logging.getLogger(__name__).warning(
                    "dispatch %s: no new run is launched until `queue resume`", mode
                )
            else:
                logging.getLogger(__name__).info("dispatch running")
        return control["mode"] == "running"

    def _finish_drain(self) -> None:
        """A drain whose in-flight runs have all finished stays paused across restarts.

        Only a control file still saying ``draining`` becomes ``paused``: a ``queue resume``
        or another ``queue`` command given meanwhile wins. Nothing is in flight, so a control
        file that cannot be written is only reported.
        """
        log = logging.getLogger(__name__)
        try:
            control = write_control(self.directory, "paused", only_if="draining")
        except (KarnError, OSError) as error:
            log.warning(
                "drain finished: no run is in flight, but %s could not be set to paused (%s);"
                " dispatch stays %s",
                CONTROL_FILENAME,
                error,
                read_control(self.directory)["mode"],
            )
            return
        log.warning(
            "drain finished: no run is in flight; dispatch is %s%s",
            control["mode"],
            " until `queue resume`" if control["mode"] != "running" else "",
        )

    def _restore_control_claims(self) -> None:
        """Put back a control file moved aside by a crash, without ever losing the only copy."""
        if not _claims(self.directory):
            return
        try:
            with control_lock(self.directory):
                _reconcile_claims(self.directory)
        except (KarnError, OSError) as error:
            logging.getLogger(__name__).warning(
                "dispatch stays paused: a moved-aside %s could not be put back (%s)",
                CONTROL_FILENAME,
                error,
            )

    def run_until_idle(self) -> int:
        """One pass; when nothing ran only because no login could serve it, that is an error."""
        self._require_package()
        with SchedulerLock(self.directory):
            count = self._run_locked()
            if self.drained:
                self._finish_drain()
        if self.dispatch_blocked:
            # Idle because the ledger stopped every dispatch is not idle: --once must fail.
            raise KarnError(self.dispatch_blocked)
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
        # --replay-without-state acknowledges one start from entry zero: never a later loss.
        self.replay -= set(states)
        self.unavailable_logins = {}
        self.dispatch_blocked = None
        self.drained = False
        active = {}
        deferred = {}
        count = 0
        interrupted = None
        draining = False
        ledger: list[dict] = []

        def queued_before(name, other):
            order = queue_order((name, other), ledger)
            return name != other and order[0] == name

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
                            queued_before(name, job["name"]) and pool == plugin
                            for name, pool in deferred.items()
                        )
                        if value is None:
                            admitted = admitted and not unpooled_live()
                        if admitted and interrupted is None and not self._dispatch_open():
                            # A paused entry stays pending: it retries once dispatch reopens.
                            job["held"] = True
                            admitted = False
                        acknowledge(worker, admitted and interrupted is None)
                    elif kind == "launch":
                        admitted = interrupted is None and self._dispatch_open()
                        if admitted:
                            launch(job)
                        elif interrupted is None:
                            job["held"] = True
                        acknowledge(worker, admitted)
                        job["probing"] = False
                    elif kind in ("busy", "unavailable"):
                        # A refusal for a closed dispatch is no pool's fault: retry on the timer.
                        deferred[job["name"]] = (
                            None if job.get("held") else value.rsplit(":", 1)[-1]
                        )
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

        def block(reason):
            """Stop admitting runs; live workers finish, and the next pass retries."""
            if self.dispatch_blocked != reason:
                # Logged every pass it persists, unlike other warnings: dispatch is stopped.
                self.dispatch_blocked = reason
                logging.getLogger(__name__).warning(
                    "%s: nothing is dispatched until %s is repaired, or removed (then every"
                    " Batch without state needs --replay-without-state); an unwritable batch"
                    " directory or state/ must be made writable",
                    reason,
                    LEDGER_FILENAME,
                )
            return False

        def save_acknowledgements():
            """Persist --replay-without-state starts; False (and blocked) if the write fails."""
            if not self.unsaved_acknowledgements:
                return True
            for entry in ledger:
                if entry["batch"] in self.unsaved_acknowledgements:
                    entry["acknowledged"] = True
            try:
                self._save_ledger(ledger)
            except OSError as error:
                return block("queue_ledger_unwritable:" + type(error).__name__)
            self.unsaved_acknowledgements.clear()
            return True

        def dispatch():
            nonlocal ledger
            # The ledger is synced even while paused, so a damaged one is never hidden.
            try:
                ledger = self._sync_ledger()
            except (KarnError, OSError) as error:
                return block(
                    str(error)
                    if isinstance(error, KarnError)
                    else "queue_ledger_unwritable:" + type(error).__name__
                )
            if not save_acknowledgements():
                return False
            self.dispatch_blocked = None
            if not self._dispatch_open():
                return False
            recorded = {entry["batch"] for entry in ledger} | set(states)
            # A file that appeared since the sync is recorded by the next one.
            names = {path.stem for path in self.directory.glob("*.toml")} & recorded | set(states)
            for name in queue_order(names, ledger):
                path = self.directory / (name + ".toml")
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
                                self._warn(
                                    f"{name}: state/{name}.json is missing; restore it, or pass"
                                    f" --replay-without-state {name} to start from entry zero"
                                )
                                continue
                            try:
                                state = self._start_state(state_path, path.stem)
                            except OSError as error:
                                return block("queue_state_unwritable:" + type(error).__name__)
                            self.unsaved_acknowledgements.add(name)
                            if not save_acknowledgements():
                                return False
                        # Usable state, written or restored: the acknowledgement is spent.
                        self.replay.discard(name)
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
                    self.drained = read_control(self.directory)["mode"] == "draining"
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
                if self.drained:
                    self._finish_drain()
                    return
                self._pause(poll_seconds)
