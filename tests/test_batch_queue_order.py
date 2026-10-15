"""A running scheduler admits new Batches, runs them in queue order, and refuses lost state."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from silverquillm.karn.batching import LEDGER_FILENAME, KarnScheduler, queue_rows, read_ledger
from silverquillm.karn.definition import KarnError
from silverquillm.monitor.queue import queued_batches

from .scheduler_fixtures import ThreadWorker


def write_batch(directory, name, constructs):
    directory.mkdir(exist_ok=True)
    (directory / (name + ".toml")).write_text(
        'format = "karn-v5"\n'
        + "".join(
            f'[[runs]]\nbuild_output = "fixture"\nconstruct = "{construct}"\nbenchmark = "example"\n'
            for construct in constructs
        )
    )


def write_ledger(directory, *entries):
    directory.mkdir(exist_ok=True)
    (directory / LEDGER_FILENAME).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batches": [
                    {"batch": name, "queued_at": None, "acknowledged": acknowledged}
                    for name, acknowledged in entries
                ],
            }
        )
    )


def write_state(directory, name, done=0):
    (directory / "state").mkdir(parents=True, exist_ok=True)
    (directory / "state" / (name + ".json")).write_text(
        json.dumps(
            {
                "schema_version": 2,
                "batch": name,
                "runs": [
                    {"index": index, "run_id": f"{name}{index}", "spec": {}, "status": "done"}
                    for index in range(done)
                ],
            }
        )
    )


def completed():
    return SimpleNamespace(
        run_metadata={"execution": {"status": "completed"}},
        candidate=SimpleNamespace(to_dict=dict),
    )


def make_scheduler(tmp_path, directory, executed, *, replay=(), during=None):
    def execute(**kwargs):
        executed.append(kwargs["construct"])
        if during is not None:
            during(kwargs["construct"])
        return completed()

    return KarnScheduler(
        directory,
        worker_factory=ThreadWorker,
        bench_root=tmp_path,
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=tmp_path / "state",
        replay_without_state=replay,
        executor=execute,
    )


def test_a_batch_added_while_a_run_is_in_flight_starts_without_a_restart(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "z-first", ["z1"])
    executed = []

    def add_batch(construct):
        if construct == "z1":
            write_batch(directory, "a-second", ["a1"])

    scheduler = make_scheduler(tmp_path, directory, executed, replay=["z-first"], during=add_batch)
    assert scheduler.run_until_idle() == 2
    assert executed == ["z1", "a1"]
    assert [entry["batch"] for entry in read_ledger(directory)] == ["z-first", "a-second"]
    assert all(entry["acknowledged"] for entry in read_ledger(directory))


def test_a_later_batch_follows_an_earlier_one_whatever_their_names(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "z-first", ["z1", "z2"])
    write_ledger(directory, ("z-first", True))
    write_state(directory, "z-first")
    write_batch(directory, "a-second", ["a1"])
    executed = []
    assert [row["batch"] for row in queue_rows(directory)] == ["z-first", "a-second"]
    assert [batch.batch for batch in queued_batches(directory)] == ["z-first", "a-second"]
    assert make_scheduler(tmp_path, directory, executed).run_until_idle() == 3
    assert executed == ["z1", "z2", "a1"]


def test_queue_order_is_stable_across_scheduler_restarts(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "m", ["m1"])
    executed = []
    make_scheduler(tmp_path, directory, executed, replay=["m"]).run_until_idle()
    write_batch(directory, "z", ["z1"])
    make_scheduler(tmp_path, directory, executed).run_until_idle()
    write_batch(directory, "a", ["a1"])
    make_scheduler(tmp_path, directory, executed).run_until_idle()
    assert executed == ["m1", "z1", "a1"]
    assert [row["batch"] for row in queue_rows(directory)] == ["m", "z", "a"]


def test_a_batch_whose_state_was_lost_is_refused_until_acknowledged(tmp_path, caplog):
    directory = tmp_path / "batches"
    write_batch(directory, "lost", ["l1", "l2"])
    write_ledger(directory, ("lost", True))
    executed = []
    with caplog.at_level("WARNING"):
        assert make_scheduler(tmp_path, directory, executed).run_until_idle() == 0
    assert executed == []
    assert not (directory / "state" / "lost.json").exists()
    assert "state/lost.json is missing" in caplog.text
    assert "--replay-without-state lost" in caplog.text
    assert queue_rows(directory)[0]["status"] == "missing_state"
    assert queued_batches(directory)[0].needs_ack
    assert make_scheduler(tmp_path, directory, executed, replay=["lost"]).run_until_idle() == 2
    assert executed == ["l1", "l2"]


def test_without_a_ledger_a_stateless_batch_still_needs_an_acknowledgement(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "older", ["o1"])
    write_batch(directory, "started", ["s1", "s2"])
    write_state(directory, "started", done=1)
    executed = []
    assert make_scheduler(tmp_path, directory, executed).run_until_idle() == 1
    assert executed == ["s2"]
    assert read_ledger(directory) == [
        {"batch": "older", "queued_at": None, "acknowledged": False},
        {"batch": "started", "queued_at": None, "acknowledged": True},
    ]
    assert queue_rows(directory)[0]["status"] == "missing_state"
    write_batch(directory, "newer", ["n1"])
    assert {row["batch"]: row["status"] for row in queue_rows(directory)}["newer"] == "pending"
    assert {batch.batch: batch.status for batch in queued_batches(directory)}["newer"] == "pending"
    assert make_scheduler(tmp_path, directory, executed).run_until_idle() == 1
    assert executed == ["s2", "n1"]
    assert make_scheduler(tmp_path, directory, executed, replay=["older"]).run_until_idle() == 1
    assert executed == ["s2", "n1", "o1"]
    assert all(entry["acknowledged"] for entry in read_ledger(directory))


def test_a_lost_ledger_never_restarts_a_batch_from_entry_zero(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1", "a2"])
    executed = []
    make_scheduler(tmp_path, directory, executed, replay=["a"]).run_until_idle()
    (directory / LEDGER_FILENAME).unlink()
    (directory / "state" / "a.json").unlink()
    assert make_scheduler(tmp_path, directory, executed).run_until_idle() == 0
    assert executed == ["a1", "a2"]


def test_a_batch_with_state_but_no_ledger_entry_resumes_from_its_state(tmp_path):
    """A crash between writing a new Batch's state and its ledger entry loses nothing."""
    directory = tmp_path / "batches"
    write_ledger(directory)
    write_batch(directory, "b", ["b1", "b2"])
    write_state(directory, "b", done=1)
    executed = []
    assert make_scheduler(tmp_path, directory, executed).run_until_idle() == 1
    assert executed == ["b2"]


