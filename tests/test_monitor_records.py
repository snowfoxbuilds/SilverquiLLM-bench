"""How the monitor reads Run Records (RUN-MONITORING.md): which records make a run Finished,
which execution each record's spend belongs to, and whose Login Profile it charges."""

from __future__ import annotations

import contextlib
import json
import shutil
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from silverquillm.karn.exclusions import Exclusion, write_exclusion
from silverquillm.karn.execution import run_lock
from silverquillm.monitor import Monitor, Stage
from silverquillm.monitor.costs import ProvisionalCost
from silverquillm.monitor.estimates import weekly_usage
from silverquillm.monitor.history import UsageReading
from silverquillm.monitor.live import live_runs
from silverquillm.monitor.locks import held_locks

from .test_karn_subscription_usage import claude_event
from .test_monitor import (
    CANDIDATE_HASH,
    NOW,
    OTHER_HASH,
    OTHER_IDENTITY,
    START,
    FakeProcess,
    container,
    enroll_slot,
    event,
    make_run,
    ms,
    proc_locks,
    publish,
    retain,
    stages,
    valid_record,
)

RATES = {"claude": Decimal(25), "codex": Decimal(5)}
PROFILE = "karn-claude-login/bare-claude-opus"


def claude_usage(percent, resets="2026-10-09T00:00:00Z", observed=None):
    return {
        "completeness": "complete",
        "reasons": [],
        "value": {
            "provider": "claude",
            "utilization_percent": percent,
            "window_minutes": 10080,
            "resets_at": resets,
            "observed_at": observed,
        },
    }


def at(minutes, usd):
    """One priced request ``minutes`` after the records' start."""
    return (START + timedelta(minutes=minutes), usd)


class Host:
    """This host's run directory, Results Repo clone and one enrolled Claude Login Profile."""

    def __init__(self, tmp_path: Path, *, label: str | None = "host-a", hostname=None, popen=None):
        self.tmp_path = tmp_path
        self.now = NOW
        self.popen = popen
        self.runs, self.repo, self.state = (tmp_path / n for n in ("runs", "repo", "state"))
        self.runs.mkdir()
        self.repo.mkdir()
        enroll_slot(self.state, "karn-claude-login", "bare-claude-opus")
        environ = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
        if label is not None:
            environ["SILVERQUILLM_HOST_LABEL"] = label
        self.environ, self.hostname = environ, hostname
        self.locks = tmp_path / "proc-locks"
        self.locks.write_text("")
        self.containers = []
        self._monitor = None

    def release(self) -> None:
        """Every runner has exited: the copied lock table holds nothing."""
        self.locks.write_text("")

    def own(self, *run_dirs: Path) -> None:
        """Hold these runs' locks in the copied lock table, as their runners would."""
        with contextlib.ExitStack() as stack:
            for run_dir in run_dirs:
                stack.enter_context(run_lock(run_dir))
            self.locks.write_text(Path("/proc/locks").read_text())

    @property
    def monitor(self) -> Monitor:
        if self._monitor is None:
            self._monitor = Monitor(
                given={"runs_dir": self.runs, "results_repo": self.repo, "state_root": self.state},
                environ=self.environ,
                docker=lambda: (list(self.containers), None),
                proc_locks=self.locks,
                clock=lambda: self.now,
                follow_output=self.popen is not None,
                hostname=self.hostname,
                **({"popen": self.popen} if self.popen is not None else {}),
            )
        return self._monitor

    def snapshot(self):
        self.monitor.history(refresh=True)
        return self.monitor.snapshot()

    def weekly(self):
        [profile] = self.snapshot().profiles
        return profile.weekly


# Finished rests on validated records


def test_a_published_only_record_is_final_only_with_a_confirmed_stop(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    make_run(runs, "stopped")
    publish(repo, "stopped")
    make_run(runs, "unconfirmed")
    publish(repo, "unconfirmed", stopped=False)
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "unconfirmed": (Stage.NEEDS_RECOVER, ("unconfirmed_stop",))
    }


def test_an_empty_destination_is_not_a_published_record(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    retain(make_run(runs, "r1") / "run-record.json", "r1")
    (repo / "results" / CANDIDATE_HASH / "r1").mkdir(parents=True)
    make_run(runs, "r2")
    (repo / "results" / CANDIDATE_HASH / "r2").mkdir(parents=True)
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unreadable_published_record",)),
        "r2": (Stage.NEEDS_RECOVER, ("unreadable_published_record",)),
    }


