"""Isolated scheduler workers; only the scheduler writes queue state."""

from __future__ import annotations

import contextlib
import multiprocessing
import os
import signal
import socket
from pathlib import Path

from .definition import KarnError
from .interruption import terminate_as_interrupt
from .login_pool import LoginPoolBusyError, LoginPoolUnavailableError
from .records import RecordWritePendingError


def process_identity(pid: int) -> dict:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        birth = fields[19] if fields[0] not in ("Z", "X") else None
    except (OSError, IndexError):
        birth = None
    return {
        "pid": pid,
        "host": socket.gethostname(),
        "birth": birth,
        "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    }


def owner_alive(owner: dict | None) -> bool:
    return bool(
        isinstance(owner, dict)
        and type(owner.get("pid")) is int
        and owner.get("birth")
        and owner.get("host") == socket.gethostname()
        and process_identity(owner["pid"]) == owner
    )


def record_outcome(record, *, pending=False) -> dict:
    execution = record.run_metadata["execution"]
    status = execution["status"]
    result = {
        "status": "done" if status == "completed" else "failed",
        "execution_status": status,
        "candidate": record.candidate.to_dict(),
    }
    unsettled = sorted(
        {"login_harvest_failed", "login_harvest_pending"}.intersection(
            execution.get("observation_errors", [])
        )
    )
    if unsettled:
        result["login_settlement_pending"] = ",".join(unsettled)
    if pending:
        result.update(record_write_pending=True, error="record_write_pending")
    return result


def execute_worker(connection, executor, arguments):
    def send(kind, value=None):
        try:
            connection.send((kind, value))
            return True
        except (BrokenPipeError, EOFError, OSError):
            return False

    def request(kind, value=None):
        if not send(kind, value):
            raise KeyboardInterrupt
        try:
            admitted = connection.recv()
        except EOFError:
            raise KeyboardInterrupt from None
        if not admitted:
            raise LoginPoolBusyError(
                "login_pool_busy:" + (value.split("/", 1)[0] if value else "unpooled")
            )

    try:
        result = executor(
            **arguments,
            login_blocking=False,
            login_wait=lambda message: send("warning", message),
            on_login_selected=lambda login: request("selected", login),
            on_login_released=lambda: send("released"),
            on_launch=lambda: request("launch"),
        )
        send("result", record_outcome(result))
    except (LoginPoolBusyError, LoginPoolUnavailableError) as error:
        send("busy" if isinstance(error, LoginPoolBusyError) else "unavailable", str(error))
    except RecordWritePendingError as error:
        send("result", record_outcome(error.record, pending=True))
    except (KeyboardInterrupt, SystemExit) as error:
        send("interrupt", error.code if isinstance(error, SystemExit) else None)
    except Exception as error:  # noqa: BLE001 -- isolate one entry's failure from the queue.
        send(
            "result",
            {
                "status": "failed",
                "error": str(error) if isinstance(error, KarnError) else type(error).__name__,
            },
        )
    finally:
        connection.close()


def _spawn_main(connection, executor, arguments):
    # Terminal signals go to the scheduler, which interrupts each owned worker once.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    with terminate_as_interrupt():
        signal.pthread_sigmask(signal.SIG_UNBLOCK, (signal.SIGINT, signal.SIGTERM, signal.SIGHUP))
        execute_worker(connection, executor, arguments)


class SpawnWorker:
    def __init__(self, executor, arguments):
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_spawn_main, args=(child, executor, arguments))
        try:
            self.process.start()
        except BaseException:
            self.connection.close()
            self.process.close()
            raise
        finally:
            child.close()
        self.owner = process_identity(self.process.pid)

    def interrupt(self):
        if self.process.is_alive():
            with contextlib.suppress(ProcessLookupError):
                os.kill(self.process.pid, signal.SIGTERM)

    def alive(self):
        return self.process.is_alive()

    def close(self):
        self.process.join()
        self.connection.close()
        self.process.close()