def test_an_unreadable_new_batch_is_not_recorded_until_it_is_valid(tmp_path):
    directory = tmp_path / "batches"
    write_ledger(directory)
    (directory / "half.toml").write_text('format = "karn-v5"\n[[runs]]\nbuild_output = ')
    executed = []
    assert make_scheduler(tmp_path, directory, executed).run_until_idle() == 0
    assert read_ledger(directory) == []
    write_batch(directory, "half", ["h1"])
    assert make_scheduler(tmp_path, directory, executed).run_until_idle() == 1
    assert executed == ["h1"]


def test_a_damaged_ledger_dispatches_nothing(tmp_path, caplog):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1"])
    write_state(directory, "a")
    (directory / LEDGER_FILENAME).write_text("{")
    executed = []
    with caplog.at_level("WARNING"), pytest.raises(KarnError, match="queue_ledger_invalid"):
        make_scheduler(tmp_path, directory, executed).run_until_idle()
    assert executed == []
    assert "queue_ledger_invalid" in caplog.text
    write_batch(directory, "b", ["b1"])
    rows = {row["batch"]: row for row in queue_rows(directory)}
    assert rows["b"]["status"] == rows["a"]["status"] == "ledger_damaged"
    assert rows["b"]["error"] == "queue_ledger_invalid"


