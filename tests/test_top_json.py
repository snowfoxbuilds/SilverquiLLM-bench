"""``silverquillm top --json``: one headless snapshot of what the monitor shows (#225)."""

from __future__ import annotations

import functools
import io
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from click.testing import CliRunner

from silverquillm.cli import main as cli
from silverquillm.karn.execution import run_lock
from silverquillm.monitor import Monitor, ProfileStatus, ProfileView
from silverquillm.monitor.headless import snapshot_document
from silverquillm.monitor.queue import ledger_status
from silverquillm.top import print_snapshot

from .test_monitor import (
    NOW as MONITOR_NOW,
)
from .test_monitor import (
    RUN_SPEC,
    container,
    cost_measurements,
    enroll_slot,
    make_run,
    publish,
    summary_of,
    tree_state,
    write_batch,
)
from .top_fixtures import NOW, FakeMonitor


def _document(snapshot):
    document = snapshot_document(snapshot)
    # Every value survives a JSON round trip unchanged: no dates, decimals or paths leak.
    assert json.loads(json.dumps(document)) == document
    return document


def test_the_document_carries_each_runs_stage_reasons_and_batch():
    snapshot = FakeMonitor().snapshot()
    first = snapshot.running[0].run.run_id
    queued = [replace(snapshot.queued[0], run_ids=("r0", first)), *snapshot.queued[1:]]
    document = _document(replace(snapshot, queued=queued))

    assert document["schema_version"] == 1
    assert document["taken_at"] == "2026-10-07T15:30:00Z"
    assert document["host_label"] == "lab-1"
    assert document["dispatch"] == "running"
    assert document["ledger"] == {"status": "none", "error": None}
    assert [run["stage"] for run in document["runs"]] == [
        view.run.stage.value for view in snapshot.running
    ]
    run = document["runs"][0]
    assert run["batch"] == "2026-10-07-effort-sweep" and run["batch_entry"] == 1
    assert run["login_profile"] == snapshot.running[0].run.login_profile
    assert run["started_at"].endswith("Z")
    needs_recover = [run for run in document["runs"] if run["stage"] == "needs_recover"]
    assert needs_recover and all(run["reasons"] for run in needs_recover)
    unbatched = [run for run in document["runs"] if run["run_id"] != first]
    assert all(run["batch"] is None for run in unbatched)


def test_the_queue_lists_every_batch_in_queue_order_with_its_unstarted_entries():
    document = _document(FakeMonitor().snapshot())
    assert [batch["batch"] for batch in document["queue"]] == [
        "2026-10-07-effort-sweep",
        "2026-10-08-night",
        "2026-10-09-new",
    ]
    sweep = document["queue"][0]
    assert (sweep["status"], sweep["started"], sweep["total"]) == ("pending", 2, 5)
    assert [entry["index"] for entry in sweep["pending"]] == [2, 3, 4]
    assert document["queue"][1]["not_before"] == "2026-10-07T23:00:00Z"
    assert document["queue"][2]["status"] == "missing_state"


def test_each_login_profile_has_one_state_word_most_blocking_first():
    snapshot = FakeMonitor().snapshot()

    def view(**fields):
        status = ProfileStatus("karn-codex-login", "s", "codex", **fields)
        return ProfileView(status, None, None)

    cooling = NOW + timedelta(hours=1)
    profiles = [
        view(busy=False, pending=False),
        view(busy=True, pending=False, cooldown_until=cooling),
        view(busy=False, pending=True, pending_run="r9"),
        view(busy=None, pending=False),
        view(busy=False, pending=False, cooldown_until=cooling),
    ]
    logins = _document(replace(snapshot, profiles=profiles))["logins"]
    assert [login["state"] for login in logins] == [
        "free",
        "busy",
        "pending",
        "unknown",
        "cooldown",
    ]
    assert logins[2]["pending_run"] == "r9"
    assert logins[4]["cooldown_until"] == "2026-10-07T16:30:00Z"
    assert logins[0]["weekly_usage_percent"] is None


def test_the_fixture_logins_report_weekly_usage():
    logins = _document(FakeMonitor().snapshot())["logins"]
    opus = next(login for login in logins if login["login_profile"].endswith("bare-claude-opus"))
    assert opus["weekly_usage_percent"] == 41.0 and opus["weekly_usage_estimated"] is False
    assert opus["state"] == "busy"


def test_dispatch_mode_and_a_damaged_ledger_are_reported():
    snapshot = FakeMonitor().snapshot()
    document = _document(
        replace(
            snapshot, dispatch="draining", ledger="damaged", ledger_error="queue_ledger_invalid"
        )
    )
    assert document["dispatch"] == "draining"
    assert document["ledger"] == {"status": "damaged", "error": "queue_ledger_invalid"}


