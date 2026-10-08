"""Every job the app starts completes once, quitting never waits on a read, and opening a run
shows nothing of the run before it."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from silverquillm.monitor import LogLine, Monitor, WorkspaceView
from silverquillm.monitor.output import LogFollower
from silverquillm.monitor.snapshot import _Live
from silverquillm.top.dashboard import RunChosen
from silverquillm.top.details import DetailsView

from .test_top import _app, _plain, _settle, synchronous
from .test_top_lifecycle import Slow, _lines, _wait_for
from .top_fixtures import FakeMonitor, history, output_lines

REPO = Path(__file__).resolve().parents[1]


class Gated(FakeMonitor):
    """Reads that wait at a gate while it is closed, and that tag output with the run."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gate = threading.Event()
        self.gate.set()
        self.waiting = 0
        self.fail_output = 0
        self.after_close = 0

    def _pass(self):
        self.after_close += self.closed
        self.waiting += 1
        self.gate.wait(10)
        self.waiting -= 1

    def snapshot(self):
        self._pass()
        return super().snapshot()

    def output(self, run_id, stream=None, since=0):
        self._pass()
        if self.fail_output:
            self.fail_output -= 1
            raise RuntimeError("docker went away")
        return [
            LogLine(line.seq, line.stream, f"{run_id[:8]} {line.text}", line.at)
            for line in super().output(run_id, stream, since)
        ]


def _choose(app, run_id):
    app.on_run_chosen(RunChosen(run_id))


def _stdout_count():
    return sum(1 for line in output_lines() if line.stream == "stdout")


# Every job completes once ----------------------------------------------------------


@synchronous
async def test_a_details_job_gone_stale_while_waiting_still_frees_its_slot():
    monitor = Gated()
    first, second, third = (view.run.run_id for view in monitor.running[1:4])
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        monitor.gate.clear()
        app.poll()  # holds the monitor while the details jobs below queue behind it
        await _wait_for(lambda: monitor.waiting == 1)
        _choose(app, first)  # starts a details job that waits on the poll
        _choose(app, second)  # makes the first stale before it reads anything
        monitor.gate.set()
        await _settle(app, pilot)
        assert app.busy == {"poll": False, "details": False}
        details = app.query_one(DetailsView)
        assert details.shown.run_id == second
        assert first not in {run_id for run_id, _ in monitor.output_calls}, "stale before I/O"
        raw = await _lines(app, pilot, "tab-raw", "#log-raw")
        assert raw and all(line.startswith(second[:8]) for line in raw)
        assert len(raw) == _stdout_count(), "no duplicate output"
        _choose(app, third)  # details are not frozen afterwards
        await _settle(app, pilot)
        raw = await _lines(app, pilot, "tab-raw", "#log-raw")
        assert raw and all(line.startswith(third[:8]) for line in raw)


@synchronous
async def test_a_failed_read_frees_its_slot_and_is_retried():
    monitor = Gated()
    run_id = monitor.running[1].run.run_id
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        monitor.fail_output = 1
        _choose(app, run_id)
        await _settle(app, pilot)
        assert app.busy == {"poll": False, "details": False}
        assert await _lines(app, pilot, "tab-raw", "#log-raw") == []
        app.poll()
        await _settle(app, pilot)
        raw = await _lines(app, pilot, "tab-raw", "#log-raw")
        assert len(raw) == _stdout_count()


@synchronous
async def test_a_run_finishing_while_its_details_are_queued_shows_its_retained_logs_once():
    monitor = Gated()
    run_id = monitor.running[1].run.run_id
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        monitor.gate.clear()
        app.poll()
        await _wait_for(lambda: monitor.waiting == 1)
        _choose(app, run_id)  # a live fetch queued behind the poll
        monitor.running = [view for view in monitor.running if view.run.run_id != run_id]
        monitor.gate.set()
        await _settle(app, pilot)
        app.poll()  # the poll above may have read the run as still live
        await _settle(app, pilot)
        shown = app.query_one(DetailsView).shown
        assert shown.live is None and shown.retained_loaded
        raw = await _lines(app, pilot, "tab-raw", "#log-raw")
        assert len(raw) == _stdout_count(), "retained once, no live leftovers"