def test_serve_mode_warns_about_a_skipped_batch(tmp_path, caplog, monkeypatch):
    directory = tmp_path / "batches"
    write_batch(directory, "lost", ["l1"])
    write_ledger(directory, ("lost", True))

    def stop(seconds):
        raise KeyboardInterrupt

    runner = make_scheduler(tmp_path, directory, [])
    monkeypatch.setattr(runner, "_pause", stop)
    with caplog.at_level("WARNING"), pytest.raises(KeyboardInterrupt):
        runner.serve(poll_seconds=1)
    assert "--replay-without-state lost" in caplog.text


def test_starting_a_state_never_replaces_one_that_appeared_meanwhile(tmp_path):
    directory = tmp_path / "batches"
    write_state(directory, "b", done=2)
    scheduler = make_scheduler(tmp_path, directory, [])
    state = scheduler._start_state(directory / "state" / "b.json", "b")
    assert len(state["runs"]) == 2
    assert len(json.loads((directory / "state" / "b.json").read_text())["runs"]) == 2
    assert [path.name for path in (directory / "state").iterdir()] == ["b.json"]


def test_a_ledger_that_is_not_a_regular_file_is_refused_without_blocking(tmp_path):
    directory = tmp_path / "batches"
    directory.mkdir()
    os.mkfifo(directory / LEDGER_FILENAME)
    with pytest.raises(KarnError, match="queue_ledger_invalid"):
        read_ledger(directory)
    write_batch(directory, "a", ["a1"])
    assert queue_rows(directory)[0]["status"] == "ledger_damaged"
    assert queued_batches(directory)[0].status == "ledger_damaged"
    executed = []
    with pytest.raises(KarnError, match="queue_ledger_invalid"):
        make_scheduler(tmp_path, directory, executed, replay=["a"]).run_until_idle()
    assert executed == []


def test_a_batch_written_during_a_pass_draws_no_missing_state_warning(tmp_path, caplog):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1"])
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["a"])
    sync = scheduler._sync_ledger

    def sync_then_add():
        ledger = sync()
        write_batch(directory, "late", ["l1"])
        return ledger

    scheduler._sync_ledger = sync_then_add
    with caplog.at_level("WARNING"):
        assert scheduler.run_until_idle() == 2
    assert executed == ["a1", "l1"]
    assert "missing" not in caplog.text


def test_a_replay_acknowledgement_starts_a_batch_from_zero_only_once(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1"])
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["a"])
    assert scheduler.run_until_idle() == 1
    (directory / "state" / "a.json").unlink()  # the state is lost again
    assert scheduler.run_until_idle() == 0
    assert executed == ["a1"]


def test_a_replay_flag_for_a_batch_that_has_state_is_never_used(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1", "a2"])
    write_ledger(directory, ("a", True))
    write_state(directory, "a", done=1)
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["a"])
    assert scheduler.run_until_idle() == 1
    (directory / "state" / "a.json").unlink()
    assert scheduler.run_until_idle() == 0
    assert executed == ["a2"]


