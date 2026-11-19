"""Usage Limits: the store, `login limit`, the check and where it runs (KARN-BENCHMARK-CONTRACT.md,
Subscription authentication)."""

from __future__ import annotations

import fcntl
import io
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.host_config import HostConfig
from silverquillm.karn import execution, recovery, usage_limit
from silverquillm.karn.cooldowns import add_cooldown as schedule_cooldown
from silverquillm.karn.cooldowns import cooldown, read_schedule
from silverquillm.karn.definition import KarnError
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.host import DockerHost
from silverquillm.karn.usage_limit import (
    LIMIT_FILE,
    UsageLimit,
    apply_limit,
    check_usage_limit,
    clear_limit,
    due_cooldowns,
    next_reset,
    read_limit,
    run_readings,
    set_limit,
)
from silverquillm.monitor import usage as monitor_usage
from silverquillm.monitor.estimates import WeeklyUsage
from silverquillm.monitor.headless import _login
from silverquillm.monitor.history import FABLE, WEEKLY, UsageReading
from silverquillm.monitor.pools import login_profiles
from silverquillm.monitor.snapshot import ProfileView
from silverquillm.monitor.usage import ProfileUsage

from .grader_fixtures import local_grader
from .test_karn_host import FakeDocker
from .test_karn_lifecycle import (
    DyingHost,
    SessionDocker,
    die_after_start,
    grade_locally,
    pool_slot,
)
from .test_karn_subscription_usage import UsageSessionDocker, codex_line, login_common
from .test_monitor import make_run, publish, retain
from .test_monitor_records import PROFILE, RATES, Host, claude_usage

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
RESET = datetime(2026, 10, 9, 0, 0, tzinfo=UTC)
CONFIG = HostConfig(Path("/nonexistent/config.toml"), False, usage_rates=RATES, host_label="host-a")
PLUGIN_SDK = pytest.mark.skipif(
    sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13"
)


@pytest.fixture(autouse=True)
def _grade_without_docker(monkeypatch):
    grade_locally(monkeypatch)


def reading(percent=50.0, resets=RESET, window=WEEKLY):
    return UsageReading("claude", percent, 10080, resets, NOW - timedelta(hours=1), window=window)


def usage(weekly=None, fable=None, *, weekly_reading=None, fable_reading=None):
    def figure(percent, source):
        return None if percent is None else WeeklyUsage(PROFILE, percent, False, source)

    return ProfileUsage(
        figure(weekly, weekly_reading), figure(fable, fable_reading), weekly_reading, fable_reading
    )


# The store -----------------------------------------------------------------------


def test_a_limit_round_trips_with_either_ceiling(tmp_path):
    set_limit(tmp_path, usage_limit.usage_limit(80), now=NOW)
    assert read_limit(tmp_path) == UsageLimit(80.0, None)
    set_limit(tmp_path, usage_limit.usage_limit(None, 90.5), now=NOW)
    assert read_limit(tmp_path) == UsageLimit(None, 90.5)
    document = json.loads((tmp_path / LIMIT_FILE).read_text())
    assert document == {
        "format": 1,
        "weekly_percent": None,
        "fable_percent": 90.5,
        "set_at": "2026-10-07T12:00:00Z",
    }
    assert oct((tmp_path / LIMIT_FILE).stat().st_mode & 0o777) == "0o600"
    assert clear_limit(tmp_path) is True
    assert clear_limit(tmp_path) is False
    assert read_limit(tmp_path) is None


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"format": 2, "weekly_percent": 80}',
        '{"format": 1, "weekly_percent": 0}',
        '{"format": 1, "weekly_percent": 101}',
        '{"format": 1, "weekly_percent": true}',
        '{"format": 1}',
        "[]",
    ],
)
def test_an_unreadable_limit_is_no_limit(tmp_path, content):
    (tmp_path / LIMIT_FILE).write_text(content)
    assert read_limit(tmp_path) is None


def test_a_linked_limit_is_never_followed(tmp_path):
    target = tmp_path / "elsewhere.json"
    target.write_text('{"format": 1, "weekly_percent": 80}')
    (tmp_path / LIMIT_FILE).symlink_to(target)
    assert read_limit(tmp_path) is None


@pytest.mark.parametrize(
    ("weekly", "fable"), [(None, None), (0, None), (-5, None), (100.5, None), (float("nan"), 50)]
)
def test_a_ceiling_outside_0_to_100_is_refused(weekly, fable):
    with pytest.raises(KarnError):
        usage_limit.usage_limit(weekly, fable)


# The next reset --------------------------------------------------------------------


def test_the_next_reset_is_the_readings_own_while_it_is_to_come():
    assert next_reset(reading(resets=RESET), NOW) == RESET


@pytest.mark.parametrize(
    ("passed", "expected"),
    [
        (timedelta(hours=2), timedelta(days=7) - timedelta(hours=2)),
        (timedelta(days=7), timedelta(days=7)),
        (timedelta(days=15), timedelta(days=6)),
    ],
)
def test_a_passed_reset_moves_on_in_seven_day_steps(passed, expected):
    assert next_reset(reading(resets=NOW - passed), NOW) == NOW + expected


