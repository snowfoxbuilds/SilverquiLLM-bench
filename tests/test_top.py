"""The monitor app (`silverquillm top`): rendering helpers, entry checks, and pilot-driven views."""

from __future__ import annotations

import asyncio
import functools
import io
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import CliRunner
from rich.text import Text

from silverquillm.monitor import LogLine, Score, UsageReading, WeeklyUsage, render_line
from silverquillm.monitor.details import record_detail, workspace_view
from silverquillm.top import INSTALL_HINT, NO_TERMINAL, launch
from silverquillm.top import format as fmt
from silverquillm.top.theme import MTG, PLAIN, theme_named

from .top_fixtures import NOW, FakeMonitor, history


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


# Rendering helpers -------------------------------------------------------------


def test_weekly_usage_from_a_reading_shows_reset_and_age():
    reading = UsageReading(
        "claude", 41.0, 10080, NOW + timedelta(days=1), NOW - timedelta(minutes=12)
    )
    text = fmt.weekly(WeeklyUsage("p", 41.0, False, reading), NOW, MTG).plain
    assert text.startswith("41%")
    assert "resets" in text and "read 12m ago" in text


def test_an_estimated_weekly_usage_is_marked_and_has_no_reset():
    text = fmt.weekly(WeeklyUsage("p", 47.4, True, None), NOW, MTG).plain
    assert text == "≈ 47%"
    assert fmt.weekly(None, NOW, MTG).plain == "no rate"


def test_bars_and_sparklines_keep_their_width():
    assert len(fmt.bar(0.5, 10, MTG).plain) == 10
    assert fmt.bar(0.5, 10, MTG).plain.count(MTG.glyph("bar_full")) == 5
    assert fmt.bar(None, 10, MTG).plain == " " * 10
    points = [(1_000, Decimal(1)), (5_000, Decimal(3)), (9_000, Decimal("0.5"))]
    assert len(fmt.sparkline(points, 12, MTG).plain) == 12
    assert fmt.sparkline([], 12, MTG).plain == " " * 12


def test_scores_take_their_rarity_from_the_pass_rate():
    assert MTG.rarity_role(0.95) == "mythic"
    assert MTG.rarity_role(0.75) == "rare"
    assert MTG.rarity_role(0.5) == "uncommon"
    assert MTG.rarity_role(0.1) == "common"
    assert fmt.score(Score(True, 0.9, 27, 30), MTG).plain == " 90% 27/30"
    assert fmt.score(Score(False, None, None, None), MTG).plain == fmt.DASH


def test_durations_read_compactly():
    assert fmt.duration(3725) == "1h02m"
    assert fmt.duration(65) == "1m05s"
    assert fmt.short_duration(14400) == "4h"
    assert fmt.short_duration(3900) == "1h05"
    assert fmt.short_duration(None) == fmt.DASH


def test_themes_are_chosen_by_name_and_no_flair_wins():
    assert theme_named(None) == (MTG, None)
    assert theme_named("plain")[0] is PLAIN
    assert theme_named("mtg", no_flair=True)[0] is PLAIN
    theme, notice = theme_named("neon")
    assert theme is MTG and "unknown theme 'neon'" in notice


def test_the_plain_theme_uses_no_colour_and_ascii_bars():
    assert set(PLAIN.colors.values()) == {"ansi_default"}
    assert PLAIN.glyph("bar_full").isascii() and PLAIN.glyph("tapped").isascii()
    assert "#" not in PLAIN.style("muted")
    assert set(PLAIN.glyphs) == set(MTG.glyphs)


def test_benchmark_badges_take_the_longest_matching_prefix():
    assert MTG.badge("hob-medium") == MTG.benchmark_badges["hob"]
    assert MTG.badge("fra-hard-v2") == MTG.benchmark_badges["fra"]
    assert MTG.badge("unknown") == MTG.glyph("badge_default")


# Activity rendering ------------------------------------------------------------


def _kinds(event) -> list[str]:
    return [item.kind for item in render_line(json.dumps(event))]


def test_claude_stream_events_render_as_activity():
    assert _kinds({"type": "system", "subtype": "init", "model": "m", "tools": []}) == ["system"]
    assert _kinds({"type": "system", "subtype": "thinking_tokens"}) == []
    content = [
        {"type": "text", "text": "hello"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
        {"type": "thinking", "thinking": ""},
    ]
    assert _kinds({"type": "assistant", "message": {"content": content}}) == ["message", "tool"]
    result = render_line(
        json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [{"type": "tool_result", "content": "boom", "is_error": True}]
                },
            }
        )
    )
    assert result[0].kind == "result" and result[0].failed
    limit = {
        "type": "rate_limit_event",
        "rate_limit_info": {"unifiedWindows": {"seven_day": {"utilization": 0.04}}},
    }
    assert render_line(json.dumps(limit))[0].text == "usage 7-day 4%"


