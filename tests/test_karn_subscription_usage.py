from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from silverquillm.karn import execution, recovery
from silverquillm.karn import subscription_usage as subscription_usage_module
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.host import DockerHost
from silverquillm.karn.login import NATIVE_PRESERVED
from silverquillm.karn.subscription_usage import (
    claude_usage,
    codex_usage,
    provider_for,
    subscription_usage,
)

from .grader_fixtures import local_grader
from .test_karn_execution import FixtureHost, benchmark_data, options
from .test_karn_host import FakeDocker
from .test_karn_lifecycle import (
    DyingHost,
    SessionDocker,
    die_after_start,
    enroll,
    grade_locally,
    login_candidate,
    pool_slot,
)

WEEK = 10080


@pytest.fixture(autouse=True)
def _grade_without_docker(monkeypatch):
    grade_locally(monkeypatch)


def claude_event(fraction, resets_at=1791468000, **extra):
    return {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "allowed",
            "unifiedWindows": {
                "five_hour": {"utilization": 0.5, "resetsAt": 1790888400},
                "seven_day": {"utilization": fraction, "resetsAt": resets_at},
            },
            **extra,
        },
        "session_id": "secret-session",
    }


def codex_line(percent, *, timestamp="2026-09-27T15:35:37.665Z", primary=None, secondary=None):
    primary = primary or {"used_percent": percent, "window_minutes": WEEK, "resets_at": 1791046725}
    return {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {"total_token_usage": {"input_tokens": 1}},
            "rate_limits": {
                "limit_id": "codex",
                "primary": primary,
                "secondary": secondary,
                "credits": {"balance": "secret-balance"},
                "plan_type": "pro",
            },
        },
    }


def write_lines(path: Path, rows) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join((row if isinstance(row, str) else json.dumps(row)) + "\n" for row in rows)
    )
    return path


# ---- Claude stdout ------------------------------------------------------------------------


def test_claude_keeps_the_last_seven_day_reading_as_a_percentage(tmp_path):
    stdout = write_lines(
        tmp_path / "stdout.log",
        [
            {"type": "system", "subtype": "init"},
            claude_event(0.04),
            {"type": "assistant", "message": {"content": "mentions rate_limit_event"}},
            claude_event(0.06),
        ],
    )
    assert claude_usage(stdout) == {
        "completeness": "complete",
        "reasons": [],
        "value": {
            "provider": "claude",
            "utilization_percent": 6.0,
            "window_minutes": WEEK,
            "resets_at": "2026-10-08T14:00:00Z",
            "observed_at": None,
        },
    }


def test_claude_keeps_only_the_allowlisted_fields(tmp_path):
    stdout = write_lines(tmp_path / "stdout.log", [claude_event(0.5, overageStatus="secret")])
    result = claude_usage(stdout)
    assert set(result["value"]) == {
        "provider",
        "utilization_percent",
        "window_minutes",
        "resets_at",
        "observed_at",
    }
    assert "secret" not in json.dumps(result) and "five_hour" not in json.dumps(result)


@pytest.mark.parametrize(
    "fraction, resets_at",
    [
        (True, 1791468000),
        ("0.5", 1791468000),
        (-0.1, 1791468000),
        (11, 1791468000),
        (0.5, "1791468000"),
        (0.5, 10**400),
        (0.5, 1),
        (0.5, None),
    ],
)
def test_claude_drops_a_malformed_reading_and_keeps_a_valid_one(tmp_path, fraction, resets_at):
    stdout = write_lines(
        tmp_path / "stdout.log", [claude_event(0.2), claude_event(fraction, resets_at)]
    )
    result = claude_usage(stdout)
    assert result["completeness"] == "complete"
    assert result["value"]["utilization_percent"] == 20.0
    assert result["reasons"] == ["malformed_reading_dropped"]


def test_claude_without_a_reading_is_missing_with_a_reason(tmp_path):
    absent = write_lines(tmp_path / "absent.log", [{"type": "system"}])
    assert claude_usage(absent)["reasons"] == ["claude_rate_limit_event_absent"]
    malformed = write_lines(
        tmp_path / "malformed.log",
        ['{"type":"rate_limit_event", truncated', {"type": "rate_limit_event"}, "[" * 100_000],
    )
    result = claude_usage(malformed)
    assert result == {
        "completeness": "missing",
        "reasons": ["claude_rate_limit_event_absent", "malformed_reading_dropped"],
        "value": None,
    }
    assert claude_usage(tmp_path / "nowhere.log")["reasons"] == ["claude_stdout_unavailable"]