# Quitting ------------------------------------------------------------------------------


@synchronous
async def test_quitting_before_any_job_reads_closes_the_monitor_without_reading():
    monitor = Slow(delay=0.3)
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.press("q")
    assert monitor.shutdown_begun
    await _wait_for(lambda: monitor.closed)
    assert monitor.snapshots <= 1 and monitor.after_close == 0


@synchronous
async def test_quitting_an_idle_app_closes_the_monitor_at_once():
    monitor = FakeMonitor()
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("q")
    assert monitor.shutdown_begun and monitor.closed


ENTRYPOINT = textwrap.dedent(
    """
    import subprocess, sys, threading, time
    sys.path.insert(0, {repo!r})
    from tests.top_fixtures import FakeMonitor
    from silverquillm.top.app import build_app
    from silverquillm.top.theme import MTG

    class Stuck(FakeMonitor):
        def __init__(self):
            super().__init__()
            # Stands in for a ``docker logs`` follower the monitor owns.
            self.follower = subprocess.Popen(["sleep", "60"])
            self.started = threading.Event()
            self.reads_after_close = 0

        def begin_shutdown(self):
            super().begin_shutdown()
            self.follower.terminate()

        def snapshot(self):
            self.reads_after_close += self.closed
            self.started.set()
            time.sleep(30)  # a Docker daemon that never answers
            return super().snapshot()

    monitor = Stuck()
    print("follower", monitor.follower.pid, flush=True)

    async def pilot(pilot):
        while not monitor.started.is_set():
            await pilot.pause(0.02)
        await pilot.press("q")

    app = build_app(monitor, MTG, interval=0.05)
    began = time.monotonic()
    app.run(headless=True, size=(160, 44), auto_pilot=pilot)
    app.release_monitor()
    workers = [t.name for t in threading.enumerate() if t.name.startswith("top-")]
    print("returned", round(time.monotonic() - began, 2), flush=True)
    print("workers", len(workers), flush=True)
    print("reads_after_close", monitor.reads_after_close, flush=True)
    """
)


def _gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    try:  # a terminated child its exited parent left behind is reaped by init shortly
        with open(f"/proc/{pid}/stat") as stat:
            return stat.read().split(")")[-1].split()[0] == "Z"
    except OSError:
        return True


@pytest.mark.skipif(sys.platform != "linux", reason="checks the follower through /proc")
def test_the_real_entrypoint_quits_promptly_with_a_stuck_read(tmp_path):
    began = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-c", ENTRYPOINT.format(repo=str(REPO))],
        capture_output=True,
        text=True,
        check=False,
        timeout=25,
        cwd=tmp_path,
        env={**os.environ, "TEXTUAL": "", "COLUMNS": "160", "LINES": "44"},
    )
    elapsed = time.monotonic() - began
    assert result.returncode == 0, result.stderr[-2000:]
    facts = dict(line.split(" ", 1) for line in result.stdout.splitlines() if " " in line)
    assert elapsed < 10, "the process never waits out the 30 s read"
    assert float(facts["returned"]) < 3
    assert int(facts["workers"]) <= 1, "one poll in flight, nothing piled up"
    assert facts["reads_after_close"] == "0"
    pid = int(facts["follower"])
    deadline = time.monotonic() + 5
    while not _gone(pid):
        if time.monotonic() > deadline:
            os.kill(pid, signal.SIGKILL)
            pytest.fail("the follower outlived the monitor")
        time.sleep(0.05)


# Opening another run --------------------------------------------------------------------


