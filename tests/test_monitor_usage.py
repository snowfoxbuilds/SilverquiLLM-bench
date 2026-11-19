"""The Estimated Weekly Usage estimator the monitor shares with the host's Usage Limit check
(RUN-MONITORING.md, Estimated Weekly Usage): a process without a monitor gets the figure the
monitor shows from the same records, run directories and readings."""

from __future__ import annotations

import errno
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from silverquillm.monitor import costs
from silverquillm.monitor.costs import EVENTS_FILE, ProvisionalCost
from silverquillm.monitor.estimates import newest_reading
from silverquillm.monitor.history import UsageReading
from silverquillm.monitor.usage import ExecutionSpend, estimate_profile_usage, execution_spend

from .test_monitor import NOW, event, finishes, make_run, ms, publish, retain
from .test_monitor_records import PROFILE, RATES, Host, at, claude_usage, fable_run, live_cost


def estimate(host: Host, *, readings=(), login=PROFILE, execution=None):
    return estimate_profile_usage(
        login,
        "claude",
        rates=RATES,
        host_label="host-a",
        state_root=host.state,
        runs_dir=host.runs,
        results_repo=host.repo,
        readings=readings,
        execution=execution,
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


# An unrecorded run's whole events file counts, however large its backlog


CHUNK = 256


@pytest.fixture
def small_chunks(monkeypatch):
    """Chunks and the line limit scaled down, so a multi-chunk backlog stays small."""
    monkeypatch.setattr(costs, "MAX_READ", CHUNK)
    monkeypatch.setattr(costs, "MAX_LINE", 4 * CHUNK)


def request(identity, usd, request_id=None, **padding):
    attributes = {"cost_usd": usd, **padding}
    if request_id is not None:
        attributes["request_id"] = request_id
    moment = NOW - timedelta(minutes=5)
    return json.dumps(event(identity, "claude_code.api_request", attributes, stamp=ms(moment)))


def write_events(directory, *lines, end="\n"):
    path = directory / EVENTS_FILE
    path.write_text("\n".join(lines) + end)
    return path


def snapshot_cost(directory):
    cost = ProvisionalCost(directory, "claude")
    cost.read_snapshot()
    return cost


@pytest.mark.parametrize("fable", [False, True], ids=["weekly", "fable"])
def test_a_standalone_estimate_reads_past_the_first_chunk(tmp_path, small_chunks, fable):
    """The monitor reaches its figure over successive polls; one standalone call reaches it."""
    host = Host(tmp_path)
    usage = claude_usage(20.0, resets="2026-10-08T14:00:00Z")
    usage["fable"] = {**usage["value"], "utilization_percent": 80.0}
    publish(host.repo, "r0", usage=usage, requests=[])
    run = (fable_run if fable else make_run)(host.runs, "r1")
    path = write_events(run, *(request(f"e{n}", "1.25") for n in range(40)))
    assert path.stat().st_size > 20 * CHUNK
    host.own(run, login=True)
    found = estimate(host)
    expected = [(pytest.approx(22.0), True), (pytest.approx(82.0 if fable else 80.0), True)]
    assert figures(found) == expected
    assert monitor_figures(host) != expected, "one poll reads only the first chunk"
    for _ in range(path.stat().st_size // CHUNK):
        host.snapshot()
    assert monitor_figures(host) == figures(found)


def test_a_request_spanning_a_chunk_boundary_counts(tmp_path, small_chunks):
    filler = json.dumps(event("f", "claude_code.tool_result", {}))
    filler = filler[:-1] + ", " + json.dumps({"pad": ""})[1:]
    filler = filler.replace('"pad": ""', '"pad": "' + "x" * (CHUNK - 20 - len(filler)) + '"')
    path = write_events(tmp_path, filler, request("e1", "3"))
    assert len(filler) < CHUNK < len(filler) + 1 + len(request("e1", "3"))
    assert path.stat().st_size < 2 * CHUNK
    assert snapshot_cost(tmp_path).total == Decimal(3)


def test_a_request_repeated_across_chunks_is_charged_once(tmp_path, small_chunks):
    first = request("e1", "25", "req_1")
    fillers = [request(f"f{n}", "1") for n in range(10)]
    path = write_events(
        tmp_path, first, *fillers, request("e2", "25", "req_1"), request("e3", "30", "req_1")
    )
    assert path.stat().st_size > 5 * CHUNK
    cost = snapshot_cost(tmp_path)
    assert (cost.total, cost.conflicts, len(cost.requests)) == (Decimal(35), 1, 11)


def test_malformed_oversized_and_unfinished_lines_charge_nothing(tmp_path, small_chunks):
    oversized = request("big", "100", pad="x" * costs.MAX_LINE)
    write_events(
        tmp_path,
        "not json",
        "[1, 2]",
        '{"id": "e0", "kind": "claude_code.api_request"}',
        oversized,
        request("e1", "2"),
        request("e2", "50"),
        end="",
    )
    cost = snapshot_cost(tmp_path)
    assert (cost.total, len(cost.requests)) == (Decimal(2), 1)


def test_a_missing_or_irregular_events_file_reads_nothing(tmp_path):
    missing, directory, link, fifo = (tmp_path / n for n in ("missing", "dir", "link", "fifo"))
    for run in (missing, directory, link, fifo):
        run.mkdir()
    (directory / EVENTS_FILE).mkdir()
    target = write_events(tmp_path, request("e1", "5"))
    (link / EVENTS_FILE).symlink_to(target)
    os.mkfifo(fifo / EVENTS_FILE)
    for run in (missing, directory, link, fifo):
        cost = ProvisionalCost(run, "claude")
        finishes(cost.read_snapshot)
        assert (cost.available, cost.total) == (False, None)


def test_a_read_failure_ends_the_scan_with_what_was_read(tmp_path, small_chunks, monkeypatch):
    write_events(tmp_path, *(request(f"e{n}", "1") for n in range(10)))
    read, calls = os.read, []

    def failing(descriptor, size):
        calls.append(size)
        if len(calls) > 1:
            raise OSError(errno.EIO, "I/O error")
        return read(descriptor, size)

    monkeypatch.setattr(costs.os, "read", failing)
    cost = snapshot_cost(tmp_path)
    assert len(calls) == 2
    assert (cost.total, len(cost.requests)) == (Decimal(1), 1)


def test_appends_during_the_scan_are_left_past_the_captured_length(
    tmp_path, small_chunks, monkeypatch
):
    finished = [request(f"e{n}", "1") for n in range(5)]
    unfinished = request("e5", "10")
    path = write_events(tmp_path, *finished, unfinished[:30], end="")
    read, appended = os.read, []

    def appending(descriptor, size):
        if not appended:
            appended.append(True)
            with path.open("a") as handle:
                handle.write(unfinished[30:] + "\n" + request("e6", "100") + "\n")
        return read(descriptor, size)

    monkeypatch.setattr(costs.os, "read", appending)
    cost = snapshot_cost(tmp_path)
    monkeypatch.setattr(costs.os, "read", read)
    assert (cost.total, len(cost.requests)) == (Decimal(5), 5)
    assert snapshot_cost(tmp_path).total == Decimal(115), "a later snapshot reads them"


def test_repeated_standalone_estimates_each_count_the_whole_spend_once(tmp_path, small_chunks):
    host = Host(tmp_path)
    publish(host.repo, "r0", usage=claude_usage(20.0, resets="2026-10-08T14:00:00Z"), requests=[])
    run = make_run(host.runs, "r1")
    path = write_events(run, *(request(f"e{n}", "2.5") for n in range(20)))
    host.own(run, login=True)
    assert [estimate(host).weekly.percent for _ in range(3)] == [pytest.approx(22.0)] * 3
    with path.open("a") as handle:
        handle.write(request("e20", "25") + "\n" + request("e0", "2.5") + "\n")
    assert estimate(host).weekly.percent == pytest.approx(23.0)


def test_a_record_replaces_a_large_provisional_spend_once(tmp_path, small_chunks):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    write_events(run, *(request(f"e{n}", "5") for n in range(20)))
    host.own(run, login=True)
    assert estimate(host).weekly.percent == pytest.approx(4.0)
    record = retain(run / "run-record.json", "r1", requests=[at(1, "25")])
    found = estimate(host)
    assert found.weekly.percent == pytest.approx(1.0)
    publish(host.repo, "r1", retained=record)
    assert estimate(host).weekly.percent == pytest.approx(1.0)
    for _ in range(20):
        host.snapshot()
    assert monitor_figures(host) == figures(estimate(host))


# ---- A run's own reconciled spend, before its record exists ------------------------------


def spend(run_id, usd, moment=NOW - timedelta(minutes=5), model="claude-opus-4-7"):
    return ExecutionSpend(run_id, ((ms(moment), Decimal(usd)),), model)


def test_an_executions_spend_replaces_its_provisional_telemetry(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    live_cost(run, "50", NOW - timedelta(minutes=5))
    host.own(run, login=True)
    assert estimate(host).weekly.percent == pytest.approx(2.0)
    assert estimate(host, execution=spend("r1", "75")).weekly.percent == pytest.approx(3.0)


def test_an_executions_spend_replaces_its_earlier_record(tmp_path):
    # As a linked recovery's reconciled spend replaces what its original's record charged.
    host = Host(tmp_path)
    publish(host.repo, "r1", requests=[at(60, "25")])
    publish(host.repo, "r2", requests=[at(60, "25")])
    assert estimate(host).weekly.percent == pytest.approx(2.0)
    found = estimate(host, execution=spend("r1", "50"))
    assert found.weekly.percent == pytest.approx(3.0)


def test_an_executions_spend_counts_once_its_record_is_written(tmp_path):
    host = Host(tmp_path)
    run = make_run(host.runs, "r1")
    host.own(run, login=True)
    before = estimate(host, execution=spend("r1", "50", moment=at(1, "50")[0]))
    retain(run / "run-record.json", "r1", requests=[at(1, "50")])
    assert estimate(host).weekly.percent == pytest.approx(before.weekly.percent)
    assert estimate(host, execution=spend("r1", "50", moment=at(1, "50")[0])).weekly.percent == (
        pytest.approx(before.weekly.percent)
    )


def test_a_fable_executions_spend_counts_against_the_fable_limit_too(tmp_path):
    host = Host(tmp_path)
    usage = claude_usage(10.0, resets="2026-10-08T14:00:00Z")
    usage["fable"] = {**usage["value"], "utilization_percent": 20.0}
    publish(host.repo, "r0", usage=usage, requests=[])
    fable = estimate(host, execution=spend("r1", "50", model="claude-fable-5-2"))
    other = estimate(host, execution=spend("r1", "50"))
    assert (fable.weekly.percent, fable.fable.percent) == (
        pytest.approx(12.0),
        pytest.approx(22.0),
    )
    assert other.fable.percent == pytest.approx(20.0)


def test_mixed_otel_and_native_evidence_is_charged_once_as_its_record_would(tmp_path):
    from pathlib import Path

    from silverquillm.karn.observations import summarize_events

    fixture = Path(__file__).parent / "fixtures" / "karn_observations" / "retry.jsonl"
    events = [json.loads(line) for line in fixture.read_text().splitlines()]
    assert {event["source"] for event in events} == {"otel", "native"}
    measured = summarize_events(events, exit_kind="completed")
    found = execution_spend("r1", measured, "gpt-5.4")
    assert len(found.costs) == measured["agent_turns"]["responses"]["value"]
    assert sum(usd for _, usd in found.costs) == Decimal(measured["estimated_cost"]["value"])
    from silverquillm.monitor.history import summarize

    record = retain(tmp_path / "run-record.json", "r1")
    document = json.loads(record.read_text())
    document["manifest"]["run_metadata"]["measurements"] = measured
    summary = summarize(document["manifest"], document["scores"], record)
    assert found.costs == summary.request_costs