def test_claude_never_follows_a_link_for_stdout(tmp_path):
    target = write_lines(tmp_path / "elsewhere.log", [claude_event(0.3)])
    (tmp_path / "stdout.log").symlink_to(target)
    assert claude_usage(tmp_path / "stdout.log")["reasons"] == ["claude_stdout_unavailable"]


def test_a_deeply_nested_marked_line_is_dropped_not_raised(tmp_path):
    stdout = write_lines(
        tmp_path / "stdout.log",
        ['{"type":"rate_limit_event","x":' + "[" * 200_000 + "]" * 200_000 + "}"],
    )
    assert claude_usage(stdout)["completeness"] == "missing"


def test_an_overlong_marked_line_is_dropped_unparsed(tmp_path, monkeypatch):
    stdout = write_lines(
        tmp_path / "stdout.log",
        [claude_event(0.25), claude_event(0.9, padding="x" * 600), "", "short", claude_event(0.5)],
    )
    loads = json.loads
    monkeypatch.setattr(subscription_usage_module, "MAX_LINE_BYTES", 512)
    monkeypatch.setattr(
        json,
        "loads",
        lambda line: pytest.fail("parsed an overlong line") if len(line) > 512 else loads(line),
    )
    result = claude_usage(stdout)
    assert result["value"]["utilization_percent"] == 50.0
    assert result["reasons"] == ["malformed_reading_dropped"]


# ---- Codex rollouts -----------------------------------------------------------------------


def test_codex_keeps_the_newest_weekly_reading_across_rollouts(tmp_path):
    sessions = tmp_path / "work/sessions/2026/09/27"
    write_lines(
        sessions / "rollout-b.jsonl",
        [codex_line(2.0, timestamp="2026-09-27T15:35:37.665Z")],
    )
    write_lines(
        sessions / "rollout-a.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "thread"}},
            codex_line(5.5, timestamp="2026-09-27T16:00:00Z"),
        ],
    )
    assert codex_usage(tmp_path / "work") == {
        "completeness": "complete",
        "reasons": [],
        "value": {
            "provider": "codex",
            "utilization_percent": 5.5,
            "window_minutes": WEEK,
            "resets_at": "2026-10-03T16:58:45Z",
            "observed_at": "2026-09-27T16:00:00Z",
        },
    }


def test_codex_takes_the_weekly_window_by_its_length(tmp_path):
    five_hours = {"used_percent": 70.0, "window_minutes": 300, "resets_at": 1790888400}
    weekly = {"used_percent": 12.0, "window_minutes": WEEK, "resets_at": 1791046725}
    write_lines(
        tmp_path / "work/sessions/rollout-x.jsonl",
        [codex_line(0, primary=five_hours, secondary=weekly)],
    )
    result = codex_usage(tmp_path / "work")
    assert result["value"]["utilization_percent"] == 12.0
    write_lines(
        tmp_path / "only-short/sessions/rollout-x.jsonl", [codex_line(0, primary=five_hours)]
    )
    assert codex_usage(tmp_path / "only-short")["reasons"] == [
        "codex_rate_limits_absent",
        "codex_weekly_window_absent",
    ]


def test_codex_reads_the_pinned_cli_rollout_shape(tmp_path):
    """Qualification: the rate_limits line of the preserved real rollout of run 582878e5."""
    real = {
        "timestamp": "2026-09-27T15:35:37.665Z",
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {"total_token_usage": {"input_tokens": 1}},
            "rate_limits": {
                "limit_id": "codex",
                "limit_name": None,
                "primary": {"used_percent": 2.0, "window_minutes": 10080, "resets_at": 1791046725},
                "secondary": None,
                "credits": {"has_credits": False, "unlimited": False, "balance": "0"},
                "individual_limit": None,
                "spend_control_reached": None,
                "plan_type": "pro",
                "rate_limit_reached_type": None,
            },
        },
    }
    write_lines(tmp_path / "work/sessions/rollout-x.jsonl", [real])
    assert codex_usage(tmp_path / "work")["value"] == {
        "provider": "codex",
        "utilization_percent": 2.0,
        "window_minutes": 10080,
        "resets_at": "2026-10-03T16:58:45Z",
        "observed_at": "2026-09-27T15:35:37Z",
    }