class Evidence(Gated):
    """The second historical run's evidence arrives late, never, or broken."""

    def __init__(self, mode: str):
        super().__init__(running=[])
        self.mode = mode
        self.target = history()[1].run_id
        self.detail_gate = threading.Event()
        self.detail_gate.set()

    def _late(self, run_id):
        if run_id == self.target:
            self.detail_gate.wait(10)

    def output(self, run_id, stream=None, since=0):
        self._late(run_id)
        if run_id == self.target and self.mode in ("none", "unavailable"):
            return []
        return super().output(run_id, stream, since)

    def workspace(self, run_id):
        self._late(run_id)
        if run_id == self.target and self.mode == "error":
            raise OSError("snapshots.json is unreadable")
        if run_id == self.target and self.mode in ("none", "unavailable"):
            return WorkspaceView((), ())
        return super().workspace(run_id)

    def record_detail(self, summary):
        if summary.run_id == self.target:
            if self.mode == "error":
                raise OSError("manifest briefly unreadable")
            if self.mode in ("none", "unavailable"):
                return None
        return super().record_detail(summary)


async def _evidence(app, pilot) -> dict:
    tables = {
        name: app.query_one(f"#{name}-table").row_count
        for name in ("requests", "snapshots", "commits")
    }
    return {
        **tables,
        "raw": await _lines(app, pilot, "tab-raw", "#log-raw"),
        "stderr": await _lines(app, pilot, "tab-stderr", "#log-stderr"),
        "head": _plain(app.query_one("#detail-head").content),
        "spark": _plain(app.query_one("#request-spark").content),
    }


def _nothing_of(evidence: dict, run_id: str, *, empty: bool = True) -> None:
    """No trace of ``run_id``; with ``empty``, no evidence of any run in the tables either."""
    assert run_id not in evidence["head"]
    assert not any(line.startswith(run_id[:8]) for line in evidence["raw"] + evidence["stderr"])
    if empty:
        assert evidence["requests"] == evidence["snapshots"] == evidence["commits"] == 0
        assert "priced" not in evidence["spark"], "no spend line from the previous run"


@pytest.mark.parametrize("mode", ["blocked", "none", "error", "unavailable"])
def test_opening_a_run_never_shows_the_previous_runs_evidence(mode):
    @synchronous
    async def check():
        monitor = Evidence(mode)
        previous, target = history()[0].run_id, monitor.target
        app = _app(monitor)
        async with app.run_test(size=(160, 44)) as pilot:
            await _settle(app, pilot)
            _choose(app, previous)
            app.action_view("details")
            await _settle(app, pilot)
            before = await _evidence(app, pilot)
            assert before["requests"] == 30 and before["commits"] and before["raw"]
            if mode == "blocked":
                monitor.detail_gate.clear()
            _choose(app, target)
            immediately = await _evidence(app, pilot)
            _nothing_of(immediately, previous)
            assert target in immediately["head"]
            if mode == "blocked":
                monitor.detail_gate.set()
            await _settle(app, pilot)
            app.poll()
            await _settle(app, pilot)
            after = await _evidence(app, pilot)
            _nothing_of(after, previous, empty=mode != "blocked")
            if mode == "blocked":
                assert after["requests"] == 30, "the run's own requests, once"
                assert len(after["raw"]) == _stdout_count()
                assert all(line.startswith(target[:8]) for line in after["raw"])
            else:
                assert after["requests"] == 0 and after["raw"] == []
            if mode in ("none", "unavailable"):
                assert "not readable" in after["spark"]

    check()


# The monitor's side of quitting ---------------------------------------------------------


def _sleeping_docker(argv, **kwargs):
    return subprocess.Popen(["sleep", "60"], **kwargs)


def test_begin_shutdown_ends_followers_without_waiting_and_starts_no_more(tmp_path):
    monitor = Monitor(given={"runs_dir": tmp_path}, environ={})
    follower = LogFollower("sq-run-x", (), popen=_sleeping_docker)
    follower.start()
    monitor._live["x"] = _Live(run=None, cost=None, follower=follower)
    began = time.monotonic()
    monitor.begin_shutdown()
    assert time.monotonic() - began < 0.5, "nothing waits for docker logs to exit"
    assert follower._process.wait(timeout=5) is not None
    assert monitor._stopping, "no follower starts after shutdown began"
    monitor.close()
    assert not any(thread.is_alive() for thread in follower._threads)
