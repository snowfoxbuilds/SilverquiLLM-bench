"""The monitor app under hostile evidence, slow reads, late records and noisy logs."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import threading
import time
from pathlib import Path

import pytest

from silverquillm.monitor import CommitEntry, LogLine, WorkspaceView, render_line
from silverquillm.top.app import build_app
from silverquillm.top.details import MAX_LOG_LINES, DetailsView, activity_rows
from silverquillm.top.historic import HistoryView
from silverquillm.top.theme import MTG, PLAIN

from .test_top import _app, _plain, _settle, synchronous
from .top_fixtures import NOW, FakeMonitor, history, output_lines, workspace

# Candidate evidence is literal --------------------------------------------------

MARKUP = "Fix [/bold] parsing [red]x[/]"


def _bracketed_history():
    runs = history()
    first = runs[0]
    candidate = dataclasses.replace(first.candidate, name=MARKUP)
    runs[0] = dataclasses.replace(
        first,
        benchmark="[/b]bench",
        candidate=candidate,
        login_profile=f"karn-claude-login/{MARKUP}",
        host_label=MARKUP,
    )
    return runs


class Bracketed(FakeMonitor):
    def workspace(self, run_id):
        view = workspace()
        commit = CommitEntry(NOW, "commit", MARKUP, "9f1e0a7c3b21")
        return WorkspaceView(view.snapshots, (*view.commits, commit))


@synchronous
async def test_markup_in_candidate_evidence_is_shown_literally():
    app = _app(Bracketed(runs=_bracketed_history()))
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("2")
        view = app.query_one(HistoryView)
        view.selection = ("benchmark", "[/b]bench")
        view._fill()
        await pilot.pause()
        assert "[/b]bench" in str(app.query_one("#runs").border_title)
        table = app.query_one("#runs-table")
        cells = [str(cell) for cell in table.get_row_at(0)]
        assert MARKUP in cells, "host and login cells keep their brackets"
        assert any(cell.startswith(MARKUP) for cell in cells), "so does the candidate"
        table.focus()
        await pilot.press("enter")
        await _settle(app, pilot)
        commits = app.query_one("#commits-table")
        messages = [str(commits.get_row_at(row)[2]) for row in range(commits.row_count)]
        assert MARKUP in messages
        await pilot.press("1", "2")
        assert app.query_one("#switcher").current == "history"


@pytest.mark.parametrize(
    "event",
    [
        {"type": "result", "subtype": "success", "total_cost_usd": 10**400, "num_turns": 10**400},
        {"type": "result", "subtype": "success", "total_cost_usd": "lots", "num_turns": 1.5},
        {
            "type": "rate_limit_event",
            "rate_limit_info": {"unifiedWindows": {"seven_day": {"utilization": 10**400}}},
        },
        {"type": "turn.completed", "usage": {"input_tokens": 10**400, "output_tokens": "x"}},
        {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 10**400}},
    ],
)
def test_out_of_range_numbers_never_stop_the_activity_stream(event):
    items = render_line(json.dumps(event))
    assert all(isinstance(item.text, str) for item in items)
    assert render_line('{"type": "turn.started"}')[0].text == "turn started"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_unknown_not_formatted(value):
    line = '{"type": "result", "subtype": "success", "total_cost_usd": ' + value + "}"
    (item,) = render_line(line)
    assert "reported" not in item.text


# Background work is bounded ----------------------------------------------------


class Slow(FakeMonitor):
    """A monitor whose reads take a while and that counts any read after close."""

    def __init__(self, delay=0.2, **kwargs):
        super().__init__(**kwargs)
        self.delay = delay
        self.snapshots = 0
        self.after_close = 0
        self.active = 0
        self.most_active = 0
        self._guard = threading.Lock()

    def _read(self):
        with self._guard:
            self.active += 1
            self.most_active = max(self.most_active, self.active)
            self.after_close += self.closed
        time.sleep(self.delay)
        with self._guard:
            self.active -= 1

    def snapshot(self):
        self._read()
        self.snapshots += 1
        return super().snapshot()

    def output(self, run_id, stream=None, since=0):
        self._read()
        return [
            LogLine(line.seq, line.stream, f"{run_id[:8]} {line.text}", line.at)
            for line in super().output(run_id, stream, since)
        ]


async def _lines(app, pilot, tab: str, log: str) -> list[str]:
    """A log's rendered lines; a log in a hidden tab renders only once its tab is shown."""
    app.query_one("#detail-tabs").active = tab
    await pilot.pause()
    await pilot.pause()
    return [strip.text for strip in app.query_one(log).lines]