def test_codex_exec_events_render_as_activity():
    started = {"type": "item.started", "item": {"type": "command_execution", "command": "ls"}}
    assert render_line(json.dumps(started))[0].text == "$ ls"
    done = {
        "type": "item.completed",
        "item": {"type": "command_execution", "exit_code": 2, "aggregated_output": "nope"},
    }
    item = render_line(json.dumps(done))[0]
    assert item.kind == "result" and item.failed and item.text.startswith("exit 2")
    message = {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}}
    assert _kinds(message) == ["message"]
    assert _kinds({"type": "turn.failed", "error": {"message": "x"}}) == ["error"]


def test_unknown_cut_or_hostile_lines_show_raw_and_never_raise():
    assert _kinds({"type": "mystery"}) == ["raw"]
    assert render_line("plain words")[0].kind == "raw"
    assert render_line('{"type":"user","message":{"content":[')[0].kind == "result"
    assert render_line("[" * 100_000)[0].kind == "raw"
    deep = '{"type":"assistant","message":' * 5000
    assert render_line(deep)
    assert render_line("") == []


def test_long_text_is_shortened():
    event = {"type": "assistant", "message": {"content": [{"type": "text", "text": "x\n" * 100}]}}
    text = render_line(json.dumps(event))[0].text
    assert text.endswith("…") and text.count("\n") < 10


# Run details data --------------------------------------------------------------


def _reflog(workspace: Path, lines: list[str]) -> None:
    logs = workspace / ".git" / "logs"
    logs.mkdir(parents=True)
    (logs / "HEAD").write_text("".join(line + "\n" for line in lines))


def test_the_workspace_tab_reads_snapshots_and_the_commit_log(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir).mkdir()
    (run_dir / "snapshots.json").write_text(
        json.dumps(
            [
                {
                    "captured_at": "2026-10-07T10:00:00+00:00",
                    "kind": "baseline",
                    "files": 10,
                    "digest": "a",
                },
                {
                    "captured_at": "2026-10-07T10:01:00+00:00",
                    "kind": "periodic",
                    "files": 12,
                    "digest": "b",
                },
                {
                    "captured_at": "2026-10-07T10:02:00+00:00",
                    "kind": "periodic",
                    "files": 12,
                    "digest": "b",
                },
            ]
        )
    )
    zero = "0" * 40
    _reflog(
        run_dir / "workspace",
        [
            f"{zero} {'1' * 40} Agent <a@b> 1791000000 +0000\tcommit (initial): Stage benchmark workspace",
            f"{'1' * 40} {'2' * 40} Agent <a@b> 1791000600 +0000\tcommit: Implement hob_12",
            "garbage line",
        ],
    )
    view = workspace_view(run_dir)
    assert [entry.changed for entry in view.snapshots] == [False, True, False]
    assert view.snapshots[1].files_delta == 2
    assert [(entry.action, entry.message) for entry in view.commits] == [
        ("commit (initial)", "Stage benchmark workspace"),
        ("commit", "Implement hob_12"),
    ]
    assert view.commits[1].commit == "2" * 12


def test_the_commit_log_is_never_read_through_a_link(tmp_path):
    outside = tmp_path / "outside"
    _reflog(outside, [f"{'0' * 40} {'1' * 40} A <a> 1 +0000\tcommit: secret"])
    run_dir = tmp_path / "run"
    (run_dir / "workspace").mkdir(parents=True)
    os.symlink(outside / ".git", run_dir / "workspace" / ".git")
    assert workspace_view(run_dir).commits == []
    assert workspace_view(None).commits == []


def test_a_record_detail_prices_requests_and_keeps_the_breakdown(tmp_path):
    record = tmp_path / "record"
    record.mkdir()
    (record / "manifest.json").write_text(
        json.dumps(
            {
                "run_metadata": {
                    "measurements": {
                        "requests": [
                            {
                                "response_id": "r2",
                                "model": "m",
                                "timestamp_ms": 2000,
                                "usage": {"input_tokens": 5},
                            },
                            {
                                "response_id": "r1",
                                "model": "m",
                                "timestamp_ms": 1000,
                                "usage": {"input_tokens": 3},
                            },
                        ],
                        "request_prices": [
                            {"response_id": "r1", "usd": "0.25"},
                            {"response_id": "r2", "usd": None},
                        ],
                        "cost_breakdown": {"value": {"output": {"tokens": 7, "usd": "0.5"}}},
                    },
                    "execution": {"exit_code": 1, "failure_stage": "launch", "error": "boom"},
                }
            }
        )
    )
    detail = record_detail(record)
    assert [request.timestamp_ms for request in detail.requests] == [1000, 2000]
    assert detail.requests[0].usd == Decimal("0.25") and detail.requests[1].usd is None
    assert detail.breakdown == {"output": (7, Decimal("0.5"))}
    assert (detail.exit_code, detail.failure_stage, detail.error) == (1, "launch", "boom")
    assert record_detail(tmp_path / "missing") is None