@pytest.mark.parametrize(
    ("primary", "secondary", "expected"),
    [
        ({"used_percent": 70.0, "window_minutes": 15, "resets_at": 1790888400}, "weekly", 12.0),
        ("weekly", None, 12.0),
        ({"used_percent": 1.0, "window_minutes": "10080", "resets_at": 1}, "weekly", 12.0),
        ({"used_percent": "x", "window_minutes": WEEK, "resets_at": 1791046725}, "weekly", 12.0),
        ({"used_percent": 1.0, "window_minutes": 60, "resets_at": 1}, None, None),
    ],
)
def test_codex_chooses_the_window_lasting_a_week_whatever_its_name(
    tmp_path, primary, secondary, expected
):
    weekly = {"used_percent": 12.0, "window_minutes": WEEK, "resets_at": 1791046725}
    primary = weekly if primary == "weekly" else primary
    secondary = weekly if secondary == "weekly" else secondary
    line = codex_line(0)
    line["payload"]["rate_limits"].update(primary=primary, secondary=secondary)
    write_lines(tmp_path / "work/sessions/rollout-x.jsonl", [line])
    result = codex_usage(tmp_path / "work")
    if expected is None:
        assert result["completeness"] == "missing"
    else:
        assert result["value"]["utilization_percent"] == expected


def test_codex_keeps_only_the_allowlisted_fields(tmp_path):
    write_lines(tmp_path / "work/sessions/rollout-x.jsonl", [codex_line(3.0)])
    result = codex_usage(tmp_path / "work")
    assert set(result["value"]) == {
        "provider",
        "utilization_percent",
        "window_minutes",
        "resets_at",
        "observed_at",
    }
    assert "secret" not in json.dumps(result) and "token_count" not in json.dumps(result)


def test_codex_opens_only_rollout_files_in_sessions(tmp_path):
    work = tmp_path / "work"
    write_lines(work / "auth.json", [codex_line(99.0)])
    write_lines(work / "sessions/notes.jsonl", [codex_line(98.0)])
    write_lines(work / "sessions/rollout-x.json", [codex_line(97.0)])
    write_lines(work / "elsewhere/rollout-y.jsonl", [codex_line(96.0)])
    assert codex_usage(work)["reasons"] == ["codex_rate_limits_absent"]
    write_lines(work / "sessions/rollout-z.jsonl", [codex_line(4.0)])
    assert codex_usage(work)["value"]["utilization_percent"] == 4.0


def test_codex_follows_no_link(tmp_path):
    outside = write_lines(tmp_path / "outside/rollout-x.jsonl", [codex_line(50.0)])
    work = tmp_path / "work"
    (work / "sessions").mkdir(parents=True)
    (work / "sessions/rollout-link.jsonl").symlink_to(outside)
    (work / "sessions/nested").symlink_to(outside.parent, target_is_directory=True)
    assert codex_usage(work)["completeness"] == "missing"
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "sessions").symlink_to(outside.parent, target_is_directory=True)
    assert codex_usage(linked)["reasons"] == ["codex_sessions_unavailable"]


def test_codex_drops_malformed_readings(tmp_path):
    bad = [
        codex_line(True),
        codex_line(float("nan")),
        codex_line(5000.0),
        codex_line(1.0, primary={"used_percent": 1.0, "window_minutes": WEEK, "resets_at": "x"}),
        codex_line(1.0, primary={"used_percent": 1.0, "window_minutes": True, "resets_at": 1}),
        {"timestamp": "z", "payload": {"rate_limits": "nope"}},
        '{"payload": {"rate_limits": truncated',
        codex_line(8.0, timestamp="not a time"),
    ]
    write_lines(tmp_path / "work/sessions/rollout-x.jsonl", bad)
    result = codex_usage(tmp_path / "work")
    assert result["completeness"] == "complete"
    assert result["value"]["utilization_percent"] == 8.0
    assert result["value"]["observed_at"] is None
    assert "malformed_reading_dropped" in result["reasons"]


