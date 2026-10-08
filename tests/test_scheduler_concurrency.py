"""Native scheduler workers compete for real pool locks without running containers."""

from __future__ import annotations

import contextlib
import json
import multiprocessing
import os
import signal
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from silverquillm.karn.batching import KarnScheduler, read_state
from silverquillm.karn.definition import KarnError, canonical
from silverquillm.karn.interruption import terminate_as_interrupt
from silverquillm.karn.login_cooldown import set_cooldown
from silverquillm.karn.login_pool import LoginPool
from silverquillm.karn.scheduler_worker import SpawnWorker, owner_alive, process_identity
from silverquillm.queue_state import SchedulerLock

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = "karn-claude-login"
CODEX = "karn-codex-login"


def _wait_file(path, timeout=15):
    until = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() > until:
            raise AssertionError(f"timed out waiting for {path}")
        time.sleep(0.01)


def _execute(**kwargs):
    state = kwargs["state_root"]
    name = kwargs["construct"]
    plugin = kwargs["benchmark_id"]
    with (state / (name + ".attempts")).open("a") as attempts:
        attempts.write("attempt\n")
    with contextlib.ExitStack() as held:
        login = None
        if plugin != "unpooled":
            pool = LoginPool.of(state, plugin)
            login = pool.ref(pool.acquire(held, wait=kwargs["login_blocking"]))
        kwargs["on_login_selected"](login)
        if name == "prelaunch":
            (state / "prelaunch.claimed").touch()
            _wait_file(state / "prelaunch.proceed")
        kwargs["on_launch"]()
        assert any(
            row["run_id"] == kwargs["run_id"]
            for path in (kwargs["build_output"] / "state").glob("*.json")
            for row in json.loads(path.read_text())["runs"]
        )
        # A spawned worker must not inherit the scheduler's flock descriptor.
        assert not any(
            os.readlink(fd).endswith(".scheduler.lock")
            for fd in Path("/proc/self/fd").iterdir()
            if fd.exists()
        )
        (state / (name + ".started")).write_text(login or "unpooled")
        status = "completed"
        try:
            _wait_file(state / (name + ".release"))
        except KeyboardInterrupt:
            status = "interrupted"
        held.close()
        kwargs["on_login_released"]()
        (state / (name + ".released")).touch()
        if name == "first" and status != "interrupted":
            _wait_file(state / "first.grade")
        if name == "failure":
            raise KarnError("fixture_failure")
        (state / (name + ".finished")).touch()
        return SimpleNamespace(
            run_metadata={"execution": {"status": status}},
            candidate=SimpleNamespace(to_dict=dict),
        )


def _complete_after_release(**kwargs):
    _wait_file(kwargs["state_root"] / "complete")
    return SimpleNamespace(
        run_metadata={"execution": {"status": "completed"}},
        candidate=SimpleNamespace(to_dict=dict),
    )


def _scheduler_process(directory, state):
    runner = make_scheduler(directory, state, slot_poll_seconds=0.1)
    if (state / "fail-saves").exists():
        save = runner._save

        def fail_completed(path, document):
            if any(row["status"] != "running" for row in document["runs"]):
                raise OSError("fixture_disk_full")
            save(path, document)

        runner._save = fail_completed
    try:
        with terminate_as_interrupt():
            count = runner.run_until_idle()
        (state / "count").write_text(str(count))
    except KeyboardInterrupt:
        (state / "interrupted").touch()
    except OSError as error:
        (state / "error").write_text(str(error))


def make_scheduler(directory, state, **extra):
    return KarnScheduler(
        directory,
        bench_root=ROOT,
        results_dir=state / "runs",
        results_repo=state / "records",
        state_root=state,
        replay_without_state=["a", "b"],
        executor=_execute,
        **extra,
    )


def _batch(directory, names, plugin=CLAUDE, batch="a"):
    directory.mkdir(exist_ok=True)
    (directory / (batch + ".toml")).write_text(
        'format="karn-v5"\n'
        + "".join(
            f'[[runs]]\nbuild_output={json.dumps(str(directory))}\nconstruct="{name}"\n'
            f'benchmark="{plugin if isinstance(plugin, str) else plugin[index]}"\n'
            for index, name in enumerate(names)
        )
    )


