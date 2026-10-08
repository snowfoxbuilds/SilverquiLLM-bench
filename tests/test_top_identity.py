"""History rows are whole Run Records, numbers from evidence render or read as unknown, and
an execution's details follow the record that applies to it even across a missed poll
(RUN-MONITORING.md)."""

from __future__ import annotations

import json
from decimal import Decimal

from rich.text import Text

from silverquillm.monitor import Monitor
from silverquillm.top import format as fmt
from silverquillm.top.app import build_app
from silverquillm.top.dashboard import RunChosen, RunningPane
from silverquillm.top.details import DetailsView, header
from silverquillm.top.historic import HistoryView
from silverquillm.top.theme import MTG

from .test_monitor import (
    NOW,
    OTHER_IDENTITY,
    container,
    event,
    make_run,
    ms,
    publish,
    retain,
)
from .test_monitor_records import Host, at
from .test_top import _plain, _settle, synchronous
from .test_top_lifecycle import _lines


def _app(host_or_monitor):
    monitor = getattr(host_or_monitor, "monitor", host_or_monitor)
    return build_app(monitor, MTG, interval=60, clock=lambda: NOW)


def _head(details) -> str:
    return _plain(header(details.shown, NOW, MTG))


def _table(details, selector="#requests-table") -> list[list[str]]:
    table = details.query_one(selector)
    return [[str(cell) for cell in table.get_row_at(row)] for row in range(table.row_count)]


async def _open_row(app, pilot, path):
    """Open the history row of the record stored at ``path``, as the operator would."""
    app.action_view("history")
    await pilot.pause()
    history = app.query_one(HistoryView)
    table = history.query_one("#runs-table")
    index = [str(run.path) for run in history.shown].index(str(path))
    table.focus()
    table.move_cursor(row=index)
    await pilot.press("enter")
    await _settle(app, pilot)
    await _settle(app, pilot)
    return app.query_one(DetailsView)


# A history row is one Run Record --------------------------------------------------


