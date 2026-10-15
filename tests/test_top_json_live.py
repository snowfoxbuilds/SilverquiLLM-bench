"""``top --json`` reads live Claude usage once and keeps each run's batch after its TOML is gone."""

from __future__ import annotations

import io
import json
import threading
import time

import pytest

from silverquillm.monitor import Monitor
from silverquillm.monitor.headless import snapshot_document
from silverquillm.monitor.output import sampled_claude_reading
from silverquillm.monitor.queue import batch_runs
from silverquillm.top import print_snapshot

from .test_monitor import RUN_SPEC, container, make_run, tree_state, write_batch
from .test_monitor_records import (
    FakeProcess,
    Followers,
    Host,
    claude_usage,
    publish,
    settle,
    stdout_with_reading,
)

# --- one bounded, synchronous usage reading ---------------------------------------------


class Launches(Followers):
    """``Followers`` that also remembers every ``docker`` command it was asked to run."""

    def __init__(self):
        super().__init__()
        self.commands: list[list[str]] = []

    def __call__(self, arguments, **kwargs):
        self.commands.append(list(arguments))
        return super().__call__(arguments, **kwargs)


def sampling_monitor(host: Host, popen) -> Monitor:
    """The monitor ``top --json`` builds: no log follower, one usage sample per snapshot."""
    return Monitor(
        given={"runs_dir": host.runs, "results_repo": host.repo, "state_root": host.state},
        environ=host.environ,
        docker=lambda: (list(host.containers), None),
        proc_locks=host.locks,
        clock=lambda: host.now,
        follow_output=False,
        sample_usage=True,
        popen=popen,
        hostname=host.hostname,
    )


def live_host(tmp_path, stdout: bytes, popen=None) -> tuple[Host, Followers]:
    followers = popen or Launches()
    host = Host(tmp_path, popen=followers)
    run = make_run(host.runs, "r1")
    followers.stdout["sq-run-r1"] = stdout
    host.own(run)
    host.containers = [container("r1")]
    return host, followers


def sampled_percent(host: Host, popen) -> float | None:
    monitor = sampling_monitor(host, popen)
    try:
        monitor.history(refresh=True)
        [profile] = monitor.snapshot().profiles
        return profile.weekly.percent
    finally:
        monitor.close()


def test_the_headless_snapshot_reads_the_same_live_claude_usage_as_the_dashboard(tmp_path):
    host, followers = live_host(tmp_path, stdout_with_reading(0.92, 30))
    dashboard = settle(host, 92.0)
    assert dashboard.percent == pytest.approx(92.0)
    assert sampled_percent(host, followers) == pytest.approx(dashboard.percent)


def test_print_snapshot_reports_the_live_reading_and_leaves_no_follower(tmp_path):
    launches = Launches()
    host, _ = live_host(tmp_path, stdout_with_reading(0.92, 30), launches)
    before = threading.active_count()
    stdout = io.StringIO()
    status = print_snapshot(
        {"runs_dir": host.runs, "results_repo": host.repo, "state_root": host.state},
        stdout=stdout,
        environ=host.environ,
        docker=lambda: (list(host.containers), None),
        proc_locks=host.locks,
        clock=lambda: host.now,
        popen=launches,
    )
    assert status == 0
    [login] = json.loads(stdout.getvalue())["logins"]
    assert login["weekly_usage_percent"] == pytest.approx(92.0)
    # One `docker logs` without --follow; every reader thread has ended.
    assert launches.commands == [
        ["docker", "logs", "--timestamps", "--tail", "2000", "sq-run-r1"]
    ]
    deadline = time.monotonic() + 2
    while threading.active_count() > before and time.monotonic() < deadline:
        time.sleep(0.01)
    assert threading.active_count() <= before


def test_a_live_reading_overrides_an_older_recorded_one(tmp_path):
    host, followers = live_host(tmp_path, stdout_with_reading(0.92, 30))
    publish(
        host.repo, "r0", host="host-a",
        usage=claude_usage(30.0, observed="2026-10-07T09:00:00Z"), requests=[],
    )  # fmt: skip
    assert sampled_percent(host, followers) == pytest.approx(92.0)


def test_no_reading_and_malformed_output_leave_the_estimate_to_records(tmp_path):
    for stdout in (
        b"",
        b"2026-10-07T11:30:00.000000000Z not json at all\n",
        b'2026-10-07T11:30:00.000000000Z {"type": "rate_limit_event", "rate_limit_info": [}\n',
        b'2026-10-07T11:30:00.000000000Z {"type": "rate_limit_event"}\n',
    ):
        target = tmp_path / str(len(stdout))
        target.mkdir()
        host, followers = live_host(target, stdout)
        assert sampled_percent(host, followers) == pytest.approx(0.0)