def test_a_damaged_ledger_warns_every_pass_and_fails_once(tmp_path, caplog):
    import logging

    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1", "a2"])
    write_ledger(directory, ("a", True))
    write_state(directory, "a")
    good = (directory / LEDGER_FILENAME).read_text()
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed)
    for _ in range(2):
        (directory / LEDGER_FILENAME).write_text("{")
        caplog.clear()
        with caplog.at_level(logging.WARNING), pytest.raises(KarnError, match="queue_ledger"):
            scheduler.run_until_idle()
        assert any("queue_ledger_invalid" in record.message for record in caplog.records)
        assert [row["status"] for row in queue_rows(directory)] == ["ledger_damaged"]
        assert [batch.status for batch in queued_batches(directory)] == ["ledger_damaged"]
        (directory / LEDGER_FILENAME).write_text(good)
    assert executed == []
    assert scheduler.run_until_idle() == 2 and scheduler.dispatch_blocked is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unwritable_batch_directory_stops_dispatch_without_crashing(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1"])
    write_state(directory, "a")
    (directory / ".scheduler.lock").touch()
    executed = []
    os.chmod(directory, 0o555)
    try:
        scheduler = make_scheduler(tmp_path, directory, executed)
        with pytest.raises(KarnError, match="queue_ledger_unwritable:PermissionError"):
            scheduler.run_until_idle()
    finally:
        os.chmod(directory, 0o755)
    assert executed == []


def test_a_crash_s_temporary_ledger_files_are_removed(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1"])
    stale = directory / ".karn-ledger-abcd1234.json"
    stale.write_text("{}")
    make_scheduler(tmp_path, directory, [], replay=["a"]).run_until_idle()
    assert not stale.exists() and read_ledger(directory)


def test_a_replay_flag_for_a_new_batch_is_spent_by_its_automatic_start(tmp_path):
    directory = tmp_path / "batches"
    write_ledger(directory)
    write_batch(directory, "new", ["n1"])
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["new"])
    assert scheduler.run_until_idle() == 1
    (directory / "state" / "new.json").unlink()  # its state is lost after the first start
    assert scheduler.run_until_idle() == 0
    assert scheduler.run_until_idle() == 0
    assert executed == ["n1"]


def test_a_replay_flag_is_spent_by_a_restored_state(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "a", ["a1", "a2"])
    write_ledger(directory, ("a", True))
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["a"])
    write_state(directory, "a", done=1)  # restored before the first pass
    assert scheduler.run_until_idle() == 1
    (directory / "state" / "a.json").unlink()
    assert scheduler.run_until_idle() == 0
    assert executed == ["a2"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_acknowledgement_that_cannot_be_saved_blocks_dispatch_until_saved(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "lost", ["l1"])
    write_ledger(directory, ("lost", False))
    (directory / "state").mkdir()
    (directory / ".scheduler.lock").touch()
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["lost"])
    os.chmod(directory, 0o555)
    try:
        for _ in range(2):
            with pytest.raises(KarnError, match="queue_ledger_unwritable:PermissionError"):
                scheduler.run_until_idle()
        assert (directory / "state" / "lost.json").exists()  # kept, never recreated
    finally:
        os.chmod(directory, 0o755)
    assert executed == []
    assert scheduler.run_until_idle() == 1
    assert read_ledger(directory) == [{"batch": "lost", "queued_at": None, "acknowledged": True}]
    assert scheduler.run_until_idle() == 0
    assert executed == ["l1"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_state_that_cannot_be_started_blocks_dispatch_without_crashing(tmp_path):
    directory = tmp_path / "batches"
    write_batch(directory, "lost", ["l1"])
    write_ledger(directory, ("lost", False))
    (directory / "state").mkdir()
    executed = []
    scheduler = make_scheduler(tmp_path, directory, executed, replay=["lost"])
    os.chmod(directory / "state", 0o555)
    try:
        with pytest.raises(KarnError, match="queue_state_unwritable:PermissionError"):
            scheduler.run_until_idle()
    finally:
        os.chmod(directory / "state", 0o755)
    assert scheduler.run_until_idle() == 1
    assert executed == ["l1"]


@pytest.mark.parametrize("first_line", ['format = "legacy"\n', ""])
def test_a_new_unsupported_batch_is_reported_and_admitted_once_corrected(
    tmp_path, caplog, monkeypatch, first_line
):
    import logging

    directory = tmp_path / "batches"
    write_ledger(directory)
    body = '[[runs]]\nbuild_output = "fixture"\nconstruct = "o1"\nbenchmark = "example"\n'
    original = first_line + body
    (directory / "old.toml").write_text(original)
    passes = []

    def stop(seconds):
        passes.append(seconds)
        if len(passes) == 2:
            raise KeyboardInterrupt

    executed = []
    runner = make_scheduler(tmp_path, directory, executed)
    monkeypatch.setattr(runner, "_pause", stop)
    with caplog.at_level(logging.WARNING), pytest.raises(KeyboardInterrupt):
        runner.serve(poll_seconds=1)
    warnings = [r.message for r in caplog.records if "old.toml" in r.message or "old" in r.message]
    assert warnings, caplog.text
    assert len(warnings) == len(set(warnings))  # each distinct warning once
    assert (directory / "old.toml").read_text() == original
    assert [entry["batch"] for entry in read_ledger(directory)] == []
    (directory / "old.toml").write_text('format = "karn-v5"\n' + body)
    assert runner.run_until_idle() == 1
    assert executed == ["o1"]
