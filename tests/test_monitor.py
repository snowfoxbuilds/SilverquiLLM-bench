"""The monitor's data layer (RUN-MONITORING.md): read-only views of runs, queue, logins, history."""

from __future__ import annotations

import contextlib
import fcntl
import io
import json
import os
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from silverquillm.karn import subscription_usage as subscription_usage_module
from silverquillm.karn.definition import KarnError, canonical, decode_definition, digest
from silverquillm.karn.exclusions import Exclusion, write_exclusion
from silverquillm.karn.execution import run_lock
from silverquillm.karn.login import secret_values
from silverquillm.karn.observations import normalize_rollout
from silverquillm.karn.records import KarnIdentity, KarnRunRecord, missing_scores
from silverquillm.karn.records import write_record as write_run_record
from silverquillm.karn.subscription_usage import codex_usage
from silverquillm.monitor import Monitor, Stage
from silverquillm.monitor.candidates import candidate_display
from silverquillm.monitor.containers import RunContainer, run_containers
from silverquillm.monitor.costs import ProvisionalCost
from silverquillm.monitor.estimates import estimated_percent, weekly_usage
from silverquillm.monitor.history import HistoryStore, UsageReading, summarize
from silverquillm.monitor.live import live_runs
from silverquillm.monitor.locks import held_locks, lock_held
from silverquillm.monitor.output import (
    LineSplitter,
    LogFollower,
    join_partials,
    live_codex_reading,
    profile_redactions,
    redacted_head,
    retained_lines,
)
from silverquillm.monitor.pools import login_profiles
from silverquillm.monitor.queue import queued_batches

from .test_karn_subscription_usage import claude_event, codex_line, write_lines

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
VECTOR = Path(__file__).parent / "fixtures/karn/wire-vectors-v4/canonical-definition-id/input.json"


def _definition() -> dict:
    value = json.loads(VECTOR.read_bytes())
    value["name"] = "bare-claude-opus"
    value["runtime"]["plugins"] = []
    value["runtime"]["environment"] = {
        "CONSTRUCT_MODEL": "claude-opus-5-5",
        "CONSTRUCT_EFFORT": "max",
    }
    return decode_definition(canonical(value))


DEFINITION = _definition()
IDENTITY = {
    "scheme": "karn-v4",
    "definition_version": 4,
    "definition_id": DEFINITION["definition_id"],
    "definition_digest": digest(canonical(DEFINITION)),
    "image": DEFINITION["image"],
    "image_id": "sha256:" + "b" * 64,
}
CANDIDATE_HASH = KarnIdentity.from_dict(IDENTITY).hash
# Another build of the same definition: a different image, so a different Candidate Hash.
OTHER_IDENTITY = {**IDENTITY, "image_id": "sha256:" + "c" * 64}
OTHER_HASH = KarnIdentity.from_dict(OTHER_IDENTITY).hash


def finishes(call, timeout=10.0):
    """The call's result; a call that blocks, on a FIFO say, fails the test instead of hanging it."""
    outcome = {}

    def target():
        try:
            outcome["value"] = call()
        except BaseException as error:  # noqa: BLE001 -- re-raised in the test's thread.
            outcome["error"] = error

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), "the call blocked"
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


def proc_locks(tmp_path: Path) -> Path:
    """A copy of the kernel's lock table, so a test sees exactly the locks held right now."""
    path = tmp_path / "proc-locks"
    path.write_text(Path("/proc/locks").read_text())
    return path


def make_run(runs_dir: Path, run_id: str, *, login="karn-claude-login/bare-claude-opus", **extra):
    run_dir = runs_dir / run_id
    (run_dir / "candidate/constructs/bare-claude-opus").mkdir(parents=True)
    (run_dir / "candidate/constructs/bare-claude-opus/definition.json").write_text(
        json.dumps(DEFINITION)
    )
    run_input = {
        "run_id": run_id,
        "construct": "bare-claude-opus",
        "candidate_identity": IDENTITY,
        "benchmark": "hob-medium",
        "login": login,
        "budget_seconds": 14400,
        "native_telemetry": {"enabled": True, "adapter": "claude"},
        "provenance": {"recipe_revision": "rev-7"},
        "started_at": "2026-10-07T11:00:00+00:00",
        **extra,
    }
    (run_dir / "run-input.json").write_text(json.dumps(run_input))
    return run_dir


def container(run_id, running=True, run_dir=None, started="2026-10-07T11:00:30Z"):
    return RunContainer(
        run_id,
        "sq-run-" + run_id,
        running,
        datetime.fromisoformat(started),
        None if running else datetime.fromisoformat("2026-10-07T11:30:30Z"),
        run_dir,
    )


# Locks


def test_the_lock_table_names_granted_flocks_only(tmp_path):
    table = tmp_path / "locks"
    table.write_text(
        "1: FLOCK  ADVISORY  WRITE 69701 08:30:13483348 0 EOF\n"
        "1: -> FLOCK  ADVISORY  WRITE 69702 08:30:13483348 0 EOF\n"
        "2: POSIX  ADVISORY  WRITE 1 00:1f:42 0 EOF\n"
        "garbage\n"
    )
    assert held_locks(table) == frozenset({(8, 48, 13483348)})
    assert held_locks(tmp_path / "absent") is None