def test_with_no_reading_the_window_lasts_seven_days():
    assert next_reset(None, NOW) == NOW + timedelta(days=7)


# What the limit asks for -----------------------------------------------------------


def test_the_weekly_ceiling_trips_at_or_above_it_until_the_next_reset():
    limit = UsageLimit(80.0, None)
    assert due_cooldowns(limit, usage(79.9, weekly_reading=reading()), now=NOW) == []
    [due] = due_cooldowns(limit, usage(80.0, weekly_reading=reading()), now=NOW)
    assert (due.start, due.end, due.scope, due.source) == (NOW, RESET, "all", "usage-limit")


def test_the_fable_ceiling_holds_back_only_fable_runs_until_its_own_reset():
    fable_reset = RESET + timedelta(hours=3)
    found = due_cooldowns(
        UsageLimit(80.0, 90.0),
        usage(50.0, 95.0, weekly_reading=reading(), fable_reading=reading(resets=fable_reset)),
        now=NOW,
    )
    assert [(c.scope, c.end) for c in found] == [("fable", fable_reset)]


def test_without_an_estimate_a_limit_never_trips():
    assert due_cooldowns(UsageLimit(1.0, 1.0), usage(), now=NOW) == []


def test_a_reset_beyond_the_horizon_holds_for_seven_days_and_keeps_the_other_trip():
    fable_reset = RESET + timedelta(hours=3)
    far = reading(resets=datetime(2099, 1, 1, tzinfo=UTC))
    found = due_cooldowns(
        UsageLimit(80.0, 90.0),
        usage(90.0, 95.0, weekly_reading=far, fable_reading=reading(resets=fable_reset)),
        now=NOW,
    )
    assert [(c.scope, c.end) for c in found] == [
        ("all", NOW + timedelta(days=7)),
        ("fable", fable_reset),
    ]


def test_a_cooldown_that_cannot_be_built_never_stops_the_others(monkeypatch):
    build = usage_limit.cooldown

    def refuse_every_run(*args, scope, **kwargs):
        if scope == "all":
            raise KarnError("cooldown_ends_before_it_starts")
        return build(*args, scope=scope, **kwargs)

    monkeypatch.setattr(usage_limit, "cooldown", refuse_every_run)
    found = due_cooldowns(
        UsageLimit(80.0, 90.0),
        usage(90.0, 95.0, weekly_reading=reading(), fable_reading=reading(window=FABLE)),
        now=NOW,
    )
    assert [c.scope for c in found] == ["fable"]


def test_a_trip_is_written_once_while_its_cooldown_is_in_force(tmp_path):
    figures = usage(90.0, 95.0, weekly_reading=reading(), fable_reading=reading(window=FABLE))
    written = apply_limit(tmp_path, UsageLimit(80.0, 90.0), figures, now=NOW)
    assert sorted(c.scope for c in written) == ["all", "fable"]
    assert apply_limit(tmp_path, UsageLimit(80.0, 90.0), figures, now=NOW) == []
    assert len(read_schedule(tmp_path, now=NOW)) == 2


def test_an_operators_cooldown_does_not_stand_in_for_a_trip(tmp_path):
    schedule_cooldown(tmp_path, cooldown(NOW, RESET, now=NOW), now=NOW)
    written = apply_limit(
        tmp_path, UsageLimit(80.0), usage(90.0, weekly_reading=reading()), now=NOW
    )
    assert [c.source for c in written] == ["usage-limit"]


def test_a_trip_keeps_the_rest_of_the_schedule(tmp_path):
    later = cooldown(RESET, RESET + timedelta(days=1), now=NOW, note="Sean's week")
    schedule_cooldown(tmp_path, later, now=NOW)
    apply_limit(tmp_path, UsageLimit(80.0), usage(90.0, weekly_reading=reading()), now=NOW)
    assert later in read_schedule(tmp_path, now=NOW)


# A run's own readings --------------------------------------------------------------


def test_a_runs_measurement_gives_its_weekly_and_fable_readings():
    measurement = claude_usage(40.0, resets="2026-10-09T00:00:00Z")
    measurement["fable"] = {**measurement["value"], "utilization_percent": 88.0}
    weekly, fable = run_readings(measurement, NOW)
    assert (weekly.window, weekly.utilization_percent, weekly.bound) == (WEEKLY, 40.0, NOW)
    assert (fable.window, fable.utilization_percent) == (FABLE, 88.0)


def test_a_missing_measurement_gives_no_reading():
    missing = {"completeness": "missing", "reasons": ["x"], "value": None}
    assert run_readings(missing, NOW) == []
    assert run_readings(None, NOW) == []


# The check against this host's estimate -------------------------------------------


def check(host, login=PROFILE, **extra):
    return check_usage_limit(
        host.login,
        login,
        "claude",
        state_root=host.state,
        runs_dir=host.runs,
        results_repo=host.repo,
        now=host.now,
        config=CONFIG,
        **extra,
    )


