"""Pause, drain and resume: dispatch stops without interrupting a run in flight."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import ClassVar

import pytest
from click.testing import CliRunner

from silverquillm.karn.batching import (
    CONTROL_FILENAME,
    LEDGER_FILENAME,
    KarnScheduler,
    queue_rows,
    read_control,
    write_control,
)
from silverquillm.karn.definition import KarnError
from silverquillm.monitor.queue import dispatch_mode

from .scheduler_fixtures import ThreadWorker
from .test_batch_queue_order import completed, make_scheduler, write_batch, write_ledger


def started(directory, name):
    state = json.loads((directory / "state" / (name + ".json")).read_text())
    return [row["spec"]["construct"] for row in state["runs"]]


def test_a_paused_queue_launches_nothing_until_resumed(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1", "b2"])
    write_control(directory, "paused")
    executed = []
    assert make_scheduler(tmp_path, directory, executed, replay=["b"]).run_until_idle() == 0
    assert executed == []
    assert read_control(directory)["mode"] == "paused"
    write_control(directory, "running")
    assert not (directory / CONTROL_FILENAME).exists()
    assert make_scheduler(tmp_path, directory, executed, replay=["b"]).run_until_idle() == 2
    assert executed == ["b1", "b2"]


def test_pausing_lets_the_run_in_flight_finish_and_launches_no_more(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1", "b2", "b3"])
    executed = []

    def pause(construct):
        if construct == "b1":
            write_control(directory, "paused")

    scheduler = make_scheduler(tmp_path, directory, executed, replay=["b"], during=pause)
    assert scheduler.run_until_idle() == 1
    assert executed == ["b1"] and started(directory, "b") == ["b1"]
    assert not scheduler.drained
    assert read_control(directory)["mode"] == "paused"


def test_a_drain_finishes_the_run_in_flight_then_stays_paused(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1", "b2"])
    executed = []

    def drain(construct):
        if construct == "b1":
            write_control(directory, "draining")

    scheduler = make_scheduler(tmp_path, directory, executed, replay=["b"], during=drain)

    def never(_seconds):
        raise AssertionError("a finished drain must stop serving")

    scheduler._pause = never
    scheduler.serve()
    assert executed == ["b1"] and started(directory, "b") == ["b1"]
    assert read_control(directory)["mode"] == "paused"


def test_a_drain_with_nothing_in_flight_stops_serving_at_once(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1"])
    write_control(directory, "draining")
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["b"])
    scheduler._pause = lambda _seconds: (_ for _ in ()).throw(AssertionError("kept serving"))
    scheduler.serve()
    assert executed == [] and read_control(directory)["mode"] == "paused"


def test_a_launch_refused_by_a_pause_leaves_the_entry_pending(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1"])
    calls = []

    def execute(**kwargs):
        calls.append(kwargs["construct"])
        if len(calls) == 1:
            write_control(directory, "paused")
        kwargs["on_launch"]()
        return completed()

    def scheduler():
        return KarnScheduler(
            directory,
            worker_factory=ThreadWorker,
            bench_root=tmp_path,
            results_dir=tmp_path / "runs",
            results_repo=tmp_path / "records",
            state_root=tmp_path / "state",
            replay_without_state=["b"],
            executor=execute,
            slot_poll_seconds=0.05,
        )

    assert scheduler().run_until_idle() == 0
    assert started(directory, "b") == []
    assert queue_rows(directory)[0]["status"] == "pending"
    write_control(directory, "running")
    assert scheduler().run_until_idle() == 1
    assert calls == ["b1", "b1"] and started(directory, "b") == ["b1"]


def test_an_unreadable_control_file_reads_as_paused(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1"])
    (directory / CONTROL_FILENAME).write_text("not json")
    assert read_control(directory) == {
        "mode": "paused",
        "since": None,
        "error": "dispatch_control_invalid",
    }
    assert dispatch_mode(directory) == "paused"
    executed = []
    assert make_scheduler(tmp_path, directory, executed, replay=["b"]).run_until_idle() == 0
    assert executed == []


def test_pausing_a_drain_keeps_when_dispatch_first_stopped(tmp_path):
    directory = tmp_path / "batches"
    directory.mkdir()
    since = write_control(directory, "draining")["since"]
    assert write_control(directory, "paused") == {"mode": "paused", "since": since}
    assert dispatch_mode(directory) == "paused"
    assert dispatch_mode(None) == "running"


def test_queue_commands_set_and_show_the_dispatch_mode(tmp_path):
    from silverquillm.cli import main as cli

    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1"])
    runner = CliRunner()

    def invoke(*arguments):
        result = runner.invoke(cli, [*arguments, "--batches-dir", str(directory)])
        assert result.exit_code == 0, result.output
        return result.output

    assert invoke("queue", "pause").startswith("dispatch: paused since ")
    assert invoke("queue", "ls").startswith("dispatch: paused since ")
    assert invoke("queue", "drain").startswith("dispatch: draining since ")
    assert invoke("queue", "resume").strip() == "dispatch: running"
    assert not invoke("queue", "ls").startswith("dispatch:")
    assert json.loads(invoke("queue", "ls", "--json"))[0]["batch"] == "b"


needs_permissions = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")


def _control_variants(directory):
    """Everything that may sit where the control file belongs, none of them a valid one."""
    path = directory / CONTROL_FILENAME

    def explicit_running():
        path.write_text(json.dumps({"schema_version": 1, "mode": "running", "since": "x"}))

    def a_directory():
        path.mkdir()

    def a_fifo():
        os.mkfifo(path)

    def a_dangling_link():
        path.symlink_to(directory / "nowhere")

    def a_link_to_a_valid_file():
        (directory / "elsewhere.json").write_text(
            json.dumps({"schema_version": 1, "mode": "draining", "since": "x"})
        )
        path.symlink_to(directory / "elsewhere.json")

    def deeply_nested():
        path.write_text("[" * 100000)

    def not_utf8():
        path.write_bytes(b"\xff\xfe")

    def sparse_and_huge():
        with open(path, "wb") as handle:
            handle.truncate(100 << 30)

    return [
        explicit_running,
        a_directory,
        a_fifo,
        a_dangling_link,
        a_link_to_a_valid_file,
        deeply_nested,
        not_utf8,
        sparse_and_huge,
    ]


def _clear(path):
    if path.is_dir() and not path.is_symlink():
        path.rmdir()
    elif path.exists() or path.is_symlink():
        path.unlink()


def test_no_control_file_problem_raises_and_each_reads_as_paused(tmp_path):
    directory = tmp_path / "batches"
    directory.mkdir()
    for make in _control_variants(directory):
        make()
        control = read_control(directory)
        assert control["mode"] == "paused" and control["error"], make.__name__
        assert dispatch_mode(directory) == "paused", make.__name__
        _clear(directory / CONTROL_FILENAME)


@needs_permissions
def test_an_unreadable_batch_directory_reads_as_paused_not_running(tmp_path):
    directory = tmp_path / "batches"
    directory.mkdir()
    directory.chmod(0o600)  # no search permission: opening the control file fails with EACCES
    try:
        assert read_control(directory)["mode"] == "paused"
        assert read_control(directory)["error"].startswith("dispatch_control_unreadable:")
        assert dispatch_mode(directory) == "paused"
    finally:
        directory.chmod(0o700)


class RecordingWorker(ThreadWorker):
    interrupted: ClassVar[list[str]] = []

    def interrupt(self):
        RecordingWorker.interrupted.append("interrupt")
        super().interrupt()


def test_a_huge_control_file_written_mid_flight_interrupts_nothing(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1"])
    write_batch(directory, "c", ["c1"])
    gates = {"a1": threading.Event(), "c1": threading.Event()}
    launched = []
    RecordingWorker.interrupted = []

    def execute(**kwargs):
        construct = kwargs["construct"]
        kwargs["on_login_selected"](construct + "/s")
        kwargs["on_launch"]()
        launched.append(construct)
        assert gates[construct].wait(10)
        return completed()

    scheduler = KarnScheduler(
        directory,
        worker_factory=RecordingWorker,
        bench_root=tmp_path,
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=tmp_path / "state",
        replay_without_state=["a", "c"],
        executor=execute,
        slot_poll_seconds=0.05,
    )
    scheduler._pause = lambda _seconds: time.sleep(0.01)
    failure = []

    def serve():
        try:
            scheduler.serve(0)
        except BaseException as error:  # noqa: BLE001 - the test reports it
            failure.append(error)

    thread = threading.Thread(target=serve)
    thread.start()
    deadline = time.monotonic() + 10
    while len(launched) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert sorted(launched) == ["a1", "c1"]
    with open(directory / CONTROL_FILENAME, "wb") as handle:
        handle.truncate(100 << 30)
    gates["a1"].set()
    time.sleep(0.3)
    assert RecordingWorker.interrupted == [] and not failure
    write_control(directory, "draining")  # replaces the huge file without reading it
    gates["c1"].set()
    thread.join(10)
    assert not thread.is_alive() and not failure
    assert RecordingWorker.interrupted == []
    assert started(directory, "a") == ["a1"] and started(directory, "c") == ["c1"]
    assert read_control(directory)["mode"] == "paused"


def test_a_paused_queue_still_reports_a_damaged_ledger(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1"])
    write_ledger(directory, ("a", True))
    (directory / LEDGER_FILENAME).write_text("{")
    write_control(directory, "paused")
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed)
    with pytest.raises(KarnError, match="queue_ledger_invalid"):
        scheduler.run_until_idle()
    assert executed == []


def test_finishing_a_drain_replaces_only_a_control_file_still_draining(tmp_path):
    directory = tmp_path / "batches"
    directory.mkdir()
    # Resumed meanwhile: nothing to replace, and dispatch stays running.
    assert write_control(directory, "paused", only_if="draining")["mode"] == "running"
    assert not (directory / CONTROL_FILENAME).exists()
    # Paused again meanwhile: that file is kept as it is.
    write_control(directory, "paused")
    before = (directory / CONTROL_FILENAME).read_bytes()
    write_control(directory, "paused", only_if="draining")
    assert (directory / CONTROL_FILENAME).read_bytes() == before
    # Still draining: it becomes a pause that keeps when dispatch first stopped.
    _clear(directory / CONTROL_FILENAME)
    since = write_control(directory, "draining")["since"]
    assert write_control(directory, "paused", only_if="draining") == {
        "mode": "paused",
        "since": since,
    }
    assert not list(directory.glob(".karn-control-*"))


def test_a_control_file_moved_aside_by_a_crash_is_put_back(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1"])
    write_control(directory, "draining")
    claimed = directory / ".karn-control-claim-0123.json"
    os.rename(directory / CONTROL_FILENAME, claimed)
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["b"])
    scheduler._pause = lambda _seconds: (_ for _ in ()).throw(AssertionError("kept serving"))
    scheduler.serve()
    assert executed == [] and not claimed.exists()
    assert read_control(directory)["mode"] == "paused"


@needs_permissions
def test_a_drain_finishing_in_a_read_only_directory_still_stops_serving(tmp_path, caplog):
    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1"])
    executed = []
    make_scheduler(tmp_path, directory, executed, replay=["b"]).run_until_idle()
    write_batch(directory, "c", ["c1"])
    write_control(directory, "paused")
    make_scheduler(tmp_path, directory, executed).run_until_idle()  # records c, launches none
    write_control(directory, "draining")
    directory.chmod(0o500)
    try:
        scheduler = make_scheduler(tmp_path, directory, executed)
        scheduler._pause = lambda _seconds: (_ for _ in ()).throw(AssertionError("kept serving"))
        scheduler.serve()
    finally:
        directory.chmod(0o700)
    assert executed == ["b1"]
    assert "could not be set to paused" in caplog.text
    assert read_control(directory)["mode"] == "draining"


def test_queue_commands_replace_a_bad_control_file_and_refuse_a_directory(tmp_path):
    from silverquillm.cli import main as cli

    directory = tmp_path / "batches"
    write_batch(directory, "b", ["b1"])
    runner = CliRunner()
    path = directory / CONTROL_FILENAME
    for make in _control_variants(directory):
        if make.__name__ == "a_directory":
            continue
        make()
        result = runner.invoke(cli, ["queue", "pause", "--batches-dir", str(directory)])
        assert result.exit_code == 0, (make.__name__, result.output)
        assert read_control(directory) == {
            "mode": "paused",
            "since": read_control(directory)["since"],
        }
        _clear(path)
        make()
        result = runner.invoke(cli, ["queue", "resume", "--batches-dir", str(directory)])
        assert result.exit_code == 0, (make.__name__, result.output)
        assert read_control(directory)["mode"] == "running" and not path.is_symlink()
        _clear(path)
    path.mkdir()
    result = runner.invoke(cli, ["queue", "pause", "--batches-dir", str(directory)])
    assert result.exit_code != 0 and "remove the directory" in result.output
    result = runner.invoke(cli, ["queue", "ls", "--batches-dir", str(directory)])
    assert result.exit_code == 0 and result.output.startswith("dispatch: paused")
