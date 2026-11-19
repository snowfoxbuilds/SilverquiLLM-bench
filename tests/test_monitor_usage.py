"""The Estimated Weekly Usage estimator the monitor shares with the host's Usage Limit check
(RUN-MONITORING.md, Estimated Weekly Usage): a process without a monitor gets the figure the
monitor shows from the same records, run directories and readings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from silverquillm.monitor.estimates import newest_reading
from silverquillm.monitor.history import UsageReading
from silverquillm.monitor.usage import estimate_profile_usage

from .test_monitor import NOW, make_run, publish, retain
from .test_monitor_records import PROFILE, RATES, Host, at, claude_usage, fable_run, live_cost


def estimate(host: Host, *, readings=(), login=PROFILE):
    return estimate_profile_usage(
        login,
        "claude",
        rates=RATES,
        host_label="host-a",
        state_root=host.state,
        runs_dir=host.runs,
        results_repo=host.repo,
        readings=readings,
        now=host.now,
        proc_locks=host.locks,
    )


def figures(usage):
    return [
        None if window is None else (pytest.approx(window.percent), window.estimated)
        for window in (usage.weekly, usage.fable)
    ]


def monitor_figures(host: Host):
    [profile] = host.snapshot().profiles
    return [
        None if window is None else (pytest.approx(window.percent), window.estimated)
        for window in (profile.weekly, profile.fable)
    ]


def test_published_records_give_the_monitors_figure(tmp_path):
    host = Host(tmp_path)
    usage = claude_usage(40.0, resets="2026-10-08T14:00:00Z")
    usage["fable"] = {**usage["value"], "utilization_percent": 88.0}
    publish(host.repo, "r1", usage=usage, requests=[])
    publish(host.repo, "r2", requests=[at(60 * 24, "25")])
    publish(host.repo, "theirs", host="host-b", requests=[at(60 * 24, "50")])
    found = estimate(host)
    assert figures(found) == monitor_figures(host)
    assert found.weekly.percent == pytest.approx(41.0)
    assert found.fable.percent == pytest.approx(88.0)


def test_an_unrecorded_runs_provisional_spend_counts(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r0", usage=claude_usage(20.0, resets="2026-10-08T14:00:00Z"), requests=[])
    run = make_run(host.runs, "r1")
    live_cost(run, "50", NOW - timedelta(minutes=5))
    host.own(run, login=True)
    found = estimate(host)
    assert figures(found) == monitor_figures(host)
    assert found.weekly.percent == pytest.approx(22.0)


def test_a_fable_runs_spend_counts_against_the_fable_limit_too(tmp_path):
    host = Host(tmp_path)
    usage = claude_usage(40.0, resets="2026-10-08T14:00:00Z")
    usage["fable"] = {**usage["value"], "utilization_percent": 80.0}
    publish(host.repo, "r0", usage=usage, requests=[])
    run = fable_run(host.runs, "r1")
    live_cost(run, "25", NOW - timedelta(minutes=5))
    host.own(run, login=True)
    found = estimate(host)
    assert figures(found) == monitor_figures(host)
    assert (found.weekly.percent, found.fable.percent) == (
        pytest.approx(41.0),
        pytest.approx(81.0),
    )


def test_a_locally_retained_record_counts_once(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    publish(host.repo, "r1", retained=retain(run / "run-record.json", "r1", host=None))
    found = estimate(host)
    assert figures(found) == monitor_figures(host)
    assert found.weekly.percent == pytest.approx(1.5 / 25)


def test_a_callers_reading_anchors_the_estimate(tmp_path):
    """A runner passes the reading of the run it just ended, which no record holds yet."""
    host = Host(tmp_path)
    publish(host.repo, "r0", usage=claude_usage(20.0, resets="2026-10-08T14:00:00Z"), requests=[])
    resets = datetime(2026, 10, 9, 14, 0, tzinfo=UTC)
    reading = UsageReading("claude", 70.0, 10080, resets, NOW - timedelta(minutes=1))
    found = estimate(host, readings=[reading])
    assert (found.weekly.percent, found.weekly.estimated) == (70.0, False)
    assert found.weekly_reading == reading and found.fable_reading is None


def test_no_rate_means_no_estimate(tmp_path):
    host = Host(tmp_path)
    found = estimate_profile_usage(
        PROFILE,
        "claude",
        rates={"codex": Decimal(5)},
        host_label="host-a",
        state_root=host.state,
        runs_dir=host.runs,
        results_repo=host.repo,
        now=host.now,
        proc_locks=host.locks,
    )
    assert found.weekly is None and found.fable is None


def test_the_newest_reading_is_kept_after_its_reset_passes(tmp_path):
    """The Usage Limit projects the next reset from it, while the estimate no longer starts
    from it."""
    host = Host(tmp_path)
    publish(host.repo, "r0", usage=claude_usage(90.0, resets="2026-10-07T00:00:00Z"), requests=[])
    found = estimate(host)
    assert found.weekly.reading is None
    assert found.weekly_reading.resets_at == datetime(2026, 10, 7, tzinfo=UTC)


def test_newest_reading_prefers_a_live_reading_over_its_untimed_copy():
    resets = datetime(2026, 10, 9, tzinfo=UTC)
    live = UsageReading("claude", 30.0, 10080, resets, NOW - timedelta(hours=2))
    copy = UsageReading("claude", 30.0, 10080, resets, None, NOW - timedelta(hours=1))
    older = UsageReading("claude", 10.0, 10080, resets, NOW - timedelta(hours=3))
    assert newest_reading("claude", [copy, live, older]) == live
    assert newest_reading("codex", [copy, live]) is None
    assert newest_reading("claude", [live], "fable") is None
