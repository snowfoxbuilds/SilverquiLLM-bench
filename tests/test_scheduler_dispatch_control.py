"""Pause, drain and resume: dispatch stops without interrupting a run in flight."""

from __future__ import annotations

import json

from click.testing import CliRunner

from silverquillm.karn.batching import (
    CONTROL_FILENAME,
    KarnScheduler,
    queue_rows,
    read_control,
    write_control,
)
from silverquillm.monitor.queue import dispatch_mode

from .scheduler_fixtures import ThreadWorker
from .test_batch_queue_order import completed, make_scheduler, write_batch


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