def test_a_record_failing_its_own_validation_is_unreadable(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    run = make_run(runs, "r1")
    path = retain(run / "run-record.json", "r1")
    publish(repo, "r1", retained=path)
    document = json.loads(path.read_text())
    del document["scores"]["engine_regression"]
    path.write_text(json.dumps(document))
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unreadable_record",))
    }


def test_a_record_naming_another_run_or_stored_elsewhere_is_mismatched(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    retain(make_run(runs, "r1") / "run-record.json", "someone-else")
    # A valid record filed under a Candidate Hash that is not its own.
    make_run(runs, "r2")
    record = valid_record("r2")
    misfiled = repo / "results" / OTHER_HASH / "r2"
    misfiled.mkdir(parents=True)
    (misfiled / "manifest.json").write_text(json.dumps(record.manifest))
    (misfiled / "scores.json").write_text(json.dumps(record.scores))
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("mismatched_record",)),
        "r2": (Stage.NEEDS_RECOVER, ("unreadable_published_record",)),
    }


def test_two_published_records_under_one_run_id_are_ambiguous(tmp_path):
    from .test_monitor import OTHER_IDENTITY

    runs, repo = tmp_path / "runs", tmp_path / "repo"
    make_run(runs, "r1")
    publish(repo, "r1")
    publish(repo, "r1", identity=OTHER_IDENTITY)
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("ambiguous_published_record",))
    }


def test_a_malformed_linked_recovery_keeps_the_warning(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    run = make_run(runs, "r1")
    publish(repo, "r1", retained=retain(run / "run-record.json", "r1", stopped=False))
    (run / "recovery-1").mkdir()
    (run / "recovery-1/run-record.json").write_text('{"manifest": {}, "scores": {}}')
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unreadable_record",))
    }


def test_a_published_linked_recovery_named_by_the_link_clears_the_warning(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    run = make_run(runs, "r1")
    publish(repo, "r1", retained=retain(run / "run-record.json", "r1", stopped=False))
    link = {"run_id": "r1-recovery-1", "candidate_hash": CANDIDATE_HASH}
    (run / "recovery-record.json").write_text(json.dumps(link))
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unconfirmed_stop",))
    }
    publish(repo, "r1-recovery-1", recovery_of="r1")
    assert stages(runs, repo, tmp_path=tmp_path) == {}
    # A link naming anything but a run id and a Candidate Hash is ignored.
    (run / "recovery-record.json").write_text(
        json.dumps({"run_id": "../r1-recovery-1", "candidate_hash": CANDIDATE_HASH})
    )
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unconfirmed_stop",))
    }


