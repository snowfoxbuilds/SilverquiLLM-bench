"""Run details take their record facts from the record the dashboard applies, and spend
timelines plot by time, whatever order telemetry arrives in (RUN-MONITORING.md)."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from rich.text import Text

from silverquillm.monitor.details import record_detail
from silverquillm.top.app import build_app
from silverquillm.top.dashboard import RunChosen, RunningPane
from silverquillm.top.details import DetailsView, header
from silverquillm.top.format import sparkline
from silverquillm.top.theme import MTG

from .test_monitor import NOW, START, container, event, make_run, ms, publish, retain
from .test_monitor_records import Host, at
from .test_top import _plain, _settle, synchronous

# Sparklines plot by time ----------------------------------------------------------


def _bars(points, width=10, until_ms=None) -> str:
    return sparkline(points, width, MTG, until_ms=until_ms).plain


def test_points_out_of_arrival_order_land_in_their_own_time_buckets():
    early, late = (1_000, Decimal(1)), (10_000, Decimal(9))
    assert _bars([late, early]) == _bars([early, late])
    bars = _bars([late, early])
    assert bars[0] != " " and bars[-1] != " ", "the earliest spend is left, the latest right"


def test_unknown_timestamps_stay_out_of_the_plot_wherever_they_arrive():
    dated = [(5_000, Decimal(2)), (9_000, Decimal(2))]
    assert _bars([(0, Decimal(50)), *dated, (0, Decimal(50))]) == _bars(dated)
    assert _bars([(0, Decimal(5))]) == " " * 10


def test_equal_timestamps_and_the_upper_bound_never_leave_the_plot():
    assert _bars([(7_000, Decimal(1)), (7_000, Decimal(1))]).strip()
    bars = _bars([(1_000, Decimal(1)), (2_000, Decimal(1))], until_ms=11_000)
    assert bars[0] != " " and bars[-1] == " ", "time up to now stretches the axis"
    # An earlier event arriving after ``until_ms`` was taken still lands inside the plot.
    assert len(_bars([(5_000, Decimal(1)), (500, Decimal(1))], until_ms=4_000)) == 10


def test_a_late_earlier_event_through_the_real_reader_still_renders(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    newer, older = ms(NOW - timedelta(seconds=1)), ms(NOW - timedelta(seconds=10))
    (run / "observations.events.jsonl").write_text(
        json.dumps(event("e1", "claude_code.api_request", {"cost_usd": "3"}, stamp=newer))
        + "\n"
        + json.dumps(event("e2", "claude_code.api_request", {"cost_usd": "1"}, stamp=older))
        + "\n"
    )
    host.own(run)
    host.containers = [container("r1")]
    [view] = host.snapshot().running
    assert [stamp for stamp, _ in view.request_costs] == [newer, older]
    spend = RunningPane._cells(view, NOW, MTG)[-1]
    assert isinstance(spend, Text) and "$4" in spend.plain
    # A further earlier event on the next refresh lands too, without stopping the pane.
    with (run / "observations.events.jsonl").open("a") as events:
        stamp = ms(NOW - timedelta(minutes=5))
        events.write(json.dumps(event("e3", "claude_code.api_request", {"cost_usd": "1"}, stamp)))
        events.write("\n")
    [view] = host.snapshot().running
    assert len(view.request_costs) == 3
    RunningPane._cells(view, NOW, MTG)


# The detail reader reads both record layouts ---------------------------------------


def test_the_detail_reader_reads_a_retained_record_and_a_published_one(tmp_path):
    retained = retain(tmp_path / "r1/run-record.json", "r1", cost="40", requests=[at(1, "40")])
    published = publish(tmp_path / "repo", "r1", retained=retained)
    for record in (retained, published):
        detail = record_detail(record)
        assert detail is not None
        assert [request.usd for request in detail.requests] == [Decimal(40)]
        assert detail.requests[0].timestamp_ms == ms(START + timedelta(minutes=1))
    assert record_detail(tmp_path / "missing/run-record.json") is None
    assert record_detail(tmp_path / "missing") is None


# Run details follow the applicable record -------------------------------------------


def _recovered(host):
    """A published original with a partial $10 cost, then a retained $40 linked recovery."""
    run = make_run(host.runs, "r1")
    original = retain(run / "run-record.json", "r1", stopped=False, cost="10")
    publish(host.repo, "r1", retained=original)
    retain(
        run / "recovery-1/run-record.json",
        "r1-recovery-1",
        recovery_of="r1",
        cost="40",
        requests=[at(1, "40")],
    )
    return run


def _app(host):
    return build_app(host.monitor, MTG, interval=60, clock=lambda: NOW)


async def _open(app, pilot, run_id, *, pinned=False):
    app.post_message(RunChosen(run_id, pinned=pinned))
    await _settle(app, pilot)
    await _settle(app, pilot)
    return app.query_one(DetailsView)


def _head(details) -> str:
    return _plain(header(details.shown, NOW, MTG))


def _request_costs(details) -> list[str]:
    table = details.query_one("#requests-table")
    return [str(table.get_row_at(row)[-1]) for row in range(table.row_count)]


@synchronous
async def test_an_unfinished_run_shows_the_linked_recovery_the_dashboard_applies(tmp_path):
    host = Host(tmp_path)
    _recovered(host)
    app = _app(host)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        [view] = app.snapshot.running
        assert view.run.record.run_id == "r1-recovery-1" and view.cost == Decimal(40)
        details = await _open(app, pilot, "r1")
        shown = details.shown
        assert shown.summary.run_id == "r1-recovery-1"
        assert shown.detail is not None and shown.live.cost == Decimal(40)
        assert "$40.00" in _head(details) and "$10.00" not in _head(details)
        assert _request_costs(details) == ["$40.00"]


@synchronous
async def test_a_retained_record_awaiting_publication_supplies_its_details(tmp_path):
    host = Host(tmp_path)
    retain(make_run(host.runs, "r1") / "run-record.json", "r1", cost="40", requests=[at(1, "40")])
    app = _app(host)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        details = await _open(app, pilot, "r1")
        assert details.shown.live is not None, "still unpublished, so still on the dashboard"
        assert details.shown.summary.path.name == "run-record.json"
        assert _request_costs(details) == ["$40.00"]
        assert "$40.00" in _head(details)


@synchronous
async def test_an_original_opened_from_history_stays_the_original(tmp_path):
    host = Host(tmp_path)
    _recovered(host)
    app = _app(host)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        details = await _open(app, pilot, "r1", pinned=True)
        assert details.shown.summary.run_id == "r1"
        assert "$10.00" in _head(details) and "$40.00" not in _head(details)
        assert "$40.00" not in _request_costs(details)


@synchronous
async def test_a_recovery_applying_while_details_are_open_replaces_the_original(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    retain(run / "run-record.json", "r1", stopped=False, cost="10", requests=[at(1, "10")])
    app = _app(host)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        details = await _open(app, pilot, "r1")
        assert details.shown.summary.run_id == "r1"
        assert _request_costs(details) == ["$10.00"]
        retain(
            run / "recovery-1/run-record.json",
            "r1-recovery-1",
            recovery_of="r1",
            cost="40",
            requests=[at(2, "40")],
        )
        app.poll()
        await _settle(app, pilot)
        await _settle(app, pilot)
        assert details.shown.summary.run_id == "r1-recovery-1"
        assert _request_costs(details) == ["$40.00"], "no request of the original remains"
        assert "$40.00" in _head(details) and "$10.00" not in _head(details)


@synchronous
async def test_a_recorded_detail_that_cannot_be_read_is_retried(tmp_path):
    host = Host(tmp_path)
    record = retain(make_run(host.runs, "r1") / "run-record.json", "r1", cost="40")
    reads = []
    real = host.monitor.record_detail

    def flaky(summary):
        reads.append(summary.run_id)
        if len(reads) == 1:
            raise OSError("briefly unreadable")
        return real(summary)

    host.monitor.record_detail = flaky
    app = _app(host)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        details = await _open(app, pilot, "r1")
        assert details.shown.detail is None and not details.shown.detail_ready
        app.poll()
        await _settle(app, pilot)
        await _settle(app, pilot)
        assert details.shown.detail_ready and len(reads) == 2
    assert record.exists()


@synchronous
async def test_a_live_run_without_a_record_shows_telemetry_until_one_applies(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    (run / "observations.events.jsonl").write_text(
        json.dumps(event("e1", "claude_code.api_request", {"cost_usd": "25"}, stamp=ms(NOW))) + "\n"
    )
    host.own(run)
    host.containers = [container("r1")]
    app = _app(host)
    async with app.run_test(size=(160, 44)) as pilot:
        await _settle(app, pilot)
        details = await _open(app, pilot, "r1")
        assert details.shown.summary is None
        assert _request_costs(details) == ["$25.00"]
        retain(run / "run-record.json", "r1", cost="100", requests=[at(1, "100")])
        host.containers = []
        app.poll()
        await _settle(app, pilot)
        await _settle(app, pilot)
        assert details.shown.summary is not None and details.shown.detail_ready
        assert _request_costs(details) == ["$100.00"], "the record replaces the telemetry"