async def _wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        await asyncio.sleep(0.02)


@synchronous
async def test_slow_reads_never_pile_up_and_quitting_stays_responsive():
    monitor = Slow()
    app = build_app(monitor, MTG, interval=0.03, clock=lambda: NOW)
    threads_before = threading.active_count()
    async with app.run_test(size=(160, 44)) as pilot:
        began = time.monotonic()
        for _ in range(10):
            await pilot.press("r")
        await pilot.pause(0.6)
        assert monitor.most_active == 1, "one read at a time"
        # One poll in flight and one details fetch at most: never a thread per tick.
        assert threading.active_count() - threads_before <= 3
        # Back to back at best; ~20 ticks and 10 presses coalesce into what time allows.
        assert monitor.snapshots <= (time.monotonic() - began) / monitor.delay + 2
        started = time.monotonic()
        await pilot.press("q")
    assert time.monotonic() - started < 0.5, "quitting never waits on a read"
    await _wait_for(lambda: monitor.closed)
    assert monitor.after_close == 0


@synchronous
async def test_switching_runs_never_shows_the_previous_runs_output():
    monitor = Slow(delay=0.15)
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("down", "enter")
        await pilot.press("escape", "down", "enter")
        await _wait_for(lambda: monitor.active == 0)
        await _settle(app, pilot)
        await _wait_for(lambda: monitor.active == 0)
        await _settle(app, pilot)
        shown = app.query_one(DetailsView).shown.run_id[:8]
        raw = await _lines(app, pilot, "tab-raw", "#log-raw")
        assert all(line.startswith(shown) for line in raw), "only the shown run's output"
        stdout = [line for line in output_lines() if line.stream == "stdout"]
        assert len(raw) == len(stdout), "no duplicate output"


# A finished run's record is retried until it reads ------------------------------


@synchronous
async def test_a_record_that_reaches_history_late_is_still_shown():
    monitor = FakeMonitor()
    run_id = monitor.running[0].run.run_id
    late = dataclasses.replace(history()[0], run_id=run_id, path=Path("/results/late"))
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("down", "enter")
        await _settle(app, pilot)
        details = app.query_one(DetailsView)
        assert details.shown.run_id == run_id
        monitor.running = monitor.running[1:]
        app.poll()
        await _settle(app, pilot)
        assert details.shown.live is None and details.shown.retained_loaded
        assert details.shown.detail is None, "its summary has not reached the history yet"
        raw = await _lines(app, pilot, "tab-raw", "#log-raw")
        assert raw, "the retained logs are shown"
        monitor.runs = [late, *monitor.runs]
        app.poll()
        await _settle(app, pilot)
        assert details.shown.detail is not None and details.shown.detail_ready
        assert await _lines(app, pilot, "tab-raw", "#log-raw") == raw, "logs not appended again"
        assert len(details.shown.requests) == 30


class Flaky(FakeMonitor):
    """A manifest that is unreadable, then missing, then readable; logs never available."""

    def __init__(self):
        super().__init__()
        self.detail_calls = 0

    def record_detail(self, summary):
        self.detail_calls += 1
        if self.detail_calls == 1:
            raise OSError("manifest briefly unreadable")
        if self.detail_calls == 2:
            return None
        return super().record_detail(summary)

    def output(self, run_id, stream=None, since=0):
        self.output_calls.append((run_id, since))
        return []