def test_probing_a_run_lock_never_blocks_its_runner_or_a_recovery(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock = run_dir / ".runner.lock"
    assert lock_held(lock, held_locks()) is False
    assert not lock.exists(), "a probe never creates the lock file"
    with run_lock(run_dir):
        assert lock_held(lock, held_locks()) is True
        assert lock_held(lock, held_locks()) is True
        # The runner still holds it after the probes: a recovery is refused as before.
        with pytest.raises(KarnError, match="run_in_progress"), run_lock(run_dir):
            pass
    assert lock_held(lock, held_locks()) is False
    # And nothing a probe did keeps the next runner out.
    with run_lock(run_dir):
        assert lock_held(lock, held_locks()) is True


def test_an_unknown_lock_table_is_reported_as_unknown(tmp_path):
    lock = tmp_path / ".runner.lock"
    lock.touch()
    assert lock_held(lock, None) is None


# Containers


def test_run_containers_skip_the_proxy_and_name_the_run_directory():
    calls = []
    inspect = [
        {
            "Name": "/sq-run-abc",
            "Config": {"Labels": {"org.silverquillm.run": "abc"}},
            "State": {
                "Running": True,
                "StartedAt": "2026-10-07T11:00:30.5Z",
                "FinishedAt": "0001-01-01T00:00:00Z",
            },
            "Mounts": [{"Destination": "/workspace", "Source": "/runs/abc/workspace"}],
        },
        {
            "Name": "/sq-proxy-abc",
            "Config": {"Labels": {"org.silverquillm.run": "abc"}},
            "State": {},
        },
    ]

    class Done:
        def __init__(self, out, code=0):
            self.stdout, self.returncode = out, code

    def docker(arguments):
        calls.append(arguments)
        if arguments[0] == "ps":
            return Done(b"id1\nid2\n")
        return Done(json.dumps(inspect).encode())

    found, error = run_containers(docker)
    assert error is None
    assert [(c.run_id, c.running, c.run_dir, c.finished_at) for c in found] == [
        ("abc", True, Path("/runs/abc"), None)
    ]
    assert all(call[0] in ("ps", "container") for call in calls)
    assert run_containers(lambda arguments: Done(b"", 1)) == ([], "docker_unavailable")


def test_a_garbled_inspect_row_never_fails_the_listing():
    row = {
        "Name": "/sq-run-abc",
        "Config": {"Labels": {"org.silverquillm.run": "abc"}},
        "State": {"Running": True, "StartedAt": "9999-12-31T23:59:59-23:59"},
        "Mounts": 5,
    }

    class Done:
        returncode = 0

        def __init__(self, out):
            self.stdout = out

    def docker(arguments):
        return Done(b"id1" if arguments[0] == "ps" else json.dumps([row]).encode())

    found, error = run_containers(docker)
    assert error is None
    assert [(c.run_id, c.run_dir, c.started_at) for c in found] == [("abc", None, None)]


# Live runs and stages


def test_live_run_stages_follow_the_spec_table(tmp_path):
    runs = tmp_path / "runs"
    running, grading, starting, _orphan = (
        make_run(runs, name) for name in ("r1", "r2", "r3", "r4")
    )
    retain(make_run(runs, "r5") / "run-record.json", "r5")
    (grading / "host").mkdir()
    (grading / "host/host-result.json").write_text("{}")
    (runs / "not-a-run").mkdir()
    with run_lock(running), run_lock(grading), run_lock(starting):
        table = held_locks(proc_locks(tmp_path))
    found = {run.run_id: run for run in live_runs(runs, [container("r1"), container("r4")], table)}
    assert {name: run.stage for name, run in found.items()} == {
        "r1": Stage.RUNNING,
        "r2": Stage.GRADING,
        "r3": Stage.STARTING,
        # A runner killed outright leaves its container running with nothing to harvest it.
        "r4": Stage.NEEDS_RECOVER,
    }
    run = found["r1"]
    assert run.candidate.label == "bare-claude-opus · claude-opus-5-5 · max"
    assert run.candidate.secondary == (CANDIDATE_HASH[:8], "rev-7")
    assert (run.benchmark, run.provider, run.budget_seconds) == ("hob-medium", "claude", 14400)
    assert run.elapsed_seconds(NOW) == pytest.approx(3570)
    assert next(iter(live_runs(runs, [container("r1")], table))).stage is Stage.NEEDS_RECOVER


def test_a_live_run_outside_the_run_directory_is_found_through_its_container(tmp_path):
    elsewhere = make_run(tmp_path / "other", "r9")
    with run_lock(elsewhere):
        table = held_locks(proc_locks(tmp_path))
    found = live_runs(tmp_path / "runs", [container("r9", run_dir=elsewhere)], table)
    assert [(run.run_id, run.stage) for run in found] == [("r9", Stage.RUNNING)]


def test_without_a_lock_table_a_stage_is_unknown(tmp_path):
    (make_run(tmp_path, "r1") / ".runner.lock").touch()
    retain(make_run(tmp_path, "r2") / "run-record.json", "r2")
    found = live_runs(tmp_path, [], None)
    # A finished run needs no owner, so it stays in history even without the lock table.
    assert [(run.run_id, run.stage, run.reasons) for run in found] == [
        ("r1", Stage.UNKNOWN, ("no_record",))
    ]


START = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)


def valid_record(
    run_id: str,
    *,
    stopped=True,
    recovery_of=None,
    identity=IDENTITY,
    login="karn-claude-login/bare-claude-opus",
    host: str | None = "host-a",
    cost: str | None = "1.50",
    completeness="complete",
    requests=((START + timedelta(minutes=1), "1.50"),),
    usage=None,
    run_date="2026-10-06T10:00:00+00:00",
) -> KarnRunRecord:
    """A schema 2 record that passes the record's own validation, as a run writes one."""
    measurements = {
        "estimated_cost": {"completeness": completeness, "reasons": [], "value": cost},
        "requests": [
            {"response_id": f"{run_id}-{index}", "timestamp_ms": ms(moment)}
            for index, (moment, _) in enumerate(requests)
        ],
        "request_prices": [
            {"response_id": f"{run_id}-{index}", "usd": usd}
            for index, (_, usd) in enumerate(requests)
        ],
    }
    if usage is not None:
        measurements["subscription_usage"] = usage
    metadata = {
        "run_date": run_date,
        "benchmark_input": {},
        "candidate_definition": DEFINITION,
        "login_profile": login,
        "grading_source": {},
        "measurements": measurements,
        "execution": {
            "status": "completed",
            "workspace_stopped": stopped,
            "started_at": START.isoformat(),
            "stopped_at": (START + timedelta(minutes=20)).isoformat(),
        },
    }
    if host is not None:
        metadata["provenance"] = {
            "host_label": host,
            "host_label_source": "env",
            "bench": {"commit": None, "dirty": None},
            "benchmark_root": {"commit": None, "dirty": None},
            "recipe_revision": None,
            "allow_dirty": False,
            "dirty_reasons": [],
        }
    if recovery_of is not None:
        metadata.update(recovery_of=recovery_of, execution_run_id=recovery_of)
    manifest = {
        "schema_version": 2,
        "run_id": run_id,
        "candidate": identity,
        "candidate_hash": KarnIdentity.from_dict(identity).hash,
        "benchmark": "hob-medium",
        "budget_seconds": 14400,
        "run_metadata": metadata,
        "artifact_pointers": [],
    }
    record = KarnRunRecord(manifest, missing_scores("grading_not_run"))
    record.validate()
    return record


def retain(path: Path, run_id: str, **fields) -> Path:
    """A retained record as ``recovery._retain`` writes one: the manifest beside the scores."""
    record = valid_record(run_id, **fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"manifest": record.manifest, "scores": record.scores}))
    return path


def publish(results_repo: Path, run_id: str, *, retained: Path | None = None, **fields) -> Path:
    """Publish the record retained at ``retained``, else a new valid one, as the writer does."""
    if retained is not None:
        document = json.loads(retained.read_text())
        record = KarnRunRecord(document["manifest"], document["scores"])
    else:
        record = valid_record(run_id, **fields)
    return write_run_record(results_repo, record)