def test_codex_without_sessions_is_missing(tmp_path):
    assert codex_usage(tmp_path / "nowhere")["reasons"] == ["codex_sessions_unavailable"]


def test_an_unreadable_rollout_keeps_the_readings_already_found(tmp_path):
    sessions = tmp_path / "work/sessions"
    write_lines(sessions / "rollout-a.jsonl", [codex_line(3.0)])
    locked = write_lines(sessions / "rollout-b.jsonl", [codex_line(4.0)])
    os.chmod(locked, 0)
    try:
        if os.access(locked, os.R_OK):
            pytest.skip("running as a user that reads any file")
        result = codex_usage(tmp_path / "work")
    finally:
        os.chmod(locked, 0o600)
    assert result["value"]["utilization_percent"] == 3.0
    assert result["reasons"] == ["codex_sessions_partially_read"]


# ---- provider and dispatch ----------------------------------------------------------------


@pytest.mark.parametrize(
    "login, adapter, provider",
    [
        ("karn-codex-login/slot-1", "claude", "codex"),
        ("karn-claude-login/bare-claude-opus", "codex", "claude"),
        ("bare-codex-luna", "codex", "codex"),
        ("bare-claude-opus", "claude", "claude"),
        ("other-plugin/slot", None, None),
        (None, "codex", None),
    ],
)
def test_the_provider_is_the_login_plugins(login, adapter, provider):
    assert provider_for(login, adapter) == provider


def test_a_run_without_a_login_records_no_reading(tmp_path):
    assert subscription_usage(None, codex=None, stdout=tmp_path / "stdout.log") == {
        "completeness": "missing",
        "reasons": ["no_login_profile"],
        "value": None,
    }
    assert subscription_usage("codex", codex=None, stdout=tmp_path / "x")["reasons"] == [
        "codex_sessions_unavailable"
    ]


# ---- the run lifecycle --------------------------------------------------------------------


def test_a_run_without_a_login_plugin_records_the_reading_as_missing(plain_run):
    usage = plain_run.record.run_metadata["measurements"]["subscription_usage"]
    assert usage == {"completeness": "missing", "reasons": ["no_login_profile"], "value": None}


class StdoutHost(FixtureHost):
    def run(self, candidate, workspace, evidence_dir, prompt, **kwargs):
        result = super().run(candidate, workspace, evidence_dir, prompt, **kwargs)
        write_lines(evidence_dir / "stdout.log", [claude_event(0.25)])
        return result


def test_a_claude_run_reads_its_retained_stdout(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, "usage_provider", lambda login, adapter: "claude")
    record = run_benchmark(**options(tmp_path, host=StdoutHost()))
    usage = record.run_metadata["measurements"]["subscription_usage"]
    assert usage["completeness"] == "complete"
    assert usage["value"]["utilization_percent"] == 25.0


class UsageSessionDocker(SessionDocker):
    """Also writes a weekly rate-limit reading into the run's native rollout."""

    def command(self, *args, **kwargs):
        result = super().command(*args, **kwargs)
        if args[0] == "start":
            rollout = Path(self.native) / "sessions" / f"rollout-{self.run_id}.jsonl"
            with rollout.open("a") as stream:
                stream.write(json.dumps(codex_line(7.0)) + "\n")
        return result


def login_common(tmp_path):
    candidate = login_candidate(tmp_path)
    state = (tmp_path / "state").resolve()
    enroll(pool_slot(state))
    return state, {
        "build_output": candidate.build_output,
        "construct": "bare",
        "benchmark_id": "example",
        "bench_root": benchmark_data(tmp_path / "data"),
        "results_dir": tmp_path / "runs",
        "results_repo": tmp_path / "records",
        "state_root": state,
    }


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_a_codex_run_keeps_its_reading_before_the_login_harvest_clears_it(tmp_path):
    state, common = login_common(tmp_path)
    host = DockerHost(
        docker=UsageSessionDocker(), plugin_cache=state / "plugins", plugin_python=sys.executable
    )
    record = run_benchmark(**common, host=host, grader=local_grader())
    usage = record.run_metadata["measurements"]["subscription_usage"]
    assert usage["completeness"] == "complete", usage
    assert usage["value"]["provider"] == "codex"
    assert usage["value"]["utilization_percent"] == 7.0
    assert usage["value"]["observed_at"] == "2026-09-27T15:35:37Z"
    assert not (pool_slot(state).state / "work/sessions").exists()