@synchronous
async def test_an_unreadable_record_is_retried_and_missing_logs_are_read_once():
    monitor = Flaky()
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("2")
        app.query_one("#runs-table").focus()
        await pilot.press("enter")
        await _settle(app, pilot)
        details = app.query_one(DetailsView)
        assert details.shown.detail is None
        for _ in range(2):
            app.poll()
            await _settle(app, pilot)
        assert details.shown.detail_ready and monitor.detail_calls == 3
        assert len(monitor.output_calls) == 1, "unavailable logs are read once"
        app.poll()
        await _settle(app, pilot)
        assert monitor.detail_calls == 3, "a shown detail is not read again"


@synchronous
async def test_a_run_opened_from_history_shows_its_record_at_once():
    app = _app()
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        await pilot.press("2")
        app.query_one("#runs-table").focus()
        await pilot.press("enter")
        await _settle(app, pilot)
        shown = app.query_one(DetailsView).shown
        assert shown.detail_ready and shown.retained_loaded


# Each tab keeps its own tail ------------------------------------------------------


@pytest.mark.parametrize("flooded", ["stdout", "stderr"])
def test_one_stream_flooding_never_evicts_the_other(flooded):
    other = "stderr" if flooded == "stdout" else "stdout"

    @synchronous
    async def check():
        lines = [LogLine(1, other, "the one line that matters", NOW)]
        lines += [LogLine(seq, flooded, f"noise {seq}", NOW) for seq in range(2, MAX_LOG_LINES + 3)]
        app = _app(FakeMonitor(running=[]))
        async with app.run_test(size=(160, 44)) as pilot:
            await _settle(app, pilot)
            details = app.query_one(DetailsView)
            app.action_view("details")
            details.open("x" * 32)
            details.append_output(lines)
            raw = await _lines(app, pilot, "tab-raw", "#log-raw")
            stderr = await _lines(app, pilot, "tab-stderr", "#log-stderr")
            quiet, noisy = (raw, stderr) if other == "stdout" else (stderr, raw)
            assert quiet == ["the one line that matters"]
            assert len(noisy) == MAX_LOG_LINES and noisy[-1] == f"noise {MAX_LOG_LINES + 2}"
            assert details.shown.seq == MAX_LOG_LINES + 2

    check()


# Theme roles and the stage model ------------------------------------------------


def test_task_lists_and_sort_arrows_come_from_the_theme():
    event = {
        "type": "item.updated",
        "item": {"type": "todo_list", "items": [{"text": "a", "completed": True}, {"text": "b"}]},
    }
    line = LogLine(1, "stdout", json.dumps(event), None)
    plain = _plain(activity_rows(line, PLAIN)[0])
    assert "[x] a" in plain and "[ ] b" in plain
    fancy = _plain(activity_rows(line, MTG)[0])
    assert "☑ a" in fancy and "☐ b" in fancy
    assert (PLAIN.glyph("sort_desc"), PLAIN.glyph("problem")) == ("v", "!")


@synchronous
async def test_stuck_runs_show_why_and_whether_their_container_runs():
    app = _app()
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        table = app.query_one("#running-table")
        rows = [
            "  ".join(str(cell) for cell in table.get_row_at(row)) for row in range(table.row_count)
        ]
        stuck = next(row for row in rows if "needs recover" in row)
        assert "no record" in stuck and "login unsettled" in stuck and "container up" in stuck
        assert any("recording" in row for row in rows)
        assert "cccc3333" in _plain(app.query_one("#pools").content)
        assert app.query_one("#running").border_subtitle == "4 unfinished on this host"
        await pilot.press("enter")
        await _settle(app, pilot)
        header = _plain(app.query_one("#detail-head").content)
        assert "NEEDS RECOVER" in header and "container up" in header