def stages(runs, results_repo, *, containers=(), owned=(), pending=frozenset(), tmp_path):
    with contextlib.ExitStack() as stack:
        for run_dir in owned:
            stack.enter_context(run_lock(run_dir))
        table = held_locks(proc_locks(tmp_path))
    found = live_runs(
        runs, list(containers), table, results_repo=results_repo, pending_logins=pending
    )
    return {run.run_id: (run.stage, run.reasons) for run in found}


def test_a_normal_run_moves_through_every_stage_to_finished(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    run = runs / "r1"
    run.mkdir(parents=True)
    (run / ".runner.lock").touch()
    assert stages(runs, repo, owned=[run], tmp_path=tmp_path) == {"r1": (Stage.STARTING, ())}
    make_run(runs, "r1")
    assert stages(runs, repo, owned=[run], tmp_path=tmp_path) == {"r1": (Stage.STARTING, ())}
    live = [container("r1")]
    assert stages(runs, repo, containers=live, owned=[run], tmp_path=tmp_path) == {
        "r1": (Stage.RUNNING, ())
    }
    stopped = [container("r1", running=False)]
    assert stages(runs, repo, containers=stopped, owned=[run], tmp_path=tmp_path) == {
        "r1": (Stage.GRADING, ())
    }
    (run / "host").mkdir()
    (run / "host/host-result.json").write_text("{}")
    assert stages(runs, repo, owned=[run], tmp_path=tmp_path) == {"r1": (Stage.GRADING, ())}
    retained = retain(run / "run-record.json", "r1")
    assert stages(runs, repo, owned=[run], tmp_path=tmp_path) == {"r1": (Stage.RECORDING, ())}
    publish(repo, "r1", retained=retained)
    assert stages(runs, repo, tmp_path=tmp_path) == {}


def test_a_killed_runner_with_a_live_container_needs_recovery(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    make_run(runs, "r1")
    assert stages(runs, repo, containers=[container("r1")], tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("no_record",))
    }
    found = live_runs(runs, [container("r1")], held_locks(proc_locks(tmp_path)))
    assert found[0].container.running


def test_an_unconfirmed_stop_needs_recovery_until_its_linked_recovery_is_published(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    run = make_run(runs, "r1")
    publish(repo, "r1", retained=retain(run / "run-record.json", "r1", stopped=False))
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unconfirmed_stop",))
    }
    # A recovery in progress holds the run.
    assert stages(runs, repo, owned=[run], tmp_path=tmp_path) == {"r1": (Stage.RECORDING, ())}
    recovered = retain(run / "recovery-1/run-record.json", "r1-recovery-1", recovery_of="r1")
    assert stages(runs, repo, tmp_path=tmp_path) == {"r1": (Stage.NEEDS_RECOVER, ("unpublished",))}
    publish(repo, "r1-recovery-1", retained=recovered)
    # The original stays unconfirmed and unchanged; its linked recovery clears the warning.
    assert stages(runs, repo, tmp_path=tmp_path) == {}
    assert (
        json.loads((run / "run-record.json").read_text())["manifest"]["run_metadata"]["execution"][
            "workspace_stopped"
        ]
        is False
    )


def test_a_retained_but_unpublished_record_needs_recovery_with_final_scores(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    retain(make_run(runs, "r1") / "run-record.json", "r1")
    assert stages(runs, repo, tmp_path=tmp_path) == {"r1": (Stage.NEEDS_RECOVER, ("unpublished",))}
    # Without a Results Repo, publication is unknown and never flagged.
    assert stages(runs, None, tmp_path=tmp_path) == {}


def test_a_failed_login_harvest_needs_recovery_until_settled(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    publish(repo, "r1", retained=retain(make_run(runs, "r1") / "run-record.json", "r1"))
    assert stages(runs, repo, pending={"r1"}, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("login_settlement_pending",))
    }
    assert stages(runs, repo, pending={"other"}, tmp_path=tmp_path) == {}


def test_a_profiles_pending_journal_names_the_run_that_owns_it(tmp_path):
    state = tmp_path / "state"
    slot = state / "logins/karn-codex-login/slot-1"
    slot.mkdir(parents=True)
    (slot / "pool.json").write_text(json.dumps({"plugin_id": "karn-codex-login"}))
    (slot / "secret.json").write_text("{}")
    (slot / "active.json").write_text(
        json.dumps({"run_id": "r1", "container_name": "sq-run-r1", "mounts": ["secret-mount"]})
    )
    [profile] = login_profiles(state, held_locks(proc_locks(tmp_path)))
    assert (profile.pending, profile.pending_run) == (True, "r1")


def test_a_recovery_that_ends_unfinished_leaves_its_reasons(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    run = make_run(runs, "r1")
    original = retain(run / "run-record.json", "r1", stopped=False)
    retain(run / "recovery-1/run-record.json", "r1-recovery-1", recovery_of="r1")
    publish(repo, "r1", retained=original)
    assert stages(runs, repo, owned=[run], tmp_path=tmp_path) == {"r1": (Stage.RECORDING, ())}
    assert stages(runs, repo, pending={"r1"}, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unpublished", "login_settlement_pending"))
    }


def test_unreadable_or_ambiguous_records_need_recovery_with_the_error(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    (make_run(runs, "r1") / "run-record.json").write_text("{not json")
    run = make_run(runs, "r2")
    for index, run_id in enumerate(("a", "b"), 1):
        path = retain(run / f"recovery-{index}/run-record.json", run_id, recovery_of="r2")
        publish(repo, run_id, retained=path)
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unreadable_record",)),
        "r2": (Stage.NEEDS_RECOVER, ("ambiguous_linked_recovery",)),
    }


def test_a_run_that_never_launched_or_was_published_elsewhere_is_not_shown(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    (runs / "never").mkdir(parents=True)
    make_run(runs, "moved")
    publish(repo, "moved", identity=OTHER_IDENTITY)
    assert stages(runs, repo, tmp_path=tmp_path) == {}


def test_a_linked_recovery_record_never_follows_a_link(tmp_path):
    runs, repo = tmp_path / "runs", tmp_path / "repo"
    run = make_run(runs, "r1")
    publish(repo, "r1", retained=retain(run / "run-record.json", "r1", stopped=False))
    outside = retain(tmp_path / "outside/run-record.json", "x", recovery_of="r1")
    (run / "recovery-1").symlink_to(outside.parent, target_is_directory=True)
    publish(repo, "x", retained=outside)
    assert stages(runs, repo, tmp_path=tmp_path) == {
        "r1": (Stage.NEEDS_RECOVER, ("unconfirmed_stop",))
    }


# Candidate display


def test_candidate_display_marks_missing_values():
    display = candidate_display({"name": "bare-codex", "runtime": {"environment": {}}})
    assert display.label == "bare-codex · — · —"
    assert candidate_display(None).label == "— · — · —"


# Queue


def write_batch(directory: Path, name: str, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (name + ".toml")).write_text(body)


RUN_SPEC = """
[[runs]]
build_output = "{build}"
construct = "bare-claude-opus"
benchmark = "{benchmark}"
budget_seconds = 3600
"""


def test_queued_runs_are_the_specs_a_batch_has_not_started(tmp_path):
    build = tmp_path / "build"
    (build / "constructs/bare-claude-opus").mkdir(parents=True)
    (build / "constructs/bare-claude-opus/definition.json").write_text(json.dumps(DEFINITION))
    batches = tmp_path / "batches"
    body = 'format = "karn-v5"\nnot_before = 2026-10-08T09:00:00Z\n' + "".join(
        RUN_SPEC.format(build=build, benchmark=name) for name in ("smoke", "hob-medium", "fra-hard")
    )
    write_batch(batches, "a-started", body)
    (batches / "state").mkdir()
    (batches / "state/a-started.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "batch": "a-started",
                "runs": [{"index": 0, "run_id": "r0", "spec": {}, "status": "done"}],
            }
        )
    )
    write_batch(
        batches,
        "b-unacknowledged",
        'format = "karn-v5"\n' + RUN_SPEC.format(build=build, benchmark="smoke"),
    )
    write_batch(batches, "c-legacy", 'candidate = "x"\n')
    found = {batch.batch: batch for batch in queued_batches(batches)}
    started = found["a-started"]
    assert (started.status, started.started, started.total) == ("pending", 1, 3)
    assert started.not_before == datetime(2026, 10, 8, 9, tzinfo=UTC)
    assert [(run.index, run.benchmark) for run in started.runs] == [
        (1, "hob-medium"),
        (2, "fra-hard"),
    ]
    assert started.runs[0].candidate.label == "bare-claude-opus · claude-opus-5-5 · max"
    assert found["b-unacknowledged"].needs_ack
    assert found["c-legacy"].status == "legacy"
    assert not (batches / "state/b-unacknowledged.json").exists()


# Login Pools


def enroll_slot(state_root: Path, plugin: str, slot: str, secret: str = '"opaque"') -> Path:
    directory = state_root / "logins" / plugin / slot
    directory.mkdir(parents=True)
    (directory / "pool.json").write_text(json.dumps({"plugin_id": plugin}))
    (directory / "secret.json").write_text(secret)
    return directory


def test_a_hostile_batch_or_state_file_is_an_error_not_a_crash_or_a_hang(tmp_path):
    batches = tmp_path / "batches"
    spec = 'format = "karn-v5"\n' + RUN_SPEC.format(build=tmp_path / "nobuild", benchmark="smoke")
    for name in ("list-state", "deep-state", "fifo-state"):
        write_batch(batches, name, spec)
    write_batch(batches, "deep-toml", 'format = "karn-v5"\nx = ' + "[" * 100000)
    os.mkfifo(batches / "fifo-toml.toml")
    (batches / "state").mkdir()
    (batches / "state/list-state.json").write_text("[]")
    (batches / "state/deep-state.json").write_text("[" * 100000)
    os.mkfifo(batches / "state/fifo-state.json")
    found = finishes(lambda: queued_batches(batches))
    assert {batch.batch: batch.status for batch in found} == {
        name: "error"
        for name in ("deep-state", "deep-toml", "fifo-state", "fifo-toml", "list-state")
    }


def test_login_profiles_report_busy_and_pending_without_locking(tmp_path):
    state = tmp_path / "state"
    busy = enroll_slot(state, "karn-claude-login", "bare-claude-opus")
    pending = enroll_slot(state, "karn-codex-login", "slot-1")
    (pending / "active.json").write_text("{}")
    unfinished = state / "logins/karn-codex-login/slot-2"
    unfinished.mkdir()
    descriptor = os.open(busy / "runner.lock", os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        table = held_locks(proc_locks(tmp_path))
    finally:
        os.close(descriptor)
    found = [(p.ref, p.provider, p.busy, p.pending) for p in login_profiles(state, table)]
    assert found == [
        ("karn-claude-login/bare-claude-opus", "claude", True, False),
        ("karn-codex-login/slot-1", "codex", False, True),
    ]
    assert login_profiles(tmp_path / "missing", table) == []
    assert not (tmp_path / "missing").exists()


# History


def write_record(
    repo: Path,
    run_id: str,
    *,
    status="completed",
    minutes=20,
    login="karn-claude-login/bare-claude-opus",
    usage=None,
    cost="1.50",
    run_date="2026-10-06T10:00:00+00:00",
    definition=DEFINITION,
    candidate_hash=CANDIDATE_HASH,
    host: str | None = None,
):
    """A history record shaped as the Results Repo holds one; history reads it unvalidated."""
    directory = repo / "results" / candidate_hash / run_id
    directory.mkdir(parents=True)
    start = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
    measurements = {
        "estimated_cost": {"completeness": "complete", "reasons": [], "value": cost},
        "agent_turns": {"total": {"completeness": "complete", "reasons": [], "value": 42}},
        "usage": {"completeness": "complete", "reasons": [], "value": {"total_tokens": 1000}},
        "requests": [{"response_id": "m1", "timestamp_ms": int(start.timestamp() * 1000) + 60000}],
        "request_prices": [{"response_id": "m1", "usd": cost}],
    }
    if usage is not None:
        measurements["subscription_usage"] = usage
    manifest = {
        "schema_version": 2,
        "run_id": run_id,
        "candidate_hash": candidate_hash,
        "benchmark": "hob-medium",
        "budget_seconds": 14400,
        "run_metadata": {
            "run_date": run_date,
            "login_profile": login,
            "candidate_definition": definition,
            "measurements": measurements,
            "execution": {
                "status": status,
                "started_at": start.isoformat(),
                "stopped_at": (start + timedelta(minutes=minutes)).isoformat(),
            },
        },
    }
    if host is not None:
        manifest["run_metadata"]["provenance"] = {"host_label": host}
    scores = {
        "card_correctness": {
            "evaluated": True,
            "pass_rate": 0.5,
            "tests_passed": 5,
            "tests_total": 10,
        },
        "fdn_regression": {
            "evaluated": False,
            "pass_rate": None,
            "tests_passed": None,
            "tests_total": None,
        },
        "engine_regression": {
            "evaluated": True,
            "pass_rate": 1.0,
            "tests_passed": 3,
            "tests_total": 3,
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    (directory / "scores.json").write_text(json.dumps(scores))
    return directory


def test_history_summarizes_records_and_marks_exclusions(tmp_path):
    repo = tmp_path / "repo"
    write_record(repo, "run-a")
    write_record(repo, "run-b", status="failed", run_date="2026-10-05T10:00:00+00:00")
    write_exclusion(
        repo,
        Exclusion(
            "run-b",
            CANDIDATE_HASH,
            "pilot",
            "a pilot",
            "operator",
            None,
            "sean",
            "2026-10-06T00:00:00+00:00",
        ),
    )
    runs = HistoryStore(repo).runs()
    assert [(run.run_id, run.excluded) for run in runs] == [("run-a", None), ("run-b", "pilot")]
    run = runs[0]
    assert run.duration_seconds == 1200
    assert run.target.pass_rate == 0.5 and run.target.passed == 5
    assert run.scores["fdn_regression"].evaluated is False
    assert (run.estimated_cost, run.agent_turns, run.total_tokens) == (Decimal("1.50"), 42, 1000)
    assert run.request_costs == (
        (int(datetime(2026, 10, 6, 10, 1, tzinfo=UTC).timestamp() * 1000), Decimal("1.50")),
    )


def test_history_rereads_only_changed_records(tmp_path, monkeypatch):
    from silverquillm.monitor import history

    repo = tmp_path / "repo"
    changed = write_record(repo, "run-a")
    write_record(repo, "run-b")
    reads = []
    original = history.read_json
    monkeypatch.setattr(history, "read_json", lambda path: reads.append(path) or original(path))
    store = HistoryStore(repo)
    store.runs()
    assert len(reads) == 4
    reads.clear()
    store.runs()
    assert reads == []
    manifest = changed / "manifest.json"
    manifest.write_text(manifest.read_text().replace('"1.50"', '"2.50"'))
    os.utime(manifest, ns=(1, 1))
    runs = {run.run_id: run for run in store.runs()}
    assert {path.parent.name for path in reads} == {"run-a"}
    assert runs["run-a"].estimated_cost == Decimal("2.50")


def test_hostile_record_values_are_dropped_not_fatal(tmp_path):
    repo = tmp_path / "repo"
    hostile = {
        "not-lists": {"request_prices": 5, "requests": True},
        "unhashable": {
            "request_prices": [{"response_id": ["m1"], "usd": "1"}],
            "requests": [{"response_id": {"m": 1}, "timestamp_ms": 1}],
        },
        # Summing this with any other amount overflows Decimal's exponent range.
        "huge": {
            "request_prices": [{"response_id": "m1", "usd": "1e1000000"}],
            "subscription_usage": {
                "value": {
                    "provider": "codex",
                    "utilization_percent": 10**400,
                    "resets_at": "2026-10-09T00:00:00Z",
                }
            },
        },
    }
    for run_id, measurements in hostile.items():
        directory = write_record(repo, run_id)
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["run_metadata"]["measurements"].update(measurements)
        manifest["run_metadata"]["execution"]["stopped_at"] = "9999-12-31T23:59:59-23:59"
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / "scores.json").write_text(
            json.dumps({"card_correctness": {"pass_rate": 10**400}})
        )
    runs = HistoryStore(repo).runs()
    assert sorted(run.run_id for run in runs) == sorted(hostile)
    for run in runs:
        assert (run.request_costs, run.usage_reading, run.stopped_at) == ((), None, None)
        assert run.target.pass_rate is None


def test_a_malformed_record_is_skipped(tmp_path):
    repo = tmp_path / "repo"
    broken = repo / "results" / CANDIDATE_HASH / "broken"
    broken.mkdir(parents=True)
    (broken / "manifest.json").write_text("{" * 100000)
    write_record(repo, "run-a")
    assert [run.run_id for run in HistoryStore(repo).runs()] == ["run-a"]
    assert summarize([], None, broken) is None


# Estimates


def live(tmp_path, candidate_hash=CANDIDATE_HASH):
    run_dir = make_run(tmp_path / "runs", "live")
    with run_lock(run_dir):
        table = held_locks(proc_locks(tmp_path))
    run = live_runs(tmp_path / "runs", [container("live")], table)[0]
    if candidate_hash != CANDIDATE_HASH:
        from dataclasses import replace

        run = replace(run, candidate_hash=candidate_hash)
    return run


def test_estimated_percent_uses_the_same_candidate_hash_first(tmp_path):
    repo = tmp_path / "repo"
    write_record(repo, "same-a", minutes=100)
    write_record(repo, "same-b", minutes=120)
    write_record(repo, "other", minutes=10, candidate_hash="c" * 64)
    write_record(repo, "failed", minutes=1, status="failed")
    history = HistoryStore(repo).runs()
    run = live(tmp_path)
    # 59.5 elapsed minutes against the median of 100 and 120.
    assert estimated_percent(run, history, NOW) == pytest.approx(100 * 3570 / 6600)
    # Without that hash's history, the same Candidate display's runs serve: 100, 120 and 10.
    rebuilt = live(tmp_path / "x", candidate_hash="d" * 64)
    assert estimated_percent(rebuilt, history, NOW) == pytest.approx(100 * 3570 / 6000)


def test_estimated_percent_caps_while_live_and_is_blank_without_history(tmp_path):
    repo = tmp_path / "repo"
    write_record(repo, "short", minutes=1)
    run = live(tmp_path)
    assert estimated_percent(run, HistoryStore(repo).runs(), NOW) == 99.0
    assert estimated_percent(run, [], NOW) is None


def reading(percent, observed, resets, provider="claude"):
    return UsageReading(provider, percent, 10080, resets, observed)


def ms(moment):
    return int(moment.timestamp() * 1000)


RATES = {"claude": Decimal(25), "codex": Decimal(5)}


def test_weekly_usage_adds_cost_after_an_unreset_reading():
    observed, resets = NOW - timedelta(hours=2), NOW + timedelta(days=2)
    costs = [
        (ms(NOW - timedelta(hours=3)), Decimal(100)),
        (ms(NOW - timedelta(hours=1)), Decimal(50)),
    ]
    usage = weekly_usage("p", "claude", RATES, [reading(40.0, observed, resets)], costs, NOW)
    assert usage.percent == pytest.approx(42.0)
    assert usage.estimated and usage.resets_at == resets
    assert usage.reading_age(NOW) == timedelta(hours=2)
    exact = weekly_usage("p", "claude", RATES, [reading(40.0, observed, resets)], costs[:1], NOW)
    assert (exact.percent, exact.estimated) == (40.0, False)


def test_weekly_usage_after_the_reset_counts_cost_since_the_reset():
    resets = NOW - timedelta(hours=5)
    costs = [
        (ms(NOW - timedelta(hours=6)), Decimal(500)),
        (ms(NOW - timedelta(hours=1)), Decimal(10)),
    ]
    usage = weekly_usage(
        "p", "codex", RATES, [reading(80.0, NOW - timedelta(days=1), resets, "codex")], costs, NOW
    )
    assert (usage.percent, usage.estimated, usage.reading) == (2.0, True, None)


def test_a_reading_speaks_for_one_window_past_its_reset_at_most():
    resets = datetime(2026, 9, 15, tzinfo=UTC)
    old = reading(30.0, resets - timedelta(days=1), resets, "codex")
    costs = [(ms(datetime(2026, 9, 16, tzinfo=UTC)), Decimal(500))]

    def at(moment, readings=(old,), spend=costs):
        usage = weekly_usage("p", "codex", RATES, list(readings), spend, moment)
        return usage.percent, usage.estimated, usage.resets_at

    # Before the reset the reading stands; at the reset the following window starts at zero.
    assert at(resets - timedelta(seconds=1), spend=[]) == (30.0, False, resets)
    assert at(resets, spend=[]) == (0.0, True, None)
    # Within the window after the reset, spend since the reset counts, with no reset shown.
    assert at(resets + timedelta(days=3)) == (100.0, True, None)
    # At the following weekly boundary the anchor is stale: the trailing seven days count.
    assert at(resets + timedelta(days=7)) == (100.0, True, None)
    assert at(resets + timedelta(days=8, seconds=1)) == (0.0, True, None)
    # Weeks without a reading: the old $500 has aged out (the reviewer's October 7 probe).
    assert at(datetime(2026, 10, 7, tzinfo=UTC)) == (0.0, True, None)
    # An idle profile's recent spend ages out of the trailing week on its own.
    recent = [(ms(NOW - timedelta(days=6, hours=23)), Decimal(50))]
    assert at(NOW, spend=recent) == (10.0, True, None)
    assert at(NOW + timedelta(hours=2), spend=recent) == (0.0, True, None)
    # A fresh reading replaces the fallback.
    fresh = reading(55.0, NOW - timedelta(hours=1), NOW + timedelta(days=4), "codex")
    assert at(NOW, readings=(old, fresh), spend=recent) == (55.0, False, NOW + timedelta(days=4))


def test_weekly_usage_without_a_reading_counts_seven_days():
    costs = [
        (ms(NOW - timedelta(days=8)), Decimal(500)),
        (ms(NOW - timedelta(days=6)), Decimal(50)),
    ]
    usage = weekly_usage("p", "claude", RATES, [], costs, NOW)
    assert (usage.percent, usage.estimated) == (2.0, True)
    assert weekly_usage("p", "gemini", RATES, [], costs, NOW) is None


def test_an_untimed_reading_counts_from_its_runs_stop():
    bound = NOW - timedelta(hours=1)
    untimed = UsageReading("claude", 10.0, 10080, NOW + timedelta(days=1), None, bound)
    costs = [
        (ms(NOW - timedelta(hours=2)), Decimal(25)),
        (ms(NOW - timedelta(minutes=5)), Decimal(25)),
    ]
    usage = weekly_usage("p", "claude", RATES, [untimed], costs, NOW)
    assert usage.percent == 11.0
    assert usage.reading_age(NOW) == timedelta(hours=1)


# Provisional cost


def event(identity, kind, attributes, stamp=1790874772041):
    return {
        "id": identity,
        "kind": kind,
        "attributes": attributes,
        "timestamp_ms": stamp,
        "thread_id": "t",
    }


def test_claude_provisional_cost_sums_claude_codes_own_estimates(tmp_path):
    cost = ProvisionalCost(tmp_path, "claude")
    cost.update()
    assert cost.total is None, "no events file: native telemetry off or not started"
    path = tmp_path / "observations.events.jsonl"
    first = json.dumps(
        event(
            "e1",
            "claude_code.api_request",
            {"cost_usd": "0.5", "model": "claude-opus-5-5", "input_tokens": "2"},
        )
    )
    second = json.dumps(event("e2", "claude_code.api_request", {"cost_usd": "0.25"}))
    path.write_text(first + "\n" + first + "\n" + second[:20])
    cost.update()
    assert cost.total == Decimal("0.5")
    with path.open("a") as handle:
        handle.write(
            second[20:] + "\n" + json.dumps(event("e3", "claude_code.tool_result", {})) + "\n"
        )
    cost.update()
    assert cost.total == Decimal("0.75")
    assert [row.model for row in cost.requests] == ["claude-opus-5-5", None]
    path.write_text(second + "\n")
    cost.update()
    assert cost.total == Decimal("0.25"), "a replaced file is read again from its start"


def test_codex_provisional_cost_prices_completed_responses(tmp_path):
    attributes = {
        "event.kind": "response.completed",
        "model": "gpt-6.1-sol",
        "input_token_count": "100000",
        "cached_token_count": "0",
        "cache_write_token_count": "0",
        "output_token_count": "10000",
        "reasoning_token_count": "0",
        "tool_token_count": "110000",
    }
    rows = [
        event("e1", "codex.sse_event", attributes),
        event("e2", "codex.sse_event", {**attributes, "event.kind": "response.created"}),
        event("e3", "codex.sse_event", {**attributes, "model": "unpriced-model"}),
    ]
    (tmp_path / "observations.events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    cost = ProvisionalCost(tmp_path, "codex")
    cost.update()
    assert cost.total == Decimal("0.3")  # $2 input and $10 output per million at gpt-6.1-sol
    assert cost.unpriced == 1


def test_hostile_events_never_break_a_provisional_cost(tmp_path):
    claude, codex, fifo = (tmp_path / name for name in ("claude", "codex", "fifo"))
    for directory in (claude, codex, fifo):
        directory.mkdir()
    rows = [
        event("e1", "claude_code.api_request", {"input_tokens": "\u00b2", "cost_usd": "1e1000000"}),
        event("e2", "claude_code.api_request", {"cost_usd": "2"}),
    ]
    (claude / "observations.events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    cost = ProvisionalCost(claude, "claude")
    cost.update()
    assert (cost.total, cost.unpriced) == (Decimal(2), 1)
    completed = {"event.kind": "response.completed", "input_token_count": "1", "model": ["m"]}
    row = {**event("c1", "codex.sse_event", completed), "thread_id": {"t": 1}}
    (codex / "observations.events.jsonl").write_text(json.dumps(row) + "\n")
    cost = ProvisionalCost(codex, "codex")
    cost.update()
    assert (cost.total, cost.unpriced) == (Decimal(0), 1)
    os.mkfifo(fifo / "observations.events.jsonl")
    cost = ProvisionalCost(fifo, "codex")
    finishes(cost.update)
    assert cost.total is None


# Output and redaction


def test_a_cut_never_shows_a_secrets_prefix():
    secret = b"sk-SECRETVALUE"
    data = b"x" * 10 + secret + b"tail"
    for limit in range(len(data) + 1):
        head = redacted_head(data, limit, [secret])
        assert b"sk-" not in head and b"SECRET" not in head
    assert redacted_head(data, len(data), [secret]) == b"x" * 10 + b"[REDACTED]tail"


def test_an_overlong_line_keeps_only_its_redacted_head():
    secret = b"TOPSECRET123"
    splitter = LineSplitter([secret], limit=20)
    rows = splitter.feed(b"short " + secret + b"\n" + b"y" * 10 + secret + b"z" * 100)
    rows += splitter.feed(b"z" * 50 + secret + b"\nnext\n")
    assert [(redacted, truncated) for _, redacted, truncated in rows] == [
        (b"short [REDACTED]", False),
        (b"y" * 10, True),
        (b"next", False),
    ]
    assert all(raw in (b"", b"next") or secret in raw for raw, _, _ in rows)


class FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes):
        self.stdout, self.stderr = io.BytesIO(stdout), io.BytesIO(stderr)
        self.args = None

    def poll(self):
        return 0

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0


def test_a_followed_container_is_redacted_line_by_line_and_yields_claude_readings():
    secret = b"refresh-token-value"
    event_line = json.dumps(claude_event(0.42)).encode()
    stdout = (
        b"2026-10-07T11:59:00.000000001Z hello " + secret + b"\n"
        b"2026-10-07T11:59:30.000000000Z " + event_line + b"\n"
    )
    launched = []

    def popen(arguments, **kwargs):
        launched.append(arguments)
        return FakeProcess(stdout, b"2026-10-07T11:59:01Z warn\n")

    follower = LogFollower("sq-run-abc", [secret], popen=popen)
    follower.start()
    follower.stop()
    lines = follower.lines_since(0)
    assert launched[0][:4] == ["docker", "logs", "--follow", "--timestamps"]
    assert next(line.text for line in lines if line.stream == "stdout") == "hello [REDACTED]"
    assert all(secret.decode() not in line.text for line in lines)
    assert [line.text for line in follower.lines_since(0, "stderr")] == ["warn"]
    assert follower.reading.utilization_percent == 42.0
    assert follower.reading.observed_at == datetime(2026, 10, 7, 11, 59, 30, tzinfo=UTC)
    last = lines[-1].seq
    assert follower.lines_since(last) == []


def stamp(second: int) -> bytes:
    """``docker logs --timestamps``'s prefix of one message."""
    return b"2026-10-07T11:59:%02d.000000000Z " % second


def test_a_secret_across_dockers_partial_messages_is_redacted():
    secret = b"SECRETTOKEN123"
    # Docker logs a line longer than 16 KiB as partial messages and stamps each one.
    stdout = stamp(0) + b"A" * 16380 + secret[:4] + stamp(0) + secret[4:] + b"B" * 10 + b"\n"
    follower = LogFollower(
        "sq-run-abc", [secret], popen=lambda arguments, **kwargs: FakeProcess(stdout, b"")
    )
    follower.start()
    follower.stop()
    [line] = follower.lines_since(0)
    assert line.text == "A" * 16380 + "[REDACTED]" + "B" * 10
    assert line.at == datetime(2026, 10, 7, 11, 59, tzinfo=UTC)


def test_an_overlong_line_is_cut_before_a_secret_split_by_a_partial_stamp():
    secret = b"SECRETTOKEN123"
    head = stamp(0) + b"y" * 5
    data = head + secret[:3] + stamp(1) + secret[3:] + b"z" * 200 + b"\nnext\n"
    splitter = LineSplitter([secret], limit=len(head) + 4, join=join_partials)
    rows = []
    for index in range(0, len(data), 7):  # chunks that end inside a stamp
        rows += splitter.feed(data[index : index + 7])
    assert [(redacted, truncated) for _, redacted, truncated in rows] == [
        (head, True),
        (b"next", False),
    ]


def test_a_line_of_stamps_alone_keeps_the_buffer_bounded():
    splitter = LineSplitter([b"SECRETTOKEN123"], limit=100, join=join_partials)
    for _ in range(10000):
        assert splitter.feed(stamp(0) * 10) == []
    assert len(splitter.buffer) < 1000


def test_retained_lines_skip_a_fifo_or_a_directory(tmp_path):
    (tmp_path / "host/stdout.log").mkdir(parents=True)
    os.mkfifo(tmp_path / "host/stderr.log")
    assert finishes(lambda: retained_lines(tmp_path, "stdout")) == []
    assert finishes(lambda: retained_lines(tmp_path, "stderr")) == []


def test_retained_lines_read_the_tail_of_a_stopped_runs_log(tmp_path):
    (tmp_path / "host").mkdir()
    (tmp_path / "host/stdout.log").write_bytes(b"".join(b"line %d\n" % n for n in range(1000)))
    lines = retained_lines(tmp_path, "stdout", max_bytes=100)
    assert lines[-1].text == "line 999" and len(lines) < 20
    assert retained_lines(tmp_path, "stderr") == []


def test_profile_redactions_are_the_stored_logins_leaves(tmp_path):
    state = tmp_path / "state"
    document = json.dumps(
        {"format": 1, "files": {"auth.json": json.dumps({"refresh_token": "rt-0123456789"})}}
    )
    enroll_slot(state, "karn-codex-login", "slot-1", json.dumps(document))
    redactions = profile_redactions(state, "karn-codex-login/slot-1")
    assert redactions == secret_values(document)
    assert b"rt-0123456789" in redactions
    assert profile_redactions(state, "karn-codex-login/../x") == frozenset()
    assert profile_redactions(state, "other-plugin/slot-1") == frozenset()


def test_a_live_codex_reading_comes_from_the_profiles_rollouts(tmp_path):
    state = tmp_path / "state"
    slot = enroll_slot(state, "karn-codex-login", "slot-1")
    write_lines(slot / "plugin/work/sessions/2026/10/07/rollout-a.jsonl", [codex_line(12.5)])
    found = live_codex_reading(state, "karn-codex-login/slot-1")
    assert (found.provider, found.utilization_percent) == ("codex", 12.5)
    assert live_codex_reading(state, "karn-claude-login/slot-1") is None


# Fixes to the recorded reading's parser


def test_capped_rollouts_keep_the_newest_files(tmp_path, monkeypatch):
    sessions = tmp_path / "work/sessions"
    old = write_lines(
        sessions / "rollout-z-old.jsonl", [codex_line(1.0, timestamp="2026-10-01T00:00:00Z")]
    )
    write_lines(
        sessions / "rollout-a-new.jsonl", [codex_line(9.0, timestamp="2026-10-07T00:00:00Z")]
    )
    os.utime(old, (1, 1))
    monkeypatch.setattr(subscription_usage_module, "MAX_SESSION_FILES", 1)
    result = codex_usage(tmp_path / "work")
    assert result["value"]["utilization_percent"] == 9.0
    assert result["reasons"] == ["codex_sessions_partially_read"]


def test_a_capped_walk_keeps_the_newest_session_directories(tmp_path, monkeypatch):
    sessions = tmp_path / "work/sessions"
    for name in "abcd":
        write_lines(
            sessions / f"2026/10/01/rollout-{name}.jsonl",
            [codex_line(1.0, timestamp="2026-10-01T00:00:00Z")],
        )
    write_lines(
        sessions / "2026/10/07/rollout-e.jsonl", [codex_line(9.0, timestamp="2026-10-07T00:00:00Z")]
    )
    # 2026, 10, 07 and its rollout: the cap ends the walk before the older day.
    monkeypatch.setattr(subscription_usage_module, "MAX_WALK_ENTRIES", 4)
    result = codex_usage(tmp_path / "work")
    assert result["value"]["utilization_percent"] == 9.0
    assert result["reasons"] == ["codex_sessions_partially_read"]


def test_a_hardlinked_rollout_is_skipped_without_ending_the_walk(tmp_path):
    sessions = tmp_path / "work/sessions"
    linked = write_lines(
        sessions / "a/rollout-a.jsonl", [codex_line(50.0, timestamp="2026-10-07T00:00:00Z")]
    )
    os.link(linked, tmp_path / "elsewhere.jsonl")
    write_lines(sessions / "b/rollout-b.jsonl", [codex_line(7.0, timestamp="2026-10-01T00:00:00Z")])
    result = codex_usage(tmp_path / "work")
    assert result["value"]["utilization_percent"] == 7.0
    assert result["reasons"] == ["codex_sessions_partially_read"]


def test_a_deeply_nested_rollout_line_is_malformed_not_fatal():
    _, problems = normalize_rollout(["[" * 100000, json.dumps({"type": "x", "payload": {}})])
    assert "native_record_malformed" in problems


# The whole monitor


def tree_state(*roots: Path) -> dict:
    found = {}
    for root in roots:
        for directory, names, files in os.walk(root):
            for name in names + files:
                path = Path(directory) / name
                info = os.lstat(path)
                found[path] = (info.st_mode, info.st_size, info.st_mtime_ns)
    return found


def test_a_snapshot_reads_everything_and_writes_nothing(tmp_path):
    runs, repo, batches, state = (tmp_path / name for name in ("runs", "repo", "batches", "state"))
    make_run(runs, "live")
    (runs / "live" / "observations.events.jsonl").write_text(
        json.dumps(event("e1", "claude_code.api_request", {"cost_usd": "25"}, stamp=ms(NOW))) + "\n"
    )
    write_record(
        repo,
        "done",
        usage={
            "completeness": "complete",
            "reasons": [],
            "value": {
                "provider": "claude",
                "utilization_percent": 30.0,
                "window_minutes": 10080,
                "resets_at": "2026-10-09T00:00:00Z",
                "observed_at": None,
            },
        },
        host="host-a",
    )
    enroll_slot(state, "karn-claude-login", "bare-claude-opus")
    write_batch(
        batches,
        "queued",
        'format = "karn-v5"\n' + RUN_SPEC.format(build=tmp_path / "nobuild", benchmark="smoke"),
    )
    (batches / "state").mkdir()
    (batches / "state/queued.json").write_text(
        json.dumps({"schema_version": 2, "batch": "queued", "runs": []})
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
            clock=lambda: NOW,
            follow_output=False,
        )
        snapshot = monitor.snapshot()
        after = tree_state(runs, repo, batches, state)
    assert before == after
    assert [(view.run.run_id, view.run.stage, view.cost) for view in snapshot.running] == [
        ("live", Stage.RUNNING, Decimal(25))
    ]
    assert snapshot.counts.queued == 1 and snapshot.counts.finished_total == 1
    assert snapshot.counts.finished_recent == 1
    profile = snapshot.profiles[0]
    assert profile.run_id == "live"
    # The record's reading (30%, untimed, bounded by its stop) plus the live run's $25 at $25 per 1%.
    assert profile.weekly.percent == pytest.approx(31.0) and profile.weekly.estimated
    assert snapshot.locations["runs_dir"].source == "flag"
    assert snapshot.locations["state_root"].path == state
    assert monitor.output("done") == []
    monitor.close()


@pytest.mark.parametrize(
    "text",
    [
        "x = " + "[" * 5000 + "]" * 5000 + "\n",
        'runs_dir = "~no-such-user-xyz/runs"\n',
        "{{{",
    ],
)
def test_a_broken_host_config_is_reported_not_fatal(tmp_path, text):
    config = tmp_path / "config/silverquillm/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(text)
    monitor = Monitor(
        environ={"XDG_CONFIG_HOME": str(tmp_path / "config")},
        docker=lambda: ([], None),
        proc_locks=tmp_path / "none",
        follow_output=False,
    )
    snapshot = monitor.snapshot()
    assert snapshot.config_error
    assert snapshot.locations["state_root"].source == "default"
    monitor.close()


def test_a_follower_keeps_a_bounded_buffer():
    from silverquillm.monitor import output

    lines = b"".join(b"2026-10-07T11:59:00Z line %d\n" % n for n in range(2500))
    long = b"2026-10-07T11:59:01Z " + b"x" * (64 * 1024) + b"\n"
    follower = LogFollower(
        "sq-run-abc", (), popen=lambda *args, **kwargs: FakeProcess(lines + long, b"")
    )
    follower.start()
    follower.stop()
    kept = follower.lines_since(0)
    assert len(kept) == output.DEFAULT_KEEP == 2000
    assert kept[-1].truncated and len(kept[-1].text) <= output.MAX_LINE + 64
    assert kept[0].text == "line 501"
