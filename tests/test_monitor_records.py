"""How the monitor reads Run Records (RUN-MONITORING.md): which records make a run Finished,
which execution each record's spend belongs to, and whose Login Profile it charges."""

from __future__ import annotations

import contextlib
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from silverquillm.karn.exclusions import Exclusion, write_exclusion
from silverquillm.karn.execution import run_lock
from silverquillm.monitor import Monitor, Stage
from silverquillm.monitor.costs import ProvisionalCost
from silverquillm.monitor.estimates import weekly_usage
from silverquillm.monitor.history import UsageReading

from .test_monitor import (
    CANDIDATE_HASH,
    NOW,
    OTHER_HASH,
    START,
    container,
    enroll_slot,
    event,
    make_run,
    ms,
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

    def __init__(self, tmp_path: Path, *, label: str | None = "host-a", hostname=None):
        self.tmp_path = tmp_path
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
                clock=lambda: NOW,
                follow_output=False,
                hostname=self.hostname,
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