def test_the_check_trips_on_the_estimate_the_monitor_shows(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", usage=claude_usage(85.0, resets="2026-10-09T00:00:00Z"), requests=[])
    set_limit(host.login, UsageLimit(80.0), now=NOW)
    [written] = check(host)
    assert (written.end, written.source) == (RESET, "usage-limit")
    [profile] = host.snapshot().profiles
    assert profile.weekly.percent >= 80.0
    assert profile.status.cooldown_until == RESET


def test_the_runs_own_reading_counts_before_any_record_holds_it(tmp_path):
    host = Host(tmp_path)
    set_limit(host.login, UsageLimit(80.0), now=NOW)
    assert check(host) == []
    [written] = check(host, readings=[reading(81.0)])
    assert written.end == RESET


def test_another_hosts_records_never_trip_this_hosts_profile(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", host="host-b", usage=claude_usage(99.0), requests=[])
    set_limit(host.login, UsageLimit(80.0), now=NOW)
    assert check(host) == []


def test_a_bare_slot_name_finds_the_records_filed_under_its_profile(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", usage=claude_usage(85.0, resets="2026-10-09T00:00:00Z"), requests=[])
    set_limit(host.login, UsageLimit(80.0), now=NOW)
    [written] = check(host, login="bare-claude-opus")
    assert written.end == RESET


def test_a_profile_without_a_limit_makes_no_estimate(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("estimated without a limit")

    monkeypatch.setattr("silverquillm.monitor.usage.estimate_profile_usage", refuse)
    assert check(Host(tmp_path)) == []


def test_a_failed_check_is_reported_not_raised(tmp_path, monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(usage_limit, "check_usage_limit", broken)
    set_limit(tmp_path, UsageLimit(80.0), now=NOW)
    usage_limit.check_quietly(tmp_path, PROFILE, "claude", state_root=tmp_path)
    assert "usage_limit_check_failed: OSError" in capsys.readouterr().err


def test_readings_that_cannot_be_gathered_are_reported_not_raised(tmp_path, capsys):
    def unreadable():
        raise ValueError("stdout gone")

    set_limit(tmp_path, UsageLimit(80.0), now=NOW)
    usage_limit.check_quietly(tmp_path, PROFILE, "claude", state_root=tmp_path, readings=unreadable)
    assert "usage_limit_check_failed: ValueError" in capsys.readouterr().err


def test_without_a_limit_the_runs_readings_are_never_gathered(tmp_path):
    def refuse():
        raise AssertionError("gathered without a limit")

    usage_limit.check_quietly(tmp_path, PROFILE, "claude", state_root=tmp_path, readings=refuse)


def tripping(host):
    publish(host.repo, "r1", usage=claude_usage(85.0, resets="2026-10-09T00:00:00Z"), requests=[])
    set_limit(host.login, UsageLimit(80.0), now=NOW)
    return {
        "state_root": host.state,
        "runs_dir": host.runs,
        "results_repo": host.repo,
        "now": NOW,
        "config": CONFIG,
    }


def test_a_stalled_schedule_writer_never_holds_up_the_check(tmp_path, monkeypatch, capsys):
    host = Host(tmp_path)
    arguments = tripping(host)
    monkeypatch.setattr(usage_limit, "SCHEDULE_WAIT", 0.2, raising=False)
    stalled = os.open(host.login / ".cooldowns.lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(stalled, fcntl.LOCK_EX)
    try:
        checking = threading.Thread(
            target=usage_limit.check_quietly,
            args=(host.login, PROFILE, "claude"),
            kwargs=arguments,
            daemon=True,
        )
        checking.start()
        checking.join(timeout=5)
        assert not checking.is_alive()
    finally:
        os.close(stalled)
        checking.join(timeout=5)
    assert "usage_limit_check_failed: cooldown_schedule_busy" in capsys.readouterr().err
    assert read_schedule(host.login, now=NOW) == []


class BrokenStderr(io.TextIOBase):
    def write(self, text):
        raise BrokenPipeError(32, "Broken pipe")


def test_a_failure_while_reporting_never_escapes_the_check(tmp_path, monkeypatch):
    host = Host(tmp_path)
    arguments = tripping(host)
    monkeypatch.setattr(sys, "stderr", BrokenStderr())
    usage_limit.check_quietly(host.login, PROFILE, "claude", **arguments)
    [held] = read_schedule(host.login, now=NOW)
    assert held.source == "usage-limit"


def test_the_monitors_write_sets_and_checks_one_profile(tmp_path, monkeypatch):
    host = Host(tmp_path)
    resets = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    publish(host.repo, "r1", usage=claude_usage(85.0, resets=resets), requests=[])
    monkeypatch.setenv("SILVERQUILLM_RESULTS_REPO", str(host.repo))
    monkeypatch.setenv("SILVERQUILLM_HOST_LABEL", "host-a")
    written = usage_limit.limit_profile(
        host.login,
        PROFILE,
        "claude",
        UsageLimit(80.0),
        state_root=host.state,
        now=datetime.now(UTC),
    )
    assert [c.source for c in written] == ["usage-limit"]
    assert read_limit(host.login) == UsageLimit(80.0)


def mislead(monkeypatch, tmp_path):
    """A process environment that names another Results Repo, holding a low reading, and
    another host label: a check that resolved its own would never trip."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    publish(elsewhere, "r9", usage=claude_usage(10.0), requests=[])
    monkeypatch.setenv("SILVERQUILLM_RESULTS_REPO", str(elsewhere))
    monkeypatch.setenv("SILVERQUILLM_HOST_LABEL", "host-b")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-config"))


def limit_as_shown(host, limit=None, **given):
    """``limit_profile`` given what the monitor estimated from, as ``top`` passes it."""
    return usage_limit.limit_profile(
        host.login,
        PROFILE,
        "claude",
        limit or UsageLimit(80.0),
        state_root=host.state,
        now=NOW,
        locations={"runs_dir": host.runs, "results_repo": host.repo, "bench_root": None},
        config=CONFIG,
        host_label="host-a",
        **given,
    )


def test_the_callers_locations_and_label_replace_the_hosts_own(tmp_path, monkeypatch):
    host = Host(tmp_path)
    mislead(monkeypatch, tmp_path)
    publish(host.repo, "r1", usage=claude_usage(85.0), requests=[])
    [written] = limit_as_shown(host)
    assert (written.end, written.scope) == (RESET, "all")


def test_a_run_directory_the_caller_names_counts_where_the_host_names_none(tmp_path, monkeypatch):
    host = Host(tmp_path)
    mislead(monkeypatch, tmp_path)
    run = make_run(host.runs, "r1")
    retain(run / "run-record.json", "r1", host=None, usage=claude_usage(85.0), requests=[])
    [written] = limit_as_shown(host)
    assert written.end == RESET


def test_a_newer_reading_the_caller_holds_outweighs_an_older_record_and_keeps_its_reset(
    tmp_path,
):
    host = Host(tmp_path)
    publish(host.repo, "r1", usage=claude_usage(10.0), requests=[])
    later = RESET + timedelta(hours=5)
    [written] = limit_as_shown(host, readings=[reading(85.0, resets=later)])
    assert written.end == later


def test_a_fable_reading_alone_holds_back_only_fable_runs_until_its_own_reset(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", usage=claude_usage(10.0), requests=[])
    fable_reset = RESET + timedelta(hours=3)
    held = reading(95.0, resets=fable_reset, window=FABLE)
    [written] = limit_as_shown(host, UsageLimit(80.0, 90.0), readings=[held])
    assert (written.scope, written.end) == ("fable", fable_reset)


def test_below_the_ceiling_or_with_no_reading_nothing_is_written(tmp_path):
    host = Host(tmp_path)
    assert limit_as_shown(host) == []
    assert limit_as_shown(host, readings=[reading(79.0)]) == []
    assert read_schedule(host.login, now=NOW) == []
    assert read_limit(host.login) == UsageLimit(80.0)


def test_a_bounded_wait_gives_up_on_a_held_schedule_and_keeps_the_limit(tmp_path):
    host = Host(tmp_path)
    publish(host.repo, "r1", usage=claude_usage(85.0), requests=[])
    kept = cooldown(RESET, RESET + timedelta(days=1), now=NOW, note="kept")
    schedule_cooldown(host.login, kept, now=NOW)
    stalled = os.open(host.login / ".cooldowns.lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(stalled, fcntl.LOCK_EX)
    try:
        started = time.monotonic()
        with pytest.raises(KarnError, match="cooldown_schedule_busy"):
            limit_as_shown(host, wait=0.3)
        assert time.monotonic() - started < 3
    finally:
        os.close(stalled)
    assert read_schedule(host.login, now=NOW) == [kept]
    assert read_limit(host.login) == UsageLimit(80.0)
    [written] = limit_as_shown(host, wait=0.3)
    assert written.source == "usage-limit"
    assert kept in read_schedule(host.login, now=NOW)


# `login limit` and the listings ----------------------------------------------------


def limit_command(host, *args, env=None):
    environ = {
        **host.environ,
        "SILVERQUILLM_RESULTS_REPO": str(host.repo),
        **(env or {}),
    }
    return CliRunner().invoke(
        main, ["login", "limit", "--state-root", str(host.state), *args], env=environ
    )


def test_login_limit_sets_lists_and_clears(tmp_path):
    host = Host(tmp_path)
    result = limit_command(host, "--agent", "claude", "--weekly", "80", "bare-claude-opus")
    assert result.exit_code == 0, result.output
    assert "karn-claude-login/bare-claude-opus: limit weekly 80%" in result.output
    assert read_limit(host.login) == UsageLimit(80.0, None)
    listed = CliRunner().invoke(main, ["login", "ls", "--state-root", str(host.state)])
    assert "limit weekly 80%" in listed.output
    result = limit_command(host, "--agent", "claude", "--clear", "--all")
    assert "limit removed" in result.output and read_limit(host.login) is None


def test_setting_a_limit_checks_it_at_once(tmp_path):
    host = Host(tmp_path)
    usage_now = claude_usage(85.0, resets=(datetime.now(UTC) + timedelta(days=2)).isoformat())
    publish(host.repo, "r1", usage=usage_now, requests=[])
    result = limit_command(host, "--agent", "claude", "--weekly", "80", "bare-claude-opus")
    assert result.exit_code == 0, result.output
    assert "limit reached; cooling down until" in result.output
    [held] = read_schedule(host.login)
    assert held.source == "usage-limit"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--agent", "claude", "bare-claude-opus"], "Pass --weekly, --fable or both"),
        (["--agent", "claude", "--clear", "--weekly", "5", "bare-claude-opus"], "--clear takes"),
        (["--agent", "claude", "--weekly", "5"], "Name the slots"),
        (["--agent", "claude", "--weekly", "500", "bare-claude-opus"], "invalid_usage_limit"),
        (["--agent", "claude", "--weekly", "5", "slot-9"], "Not enrolled"),
    ],
)
def test_login_limit_refuses_a_bad_request(tmp_path, args, message):
    host = Host(tmp_path)
    result = limit_command(host, *args)
    assert result.exit_code != 0 and message in result.output
    assert not (host.login / LIMIT_FILE).exists()


def test_only_the_claude_pool_takes_a_fable_ceiling(tmp_path):
    host = Host(tmp_path)
    result = limit_command(host, "--agent", "codex", "--fable", "50", "--all")
    assert result.exit_code != 0 and "Only the claude pool" in result.output


def test_top_json_carries_each_profiles_limit(tmp_path):
    host = Host(tmp_path)
    [status] = login_profiles(host.state, set(), now=NOW)
    document = _login(ProfileView(status, None, None, None))
    assert document["usage_limit"] == {"weekly_percent": None, "fable_percent": None}
    set_limit(host.login, UsageLimit(80.0, 90.0), now=NOW)
    [status] = login_profiles(host.state, set(), now=NOW)
    assert _login(ProfileView(status, None, None, None))["usage_limit"] == {
        "weekly_percent": 80.0,
        "fable_percent": 90.0,
    }


# Where the check runs --------------------------------------------------------------


class SoonResettingDocker(UsageSessionDocker):
    """Writes a weekly reading whose window resets in two days, as a live rollout would."""

    reset = int(time.time()) + 2 * 24 * 3600

    def command(self, *args, **kwargs):
        result = super().command(*args, **kwargs)
        if args[0] == "start":
            line = codex_line(
                7.0,
                timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                primary={"used_percent": 7.0, "window_minutes": 10080, "resets_at": self.reset},
            )
            rollout = Path(self.native) / "sessions" / f"rollout-{self.run_id}.jsonl"
            with rollout.open("a") as stream:
                stream.write(json.dumps(line) + "\n")
        return result


def lock_held(path: Path) -> bool:
    descriptor = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(descriptor)
    return False


@PLUGIN_SDK
def test_a_run_trips_its_profiles_limit_before_releasing_it(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    set_limit(pool_slot(state).directory, UsageLimit(5.0), now=NOW)
    host = DockerHost(
        docker=SoonResettingDocker(), plugin_cache=state / "plugins", plugin_python=sys.executable
    )
    checked_while_held = []
    check_quietly = execution.check_quietly

    def observed(directory, *args, **kwargs):
        checked_while_held.append(lock_held(Path(directory) / "runner.lock"))
        return check_quietly(directory, *args, **kwargs)

    monkeypatch.setattr(execution, "check_quietly", observed)
    at_release = []
    run_benchmark(
        **common,
        host=host,
        grader=local_grader(),
        on_login_released=lambda: at_release.extend(read_schedule(pool_slot(state).directory)),
    )
    assert checked_while_held == [True, False]
    [held] = at_release
    assert (held.scope, held.source) == ("all", "usage-limit")
    assert held.end == datetime.fromtimestamp(SoonResettingDocker.reset, UTC)


@PLUGIN_SDK
def test_a_failed_check_never_fails_the_run(tmp_path, monkeypatch, capsys):
    state, common = login_common(tmp_path)
    set_limit(pool_slot(state).directory, UsageLimit(5.0), now=NOW)

    def broken(*args, **kwargs):
        raise RuntimeError("history unreadable")

    monkeypatch.setattr(usage_limit, "check_usage_limit", broken)
    host = DockerHost(
        docker=SoonResettingDocker(), plugin_cache=state / "plugins", plugin_python=sys.executable
    )
    record = run_benchmark(**common, host=host, grader=local_grader())
    assert record.run_metadata["execution"]["status"] == "completed"
    assert "usage_limit_check_failed: RuntimeError" in capsys.readouterr().err
    assert read_schedule(pool_slot(state).directory) == []


@PLUGIN_SDK
def test_recovery_checks_the_limit_when_it_settles_the_login(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(5.0), now=NOW)
    with pytest.raises(SystemExit):
        run_benchmark(
            **common,
            run_id="run-a",
            host=die_after_start(
                DyingHost(
                    docker=SoonResettingDocker(),
                    plugin_cache=state / "plugins",
                    plugin_python=sys.executable,
                )
            ),
        )
    assert read_schedule(profile) == []
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    options_ = {key: common[key] for key in ("bench_root", "results_dir", "results_repo")}
    recovery.recover_benchmark(run_id="run-a", spec={}, state_root=state, **options_)
    [held] = read_schedule(profile)
    assert held.source == "usage-limit"


@PLUGIN_SDK
def test_a_failure_while_reporting_never_skips_the_login_block_in_recovery(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(5.0), now=NOW)
    with pytest.raises(SystemExit):
        run_benchmark(
            **common,
            run_id="run-a",
            host=die_after_start(
                DyingHost(
                    docker=SoonResettingDocker(),
                    plugin_cache=state / "plugins",
                    plugin_python=sys.executable,
                )
            ),
        )
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    check_quietly = recovery.check_quietly

    def reporting_fails(*args, **kwargs):
        with monkeypatch.context() as patch:
            patch.setattr(sys, "stderr", BrokenStderr())
            check_quietly(*args, **kwargs)

    monkeypatch.setattr(recovery, "check_quietly", reporting_fails)
    blocked = []
    block = recovery.block_if_relogin_needed

    def observed(*args, **kwargs):
        blocked.append(args[4])
        return block(*args, **kwargs)

    monkeypatch.setattr(recovery, "block_if_relogin_needed", observed)
    options_ = {key: common[key] for key in ("bench_root", "results_dir", "results_repo")}
    recovery.recover_benchmark(run_id="run-a", spec={}, state_root=state, **options_)
    assert blocked == ["run-a"]
    [held] = read_schedule(profile)
    assert held.source == "usage-limit"


def recorded(results_repo) -> bool:
    return any(Path(results_repo).glob("results/*/*/manifest.json"))


def spend_only_in_the_record(monkeypatch):
    """An estimate that sees no spend until a record is written and then spend over any
    ceiling, as when a run's spend reached only its native events, not its telemetry."""
    seen = []

    def estimate(login, provider, *, results_repo, readings, now, **kwargs):
        seen.append((recorded(results_repo), list(readings)))
        weekly = reading(resets=now + timedelta(days=2))
        return usage(100.0 if recorded(results_repo) else 0.0, weekly_reading=weekly)

    monkeypatch.setattr(monitor_usage, "estimate_profile_usage", estimate)
    return seen


def observed_estimates(monkeypatch):
    """Each estimate the checks make, and whether a record had been written when it was."""
    seen = []
    estimate = monitor_usage.estimate_profile_usage

    def observed(*args, **kwargs):
        found = estimate(*args, **kwargs)
        seen.append((recorded(kwargs["results_repo"]), found))
        return found

    monkeypatch.setattr(monitor_usage, "estimate_profile_usage", observed)
    return seen


def observed_writes(monkeypatch):
    writes = []
    apply = usage_limit.apply_limit

    def observed(*args, **kwargs):
        writes.append(apply(*args, **kwargs))
        return writes[-1]

    monkeypatch.setattr(usage_limit, "apply_limit", observed)
    return writes


def soon_resetting_host(state):
    return DockerHost(
        docker=SoonResettingDocker(), plugin_cache=state / "plugins", plugin_python=sys.executable
    )


@PLUGIN_SDK
def test_spend_only_in_the_record_trips_once_the_record_is_written(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(50.0), now=NOW)
    seen = spend_only_in_the_record(monkeypatch)
    at_release = []
    run_benchmark(
        **common,
        host=soon_resetting_host(state),
        grader=local_grader(),
        on_login_released=lambda: at_release.extend(read_schedule(profile)),
    )
    assert at_release == []
    assert [after_record for after_record, _ in seen] == [False, True]
    assert seen[1][1] == []
    [held] = read_schedule(profile)
    assert (held.scope, held.source) == ("all", "usage-limit")


@PLUGIN_SDK
def test_a_run_below_its_ceiling_writes_nothing_after_its_record(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(50.0), now=NOW)
    seen = observed_estimates(monkeypatch)
    run_benchmark(**common, host=soon_resetting_host(state), grader=local_grader())
    assert [after_record for after_record, _ in seen] == [False, True]
    assert seen[1][1].weekly.percent < 50.0
    assert read_schedule(profile) == []


@PLUGIN_SDK
def test_a_trip_before_release_is_not_written_again_after_the_record(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(5.0), now=NOW)
    seen = observed_estimates(monkeypatch)
    writes = observed_writes(monkeypatch)
    run_benchmark(**common, host=soon_resetting_host(state), grader=local_grader())
    assert [after_record for after_record, _ in seen] == [False, True]
    assert seen[1][1].weekly.percent >= 5.0
    [[tripped], again] = writes
    assert (tripped.scope, tripped.source, again) == ("all", "usage-limit", [])
    assert read_schedule(profile) == [tripped]


@PLUGIN_SDK
def test_a_failed_check_after_the_record_never_fails_the_run(tmp_path, monkeypatch, capsys):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(5.0), now=NOW)
    check = usage_limit.check_usage_limit
    calls = []

    def fails_after_the_record(*args, **kwargs):
        calls.append(recorded(kwargs["results_repo"]))
        if calls[-1]:
            raise RuntimeError("history unreadable")
        return check(*args, **kwargs)

    monkeypatch.setattr(usage_limit, "check_usage_limit", fails_after_the_record)
    record = run_benchmark(**common, host=soon_resetting_host(state), grader=local_grader())
    assert calls == [False, True]
    assert record.run_metadata["execution"]["status"] == "completed"
    assert recorded(common["results_repo"])
    assert "usage_limit_check_failed: RuntimeError" in capsys.readouterr().err
    [held] = read_schedule(profile)
    assert held.source == "usage-limit"


@PLUGIN_SDK
def test_recovery_checks_the_limit_again_once_its_record_is_written(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(50.0), now=NOW)
    with pytest.raises(SystemExit):
        run_benchmark(
            **common,
            run_id="run-a",
            host=die_after_start(
                DyingHost(
                    docker=SoonResettingDocker(),
                    plugin_cache=state / "plugins",
                    plugin_python=sys.executable,
                )
            ),
        )
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    seen = spend_only_in_the_record(monkeypatch)
    options_ = {key: common[key] for key in ("bench_root", "results_dir", "results_repo")}
    recovery.recover_benchmark(run_id="run-a", spec={}, state_root=state, **options_)
    assert [after_record for after_record, _ in seen] == [False, True]
    assert seen[1][1] == []
    [held] = read_schedule(profile)
    assert held.source == "usage-limit"


def test_nothing_here_writes_beside_the_schedule_and_the_limit(tmp_path):
    set_limit(tmp_path, UsageLimit(80.0), now=NOW)
    apply_limit(tmp_path, UsageLimit(80.0), usage(90.0, weekly_reading=reading()), now=NOW)
    assert sorted(os.listdir(tmp_path)) == [".cooldowns.lock", "cooldowns.json", LIMIT_FILE]


# ---- Spend the record will charge, seen before the profile is released ------------------


class NativeSpendDocker(SessionDocker):
    """A Codex run whose only spend is in its native journal: one priced request, no OTel
    cost event and no weekly reading, as when the telemetry missed it."""

    output_tokens = 60_000_000
    """$900 at gpt-5.4's $15 per million output tokens: 180% at the default $5 per 1%."""
    model = "gpt-5.4"

    def command(self, *args, **kwargs):
        result = super().command(*args, **kwargs)
        if args[0] == "start":
            now = datetime.now(UTC)

            def line(kind, payload, millis):
                stamp = (now + timedelta(milliseconds=millis)).isoformat(timespec="milliseconds")
                return {"type": kind, "timestamp": stamp.replace("+00:00", "Z"), "payload": payload}

            spent = {
                "input_tokens": 100,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": self.output_tokens,
                "reasoning_output_tokens": 0,
                "total_tokens": 100 + self.output_tokens,
            }
            rows = [
                line("event_msg", {"type": "task_started", "turn_id": "turn-1"}, 0),
                line("turn_context", {"model": self.model}, 1),
                line(
                    "token_usage_record",
                    {
                        "response_id": "response-" + self.run_id,
                        "thread_id": "thread-" + self.run_id,
                        "usage": spent,
                        "thread_token_usage": spent,
                        "turn_token_usage": spent,
                    },
                    5,
                ),
                line("event_msg", {"type": "task_complete", "turn_id": "turn-1"}, 10),
            ]
            rollout = Path(self.native) / "sessions" / f"rollout-{self.run_id}.jsonl"
            with rollout.open("a") as stream:
                stream.write("".join(json.dumps(row) + "\n" for row in rows))
        return result


class SmallSpendDocker(NativeSpendDocker):
    output_tokens = 1_000_000
    """$15: 3% at the default rate."""


class UnpricedSpendDocker(NativeSpendDocker):
    model = "future-model"


def native_host(state, docker=NativeSpendDocker, host=DockerHost):
    return host(docker=docker(), plugin_cache=state / "plugins", plugin_python=sys.executable)


@PLUGIN_SDK
def test_native_only_spend_over_the_ceiling_is_held_before_the_profile_is_released(
    tmp_path, monkeypatch
):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(80.0), now=NOW)
    seen = observed_estimates(monkeypatch)
    at_release = []
    record = run_benchmark(
        **common,
        host=native_host(state),
        grader=local_grader(),
        on_login_released=lambda: at_release.extend(read_schedule(profile)),
    )
    [held] = at_release
    assert (held.scope, held.source) == ("all", "usage-limit")
    before_release, after_record = seen
    assert before_release[0] is False
    assert before_release[1].weekly.percent == pytest.approx(180.0)
    assert after_record[1].weekly.percent == pytest.approx(before_release[1].weekly.percent)
    assert read_schedule(profile) == [held]
    costs = record.run_metadata["measurements"]["run_cost"]
    assert float(costs["value"]) == pytest.approx(900.0, rel=1e-3)


@PLUGIN_SDK
def test_native_only_spend_is_held_even_when_publication_fails(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(80.0), now=NOW)

    def unpublishable(*args, **kwargs):
        raise OSError("results repo unwritable")

    monkeypatch.setattr(execution, "write_record", unpublishable)
    at_release = []
    with pytest.raises(OSError):
        run_benchmark(
            **common,
            host=native_host(state),
            grader=local_grader(),
            on_login_released=lambda: at_release.extend(read_schedule(profile)),
        )
    [held] = at_release
    assert held.source == "usage-limit"


@PLUGIN_SDK
def test_native_only_spend_is_held_before_slow_grading_ends(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(80.0), now=NOW)
    inputs = execution.grading_inputs
    while_grading = []

    def slow(*args, **kwargs):
        # Grading starts here; the profile is already another run's to take.
        if not while_grading:
            while_grading.extend(read_schedule(profile))
            while_grading.append(lock_held(profile / "runner.lock"))
        return inputs(*args, **kwargs)

    monkeypatch.setattr(execution, "grading_inputs", slow)
    run_benchmark(**common, host=native_host(state), grader=local_grader())
    *held, locked = while_grading
    assert [c.source for c in held] == ["usage-limit"]
    assert locked is False


@PLUGIN_SDK
def test_native_spend_below_the_ceiling_writes_nothing(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(80.0), now=NOW)
    seen = observed_estimates(monkeypatch)
    run_benchmark(**common, host=native_host(state, SmallSpendDocker), grader=local_grader())
    before_release, after_record = seen
    assert before_release[1].weekly.percent == pytest.approx(3.0, rel=1e-3)
    assert after_record[1].weekly.percent == pytest.approx(before_release[1].weekly.percent)
    assert read_schedule(profile) == []


@PLUGIN_SDK
def test_unpriceable_native_spend_never_fails_the_run(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(80.0), now=NOW)
    record = run_benchmark(
        **common, host=native_host(state, UnpricedSpendDocker), grader=local_grader()
    )
    assert record.run_metadata["execution"]["status"] == "completed"
    assert read_schedule(profile) == []


@PLUGIN_SDK
def test_measurements_that_fail_to_finalize_still_reach_the_check_and_the_record(
    tmp_path, monkeypatch
):
    from silverquillm.karn.observations import CodexTelemetryCollector

    def broken(self, **kwargs):
        raise RuntimeError("observations unwritable")

    monkeypatch.setattr(CodexTelemetryCollector, "finalize", broken)
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(80.0), now=NOW)
    at_release = []
    record = run_benchmark(
        **common,
        host=native_host(state),
        grader=local_grader(),
        on_login_released=lambda: at_release.extend(read_schedule(profile)),
    )
    [held] = at_release
    assert held.source == "usage-limit"
    reasons = record.run_metadata["measurements"]["agent_turns"]["total"]["reasons"]
    assert "measurement_finalization_failed" in reasons


@PLUGIN_SDK
def test_a_profile_without_a_limit_is_measured_after_its_release(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    measured_while_held = []
    measure = execution.measure

    def observed(*args, **kwargs):
        measured_while_held.append(lock_held(profile / "runner.lock"))
        return measure(*args, **kwargs)

    monkeypatch.setattr(execution, "measure", observed)
    run_benchmark(**common, host=native_host(state), grader=local_grader())
    assert measured_while_held == [False]


def test_spend_that_cannot_be_gathered_is_reported_and_the_check_goes_on(tmp_path, capsys):
    host = Host(tmp_path)
    publish(host.repo, "r1", usage=claude_usage(85.0, resets="2026-10-09T00:00:00Z"), requests=[])
    set_limit(host.login, UsageLimit(80.0), now=NOW)

    def unavailable():
        raise RuntimeError("journal unreadable")

    usage_limit.check_quietly(
        host.login,
        PROFILE,
        "claude",
        spend=unavailable,
        state_root=host.state,
        runs_dir=host.runs,
        results_repo=host.repo,
        now=host.now,
        config=CONFIG,
    )
    err = capsys.readouterr().err
    assert "usage_limit_spend_unavailable: RuntimeError" in err
    assert "Usage Limit reached; every run held" in err
    [held] = read_schedule(host.login, now=host.now)
    assert held.source == "usage-limit"


@PLUGIN_SDK
def test_recovery_holds_native_only_spend_while_it_still_holds_the_profile(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    profile = pool_slot(state).directory
    set_limit(profile, UsageLimit(80.0), now=NOW)
    with pytest.raises(SystemExit):
        run_benchmark(
            **common,
            run_id="run-a",
            host=die_after_start(native_host(state, host=DyingHost)),
        )
    assert read_schedule(profile) == []
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    seen = observed_estimates(monkeypatch)
    checked_while_held = []
    check_quietly = recovery.check_quietly

    def observed(directory, *args, **kwargs):
        checked_while_held.append(lock_held(Path(directory) / "runner.lock"))
        return check_quietly(directory, *args, **kwargs)

    monkeypatch.setattr(recovery, "check_quietly", observed)
    options_ = {key: common[key] for key in ("bench_root", "results_dir", "results_repo")}
    record = recovery.recover_benchmark(run_id="run-a", spec={}, state_root=state, **options_)
    assert checked_while_held == [True, False]
    while_held, after_record = seen
    assert while_held[0] is False
    assert while_held[1].weekly.percent == pytest.approx(180.0)
    assert after_record[1].weekly.percent == pytest.approx(while_held[1].weekly.percent)
    [held] = read_schedule(profile)
    assert held.source == "usage-limit"
    costs = record.run_metadata["measurements"]["run_cost"]
    assert float(costs["value"]) == pytest.approx(900.0, rel=1e-3)