def test_docker_that_cannot_start_reads_nothing():
    def unavailable(arguments, **kwargs):
        raise OSError("no docker")

    assert sampled_claude_reading("sq-run-r1", popen=unavailable) is None


class Hanging(FakeProcess):
    """``docker logs`` that never ends until it is terminated."""

    def __init__(self):
        super().__init__(b"", b"")
        self.ended = threading.Event()
        self.terminated = False
        self.stdout = self

    def read1(self, size=-1):
        self.ended.wait(10)
        return b""

    def close(self):
        pass

    def poll(self):
        return 0 if self.ended.is_set() else None

    def terminate(self):
        self.terminated = True
        self.ended.set()

    def wait(self, timeout=None):
        self.ended.wait(timeout)
        return 0


def test_a_docker_read_that_hangs_is_ended_within_the_time_bound():
    process = Hanging()
    started = time.monotonic()
    reading = sampled_claude_reading("sq-run-r1", popen=lambda *a, **k: process, timeout=0.3)
    assert reading is None
    assert process.terminated
    assert time.monotonic() - started < 3


def test_reading_stops_at_the_byte_bound():
    line = stdout_with_reading(0.92, 30)
    filler = b"2026-10-07T11:00:00.000000000Z " + b"x" * 1000 + b"\n"
    stdout = filler * 50 + line  # the reading lies past the bound
    reading = sampled_claude_reading(
        "sq-run-r1", popen=lambda *a, **k: FakeProcess(stdout, b""), max_bytes=10_000
    )
    assert reading is None
    found = sampled_claude_reading("sq-run-r1", popen=lambda *a, **k: FakeProcess(stdout, b""))
    assert found is not None and found.utilization_percent == pytest.approx(92.0)


# --- run attribution from retained batch state ------------------------------------------


def state(batches, name, rows):
    (batches / "state").mkdir(exist_ok=True)
    (batches / "state" / f"{name}.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "batch": name,
                "runs": [
                    {"index": index, "run_id": run_id, "spec": {}, "status": "done"}
                    for index, run_id in enumerate(rows)
                ],
            }
        )
    )


def attribution(tmp_path, batches) -> dict:
    runs = tmp_path / "runs"
    monitor = Monitor(
        given={"runs_dir": runs, "results_repo": tmp_path / "repo", "batches_dir": batches},
        environ={"XDG_CONFIG_HOME": str(tmp_path / "config"), "SILVERQUILLM_HOST_LABEL": "host-a"},
        docker=lambda: ([], None),
        proc_locks=tmp_path / "no-locks",
        follow_output=False,
    )
    (tmp_path / "no-locks").write_text("")
    try:
        document = snapshot_document(monitor.snapshot())
    finally:
        monitor.close()
    return {run["run_id"]: (run["batch"], run["batch_entry"]) for run in document["runs"]}


@pytest.mark.parametrize("submission", ["removed", "invalid"])
def test_a_run_keeps_its_batch_after_its_submission_is_gone(tmp_path, submission):
    runs, batches = tmp_path / "runs", tmp_path / "batches"
    (tmp_path / "repo").mkdir()
    make_run(runs, "r1")
    make_run(runs, "loose")
    spec = RUN_SPEC.format(build=tmp_path / "nobuild", benchmark="smoke")
    write_batch(batches, "sweep", 'format = "karn-v5"\n' + spec)
    state(batches, "sweep", ["r1"])
    assert attribution(tmp_path, batches)["r1"] == ("sweep", 0)
    if submission == "removed":
        (batches / "sweep.toml").unlink()
    else:
        (batches / "sweep.toml").write_text("this is [ not toml")
    before = tree_state(runs, batches)
    found = attribution(tmp_path, batches)
    assert tree_state(runs, batches) == before
    assert found == {"r1": ("sweep", 0), "loose": (None, None)}


def test_invalid_and_ambiguous_state_attribute_nothing(tmp_path):
    batches = tmp_path / "batches"
    batches.mkdir()
    state(batches, "good", ["a", "twice"])
    state(batches, "other", ["twice"])
    (batches / "state" / "broken.json").write_text("{not json")
    (batches / "state" / "mislabelled.json").write_text(
        json.dumps({"schema_version": 2, "batch": "something-else", "runs": []})
    )
    (batches / "state" / ".scheduler-temp.json").write_text("{}")
    before = tree_state(batches)
    assert batch_runs(batches) == {"a": ("good", 0), "twice": None}
    assert tree_state(batches) == before
    assert batch_runs(tmp_path / "missing") == {}
    assert batch_runs(None) == {}