class UnharvestableSessionDocker(UsageSessionDocker):
    """Also writes a rollout line too deep for the native journal harvest to parse."""

    def command(self, *args, **kwargs):
        result = super().command(*args, **kwargs)
        if args[0] == "start":
            rollout = Path(self.native) / "sessions" / f"rollout-{self.run_id}.jsonl"
            with rollout.open("a") as stream:
                stream.write('{"payload":' + "[" * 100_000 + "]" * 100_000 + "}\n")
        return result


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_a_failing_journal_harvest_keeps_the_codex_reading(tmp_path):
    state, common = login_common(tmp_path)
    host = DockerHost(
        docker=UnharvestableSessionDocker(),
        plugin_cache=state / "plugins",
        plugin_python=sys.executable,
    )
    record = run_benchmark(**common, host=host, grader=local_grader())
    usage = record.run_metadata["measurements"]["subscription_usage"]
    assert usage["value"]["utilization_percent"] == 7.0, usage
    assert not (pool_slot(state).state / "work/sessions").exists()


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_attributes_a_run_recorded_before_adapters_to_codex(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    with pytest.raises(SystemExit):
        run_benchmark(
            **common,
            run_id="run-a",
            host=die_after_start(
                DyingHost(
                    docker=UsageSessionDocker(),
                    plugin_cache=state / "plugins",
                    plugin_python=sys.executable,
                )
            ),
        )
    run_input = Path(common["results_dir"]) / "run-a/run-input.json"
    inputs = json.loads(run_input.read_text())
    del inputs["native_telemetry"]
    run_input.write_text(json.dumps(inputs))
    adapters = []

    def provider(login, adapter):
        adapters.append(adapter)
        return provider_for(login, adapter)

    monkeypatch.setattr(recovery, "usage_provider", provider)
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    options_ = {key: common[key] for key in ("bench_root", "results_dir", "results_repo")}
    recovery.recover_benchmark(run_id="run-a", spec={}, state_root=state, **options_)
    assert adapters == ["codex"]


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_reads_the_reading_from_the_runs_preserved_sessions(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)

    def host():
        return die_after_start(
            DyingHost(
                docker=UsageSessionDocker(),
                plugin_cache=state / "plugins",
                plugin_python=sys.executable,
            )
        )

    for run_id in ("run-a", "run-b"):
        with pytest.raises(SystemExit):
            run_benchmark(**common, run_id=run_id, host=host())
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    options_ = {key: common[key] for key in ("bench_root", "results_dir", "results_repo")}
    record = recovery.recover_benchmark(run_id="run-a", spec={}, state_root=state, **options_)
    usage = record.run_metadata["measurements"]["subscription_usage"]
    assert usage["value"]["utilization_percent"] == 7.0


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_without_preserved_sessions_reads_no_other_runs(tmp_path, monkeypatch):
    state, common = login_common(tmp_path)
    for run_id in ("run-a", "run-b"):
        with pytest.raises(SystemExit):
            run_benchmark(
                **common,
                run_id=run_id,
                host=die_after_start(
                    DyingHost(
                        docker=UsageSessionDocker(),
                        plugin_cache=state / "plugins",
                        plugin_python=sys.executable,
                    )
                ),
            )
    shutil.rmtree(Path(common["results_dir"]) / "run-a/host" / NATIVE_PRESERVED)
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    options_ = {key: common[key] for key in ("bench_root", "results_dir", "results_repo")}
    record = recovery.recover_benchmark(run_id="run-a", spec={}, state_root=state, **options_)
    usage = record.run_metadata["measurements"]["subscription_usage"]
    assert usage == {
        "completeness": "missing",
        "reasons": ["codex_sessions_unavailable"],
        "value": None,
    }