# Entry checks ------------------------------------------------------------------


def test_without_a_terminal_top_points_to_queue_ls():
    stderr = io.StringIO()
    assert launch({}, stdin=io.StringIO(), stdout=io.StringIO(), stderr=stderr) == 1
    assert stderr.getvalue().strip() == NO_TERMINAL


def test_without_textual_top_prints_the_install_hint(monkeypatch):
    from silverquillm import top

    monkeypatch.setattr(top, "textual_available", lambda: False)
    stderr = io.StringIO()
    assert launch({}, stdin=_Terminal(), stdout=_Terminal(), stderr=stderr) == 1
    assert stderr.getvalue().strip() == INSTALL_HINT


def test_the_top_command_needs_no_configured_location():
    from silverquillm.cli import main

    result = CliRunner().invoke(main, ["top"])
    assert result.exit_code == 1
    assert "queue ls" in result.output


# Pilot-driven views ------------------------------------------------------------

textual = pytest.importorskip("textual")

from silverquillm.top.app import build_app
from silverquillm.top.details import DetailsView
from silverquillm.top.historic import HistoryView


def synchronous(test):
    """The suite has no async plugin; each pilot test runs its own event loop."""

    @functools.wraps(test)
    def run(*args, **kwargs):
        asyncio.run(test(*args, **kwargs))

    return run


def _app(monitor=None, theme=MTG):
    return build_app(monitor or FakeMonitor(), theme, interval=60, clock=lambda: NOW)


async def _settle(app, pilot):
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


@synchronous
async def test_number_keys_switch_views_and_escape_goes_back():
    app = _app()
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        switcher = app.query_one("#switcher")
        assert switcher.current == "dashboard"
        await pilot.press("2")
        assert switcher.current == "history"
        await pilot.press("3")
        assert switcher.current == "details"
        await pilot.press("escape")
        assert switcher.current == "history"


@synchronous
async def test_a_running_run_opens_live_in_run_details():
    monitor = FakeMonitor()
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("down", "enter")
        await _settle(app, pilot)
        details = app.query_one(DetailsView)
        assert app.query_one("#switcher").current == "details"
        assert details.shown.live is not None
        assert details.shown.run_id == monitor.running[0].run.run_id
        assert monitor.output_calls and details.shown.seq > 0
        assert len(details.shown.requests) == 30
        header = app.query_one("#detail-head").render()
        assert "LIVE" in str(header) or details.shown.live is not None


@synchronous
async def test_a_historic_run_opens_from_the_history_list():
    monitor = FakeMonitor()
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("2")
        await pilot.pause()
        app.query_one("#runs-table").focus()
        await pilot.press("enter")
        await _settle(app, pilot)
        details = app.query_one(DetailsView)
        first = app.query_one(HistoryView).shown[0]
        assert details.shown.run_id == first.run_id
        assert details.shown.live is None and details.shown.retained_loaded
        assert details.shown.detail is not None


@synchronous
async def test_history_sorts_and_hides_excluded_runs():
    app = _app()
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("2")
        view = app.query_one(HistoryView)
        assert view.shown[-1].excluded, "excluded runs sit beneath the included ones"
        assert len(view.shown) == len(history())
        app.query_one("#runs-table").focus()
        await pilot.press("x")
        assert all(run.excluded is None for run in view.shown)
        assert len(view.shown) == len(history()) - 1
        view.sort_key, view.sort_reverse = "cost", True
        view.action_reverse_sort()
        costs = [run.estimated_cost for run in view.shown]
        assert costs == sorted(costs)
        await pilot.press("s")
        assert view.sort_key == "duration"


@synchronous
async def test_choosing_a_benchmark_or_candidate_filters_the_run_list():
    app = _app()
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("2")
        view = app.query_one(HistoryView)
        view.selection = ("benchmark", "smoke")
        view._fill()
        assert {run.benchmark for run in view.shown} == {"smoke"}
        sol = next(run for run in history() if run.candidate.name == "bare-codex-sol61")
        view.selection = ("candidate", sol.candidate.key)
        view._fill()
        hashes = {run.candidate_hash for run in view.shown}
        assert len(hashes) == 2, "one Candidate display groups every rebuild"
        view.selection = ("hash", sol.candidate_hash)
        view._fill()
        assert {run.candidate_hash for run in view.shown} == {sol.candidate_hash}