def test_ledger_status_tells_none_ok_and_damaged_apart(tmp_path):
    assert ledger_status(None) == ("none", None)
    assert ledger_status(tmp_path) == ("none", None)
    (tmp_path / "queue.json").write_text(json.dumps({"schema_version": 1, "batches": []}))
    assert ledger_status(tmp_path) == ("ok", None)
    (tmp_path / "queue.json").write_text("{")
    assert ledger_status(tmp_path) == ("damaged", "queue_ledger_invalid")


def test_a_real_snapshot_maps_a_started_run_to_its_batch_and_writes_nothing(tmp_path):
    runs, repo, batches, state = (tmp_path / name for name in ("runs", "repo", "batches", "state"))
    make_run(runs, "live")
    publish(repo, "done", host="host-a")
    enroll_slot(state, "karn-claude-login", "bare-claude-opus")
    spec = RUN_SPEC.format(build=tmp_path / "nobuild", benchmark="smoke")
    write_batch(batches, "sweep", 'format = "karn-v5"\n' + spec + spec)
    (batches / "state").mkdir()
    (batches / "state/sweep.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "batch": "sweep",
                "runs": [{"index": 0, "run_id": "live", "spec": {}, "status": "running"}],
            }
        )
    )
    lock = tmp_path / "proc-locks"
    with run_lock(runs / "live"):
        lock.write_text(Path("/proc/locks").read_text())
        before = tree_state(runs, repo, batches, state)
        monitor = Monitor(
            given={
                "runs_dir": runs,
                "results_repo": repo,
                "batches_dir": batches,
                "state_root": state,
            },
            environ={
                "XDG_CONFIG_HOME": str(tmp_path / "config"),
                "SILVERQUILLM_HOST_LABEL": "host-a",
            },
            docker=lambda: ([container("live")], None),
            proc_locks=lock,
            clock=lambda: MONITOR_NOW,
            follow_output=False,
        )
        try:
            document = _document(monitor.snapshot())
        finally:
            monitor.close()
        after = tree_state(runs, repo, batches, state)
    assert before == after
    [run] = document["runs"]
    assert (run["run_id"], run["stage"], run["batch"], run["batch_entry"]) == (
        "live",
        "running",
        "sweep",
        0,
    )
    assert run["container"]["running"] is True
    [batch] = document["queue"]
    assert (batch["status"], batch["run_ids"], len(batch["pending"])) == (
        "running",
        ["live"],
        1,
    )
    assert document["logins"][0]["login_profile"] == "karn-claude-login/bare-claude-opus"
    assert document["locations"]["runs_dir"] == {"path": str(runs), "source": "flag"}


def test_print_snapshot_needs_no_terminal(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    stdout = io.StringIO()
    status = print_snapshot(
        {"runs_dir": tmp_path / "runs", "batches_dir": tmp_path / "batches", "state_root": None},
        stdout=stdout,
        docker=lambda: ([], "docker unavailable"),
        proc_locks=tmp_path / "no-lock-table",
    )
    assert status == 0
    document = json.loads(stdout.getvalue())
    assert document["runs"] == [] and document["queue"] == []
    assert document["errors"]["docker"] == "docker unavailable"


def test_top_json_on_the_command_line(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(
        "silverquillm.monitor.Monitor",
        functools.partial(Monitor, docker=lambda: ([], None), proc_locks=tmp_path / "none"),
    )
    result = CliRunner().invoke(cli, ["top", "--json", "--batches-dir", str(tmp_path / "batches")])
    assert result.exit_code == 0, result.output
    document = json.loads(result.output)
    assert document["locations"]["batches_dir"]["source"] == "flag"
    assert document["dispatch"] == "running"


def test_a_runs_cost_is_its_run_cost_with_its_source_not_the_estimate():
    # Claude Code reported 2.10 where the price table estimated 2.00 (ADR-019).
    record = summary_of(cost_measurements(("2.10", "complete")))
    snapshot = FakeMonitor().snapshot()
    view = replace(
        snapshot.running[0],
        cost=record.cost,
        cost_source=record.cost_source,
        cost_recorded=True,
        cost_completeness=record.cost_completeness,
    )
    run = _document(replace(snapshot, running=[view, *snapshot.running[1:]]))["runs"][0]
    assert (run["run_cost_usd"], run["run_cost_source"], run["cost_recorded"]) == (
        "2.10",
        "reported",
        True,
    )
    assert "estimated_cost_usd" not in run