def _enroll(state, count, plugin=CLAUDE):
    pool = LoginPool.of(state, plugin)
    filename = ".credentials.json" if plugin == CLAUDE else "auth.json"
    secret = canonical({"format": 1, "revision": "a" * 32, "files": {filename: "e30="}}).decode()
    for number in range(count):
        profile = pool.named_slot(f"slot-{number}")
        profile.set_secret("login." + profile.name, secret)
    return pool


@contextlib.contextmanager
def _running(directory, state):
    process = multiprocessing.get_context("spawn").Process(
        target=_scheduler_process, args=(directory, state)
    )
    process.start()
    try:
        yield process
    finally:
        process.join(0.5)
        if process.is_alive():
            os.kill(process.pid, signal.SIGTERM)
        process.join(20)
        if process.is_alive():
            process.kill()
            process.join()
            pytest.fail("scheduler did not drain its workers")
        assert process.exitcode == 0
        process.close()


def test_native_workers_fill_slots_and_refill_before_grading_finishes(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _enroll(state, 2)
    _batch(directory, ["first", "second", "third"])
    with _running(directory, state) as process:
        _wait_file(state / "first.started")
        _wait_file(state / "second.started")
        assert not (state / "third.started").exists()
        rows = read_state(directory / "state/a.json", "a")["runs"]
        assert [row["status"] for row in rows] == ["running", "running"]
        assert (state / "first.started").read_text() != (state / "second.started").read_text()
        (state / "first.release").touch()
        _wait_file(state / "third.started")
        assert not (state / "first.finished").exists()
        for marker in ("first.grade", "second.release", "third.release"):
            (state / marker).touch()
        _wait_file(state / "count")
        assert (state / "count").read_text() == "3"
        process.join(10)
    assert [row["status"] for row in read_state(directory / "state/a.json", "a")["runs"]] == [
        "done"
    ] * 3
    with SchedulerLock(directory):
        pass


def test_busy_entry_does_not_repeat_preflight_until_release(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _enroll(state, 1)
    _batch(directory, ["first", "second"])
    with _running(directory, state):
        _wait_file(state / "first.started")
        _wait_file(state / "second.attempts")
        time.sleep(0.6)
        assert (state / "second.attempts").read_text().splitlines() == ["attempt"]
        (state / "first.release").touch()
        _wait_file(state / "second.started", timeout=3)
        assert not (state / "first.finished").exists()
        (state / "second.release").touch()
        (state / "first.grade").touch()
        _wait_file(state / "count")
    assert len((state / "second.attempts").read_text().splitlines()) == 2


@pytest.mark.parametrize("blocked", ["external", "cooldown", "empty"])
def test_capacity_poll_detects_external_changes_without_preflight_churn(tmp_path, blocked):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _enroll(state, 1, CODEX)
    _batch(directory, ["waiting"])
    _batch(directory, ["keeper", "next-keeper"], CODEX, batch="b")
    with contextlib.ExitStack() as held:
        if blocked != "empty":
            pool = _enroll(state, 1)
            if blocked == "external":
                pool.acquire(held, wait=False)
            else:
                now = datetime.now(UTC)
                set_cooldown(pool.root / "slot-0", now + timedelta(hours=1), now=now)
        with _running(directory, state):
            _wait_file(state / "keeper.started")
            time.sleep(0.6)
            assert (state / "waiting.attempts").read_text().splitlines() == ["attempt"]
            (state / "keeper.release").touch()
            _wait_file(state / "next-keeper.started")
            assert (state / "waiting.attempts").read_text().splitlines() == ["attempt"]
            if blocked == "external":
                held.close()
            elif blocked == "empty":
                _enroll(state, 1)
            else:
                now = datetime.now(UTC)
                set_cooldown(pool.root / "slot-0", now + timedelta(seconds=2), now=now)
            _wait_file(state / "waiting.started", timeout=4)
            assert not (state / "next-keeper.finished").exists()
            (state / "waiting.release").touch()
            (state / "next-keeper.release").touch()
            _wait_file(state / "count")
    assert len((state / "waiting.attempts").read_text().splitlines()) == 2


def test_shutdown_drains_every_owned_run_and_releases_all_locks(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    pool = _enroll(state, 2)
    _batch(directory, ["one", "two", "three"])
    with _running(directory, state) as process:
        _wait_file(state / "one.started")
        _wait_file(state / "two.started")
        os.kill(process.pid, signal.SIGTERM)
        _wait_file(state / "interrupted")
        process.join(10)
    rows = read_state(directory / "state/a.json", "a")["runs"]
    assert len(rows) == 2
    assert all(row["execution_status"] == "interrupted" for row in rows)
    with SchedulerLock(directory), contextlib.ExitStack() as held:
        assert pool.acquire(held, wait=False).name != pool.acquire(held, wait=False).name


def test_recovery_visits_every_running_row_and_defers_live_owners(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _batch(directory, [])
    (directory / "state").mkdir()
    rows = [{"index": i, "run_id": f"run-{i}", "spec": {}, "status": "running"} for i in range(4)]
    rows[1]["worker"] = process_identity(os.getpid())
    path = directory / "state/a.json"
    path.write_text(json.dumps({"schema_version": 2, "batch": "a", "runs": rows}))
    visited = []

    def recover(**kwargs):
        visited.append(kwargs["run_id"])
        if kwargs["run_id"] == "run-2":
            raise KarnError("run_in_progress")
        return SimpleNamespace(
            run_id=kwargs["run_id"],
            run_metadata={"execution": {"status": "completed"}},
            candidate=SimpleNamespace(to_dict=dict),
        )

    assert make_scheduler(directory, state, recoverer=recover).run_until_idle() == 0
    assert visited == ["run-0", "run-2", "run-3"]
    assert [row["status"] for row in read_state(path, "a")["runs"]] == [
        "done",
        "running",
        "running",
        "done",
    ]


@pytest.mark.parametrize("busy", [False, True])
def test_busy_or_unavailable_provider_does_not_block_another_batch(tmp_path, busy):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _enroll(state, 1, CODEX)
    _batch(directory, ["claude"])
    _batch(directory, ["codex"], CODEX, batch="b")
    with contextlib.ExitStack() as held:
        if busy:
            _enroll(state, 1).acquire(held, wait=False)
        (state / "codex.release").touch()
        with _running(directory, state):
            _wait_file(state / "count")
        assert (state / "count").read_text() == "1"
        assert not (state / "claude.started").exists()
        assert read_state(directory / "state/a.json", "a")["runs"] == []
        assert read_state(directory / "state/b.json", "b")["runs"][0]["status"] == "done"


def test_failed_worker_does_not_drop_following_entries(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _enroll(state, 1)
    _batch(directory, ["failure", "next"])
    for name in ("failure", "next"):
        (state / (name + ".release")).touch()
    with _running(directory, state):
        _wait_file(state / "count")
    rows = read_state(directory / "state/a.json", "a")["runs"]
    assert [row["status"] for row in rows] == ["failed", "done"]
    assert rows[0]["error"] == "fixture_failure"


def test_unpooled_entries_remain_serial(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    state.mkdir()
    _batch(directory, ["one", "two"], "unpooled")
    with _running(directory, state):
        _wait_file(state / "one.started")
        _wait_file(state / "two.attempts")
        time.sleep(0.6)
        assert not (state / "two.started").exists()
        assert (state / "two.attempts").read_text().splitlines() == ["attempt"]
        (state / "one.release").touch()
        _wait_file(state / "two.started")
        assert (state / "one.finished").exists()
        (state / "two.release").touch()
        _wait_file(state / "count")


def test_idle_active_worker_scans_batches_only_on_events_or_timer(tmp_path, monkeypatch):
    import threading

    from silverquillm.karn import batching
    from tests.scheduler_fixtures import ThreadWorker

    directory, state = tmp_path / "batches", tmp_path / "state"
    state.mkdir()
    _batch(directory, ["one"], "unpooled")
    launched = threading.Event()
    scans = []
    load_batch = batching.load_batch

    def counted_load(path):
        scans.append(time.monotonic())
        return load_batch(path)

    def execute(**kwargs):
        kwargs["on_login_selected"](None)
        kwargs["on_launch"]()
        launched.set()
        time.sleep(0.5)
        return SimpleNamespace(
            run_metadata={"execution": {"status": "completed"}},
            candidate=SimpleNamespace(to_dict=dict),
        )

    monkeypatch.setattr(batching, "load_batch", counted_load)
    scheduler = make_scheduler(directory, state, worker_factory=ThreadWorker, slot_poll_seconds=2)
    scheduler.executor = execute
    assert scheduler.run_until_idle() == 1
    assert launched.is_set()
    assert len(scans) <= 5


def test_dead_worker_does_not_stall_refilling_while_another_run_continues(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _enroll(state, 2)
    _batch(directory, ["one", "two", "three"])
    with _running(directory, state):
        _wait_file(state / "one.started")
        _wait_file(state / "two.started")
        first = read_state(directory / "state/a.json", "a")["runs"][0]
        os.kill(first["worker"]["pid"], signal.SIGKILL)
        _wait_file(state / "three.started")
        assert not (state / "two.finished").exists()
        (state / "two.release").touch()
        (state / "three.release").touch()
        _wait_file(state / "count")
    rows = read_state(directory / "state/a.json", "a")["runs"]
    assert [row["status"] for row in rows] == ["running", "done", "done"]


@pytest.mark.parametrize("poll_seconds", [0.1, 2.0])
def test_prelaunch_worker_death_retries_only_on_slot_poll(tmp_path, poll_seconds):
    from tests.scheduler_fixtures import ThreadWorker

    directory, state = tmp_path / "batches", tmp_path / "state"
    state.mkdir()
    _batch(directory, ["crash"])
    _batch(directory, ["keeper"], "unpooled", batch="b")
    attempts = []

    class DeadWorker:
        owner = None

        def __init__(self):
            self.connection, child = multiprocessing.Pipe()
            child.close()

        def alive(self):
            return False

        def close(self):
            self.connection.close()

    def worker_factory(executor, arguments):
        if arguments["construct"] == "crash":
            attempts.append(time.monotonic())
            assert len(attempts) < 100, "prelaunch failures are spinning without a poll delay"
            return DeadWorker()
        return ThreadWorker(executor, arguments)

    def execute(**kwargs):
        kwargs["on_login_selected"](None)
        kwargs["on_launch"]()
        time.sleep(0.05)
        kwargs["on_login_released"]()
        time.sleep(0.3)
        return SimpleNamespace(
            run_metadata={"execution": {"status": "completed"}},
            candidate=SimpleNamespace(to_dict=dict),
        )

    scheduler = make_scheduler(
        directory, state, worker_factory=worker_factory, slot_poll_seconds=poll_seconds
    )
    scheduler.executor = execute
    started = time.monotonic()
    assert scheduler.run_until_idle() == 1
    elapsed = time.monotonic() - started
    assert len(attempts) <= int(elapsed / poll_seconds) + 1
    if poll_seconds == 0.1:
        assert len(attempts) > 1
    else:
        assert len(attempts) == 1
    assert read_state(directory / "state/a.json", "a")["runs"] == []


@pytest.mark.parametrize("spawn", [False, True])
def test_result_sent_between_empty_poll_and_worker_exit_is_retained(tmp_path, spawn):
    from tests.scheduler_fixtures import ThreadWorker

    directory, state = tmp_path / "batches", tmp_path / "state"
    state.mkdir()
    _batch(directory, ["one"])

    def worker_factory(executor, arguments):
        worker = (SpawnWorker if spawn else ThreadWorker)(executor, arguments)
        connection = worker.connection

        class CompleteAfterEmptyPoll:
            completed = False

            def __getattr__(self, name):
                return getattr(connection, name)

            def poll(self, *args):
                ready = connection.poll(*args)
                if not self.completed:
                    assert not ready
                    self.completed = True
                    (state / "complete").touch()
                    deadline = time.monotonic() + 10
                    while worker.alive():
                        assert time.monotonic() < deadline
                        time.sleep(0.01)
                return ready

        worker.connection = CompleteAfterEmptyPoll()
        return worker

    scheduler = make_scheduler(directory, state, worker_factory=worker_factory)
    scheduler.executor = _complete_after_release
    assert scheduler.run_until_idle() == 1
    assert read_state(directory / "state/a.json", "a")["runs"][0]["status"] == "done"
    assert not scheduler.warnings


def test_restart_fills_a_free_slot_beside_an_external_live_worker(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _enroll(state, 2)
    _batch(directory, ["one", "two"])
    (directory / "state").mkdir()
    path = directory / "state/a.json"
    worker = SpawnWorker(
        _execute,
        {
            "state_root": state,
            "build_output": directory,
            "construct": "one",
            "benchmark_id": CLAUDE,
            "run_id": "external",
        },
    )
    try:
        assert worker.connection.poll(10)
        assert worker.connection.recv()[0] == "selected"
        worker.connection.send(True)
        assert worker.connection.poll(10)
        assert worker.connection.recv()[0] == "launch"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "batch": "a",
                    "runs": [
                        {
                            "index": 0,
                            "run_id": "external",
                            "spec": {},
                            "status": "running",
                            "worker": worker.owner,
                        }
                    ],
                }
            )
        )
        worker.connection.send(True)
        _wait_file(state / "one.started")
        with _running(directory, state):
            _wait_file(state / "two.started")
            assert not (state / "one.finished").exists()
            (state / "two.release").touch()
            _wait_file(state / "count")
        assert [row["status"] for row in read_state(path, "a")["runs"]] == ["running", "done"]
    finally:
        (state / "one.release").touch()
        _wait_file(state / "one.finished")
        worker.close()


def test_zombie_owner_is_not_live():
    pid = os.fork()
    if pid == 0:
        time.sleep(0.1)
        os._exit(0)
    try:
        identity = process_identity(pid)
        until = time.monotonic() + 5
        while process_identity(pid)["birth"] is not None:
            assert time.monotonic() < until
            time.sleep(0.01)
        assert not owner_alive(identity)
    finally:
        os.waitpid(pid, 0)


def test_queue_save_failure_still_drains_and_reaps_every_owned_worker(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    pool = _enroll(state, 2)
    _batch(directory, ["one", "two", "three"])
    (state / "fail-saves").touch()
    with _running(directory, state):
        _wait_file(state / "one.started")
        _wait_file(state / "two.started")
        (state / "one.release").touch()
        _wait_file(state / "error")
        assert (state / "error").read_text() == "fixture_disk_full"
        assert (state / "two.finished").exists()
        assert not (state / "three.started").exists()
    rows = read_state(directory / "state/a.json", "a")["runs"]
    assert all(not Path(f"/proc/{row['worker']['pid']}").exists() for row in rows)
    with SchedulerLock(directory), contextlib.ExitStack() as held:
        assert pool.acquire(held, wait=False).name != pool.acquire(held, wait=False).name


def test_shutdown_after_slot_claim_before_launch_keeps_entry_pending(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    pool = _enroll(state, 1)
    _batch(directory, ["prelaunch", "next"])
    with _running(directory, state) as process:
        _wait_file(state / "prelaunch.claimed")
        os.kill(process.pid, signal.SIGTERM)
        _wait_file(state / "interrupted")
    assert read_state(directory / "state/a.json", "a")["runs"] == []
    assert not (state / "next.started").exists()
    with SchedulerLock(directory), contextlib.ExitStack() as held:
        assert pool.acquire(held, wait=False).name == "slot-0"


def test_live_unpooled_owner_in_later_batch_blocks_until_it_exits(tmp_path):
    directory, state = tmp_path / "batches", tmp_path / "state"
    _enroll(state, 1)
    _batch(directory, ["two"], "unpooled")
    _batch(directory, ["one", "holder"], ["unpooled", CLAUDE], batch="b")
    (directory / "state").mkdir()
    path = directory / "state/b.json"
    worker = SpawnWorker(
        _execute,
        {
            "state_root": state,
            "build_output": directory,
            "construct": "one",
            "benchmark_id": "unpooled",
            "run_id": "external",
        },
    )
    closed = False
    try:
        assert worker.connection.poll(10)
        assert worker.connection.recv() == ("selected", None)
        worker.connection.send(True)
        assert worker.connection.poll(10)
        assert worker.connection.recv()[0] == "launch"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "batch": "b",
                    "runs": [
                        {
                            "index": 0,
                            "run_id": "external",
                            "spec": {},
                            "status": "running",
                            "worker": worker.owner,
                            "login": None,
                        },
                    ],
                }
            )
        )
        worker.connection.send(True)
        _wait_file(state / "one.started")
        with _running(directory, state):
            _wait_file(state / "holder.started")
            assert not (state / "two.started").exists()
            (state / "one.release").touch()
            _wait_file(state / "one.finished")
            worker.close()
            closed = True
            _wait_file(state / "two.started")
            assert not (state / "holder.finished").exists()
            (state / "two.release").touch()
            (state / "holder.release").touch()
            _wait_file(state / "count")
    finally:
        if not closed:
            (state / "one.release").touch()
            _wait_file(state / "one.finished")
            worker.close()
