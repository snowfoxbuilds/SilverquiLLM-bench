"""A stand-in ``Monitor`` with a busy host's worth of data, for the monitor app's tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from silverquillm.host_config import HostConfig, ResolvedLocation
from silverquillm.monitor import (
    CommitEntry,
    Counts,
    LiveRun,
    LogLine,
    MonitorSnapshot,
    ProfileStatus,
    ProfileView,
    QueuedBatch,
    QueuedRun,
    RecordDetail,
    RepoFreshness,
    RequestCost,
    RunSummary,
    RunView,
    Score,
    SnapshotEntry,
    Stage,
    UsageReading,
    WeeklyUsage,
    WorkspaceView,
    candidate_display,
)
from silverquillm.monitor.containers import RunContainer

NOW = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)


def _candidate(name, model, effort, candidate_hash):
    definition = {
        "name": name,
        "runtime": {"environment": {"CONSTRUCT_MODEL": model, "CONSTRUCT_EFFORT": effort}},
    }
    return candidate_display(definition, candidate_hash, "r42")


OPUS = _candidate("bare-claude-opus", "claude-opus-5-5", "max", "a1" * 32)
SOL = _candidate("bare-codex-sol61", "gpt-6.1-sol", "xhigh", "b2" * 32)
SOL_REBUILT = _candidate("bare-codex-sol61", "gpt-6.1-sol", "xhigh", "c3" * 32)
HAIKU = _candidate("bare-claude-haiku", "claude-haiku-4-5", "", "d4" * 32)


def _live(
    run_id, stage, benchmark, candidate, login, provider, minutes, *, running=True, reasons=()
):
    started = NOW - timedelta(minutes=minutes)
    container = RunContainer(
        run_id,
        "sq-run-" + run_id,
        running,
        started,
        None if running else NOW,
        Path("/runs") / run_id,
    )
    return LiveRun(
        run_id=run_id,
        run_dir=Path("/runs") / run_id,
        stage=stage,
        benchmark=benchmark,
        construct=candidate.name,
        candidate=candidate,
        candidate_hash=None,
        login_profile=login,
        provider=provider,
        budget_seconds=14400,
        host_started_at=started,
        container=container,
        reasons=reasons,
        native_telemetry=True,
        telemetry_adapter=provider,
    )


def _costs(minutes, step, usd):
    start = int((NOW - timedelta(minutes=minutes)).timestamp() * 1000)
    return tuple(
        (start + index * step * 1000, Decimal(usd) * (1 + index % 5)) for index in range(40)
    )


def running_views():
    return [
        RunView(
            _live(
                "aaaa1111" * 4,
                Stage.RUNNING,
                "hob-medium",
                OPUS,
                "karn-claude-login/bare-claude-opus",
                "claude",
                47,
            ),
            61.0,
            Decimal("8.41"),
            0,
            _costs(47, 60, "0.05"),
        ),
        RunView(
            _live(
                "bbbb2222" * 4,
                Stage.GRADING,
                "hob-medium",
                SOL,
                "karn-codex-login/slot-1",
                "codex",
                23,
                running=False,
            ),
            99.0,
            Decimal("2.17"),
            2,
            _costs(23, 30, "0.02"),
        ),
        RunView(
            _live(
                "cccc3333" * 4,
                Stage.NEEDS_RECOVER,
                "smoke",
                HAIKU,
                "karn-claude-login/bare-claude-haiku",
                "claude",
                300,
                reasons=("no_record", "login_settlement_pending"),
            ),
            None,
            None,
            0,
            (),
        ),
        RunView(
            _live(
                "dddd4444" * 4,
                Stage.RECORDING,
                "hob-medium",
                SOL_REBUILT,
                "karn-codex-login/slot-2",
                "codex",
                31,
                running=False,
            ),
            None,
            Decimal("3.05"),
            0,
            _costs(31, 40, "0.03"),
        ),
    ]


def queued():
    return [
        QueuedBatch(
            "2026-10-07-effort-sweep",
            "pending",
            None,
            2,
            5,
            (
                QueuedRun(2, "hob-medium", "bare-codex-sol61", "/b", 14400, SOL),
                QueuedRun(3, "hob-medium", "bare-claude-opus", "/b", 14400, OPUS),
                QueuedRun(4, "smoke", "bare-claude-haiku", "/b", 3600, HAIKU),
            ),
        ),
        QueuedBatch(
            "2026-10-08-night",
            "pending",
            NOW + timedelta(hours=7, minutes=30),
            0,
            1,
            (QueuedRun(0, "fra-hard-v2", "bare-codex-sol61", "/b", 86400, SOL),),
        ),
        QueuedBatch(
            "2026-10-09-new",
            "needs_ack",
            None,
            0,
            1,
            (QueuedRun(0, "sos", "bare-claude-opus", "/b", 86400, OPUS),),
        ),
    ]


def _reading(provider, percent, resets_in, read_ago):
    return UsageReading(provider, percent, 10080, NOW + resets_in, NOW - read_ago)


# The killed smoke run still owns its Claude login's settlement.
PENDING = {"bare-claude-haiku": "cccc3333" * 4}
# The operator held one idle login of each pool back for a few hours.
COOLING = {
    "slot-2": NOW + timedelta(hours=3, minutes=12),
    "claude-5": NOW + timedelta(minutes=50),
}


def profiles():
    rows = [
        (
            "karn-claude-login",
            "bare-claude-opus",
            "claude",
            True,
            WeeklyUsage(
                "", 41.0, False, _reading("claude", 41.0, timedelta(days=2), timedelta(minutes=12))
            ),
        ),
        (
            "karn-claude-login",
            "bare-claude-sonnet",
            "claude",
            False,
            WeeklyUsage("", 18.4, True, None),
        ),
        (
            "karn-claude-login",
            "bare-claude-haiku",
            "claude",
            False,
            WeeklyUsage(
                "", 93.0, True, _reading("claude", 88.0, timedelta(hours=5), timedelta(hours=3))
            ),
        ),
        (
            "karn-codex-login",
            "slot-1",
            "codex",
            True,
            WeeklyUsage(
                "", 47.2, True, _reading("codex", 44.0, timedelta(days=4), timedelta(hours=1))
            ),
        ),
        ("karn-codex-login", "slot-2", "codex", False, WeeklyUsage("", 3.0, True, None)),
        ("karn-codex-login", "bare-codex-luna", "codex", False, None),
        # Six of each, as the operator runs them: the rest of each pool.
        (
            "karn-claude-login",
            "claude-4",
            "claude",
            True,
            WeeklyUsage("", 62.5, True, None),
        ),
        ("karn-claude-login", "claude-5", "claude", False, WeeklyUsage("", 7.0, True, None)),
        (
            "karn-claude-login",
            "claude-6",
            "claude",
            False,
            WeeklyUsage(
                "", 24.0, False, _reading("claude", 24.0, timedelta(days=6), timedelta(minutes=3))
            ),
        ),
        (
            "karn-codex-login",
            "slot-3",
            "codex",
            True,
            WeeklyUsage(
                "", 71.0, False, _reading("codex", 71.0, timedelta(days=1), timedelta(minutes=8))
            ),
        ),
        ("karn-codex-login", "slot-4", "codex", False, WeeklyUsage("", 12.4, True, None)),
        ("karn-codex-login", "slot-5", "codex", True, WeeklyUsage("", 33.0, True, None)),
    ]
    return [
        ProfileView(
            ProfileStatus(
                plugin, slot, provider, busy, slot in PENDING, PENDING.get(slot), COOLING.get(slot)
            ),
            WeeklyUsage(f"{plugin}/{slot}", w.percent, w.estimated, w.reading) if w else None,
            None,
        )
        for plugin, slot, provider, busy, w in rows
    ]


def _score(rate, total):
    return Score(True, rate, round(rate * total), total)


def history():
    runs = []
    plan = [
        (
            OPUS,
            "hob-medium",
            "completed",
            0.93,
            0.98,
            1.0,
            "61.20",
            None,
            "karn-claude-login/bare-claude-opus",
        ),
        (
            SOL,
            "hob-medium",
            "completed",
            0.71,
            0.95,
            0.97,
            "11.84",
            None,
            "karn-codex-login/slot-1",
        ),
        (
            SOL_REBUILT,
            "hob-medium",
            "deadline",
            0.45,
            0.88,
            0.97,
            "19.03",
            None,
            "karn-codex-login/slot-2",
        ),
        (
            HAIKU,
            "smoke",
            "completed",
            1.0,
            None,
            None,
            "0.42",
            None,
            "karn-claude-login/bare-claude-haiku",
        ),
        (
            SOL,
            "hob-medium",
            "completed",
            0.0,
            0.2,
            0.5,
            "0.31",
            "zero_agent_turns",
            "karn-codex-login/slot-1",
        ),
        (
            OPUS,
            "hob-medium",
            "failed",
            0.12,
            0.99,
            1.0,
            "4.10",
            None,
            "karn-claude-login/bare-claude-opus",
        ),
    ]
    for index, (
        candidate,
        benchmark,
        status,
        target,
        fdn,
        engine,
        cost,
        excluded,
        login,
    ) in enumerate(plan):
        started = NOW - timedelta(days=index + 1, hours=index)
        scores = {
            "card_correctness": _score(target, 30),
            "fdn_regression": _score(fdn, 120)
            if fdn is not None
            else Score(False, None, None, None),
            "engine_regression": _score(engine, 90)
            if engine is not None
            else Score(False, None, None, None),
        }
        runs.append(
            RunSummary(
                run_id=f"{index:02d}" + "e" * 30,
                candidate_hash=candidate.hash8 * 8 if candidate.hash8 else "0" * 64,
                schema_version=2,
                benchmark=benchmark,
                run_date=started,
                status=status,
                started_at=started,
                stopped_at=started + timedelta(minutes=20 + 7 * index),
                budget_seconds=14400,
                scores=scores,
                estimated_cost=Decimal(cost),
                cost_complete=index != 2,
                cost_completeness="complete" if index != 2 else "partial",
                unpriced_requests=0 if index != 2 else 3,
                agent_turns=300 + 41 * index,
                total_tokens=12_000_000 + 1_300_000 * index,
                login_profile=login,
                host_label="wsl-main" if index % 2 == 0 else "pi-rack",
                candidate=candidate,
                request_costs=(),
                usage_reading=None,
                path=Path("/results") / str(index),
                excluded=excluded,
            )
        )
    return runs


CLAUDE_LINES = [
    {"type": "system", "subtype": "init", "model": "claude-opus-5-5", "tools": ["Bash", "Read"]},
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "I'll start by orienting myself in the workspace."}
            ]
        },
    },
    {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "input": {"command": "cat instructions.md && ls cards/hob"},
                }
            ]
        },
    },
    {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "content": "# HOB medium implementation task\nImplement all five selected cards.",
                }
            ]
        },
    },
    {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "unifiedWindows": {
                "seven_day": {"utilization": 0.41, "resetsAt": 1791468000},
                "five_hour": {"utilization": 0.32, "resetsAt": 1790888400},
            }
        },
    },
    {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "thinking",
                    "thinking": "The Notary Hobbits need a replacement effect on token creation.",
                }
            ]
        },
    },
    {"type": "system", "subtype": "task_started", "description": "Run the hob_131 card tests"},
    {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "content": "FAILED tests.py::test_payment_window",
                    "is_error": True,
                }
            ]
        },
    },
    {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {"file_path": "/workspace/cards/hob/hob_131/card_impl.py"},
                }
            ]
        },
    },
]


def output_lines():
    lines = [
        LogLine(index, "stdout", json.dumps(event), NOW - timedelta(minutes=40 - 4 * index))
        for index, event in enumerate(CLAUDE_LINES, 1)
    ]
    lines.append(LogLine(len(lines) + 1, "stderr", "warning: telemetry exporter retry", NOW))
    lines.append(LogLine(len(lines) + 1, "stdout", "plain text the candidate printed", NOW))
    return lines


def requests():
    start = int((NOW - timedelta(minutes=45)).timestamp() * 1000)
    return [
        RequestCost(
            start + index * 61_000,
            "claude-opus-5-5",
            {
                "input_tokens": 1200 + index,
                "cached_input_tokens": 80_000 + 900 * index,
                "cache_write_input_tokens": 3_000,
                "output_tokens": 900 + 13 * index,
            },
            Decimal("0.05") * (1 + index % 4),
        )
        for index in range(30)
    ]


def workspace():
    snapshots = [
        SnapshotEntry(
            NOW - timedelta(minutes=45 - index),
            "baseline" if index == 0 else "periodic",
            762 + index // 3,
            (index // 3 - (index - 1) // 3) if index else None,
            index % 3 == 0 and index > 0,
            index > 30,
        )
        for index in range(12)
    ]
    commits = [
        CommitEntry(
            NOW - timedelta(minutes=46),
            "commit (initial)",
            "Stage benchmark workspace",
            "2543c7902cf5",
        ),
        CommitEntry(
            NOW - timedelta(minutes=20), "commit", "Implement The Notary Hobbits", "9f1e0a7c3b21"
        ),
    ]
    return WorkspaceView(snapshots, commits)


class FakeMonitor:
    """Serves fixed data through the ``Monitor`` methods the app calls."""

    def __init__(self, *, running=None, runs=None, root: Path = Path("/home/op")):
        self.config = HostConfig(path=root / ".config/silverquillm/config.toml", loaded=True)
        self.running = running_views() if running is None else running
        self.runs = history() if runs is None else runs
        self.closed = False
        self.shutdown_begun = False
        self.root = root
        self.host_label: str | None = "lab-1"
        self.output_calls: list[tuple] = []

    def snapshot(self) -> MonitorSnapshot:
        root = self.root
        return MonitorSnapshot(
            taken_at=NOW,
            locations={
                "results_repo": ResolvedLocation("results_repo", root / "bench-results", "config"),
                "batches_dir": ResolvedLocation("batches_dir", root / "bench-batches", "config"),
                "runs_dir": ResolvedLocation(
                    "runs_dir", root / "SilverquiLLM-bench/runs/karn", "flag"
                ),
                "state_root": ResolvedLocation(
                    "state_root", root / ".local/state/silverquillm", "default"
                ),
            },
            config_file=self.config.path,
            config_error=None,
            docker_error=None,
            running=self.running,
            queued=queued(),
            profiles=profiles(),
            counts=Counts(queued=5, live=len(self.running), finished_recent=6, finished_total=354),
            repo=RepoFreshness(NOW - timedelta(hours=2), 3),
            exclusion_error=None,
            host_label=self.host_label,
        )

    def history(self, *, refresh: bool = False):
        return self.runs

    def output(self, run_id, stream=None, since=0):
        self.output_calls.append((run_id, since))
        return [line for line in output_lines() if line.seq > since]

    def provisional_requests(self, run_id):
        return requests()

    def workspace(self, run_id):
        return workspace()

    def local_candidate_hash(self, run_id):
        """This host ran each fixture run for the first history record naming it."""
        for view in self.running:
            if view.run.run_id == run_id:
                return view.run.candidate_hash
        return next((run.candidate_hash for run in self.runs if run.run_id == run_id), None)

    def record_detail(self, summary):
        return RecordDetail(
            requests(),
            {
                "uncached_input": (200_497, Decimal("0.40")),
                "cache_read": (5_273_600, Decimal("0.53")),
                "output": (59_041, Decimal("0.59")),
            },
            None,
            None,
            None,
            "final",
        )

    def begin_shutdown(self):
        self.shutdown_begun = True

    def close(self):
        self.closed = True