def test_an_orphaned_container_shows_it_is_still_running(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    publish(host.repo, "r1", retained=retain(run / "run-record.json", "r1", stopped=False))
    host.containers = [container("r1")]
    [view] = host.snapshot().running
    assert (view.run.stage, view.run.reasons) == (Stage.NEEDS_RECOVER, ("unconfirmed_stop",))
    assert view.run.container.running


# A run's cost switches to its record's once one exists


def test_a_recording_run_shows_its_records_cost_not_the_live_estimate(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    (run / "observations.events.jsonl").write_text(
        json.dumps(event("e1", "claude_code.api_request", {"cost_usd": "25"}, stamp=ms(NOW))) + "\n"
    )
    host.own(run)
    host.containers = [container("r1")]
    [view] = host.snapshot().running
    assert (view.cost, view.cost_recorded, view.cost_completeness) == (Decimal(25), False, None)
    retain(run / "run-record.json", "r1", cost="100", requests=[at(1, "100")])
    host.containers = []
    [view] = host.snapshot().running
    assert view.run.stage is Stage.RECORDING
    assert (view.cost, view.cost_recorded, view.cost_completeness) == (
        Decimal(100),
        True,
        "complete",
    )
    assert view.request_costs == ((ms(START + timedelta(minutes=1)), Decimal(100)),)
    # The execution is charged once, from its record: $100 at $25 per 1%.
    assert host.weekly().percent == pytest.approx(4.0)


def test_an_unpublished_or_unsettled_run_shows_its_records_cost(tmp_path):
    host = Host(tmp_path)
    retain(make_run(host.runs, "r1") / "run-record.json", "r1", cost="40", requests=[at(1, "40")])
    [view] = host.snapshot().running
    assert view.run.reasons == ("unpublished",)
    assert (view.cost, view.cost_recorded) == (Decimal(40), True)


def test_a_linked_recovery_supplies_the_recorded_cost(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    retain(run / "run-record.json", "r1", stopped=False, cost="10", completeness="partial")
    retain(run / "recovery-1/run-record.json", "r1-recovery-1", recovery_of="r1", cost="40")
    [view] = host.snapshot().running
    assert (view.cost, view.cost_completeness) == (Decimal(40), "complete")


def test_a_missing_recorded_cost_stays_missing(tmp_path):
    host = Host(tmp_path)
    retain(
        make_run(host.runs, "r1") / "run-record.json",
        "r1",
        cost=None,
        completeness="missing",
        requests=[],
    )
    [view] = host.snapshot().running
    assert (view.cost, view.cost_recorded, view.cost_completeness) == (None, True, "missing")


# Each execution and each logical request is charged once


def test_an_original_and_its_linked_recovery_charge_their_execution_once(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", stopped=False, requests=[at(1, "25")])
    assert host.weekly().percent == pytest.approx(1.0)
    publish(host.repo, "r1-recovery-1", recovery_of="r1", requests=[at(1, "25")])
    assert host.weekly().percent == pytest.approx(1.0)


def test_a_recovery_replaces_its_originals_partial_measurements(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", stopped=False, completeness="partial", requests=[at(1, "10")])
    publish(host.repo, "r1-recovery-1", recovery_of="r1", requests=[at(1, "10"), at(2, "40")])
    assert host.weekly().percent == pytest.approx(2.0)


def test_a_recovery_published_while_monitoring_never_charges_twice(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    original = retain(run / "run-record.json", "r1", stopped=False, requests=[at(1, "25")])
    publish(host.repo, "r1", retained=original)
    assert host.weekly().percent == pytest.approx(1.0)
    recovered = retain(
        run / "recovery-1/run-record.json",
        "r1-recovery-1",
        recovery_of="r1",
        requests=[at(1, "25")],
    )
    assert host.weekly().percent == pytest.approx(1.0)
    publish(host.repo, "r1-recovery-1", retained=recovered)
    snapshot = host.snapshot()
    assert snapshot.running == []
    assert snapshot.profiles[0].weekly.percent == pytest.approx(1.0)


def test_excluded_and_distinct_executions_each_count(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", requests=[at(1, "25")])
    publish(host.repo, "r2", requests=[at(2, "25")])
    write_exclusion(
        host.repo,
        Exclusion(
            "r1", CANDIDATE_HASH, "pilot", "a pilot", "operator", None, "op", NOW.isoformat()
        ),
    )
    assert host.weekly().percent == pytest.approx(2.0)


def test_a_repeated_claude_request_is_charged_once_and_a_disagreement_is_flagged(tmp_path):
    lines = [
        event("e1", "claude_code.api_request", {"request_id": "req_1", "cost_usd": "25"}),
        event("e2", "claude_code.api_request", {"request_id": "req_1", "cost_usd": "25"}),
        event("e3", "claude_code.api_request", {"request_id": "req_1", "cost_usd": "30"}),
        event("e4", "claude_code.api_request", {"request_id": "req_2", "cost_usd": "5"}),
        # Without a request id, each event is its own request.
        event("e5", "claude_code.api_request", {"cost_usd": "1"}),
        event("e6", "claude_code.api_request", {"cost_usd": "1"}),
    ]
    (tmp_path / "observations.events.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in lines)
    )
    cost = ProvisionalCost(tmp_path, "claude")
    cost.update()
    assert (cost.total, cost.conflicts, len(cost.requests)) == (Decimal(32), 1, 4)


# Only this host's records charge its Login Profiles


def test_another_hosts_identically_named_profile_is_not_this_one(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "theirs", host="host-b", usage=claude_usage(80.0), requests=[at(1, "50")])
    weekly = host.weekly()
    assert (weekly.percent, weekly.reading) == (0.0, None)
    # The record stays in history.
    assert [run.run_id for run in host.monitor.history()] == ["theirs"]


def test_a_record_without_host_provenance_is_never_guessed_local(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "unknown", host=None, requests=[at(1, "50")])
    assert host.weekly().percent == 0.0
    assert host.snapshot().host_label == "host-a"


def test_a_record_retained_in_this_hosts_run_directory_is_this_hosts(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    publish(host.repo, "r1", retained=retain(run / "run-record.json", "r1", host=None))
    assert host.snapshot().running == []
    assert host.weekly().percent == pytest.approx(1.5 / 25)


def test_the_host_label_falls_back_to_the_hostname(tmp_path):
    host = Host(tmp_path, label=None, hostname=lambda: "host-a.lan")
    publish(host.repo, "mine", requests=[at(1, "25")])
    publish(host.repo, "theirs", host="host-b", requests=[at(2, "25")])
    assert host.snapshot().host_label == "host-a"
    assert host.weekly().percent == pytest.approx(1.0)


def test_an_invalid_host_label_counts_no_history(tmp_path):
    host = Host(tmp_path, label="not a label")
    publish(host.repo, "mine", requests=[at(1, "25")])
    assert host.snapshot().host_label is None
    assert host.weekly().percent == 0.0


def test_a_same_host_record_from_before_pools_charges_its_adopted_profile(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "legacy", login="bare-claude-opus", requests=[at(1, "25")])
    publish(host.repo, "elsewhere", login="bare-claude-opus", host="host-b", requests=[at(2, "25")])
    assert host.weekly().percent == pytest.approx(1.0)


# An untimed reading's age is only bounded


def untimed(percent, stopped, resets):
    return UsageReading("claude", percent, 10080, resets, None, stopped)


def test_an_untimed_reading_is_approximate_and_its_age_a_lower_bound():
    stopped = NOW - timedelta(hours=2)
    resets = NOW + timedelta(days=2)
    # A request before the stop may follow the reading, but it cannot be placed.
    costs = [(ms(stopped - timedelta(minutes=5)), Decimal(25))]
    weekly = weekly_usage(PROFILE, "claude", RATES, [untimed(30.0, stopped, resets)], costs, NOW)
    assert (weekly.percent, weekly.estimated, weekly.reading_age_exact) == (30.0, True, False)
    assert weekly.reading_age(NOW) == timedelta(hours=2)


def test_a_live_reading_wins_over_its_untimed_retained_copy():
    observed = NOW - timedelta(hours=3)
    resets = NOW + timedelta(days=2)
    live = UsageReading("claude", 30.0, 10080, resets, observed)
    copy = untimed(30.0, NOW - timedelta(hours=2), resets)
    weekly = weekly_usage(PROFILE, "claude", RATES, [copy, live], [], NOW)
    assert (weekly.percent, weekly.estimated, weekly.reading_age_exact) == (30.0, False, True)
    assert weekly.reading_age(NOW) == timedelta(hours=3)


# Directory and container observations of one run join by its canonical path


def owned_table(tmp_path, *run_dirs):
    with contextlib.ExitStack() as stack:
        for run_dir in run_dirs:
            stack.enter_context(run_lock(run_dir))
        return held_locks(proc_locks(tmp_path))


def rows(found):
    return [(run.run_id, run.stage, run.container is not None) for run in found]


@pytest.mark.parametrize("root", ["absolute", "relative", "linked"])
@pytest.mark.parametrize("owned", [True, False])
def test_each_physical_run_is_one_row_however_its_root_is_named(tmp_path, monkeypatch, root, owned):
    real = tmp_path / "real-runs"
    run = make_run(real, "r1")
    table = owned_table(tmp_path, *([run] if owned else []))
    if root == "relative":
        monkeypatch.chdir(tmp_path)
        runs = Path("real-runs")
    elif root == "linked":
        runs = tmp_path / "runs-link"
        runs.symlink_to(real, target_is_directory=True)
    else:
        runs = real
    # The runner resolves its paths before launch, so Docker names the real directory.
    found = live_runs(runs, [container("r1", run_dir=run)], table)
    stage = Stage.RUNNING if owned else Stage.NEEDS_RECOVER
    assert rows(found) == [("r1", stage, True)]
    assert found[0].container.running


@pytest.mark.parametrize("owned", [True, False])
def test_a_run_outside_the_root_is_still_found_once_through_its_container(tmp_path, owned):
    runs = tmp_path / "runs"
    make_run(runs, "r1")
    elsewhere = make_run(tmp_path / "elsewhere", "r9")
    table = owned_table(tmp_path, *([elsewhere] if owned else []))
    found = live_runs(runs, [container("r9", run_dir=elsewhere)], table)
    stage = Stage.RUNNING if owned else Stage.NEEDS_RECOVER
    assert sorted(rows(found), key=str) == [
        ("r1", Stage.NEEDS_RECOVER, False),
        ("r9", stage, True),
    ]


def test_a_linked_child_run_directory_is_still_not_listed(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    target = make_run(tmp_path / "elsewhere", "r1")
    (runs / "r1").symlink_to(target, target_is_directory=True)
    assert live_runs(runs, [], owned_table(tmp_path)) == []


def test_an_unavailable_run_root_or_container_path_never_fails_the_listing(tmp_path):
    missing = tmp_path / "no-such-runs"
    bogus = container("r1", run_dir=Path("/no/such/place/r1"))
    assert rows(live_runs(missing, [bogus], owned_table(tmp_path))) == [
        ("r1", Stage.NEEDS_RECOVER, True)
    ]


def test_a_linked_run_root_counts_one_live_run_in_a_snapshot(tmp_path):
    host = Host(tmp_path)
    real = tmp_path / "real-runs"
    run = make_run(real, "r1")
    host.runs.rmdir()
    host.runs.symlink_to(real, target_is_directory=True)
    host.own(run)
    host.containers = [container("r1", run_dir=run)]
    snapshot = host.snapshot()
    assert [(view.run.run_id, view.run.stage) for view in snapshot.running] == [
        ("r1", Stage.RUNNING)
    ]
    assert snapshot.counts.live == 1


# Only validated records charge spend or anchor usage


def test_a_record_missing_its_scores_stays_in_history_but_charges_nothing(tmp_path):
    host = Host(tmp_path)
    directory = publish(host.repo, "r1", usage=claude_usage(60.0), requests=[at(1, "25")])
    scores = (directory / "scores.json").read_text()
    (directory / "scores.json").unlink()
    weekly = host.weekly()
    assert (weekly.percent, weekly.reading) == (0.0, None)
    assert [run.run_id for run in host.monitor.history()] == ["r1"]
    # The same record becomes readable on a later refresh and then anchors the usage.
    (directory / "scores.json").write_text(scores)
    weekly = host.weekly()
    assert (weekly.percent, weekly.reading.utilization_percent) == (60.0, 60.0)


def test_a_misfiled_record_charges_nothing(tmp_path):
    host = Host(tmp_path)
    directory = publish(host.repo, "r1", requests=[at(1, "25")])
    misfiled = host.repo / "results" / OTHER_HASH / "r1"
    misfiled.parent.mkdir(parents=True)
    shutil.move(directory, misfiled)
    assert host.weekly().percent == 0.0
    assert [run.run_id for run in host.monitor.history()] == ["r1"]


def test_a_record_with_an_invalid_candidate_identity_charges_nothing(tmp_path):
    host = Host(tmp_path)
    directory = publish(host.repo, "r1", requests=[at(1, "25")])
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["candidate"] = OTHER_IDENTITY
    (directory / "manifest.json").write_text(json.dumps(manifest))
    assert host.weekly().percent == 0.0


def test_an_invalid_recovery_never_replaces_its_valid_original(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    original = retain(
        run / "run-record.json", "r1", stopped=False, cost="25", requests=[at(1, "25")]
    )
    publish(host.repo, "r1", retained=original)
    recovery = publish(
        host.repo, "r1-recovery-1", recovery_of="r1", cost="2500", requests=[at(1, "2500")]
    )
    (recovery / "scores.json").unlink()
    snapshot = host.snapshot()
    [view] = snapshot.running
    assert (view.run.stage, view.cost) == (Stage.NEEDS_RECOVER, Decimal(25))
    # The profile charges the same record the run's own view shows: $25 at $25 per 1%.
    assert snapshot.profiles[0].weekly.percent == pytest.approx(1.0)


def test_a_history_only_original_and_invalid_recovery_charge_the_original(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", stopped=False, requests=[at(1, "25")])
    recovery = publish(host.repo, "r1-recovery-1", recovery_of="r1", requests=[at(1, "2500")])
    (recovery / "scores.json").unlink()
    assert host.weekly().percent == pytest.approx(1.0)


# A reading seen live outlives the run that saw it


def stdout_with_reading(fraction, minute):
    """``docker logs`` stdout carrying one weekly reading, logged at 11:``minute``."""
    line = json.dumps(claude_event(fraction)).encode()
    return b"2026-10-07T11:%02d:00.000000000Z " % minute + line + b"\n"


class Followers:
    """A fake ``docker logs`` per run container, each emitting its configured stdout."""

    def __init__(self):
        self.stdout: dict[str, bytes] = {}

    def __call__(self, arguments, **kwargs):
        return FakeProcess(self.stdout.get(arguments[-1], b""), b"")


def settle(host, expected):
    """Snapshot until the background followers have delivered their lines."""
    deadline = time.monotonic() + 5
    while True:
        weekly = host.weekly()
        if weekly.percent == pytest.approx(expected) or time.monotonic() > deadline:
            return weekly
        time.sleep(0.02)


def live_cost(run, usd, moment):
    line = event("e-" + run.name, "claude_code.api_request", {"cost_usd": usd}, stamp=ms(moment))
    (run / "observations.events.jsonl").write_text(json.dumps(line) + "\n")


def test_a_timed_reading_survives_its_run_finishing(tmp_path):
    followers = Followers()
    host = Host(tmp_path, popen=followers)
    run = make_run(host.runs, "r1")
    spent = NOW - timedelta(minutes=10)
    followers.stdout["sq-run-r1"] = stdout_with_reading(0.30, 30)
    live_cost(run, "25", spent)
    host.own(run)
    host.containers = [container("r1")]
    # Running: the live 30% reading at 11:30 plus the $25 after it.
    weekly = settle(host, 31.0)
    assert (weekly.percent, weekly.reading_age_exact) == (pytest.approx(31.0), True)

    # Recording: the record keeps only an untimed copy of the same reading.
    usage = claude_usage(30.0, resets="2026-10-08T14:00:00Z")
    record = retain(run / "run-record.json", "r1", usage=usage, requests=[(spent, "25")])
    host.containers = []
    assert host.snapshot().running[0].run.stage is Stage.RECORDING
    weekly = host.weekly()
    assert (weekly.percent, weekly.reading_age_exact) == (pytest.approx(31.0), True)

    # Finished, before history is refreshed and after: the observation time is not lost.
    publish(host.repo, "r1", retained=record)
    host.release()
    snapshot = host.monitor.snapshot()
    assert snapshot.running == []
    weekly = snapshot.profiles[0].weekly
    assert (weekly.percent, weekly.reading_age_exact) == (pytest.approx(31.0), True)
    assert weekly.reading_age(NOW) == timedelta(minutes=30)
    weekly = host.weekly()
    assert (weekly.percent, weekly.reading_age_exact) == (pytest.approx(31.0), True)


def test_the_next_run_keeps_then_replaces_the_retained_reading_until_it_expires(tmp_path):
    followers = Followers()
    host = Host(tmp_path, popen=followers)
    first = make_run(host.runs, "r1")
    followers.stdout["sq-run-r1"] = stdout_with_reading(0.30, 30)
    host.own(first)
    host.containers = [container("r1")]
    settle(host, 30.0)
    publish(host.repo, "r1", retained=retain(first / "run-record.json", "r1", requests=[]))
    host.release()
    host.containers = []
    assert host.weekly().percent == pytest.approx(30.0)

    # The next run on the profile has no reading of its own, so the kept one still anchors.
    second = make_run(host.runs, "r2")
    live_cost(second, "25", NOW - timedelta(minutes=5))
    host.own(second)
    host.containers = [container("r2")]
    assert host.weekly().percent == pytest.approx(31.0)
    publish(host.repo, "r2", retained=retain(second / "run-record.json", "r2", requests=[]))
    host.release()
    host.containers = []
    host.weekly()

    # A genuinely newer reading replaces it; spend before that reading is inside it.
    third = make_run(host.runs, "r3")
    followers.stdout["sq-run-r3"] = stdout_with_reading(0.40, 58)
    host.own(third)
    host.containers = [container("r3")]
    weekly = settle(host, 40.0)
    assert weekly.reading.observed_at == NOW - timedelta(minutes=2)

    # Past its reset the reading anchors nothing but the spend since the reset.
    host.release()
    host.containers = []
    host.now = datetime.fromisoformat("2026-10-08T15:00:00+00:00")
    weekly = host.weekly()
    assert (weekly.reading, weekly.estimated) == (None, True)
    # A window past that it is dropped, and the last seven days count.
    host.now = datetime.fromisoformat("2026-10-15T15:00:00+00:00")
    assert (host.weekly().percent, host.weekly().reading) == (0.0, None)