@synchronous
async def test_two_records_sharing_a_run_id_each_open_as_themselves(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    (run / "host").mkdir()
    (run / "host/stdout.log").write_text("local evidence of r1\n")
    ours = publish(host.repo, "r1", cost="10", requests=[at(1, "10")])
    theirs = publish(host.repo, "r1", identity=OTHER_IDENTITY, cost="40", requests=[at(2, "40")])
    app = _app(host)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        [view] = app.snapshot.running
        assert view.run.reasons == ("ambiguous_published_record",), "the core still warns"
        history = app.query_one(HistoryView)
        assert sorted(str(r.path) for r in history.shown) == sorted([str(ours), str(theirs)])
        app.action_view("history")
        await pilot.press("s", "S")
        app.poll()
        await _settle(app, pilot)
        assert len(history.shown) == 2, "sorting and a refresh keep both records"

        details = await _open_row(app, pilot, theirs)
        assert details.shown.summary.path == theirs
        assert "$40.00" in _head(details) and "$10.00" not in _head(details)
        assert [row[-1] for row in _table(details)] == ["$40.00"]
        assert details.shown.live is None, "this host's r1 ran the other candidate"
        assert await _lines(app, pilot, "tab-raw", "#log-raw") == []

        details = await _open_row(app, pilot, ours)
        assert details.shown.summary.path == ours
        assert "$10.00" in _head(details) and "$40.00" not in _head(details)
        assert [row[-1] for row in _table(details)] == ["$10.00"]
        assert any(
            "local evidence" in line for line in await _lines(app, pilot, "tab-raw", "#log-raw")
        )


# Numbers from evidence are bounded where they are read and rendered -----------------


def test_counts_outside_a_sane_range_read_as_unknown():
    for value in (10**400, -1, True, "5", 1.5, None):
        assert fmt.count(value) == fmt.DASH
    assert fmt.count(1500) == "1.5k" and fmt.count(0) == "0"


def test_a_sparkline_ignores_stamps_no_datetime_can_hold():
    points = [(10**400, Decimal(5)), (-3, Decimal(5)), (1_000, Decimal(1)), (2_000, Decimal(1))]
    assert len(fmt.sparkline(points, 10, MTG, until_ms=10**400).plain) == 10
    assert fmt.sparkline([(10**400, Decimal(1))], 4, MTG).plain == "    "


def test_huge_live_telemetry_numbers_render_as_unknown(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    huge = event(
        "e1", "claude_code.api_request", {"cost_usd": "1", "input_tokens": 10**400}, stamp=10**400
    )
    fine = event(
        "e2", "claude_code.api_request", {"cost_usd": "2", "input_tokens": 1200}, stamp=ms(NOW)
    )
    (run / "observations.events.jsonl").write_text(
        json.dumps(huge) + "\n" + json.dumps(fine) + "\n"
    )
    host.own(run)
    host.containers = [container("r1")]
    [view] = host.snapshot().running
    spend = RunningPane._cells(view, NOW, MTG)[-1]
    assert isinstance(spend, Text) and "$3" in spend.plain, "both requests still count"
    requests = host.monitor.provisional_requests("r1")
    assert [r.timestamp_ms for r in requests] == [0, ms(NOW)], "an impossible time is unknown"
    assert [r.tokens.get("input_tokens") for r in requests] == [None, 1200]


def _huge_record(host):
    """A published record that validates, with numbers no float or datetime can hold."""
    directory = publish(host.repo, "r1", cost="5", requests=[at(1, "2"), at(2, "3")])
    manifest = json.loads((directory / "manifest.json").read_text())
    measurements = manifest["run_metadata"]["measurements"]
    measurements["requests"][0].update(usage={"input_tokens": 10**400, "output_tokens": -5})
    measurements["requests"][0]["timestamp_ms"] = 10**400
    measurements["requests"][1].update(usage={"input_tokens": 1200, "output_tokens": "many"})
    measurements["agent_turns"] = {
        "completeness": "complete",
        "reasons": [],
        "value": {"total": 10**400},
    }
    measurements["usage"] = {
        "completeness": "complete",
        "reasons": [],
        "value": {"total_tokens": -1},
    }
    measurements["cost_breakdown"] = {
        "completeness": "complete",
        "reasons": [],
        "value": {
            "output": {"tokens": 10**400, "usd": "1"},
            "uncached_input": {"tokens": 7, "usd": "2"},
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory


@synchronous
async def test_a_record_with_huge_numbers_renders_and_navigates(tmp_path):
    host = Host(tmp_path)
    directory = _huge_record(host)
    app = _app(host)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        [summary] = app.query_one(HistoryView).shown
        assert summary.path == directory, "the record still validates and is listed"
        assert summary.agent_turns is None and summary.total_tokens is None
        details = await _open_row(app, pilot, directory)
        rows = _table(details)
        assert len(rows) == 2, "every request is still listed"
        # The untimed request sorts first; its impossible counts read as unknown, not zero.
        assert rows[0][0] == fmt.DASH and rows[0][2] == fmt.DASH and rows[0][-1] == "$2.00"
        assert rows[1][2] == "1.2k" and rows[1][-1] == "$3.00"
        assert details.shown.detail.breakdown["output"][0] is None
        assert details.shown.detail.breakdown["uncached_input"] == (7, Decimal(2))
        assert "$5.00" in _head(details)
        app.action_view("dashboard")
        await pilot.pause()
        app.action_view("history")
        await pilot.pause()


# Details follow the record that applies, even across a missed poll ------------------


async def _open(app, pilot, run_id):
    app.post_message(RunChosen(run_id))
    await _settle(app, pilot)
    await _settle(app, pilot)
    return app.query_one(DetailsView)


@synchronous
async def test_a_recovery_that_finishes_between_polls_replaces_the_original(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    original = retain(
        run / "run-record.json", "r1", stopped=False, cost="10", requests=[at(1, "10")]
    )
    publish(host.repo, "r1", retained=original)
    app = _app(host)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        details = await _open(app, pilot, "r1")
        assert details.shown.summary.run_id == "r1" and details.shown.live is not None
        # Between two polls the recovery is retained and published: the run is Finished.
        recovery = retain(
            run / "recovery-1/run-record.json",
            "r1-recovery-1",
            recovery_of="r1",
            cost="40",
            requests=[at(2, "40")],
        )
        publish(host.repo, "r1-recovery-1", retained=recovery)
        app.poll()
        await _settle(app, pilot)
        await _settle(app, pilot)
        assert app.snapshot.running == []
        assert details.shown.summary.run_id == "r1-recovery-1"
        assert [row[-1] for row in _table(details)] == ["$40.00"], "none of the original's"
        assert "$40.00" in _head(details) and "$10.00" not in _head(details)


@synchronous
async def test_a_retained_final_record_applies_without_a_results_repo(tmp_path):
    host = Host(tmp_path)
    monitor = Monitor(
        given={"runs_dir": host.runs, "state_root": host.state},
        environ=host.environ,
        docker=lambda: (list(host.containers), None),
        proc_locks=host.locks,
        clock=lambda: host.now,
        follow_output=False,
    )
    run = make_run(host.runs, "r1")
    (run / "observations.events.jsonl").write_text(
        json.dumps(event("e1", "claude_code.api_request", {"cost_usd": "25"}, stamp=ms(NOW))) + "\n"
    )
    host.own(run)
    host.containers = [container("r1")]
    app = _app(monitor)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        details = await _open(app, pilot, "r1")
        assert details.shown.summary is None and [r[-1] for r in _table(details)] == ["$25.00"]
        # The run records itself and its runner exits, all between two polls.
        retain(run / "run-record.json", "r1", cost="100", requests=[at(1, "100")])
        host.containers = []
        host.release()
        app.poll()
        await _settle(app, pilot)
        await _settle(app, pilot)
        assert app.snapshot.running == []
        assert details.shown.summary is not None and details.shown.summary.run_id == "r1"
        assert [r[-1] for r in _table(details)] == ["$100.00"], "the record replaces telemetry"
        assert "$100.00" in _head(details)