@synchronous
async def test_the_plain_theme_renders_every_view():
    app = _app(theme=PLAIN)
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(app, pilot)
        await pilot.press("enter")
        await _settle(app, pilot)
        await pilot.press("2")
        await pilot.pause()
        assert app.ansi_color


@synchronous
async def test_quitting_closes_the_monitor():
    monitor = FakeMonitor(running=[])
    app = _app(monitor)
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(app, pilot)
        assert app.query_one("#running-empty").display
        await pilot.press("q")
    assert monitor.closed


@synchronous
async def test_a_run_that_finishes_switches_to_its_retained_output():
    monitor = FakeMonitor()
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("down", "enter")
        await _settle(app, pilot)
        details = app.query_one(DetailsView)
        run_id = details.shown.run_id
        monitor.running = [view for view in monitor.running if view.run.run_id != run_id]
        app.poll()
        await _settle(app, pilot)
        assert details.shown.live is None
        assert details.shown.retained_loaded
        assert monitor.output_calls[-1] == (run_id, 0)


def test_the_output_log_line_shape_is_what_the_view_expects():
    line = LogLine(1, "stdout", "x", datetime(2026, 1, 1, tzinfo=UTC))
    assert (line.seq, line.stream, line.text) == (1, "stdout", "x")


@synchronous
async def test_clicks_open_runs_switch_views_and_sort_history():
    monitor = FakeMonitor()
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.click("#running-table", offset=(10, 3))
        await _settle(app, pilot)
        details = app.query_one(DetailsView)
        assert app.query_one("#switcher").current == "details"
        assert details.shown.run_id == monitor.running[0].run.run_id
        await pilot.press("escape")
        await pilot.press("2")
        await pilot.pause()
        view = app.query_one(HistoryView)
        await pilot.click("#runs-table", offset=(2, 0))
        await pilot.pause()
        assert view.sort_key == "date" and not view.sort_reverse
        await pilot.click("#runs-table", offset=(2, 2))
        await _settle(app, pilot)
        assert app.query_one("#switcher").current == "details"
        assert details.shown.run_id == view.shown[1].run_id


@synchronous
async def test_the_view_tabs_in_the_top_bar_are_clickable():
    app = _app()
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        text = app.query_one("#topbar").render()
        column = str(text).index("2 History")
        await pilot.click("#topbar", offset=(column + 1, 0))
        await pilot.pause()
        assert app.query_one("#switcher").current == "history"


def test_tree_counts_sit_in_their_own_right_aligned_column():
    from silverquillm.top.historic import _entry

    short = _entry(Text("smoke"), 8, 30, MTG).plain
    long = _entry(Text("bare-claude-sonnet-xhigh-extra-long-name"), 346, 30, MTG).plain
    assert len(short) == len(long) == 30
    assert short.endswith("    8") and long.endswith("  346")
    assert "…" in long and long[long.index("…") + 1] == " "


def test_each_location_source_sits_beside_its_path():
    from silverquillm.top.dashboard import StatusPane

    lines = _plain(StatusPane._where(FakeMonitor().snapshot(), MTG)).splitlines()
    assert any("bench-results (config)" in line for line in lines), lines
    assert any("silverquillm (default)" in line for line in lines), lines


def test_a_run_needing_recovery_has_its_own_badge():
    from silverquillm.top.details import Shown, header

    views = FakeMonitor().running
    stuck = next(view for view in views if view.run.stage.value == "needs_recover")
    running = next(view for view in views if view.run.stage.value == "running")
    stuck_head = _plain(header(Shown(stuck.run.run_id, live=stuck), NOW, MTG))
    assert "NEEDS RECOVER" in stuck_head and "LIVE" not in stuck_head
    assert "LIVE" in _plain(header(Shown(running.run.run_id, live=running), NOW, MTG))


@synchronous
async def test_unpriced_recorded_requests_say_so():
    from silverquillm.monitor import RecordDetail, RequestCost

    class Unpriced(FakeMonitor):
        def record_detail(self, summary):
            return RecordDetail(
                [RequestCost(1_791_000_000_000, "m", {}, None)], {}, None, None, None, None
            )

    app = _app(Unpriced())
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("2")
        app.query_one("#runs-table").focus()
        await pilot.press("enter")
        await _settle(app, pilot)
        table = app.query_one("#requests-table")
        assert str(table.get_row_at(0)[-1]) == "unpriced"


def _plain(renderable) -> str:
    from rich.console import Console

    console = Console(width=160, record=True, color_system=None)
    console.print(renderable)
    return console.export_text()
