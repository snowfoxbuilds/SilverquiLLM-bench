"""``silverquillm.scheduler`` — the batch queue and single-writer scheduler (#66 Part B).

A stubbed executor stands in for the bundle run path and a fake container
runtime for the docker CLI; everything else is real: batch files on disk,
TheOzolith-exported fixture candidates verified at run start, the ``smoke``
benchmark's config, the ``flock`` lock, the committed state files and the
host-local runtime metadata.  The tests prove the #39 §5 semantics — file
order, ``not_before`` gating, re-read before each not-yet-started run,
identity resolved at run start, a failed run continuing the batch, lock
exclusivity, a batch file never written by the scheduler — and the #66
review rulings: committed state is portable (no path, pid, host, traceback
or secret), missing state blocks a batch until a batch-scoped replay
acknowledgement, abandoned containers are reconciled before anything runs
(or the scheduler stops), state from another host fails closed, and no git
command ever runs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from silverquillm import scheduler as sched
from silverquillm.candidate import load_candidate_bundle
from silverquillm.contract import container_name
from silverquillm.results_repo import candidate_hash
from tests.candidate_fixtures import (
    FAKE_ANTHROPIC_KEY,
    SLOT_ASSIGNMENTS,
    SLOT_MENTIONS,
    export_bundle,
    make_candidate_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
HOST = "bench-host"


class Clock:
    def __init__(self, start: datetime = T0) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: int) -> None:
        self.now += timedelta(**delta)


class StubExecutor:
    """Records every resolved run; returns scripted outcomes (an exception
    instance is raised); ``hook(call_index, resolved)`` runs before returning."""

    def __init__(self, outcomes: list[Any] | None = None, hook=None) -> None:
        self.calls: list[sched.ResolvedRun] = []
        self.outcomes = list(outcomes or [])
        self.hook = hook

    def __call__(self, resolved: sched.ResolvedRun) -> sched.RunOutcome:
        self.calls.append(resolved)
        if self.hook is not None:
            self.hook(len(self.calls) - 1, resolved)
        outcome = self.outcomes.pop(0) if self.outcomes else sched.RunOutcome(ok=True, summary="stub ok")
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeContainers:
    """A container runtime double: ``present`` maps container name to status."""

    def __init__(
        self,
        present: dict[str, str] | None = None,
        *,
        fail_remove: bool = False,
        sticky: bool = False,
        fail_status: bool = False,
    ) -> None:
        self.present = dict(present or {})
        self.removed: list[str] = []
        self.inspected: list[str] = []
        self.fail_remove = fail_remove
        self.sticky = sticky
        self.fail_status = fail_status

    @property
    def touched(self) -> list[str]:
        """Every container name the scheduler inspected or removed."""
        return self.inspected + self.removed

    def status(self, name: str) -> str | None:
        self.inspected.append(name)
        if self.fail_status:
            raise sched.ReconciliationError("docker inspect could not run: no daemon")
        return self.present.get(name)

    def remove(self, name: str) -> None:
        self.removed.append(name)
        if self.fail_remove:
            raise sched.ReconciliationError(f"docker rm --force {name} failed: permission denied")
        if not self.sticky:
            self.present.pop(name, None)


class Interrupted(BaseException):
    """Stands in for KeyboardInterrupt (which pytest would treat as its own)."""


def write_batch(
    batches: Path, name: str, runs: list[dict[str, Any]], *, not_before: str | None = None, admit: bool = True
) -> Path:
    """Write ``batches/<name>.toml``.  With *admit* (the default) an empty
    committed state is created if none exists — the operator's acknowledgement
    that the batch starts from entry 0 — so the batch is runnable."""
    lines = []
    if not_before is not None:
        lines.append(f"not_before = {not_before}")
    for run in runs:
        lines.append("")
        lines.append("[[runs]]")
        for key, value in run.items():
            lines.append(f"{key} = {json.dumps(value)}")
    path = batches / f"{name}.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if admit and not sched.state_path(batches, name).exists():
        sched.save_state(batches, sched.BatchState(batch=name, batch_file=path.name), now=T0)
    return path


def spec(candidate: Path | str, mode: str = "basic", benchmark: str = "smoke", budget: int = 600) -> dict[str, Any]:
    return {"candidate": str(candidate), "mode": mode, "benchmark": benchmark, "budget_seconds": budget}


def consumed(candidate: Path | str, **kwargs: Any) -> dict[str, Any]:
    """The spec as the committed state records it (an absolute reference sanitized)."""
    return sched.portable_spec(sched.RunSpec(**spec(candidate, **kwargs)))


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """Every batch file's bytes and mtime_ns under *root* (state/, runtime/
    and the lock are the scheduler's)."""
    return {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(root.iterdir())
        if p.is_file() and p.suffix == ".toml"
    }


def state_files(batches: Path) -> dict[str, bytes]:
    state_dir = batches / "state"
    return {p.name: p.read_bytes() for p in sorted(state_dir.iterdir())} if state_dir.is_dir() else {}


@pytest.fixture
def batches(tmp_path: Path) -> Path:
    path = tmp_path / "batches"
    path.mkdir()
    return path


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    return make_candidate_dir(tmp_path / "cands", slug="fixture-claude")


@pytest.fixture
def logs() -> list[str]:
    return []


def make_scheduler(
    batches: Path,
    executor,
    *,
    clock: Clock | None = None,
    logs: list[str] | None = None,
    tmp: Path | None = None,
    containers: FakeContainers | None = None,
    **kwargs,
) -> sched.Scheduler:
    clock = clock or Clock()
    kwargs.setdefault("runs_root", (tmp or batches.parent) / "runs")
    kwargs.setdefault("repo_root", REPO_ROOT)
    kwargs.setdefault("hostname", HOST)
    return sched.Scheduler(
        batches,
        executor=executor,
        container_runtime=containers if containers is not None else FakeContainers(),
        now=clock,
        sleep=lambda seconds: None,
        log=(logs if logs is not None else []).append,
        **kwargs,
    )


def load_state(batches: Path, batch_id: str) -> sched.BatchState:
    state = sched.load_state(batches, batch_id)
    assert state is not None, f"no state for {batch_id}"
    return state


def leave_running(batches: Path, batch_id: str, candidate: Path, run_id: str, *, runtime_host: str | None = HOST) -> str:
    """Commit a state with entry 0 left ``running`` (a dead scheduler), and
    write the host-local runtime metadata for it when *runtime_host* is given.
    Returns the run's deterministic container name."""
    state = sched.BatchState(batch=batch_id, batch_file=f"{batch_id}.toml")
    state.runs.append(
        sched.RunState(index=0, spec=consumed(candidate), state="running", run_id=run_id, started_at="2026-09-03T11:00:00+00:00")
    )
    sched.save_state(batches, state, now=T0)
    if runtime_host is not None:
        sched.save_runtime(batches, runtime_record(batch_id, run_id, hostname=runtime_host))
    return container_name(run_id)


def runtime_record(batch_id: str, run_id: str, *, index: int = 0, hostname: str = HOST) -> sched.RuntimeRecord:
    return sched.RuntimeRecord(
        batch=batch_id, index=index, run_id=run_id, pid=424242, hostname=hostname, started_at="2026-09-03T11:00:00+00:00"
    )


def write_runtime_json(batches: Path, batch_id: str, payload: dict[str, Any] | str) -> Path:
    """A hand-written (possibly malformed) runtime file."""
    path = sched.runtime_path(batches, batch_id)
    path.parent.mkdir(exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload, indent=2), encoding="utf-8")
    return path


def runtime_payload(batch_id: str, run_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    payload = runtime_record(batch_id, run_id).to_dict()
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Batch files
# ---------------------------------------------------------------------------


class TestBatchFiles:
    def test_parses_the_documented_shape(self, batches: Path) -> None:
        path = write_batch(batches, "2026-09-04-hob", [spec("candidates/x"), spec("y", "planned", "hob-medium", 14400)], not_before="2026-09-04T02:00:00Z")
        batch = sched.load_batch(path)
        assert batch.id == "2026-09-04-hob" and batch.path == path
        assert batch.not_before == datetime(2026, 9, 4, 2, 0, tzinfo=UTC)
        assert [r.to_dict() for r in batch.runs] == [
            {"candidate": "candidates/x", "mode": "basic", "benchmark": "smoke", "budget_seconds": 600},
            {"candidate": "y", "mode": "planned", "benchmark": "hob-medium", "budget_seconds": 14400},
        ]
        assert batch.due(datetime(2026, 9, 4, 2, 0, tzinfo=UTC)) and not batch.due(T0)

    def test_not_before_as_a_string_and_with_an_offset(self, batches: Path) -> None:
        batch = sched.parse_batch('not_before = "2026-09-04T04:00:00+02:00"\n', batch_id="b", path=batches / "b.toml")
        assert batch.not_before == datetime(2026, 9, 4, 2, 0, tzinfo=UTC)
        assert batch.runs == ()

    @pytest.mark.parametrize(
        "text, message",
        [
            ("nope = 1\n", "unknown top-level key"),
            ("not_before = 2026-09-04T02:00:00\n", "UTC offset"),
            ("not_before = 2026-09-04\n", "RFC 3339"),
            ('not_before = "yesterday"\n', "RFC 3339"),
            ("runs = 3\n", "array"),
            ('[[runs]]\ncandidate = "x"\nmode = "basic"\nbenchmark = "smoke"\n', "missing key"),
            ('[[runs]]\ncandidate = "x"\nmode = "basic"\nbenchmark = "smoke"\nbudget_seconds = 10\nbudget_second = 1\n', "unknown key"),
            ('[[runs]]\ncandidate = "x"\nmode = "basic"\nbenchmark = "smoke"\nbudget_seconds = "10"\n', "positive integer"),
            ('[[runs]]\ncandidate = "x"\nmode = "basic"\nbenchmark = "smoke"\nbudget_seconds = 0\n', "positive integer"),
            ('[[runs]]\ncandidate = "x"\nmode = "basic"\nbenchmark = "smoke"\nbudget_seconds = true\n', "positive integer"),
            ('[[runs]]\ncandidate = ""\nmode = "basic"\nbenchmark = "smoke"\nbudget_seconds = 1\n', "non-empty"),
            ("[[runs\n", "TOML"),
        ],
    )
    def test_malformed_batches_are_refused_with_the_reason(self, batches: Path, text: str, message: str) -> None:
        with pytest.raises(sched.BatchError, match=message):
            sched.parse_batch(text, batch_id="b", path=batches / "b.toml")

    def test_listing_is_name_ordered_regular_toml_files_only(self, batches: Path) -> None:
        for name in ("b.toml", "a.toml", ".hidden.toml", "notes.md"):
            (batches / name).write_text("", encoding="utf-8")
        (batches / "link.toml").symlink_to(batches / "a.toml")
        (batches / "state").mkdir()
        assert [p.name for p in sched.list_batch_files(batches)] == ["a.toml", "b.toml"]
        assert sched.list_batch_files(batches / "missing") == []


# ---------------------------------------------------------------------------
# Committed state — portable, strict, fail-closed
# ---------------------------------------------------------------------------


class TestState:
    def test_round_trip_and_absence(self, batches: Path) -> None:
        assert sched.load_state(batches, "b") is None
        state = sched.BatchState(batch="b", batch_file="b.toml")
        state.runs.append(sched.RunState(index=0, spec=spec("c"), state="done", run_id="r0", identity={"scheme": "ozolith-v1"}))
        path = sched.save_state(batches, state, now=T0)
        assert path == batches / "state" / "b.json"
        loaded = load_state(batches, "b")
        assert loaded.consumed == 1 and loaded.runs[0].run_id == "r0" and loaded.runs[0].identity == {"scheme": "ozolith-v1"}
        assert loaded.updated_at == "2026-09-03T12:00:00+00:00" and loaded.batch_file == "b.toml"
        payload = json.loads(path.read_text())
        assert payload["schema_version"] == sched.STATE_SCHEMA_VERSION
        assert set(payload["runs"][0]) == {
            "index", "spec", "state", "started_at", "finished_at", "run_id", "candidate_hash",
            "hash8", "identity", "resolved_at", "ok", "failure_class", "summary", "error",
        }

    @pytest.mark.parametrize(
        "payload, message",
        [
            ("{not json", "Expecting"),
            ('{"schema_version": 2, "batch": "b", "runs": []}', "schema_version"),
            ('{"schema_version": 1, "batch": "other", "runs": []}', "records batch"),
            ('{"schema_version": 1, "batch": "b", "runs": [], "pid": 1}', "unknown field"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 1, "spec": {}, "state": "done"}]}', "cursor"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 0, "spec": {}, "state": "flying"}]}', "unknown run state"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 0, "spec": {}, "state": "done", "run_dir": "/x"}]}', "unknown run field"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 0, "spec": {"candidate": "/home/op/cands/x"}, "state": "done"}]}', "absolute path"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 0, "spec": {"candidate": "x", "path": "/x"}, "state": "done"}]}', "unknown spec field"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 0, "spec": {"budget_seconds": "9"}, "state": "done"}]}', "integer"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 0, "spec": {}, "state": "running", "run_id": ""}]}', "run_id"),
        ],
    )
    def test_unreadable_state_raises(self, batches: Path, payload: str, message: str) -> None:
        (batches / "state").mkdir()
        (batches / "state" / "b.json").write_text(payload, encoding="utf-8")
        with pytest.raises(sched.StateError, match=message):
            sched.load_state(batches, "b")

    @pytest.mark.parametrize(
        "payload",
        [
            "{not json",
            '{"schema_version": 99, "batch": "b", "runs": []}',
            '{"schema_version": 1, "batch": "b", "runs": [{"index": 0, "spec": {}, "state": "done", "extra": 1}]}',
        ],
    )
    def test_malformed_or_future_version_state_blocks_the_batch_and_executes_nothing(
        self, batches: Path, candidate: Path, logs, payload: str
    ) -> None:
        write_batch(batches, "b", [spec(candidate)])
        (batches / "state" / "b.json").write_text(payload, encoding="utf-8")
        write_batch(batches, "c", [spec(candidate, budget=7)])
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 1
        assert [c.batch_id for c in executor.calls] == ["c"]
        assert (batches / "state" / "b.json").read_text(encoding="utf-8") == payload, "never repaired"
        assert any(line.startswith("BLOCKED b [unreadable-state]") for line in logs)
        state, block = sched.inspect_batch(batches, "b", hostname=HOST)
        assert state is None and block is not None and block.kind == sched.BLOCK_UNREADABLE_STATE

    def test_committed_state_is_portable(self, tmp_path: Path, logs) -> None:
        """No absolute path, home directory, pid, hostname, container name,
        traceback or credential shape reaches the committed state — even when
        the errors the scheduler records mention them."""
        repo = tmp_path / "repo"
        batches = repo / "batches"
        batches.mkdir(parents=True)
        (repo / "benchmarks").symlink_to(REPO_ROOT / "benchmarks")  # the benchmark ids resolve under the repo root
        candidate = make_candidate_dir(repo / "candidates", slug="fixture-claude")
        write_batch(batches, "a", [
            spec("candidates/nope"),  # resolution error names the paths it tried
            spec(f"candidates/{candidate.name}"),  # executor raises with a secret and a home path
            spec(f"candidates/{candidate.name}"),
        ])
        leak = RuntimeError(f"boom {FAKE_ANTHROPIC_KEY} in {Path.home()}/private and {tmp_path}/x\nsecond line")
        # Entry 0 never reaches the executor (unresolvable); entries 1 and 2 do.
        executor = StubExecutor([leak, sched.RunOutcome(ok=False, summary=f"[timeout] at agent: log at {repo}/runs/x.log", failure_class="timeout")])
        runner = make_scheduler(batches, executor, logs=logs, repo_root=repo, results_repo=tmp_path / "results-repo")
        assert runner.run_until_idle() == 3

        text = (batches / "state" / "a.json").read_text(encoding="utf-8")
        payload = json.loads(text)
        assert [r["state"] for r in payload["runs"]] == ["failed", "failed", "failed"]
        assert payload["batch_file"] == "a.toml"
        for forbidden in (
            str(tmp_path), str(repo), str(Path.home()), str(os.getpid()), HOST, socket.gethostname(),
            "Traceback", FAKE_ANTHROPIC_KEY, "silverquillm-", "pid",
        ):
            assert forbidden not in text, forbidden
        assert not re.search(r'"(?:run_dir|candidate_path|record_dir|pid|hostname|container)"', text)
        # The sanitized summaries still say what happened.
        assert "resolves to no directory" in payload["runs"][0]["error"] and "<repo>/candidates/nope" in payload["runs"][0]["error"]
        assert payload["runs"][1]["error"].startswith("RuntimeError: boom [redacted: Anthropic API key] in <home>/private")
        assert payload["runs"][2]["summary"] == "[timeout] at agent: log at <runs>/x.log"
        # Logs carry the redacted traceback for the operator, never the value.
        joined = "\n".join(logs)
        assert "Traceback" in joined and FAKE_ANTHROPIC_KEY not in joined and "[redacted: Anthropic API key]" in joined

    def test_a_fresh_checkout_with_committed_state_resumes_at_the_recorded_cursor(self, tmp_path: Path, candidate: Path, logs) -> None:
        batches = tmp_path / "host-a" / "batches"
        batches.mkdir(parents=True)
        write_batch(batches, "a", [spec(candidate, budget=1), spec(candidate, budget=2), spec(candidate, budget=3)])
        first = StubExecutor()
        runner = make_scheduler(batches, first, logs=logs, tmp=tmp_path / "host-a")
        with sched.SchedulerLock(batches):
            runner._start()
            assert runner.run_next() is True  # one run, then "host A" is replaced
        assert [c.spec.budget_seconds for c in first.calls] == [1]
        # The replacement host checks out exactly what was committed: the
        # batch file and the state file — no lock, no runtime metadata.
        restored = tmp_path / "host-b" / "batches"
        (restored / "state").mkdir(parents=True)
        shutil.copy(batches / "a.toml", restored / "a.toml")
        shutil.copy(batches / "state" / "a.json", restored / "state" / "a.json")
        # The checkpoint names the absolute candidate reference only as a label.
        committed = (restored / "state" / "a.json").read_text(encoding="utf-8")
        assert str(candidate) not in committed and str(tmp_path) not in committed
        assert json.loads(committed)["runs"][0]["spec"]["candidate"] == f"<external-candidate>/{candidate.name}"
        second = StubExecutor()
        assert make_scheduler(restored, second, logs=logs, tmp=tmp_path / "host-b", hostname="host-b").run_until_idle() == 2
        assert [(c.index, c.spec.budget_seconds) for c in second.calls] == [(1, 2), (2, 3)]
        assert [c.candidate_path for c in second.calls] == [candidate.resolve()] * 2, "pending entries resolve from the batch file"
        assert [r.state for r in load_state(restored, "a").runs] == ["done", "done", "done"]


class TestMissingStateReplayProtection:
    def test_a_batch_without_state_executes_nothing_and_warns_about_replay_cost(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)], admit=False)
        executor = StubExecutor()
        runner = make_scheduler(batches, executor, logs=logs)
        assert runner.run_until_idle() == 0 and executor.calls == []
        assert not (batches / "state").exists(), "no state is created without the acknowledgement"
        warnings = [line for line in logs if line.startswith("BLOCKED a [missing-state]")]
        assert len(warnings) == 1, logs
        assert "REPLAY" in warnings[0] and "costs" in warnings[0] and "--replay-without-state a" in warnings[0]
        assert runner.run_until_idle() == 0
        assert len([line for line in logs if line.startswith("BLOCKED a")]) == 1, "reported once per file version"

    def test_only_the_ambiguous_batch_is_blocked_and_ordering_holds(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate, budget=1)])
        write_batch(batches, "b", [spec(candidate, budget=2)], admit=False)
        write_batch(batches, "c", [spec(candidate, budget=3)])
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 2
        assert [(c.batch_id, c.spec.budget_seconds) for c in executor.calls] == [("a", 1), ("c", 3)]
        assert not sched.state_path(batches, "b").exists()

    def test_batch_scoped_replay_acknowledgement_creates_state_and_starts_only_that_batch(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate, budget=1)], admit=False)
        write_batch(batches, "b", [spec(candidate, budget=2)], admit=False)
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs, replay_without_state=("a",)).run_until_idle() == 1
        assert [(c.batch_id, c.index) for c in executor.calls] == [("a", 0)]
        assert load_state(batches, "a").runs[0].state == "done"
        assert not sched.state_path(batches, "b").exists()
        assert any(line.startswith("REPLAY ACKNOWLEDGED a") for line in logs)
        assert any(line.startswith("BLOCKED b [missing-state]") for line in logs)

    def test_replay_acknowledgement_for_the_wrong_batch_refuses_and_executes_nothing(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)], admit=False)
        write_batch(batches, "ok", [spec(candidate)])
        executor = StubExecutor()
        with pytest.raises(sched.AcknowledgementError, match="no batch file"):
            make_scheduler(batches, executor, logs=logs, replay_without_state=("typo",)).run_until_idle()
        assert executor.calls == [] and not sched.state_path(batches, "a").exists()
        # Acknowledging a batch whose state exists is a misunderstanding, refused too.
        with pytest.raises(sched.AcknowledgementError, match="already exists"):
            make_scheduler(batches, executor, logs=logs, replay_without_state=("ok",)).run_until_idle()
        assert executor.calls == []
        assert sched.lock_status(batches).held is False


# ---------------------------------------------------------------------------
# The lock
# ---------------------------------------------------------------------------


class TestLock:
    def test_a_second_scheduler_instance_refuses_to_start(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)])
        before = state_files(batches)
        executor = StubExecutor()
        with sched.SchedulerLock(batches):
            status = sched.lock_status(batches)
            assert status.held is True and status.holder["pid"] == os.getpid()
            with pytest.raises(sched.SchedulerLockedError, match=f"pid {os.getpid()}"):
                make_scheduler(batches, executor, logs=logs).run_until_idle()
            assert executor.calls == []
            assert state_files(batches) == before
        assert sched.lock_status(batches).held is False
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 1

    def test_probe_without_a_lock_file_and_release_on_exit(self, batches: Path) -> None:
        assert sched.lock_status(batches) == sched.LockStatus(held=False, holder=None)
        with sched.SchedulerLock(batches) as lock:
            assert lock.path == batches / ".scheduler.lock"
        assert sched.lock_status(batches).held is False


# ---------------------------------------------------------------------------
# Scheduling semantics
# ---------------------------------------------------------------------------


class TestScheduler:
    def test_runs_in_file_order_records_outcomes_and_never_writes_the_batch(self, batches: Path, candidate: Path, tmp_path: Path, logs) -> None:
        path = write_batch(batches, "a", [spec(candidate), spec(candidate, mode="planned", budget=900)])
        os.utime(path, (1_600_000_000, 1_600_000_000))
        before = snapshot(batches)
        executor = StubExecutor()
        clock = Clock()
        assert make_scheduler(batches, executor, clock=clock, logs=logs, tmp=tmp_path).run_until_idle() == 2

        assert snapshot(batches) == before, "the scheduler never writes a batch file"
        assert [c.mode.name for c in executor.calls] == ["basic", "planned"]
        assert all(c.benchmark.id == "smoke" for c in executor.calls)
        assert [c.spec.budget_seconds for c in executor.calls] == [600, 900]
        state = load_state(batches, "a")
        assert [r.state for r in state.runs] == ["done", "done"]
        assert state.batch_file == "a.toml"
        bundle = load_candidate_bundle(candidate)
        for run, resolved in zip(state.runs, executor.calls, strict=True):
            assert run.candidate_hash == bundle.candidate_hash == resolved.bundle.candidate_hash
            assert run.identity == bundle.identity.to_dict()
            assert run.run_id == resolved.run_id and run.run_id.startswith("smoke-fixture-claude--")
            assert resolved.run_dir == tmp_path / "runs" / candidate.name / run.run_id and resolved.run_dir.is_dir()
            assert resolved.container == f"silverquillm-{run.run_id}"
            assert run.started_at == "2026-09-03T12:00:00+00:00" and run.finished_at
            assert run.ok is True and run.summary == "stub ok"
        assert state.runs[0].run_id != state.runs[1].run_id
        assert any("STARTED a #0" in line for line in logs) and any("DONE a #1" in line for line in logs)
        assert not (batches / "runtime" / "a.json").exists(), "runtime metadata is removed after the terminal transition"

    def test_a_failed_run_continues_the_batch(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)] * 3)
        executor = StubExecutor([
            sched.RunOutcome(ok=False, summary="[timeout] at agent: agent timed out", failure_class="timeout"),
            RuntimeError("executor exploded"),
        ])
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 3
        state = load_state(batches, "a")
        assert [r.state for r in state.runs] == ["failed", "failed", "done"]
        assert state.runs[0].failure_class == "timeout" and state.runs[0].ok is False
        assert state.runs[1].failure_class == "scheduler" and state.runs[1].error == "RuntimeError: executor exploded"
        assert "Traceback" not in state.runs[1].error and any("Traceback" in line for line in logs)
        assert state.runs[2].ok is True
        assert len(executor.calls) == 3

    def test_an_unresolvable_spec_fails_without_the_executor_and_the_batch_continues(self, batches: Path, candidate: Path, tmp_path: Path, logs) -> None:
        tampered = tmp_path / "tampered"
        shutil.copytree(candidate, tampered / candidate.name)
        dockerfile = tampered / candidate.name / "bundle" / "Dockerfile"
        dockerfile.write_text(dockerfile.read_text() + "RUN echo x\n")
        write_batch(batches, "a", [
            spec(tmp_path / "missing"),
            spec(candidate, mode="unknown-mode"),
            spec(candidate, benchmark="unknown-benchmark"),
            spec(tampered / candidate.name),
            spec(candidate),
        ])
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 5
        state = load_state(batches, "a")
        assert [r.state for r in state.runs] == ["failed"] * 4 + ["done"]
        assert all(r.failure_class == "unresolvable" and r.run_id is None for r in state.runs[:4])
        assert "resolves to no directory" in state.runs[0].error
        assert "unknown benchmark mode" in state.runs[1].error
        assert "unknown benchmark" in state.runs[2].error
        assert "verification" in state.runs[3].error
        assert len(executor.calls) == 1

    def test_not_before_gates_the_batch(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)], not_before="2026-09-04T00:00:00Z")
        clock = Clock(T0)
        executor = StubExecutor()
        runner = make_scheduler(batches, executor, clock=clock, logs=logs)
        assert runner.run_until_idle() == 0 and executor.calls == []
        assert load_state(batches, "a").consumed == 0
        clock.advance(hours=12)
        assert runner.run_until_idle() == 1 and len(executor.calls) == 1

    def test_batches_execute_serially_in_name_order(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "b", [spec(candidate, budget=2)])
        write_batch(batches, "a", [spec(candidate, budget=1), spec(candidate, budget=11)])
        write_batch(batches, "c", [spec(candidate, budget=3)], not_before="2027-01-01T00:00:00Z")
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 3
        assert [(c.batch_id, c.index, c.spec.budget_seconds) for c in executor.calls] == [("a", 0, 1), ("a", 1, 11), ("b", 0, 2)]
        assert load_state(batches, "c").consumed == 0

    def test_mid_batch_edits_affect_only_not_yet_started_runs(self, batches: Path, candidate: Path, logs) -> None:
        path = write_batch(batches, "a", [spec(candidate, budget=1), spec(candidate, budget=2)])
        edited: dict[str, Any] = {}

        def edit_while_first_run_executes(call: int, resolved: sched.ResolvedRun) -> None:
            if call == 0:
                # Entry 0 is running: its edit must have no effect.  Entry 1 is
                # not yet started: its edit takes effect.  Entry 2 is appended.
                write_batch(batches, "a", [
                    spec(candidate, mode="planned", budget=100),
                    spec(candidate, mode="planned", budget=200),
                    spec(candidate, budget=300),
                ])
                edited["text"] = path.read_bytes()
                edited["mtime"] = path.stat().st_mtime_ns

        executor = StubExecutor(hook=edit_while_first_run_executes)
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 3
        assert [(c.index, c.mode.name, c.spec.budget_seconds) for c in executor.calls] == [(0, "basic", 1), (1, "planned", 200), (2, "basic", 300)]
        state = load_state(batches, "a")
        assert [r.spec["budget_seconds"] for r in state.runs] == [1, 200, 300]
        assert [r.state for r in state.runs] == ["done"] * 3
        assert path.read_bytes() == edited["text"] and path.stat().st_mtime_ns == edited["mtime"]

    def test_a_file_that_shrinks_below_the_cursor_has_no_more_work(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate), spec(candidate)])

        def truncate(call: int, resolved: sched.ResolvedRun) -> None:
            if call == 0:
                write_batch(batches, "a", [])

        executor = StubExecutor(hook=truncate)
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 1
        assert load_state(batches, "a").consumed == 1
        # Appending later resumes the batch at the cursor.
        write_batch(batches, "a", [spec(candidate), spec(candidate, budget=42)])
        executor2 = StubExecutor()
        assert make_scheduler(batches, executor2, logs=logs).run_until_idle() == 1
        assert executor2.calls[0].index == 1 and executor2.calls[0].spec.budget_seconds == 42

    def test_identity_is_resolved_at_run_start_not_authoring_time(self, batches: Path, tmp_path: Path, logs) -> None:
        # A bare bundle directory (no hash suffix) so the candidate can change in place.
        cand = tmp_path / "cand"
        export_bundle(tmp_path / "src-a", out=cand)
        hash_a = load_candidate_bundle(cand).candidate_hash
        write_batch(batches, "a", [spec(cand), spec(cand)])  # authored against A

        def swap_after_first_run(call: int, resolved: sched.ResolvedRun) -> None:
            if call == 0:
                shutil.rmtree(cand)
                export_bundle(tmp_path / "src-b", out=cand, model="claude-opus-5")

        # Edit the candidate between authoring and execution: the first run
        # already sees the edit, so swap BEFORE running too.
        shutil.rmtree(cand)
        export_bundle(tmp_path / "src-b0", out=cand, model="claude-opus-4-6")
        hash_b0 = load_candidate_bundle(cand).candidate_hash
        executor = StubExecutor(hook=swap_after_first_run)
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 2
        hash_b = load_candidate_bundle(cand).candidate_hash
        assert len({hash_a, hash_b0, hash_b}) == 3
        state = load_state(batches, "a")
        assert [r.candidate_hash for r in state.runs] == [hash_b0, hash_b]
        assert [c.bundle.candidate_hash for c in executor.calls] == [hash_b0, hash_b]
        assert all(r.identity["verified"] is True and r.resolved_at for r in state.runs)
        assert hash_a not in {r.candidate_hash for r in state.runs}
        assert state.runs[0].candidate_hash == candidate_hash(executor.calls[0].bundle.identity)

    def test_a_malformed_batch_is_skipped_loudly_once_and_others_still_run(self, batches: Path, candidate: Path, logs) -> None:
        (batches / "a.toml").write_text("not_before = 2026-09-04\n", encoding="utf-8")
        write_batch(batches, "b", [spec(candidate)])
        executor = StubExecutor()
        runner = make_scheduler(batches, executor, logs=logs)
        assert runner.run_until_idle() == 1
        assert runner.run_until_idle() == 0
        skipped = [line for line in logs if line.startswith("SKIPPED malformed a.toml")]
        assert len(skipped) == 1 and "RFC 3339" in skipped[0]
        assert not (batches / "state" / "a.json").exists()
        assert load_state(batches, "b").runs[0].state == "done"

    def test_serve_polls_when_idle(self, batches: Path, logs) -> None:
        naps: list[float] = []

        def sleep(seconds: float) -> None:
            naps.append(seconds)
            if len(naps) == 2:
                raise KeyboardInterrupt

        runner = sched.Scheduler(
            batches, executor=StubExecutor(), container_runtime=FakeContainers(), repo_root=REPO_ROOT,
            poll_seconds=7, sleep=sleep, log=logs.append,
        )
        with pytest.raises(KeyboardInterrupt):
            runner.serve()
        assert naps == [7, 7]
        assert sched.lock_status(batches).held is False
        assert logs == ["scheduler serving <batches> (poll 7s)"], "the serve line names the queue by placeholder"
        assert str(batches) not in "\n".join(logs)


# ---------------------------------------------------------------------------
# Abandoned runs: reconciliation before anything else runs
# ---------------------------------------------------------------------------


class TestRecovery:
    def test_same_host_recovery_removes_the_abandoned_container_before_continuing(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        container = leave_running(batches, "a", candidate, "smoke-x-2026-09-03T11-00")
        containers = FakeContainers({container: "running"})
        order: list[str] = []
        executor = StubExecutor(hook=lambda call, resolved: order.append("executed"))
        containers_remove = containers.remove

        def remove(name: str) -> None:
            order.append("removed")
            containers_remove(name)

        containers.remove = remove  # type: ignore[method-assign]
        assert make_scheduler(batches, executor, logs=logs, containers=containers).run_until_idle() == 1
        assert order == ["removed", "executed"], "the abandoned container goes before any new work"
        assert containers.removed == [container] and containers.present == {}
        state = load_state(batches, "a")
        assert state.runs[0].state == "failed" and state.runs[0].failure_class == "abandoned"
        assert "removed (running)" in state.runs[0].error and "424242" not in state.runs[0].error
        assert state.runs[1].state == "done" and executor.calls[0].index == 1
        assert not (batches / "runtime" / "a.json").exists()
        assert any(line.startswith("RECOVERED a #0") for line in logs)

    def test_an_already_exited_or_absent_container_is_reconciled_too(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        container = leave_running(batches, "a", candidate, "smoke-x-2026-09-03T11-00")
        containers = FakeContainers({container: "exited"})
        assert make_scheduler(batches, StubExecutor(), logs=logs, containers=containers).run_until_idle() == 1
        assert containers.removed == [container]
        assert "removed (exited)" in load_state(batches, "a").runs[0].error
        # Absent: nothing to remove, still reconciled.
        write_batch(batches, "b", [spec(candidate)])
        leave_running(batches, "b", candidate, "smoke-y-2026-09-03T11-00")
        absent = FakeContainers()
        assert make_scheduler(batches, StubExecutor(), logs=logs, containers=absent).run_until_idle() == 0
        assert absent.removed == [] and "container absent" in load_state(batches, "b").runs[0].error

    @pytest.mark.parametrize("kind", ["fail_remove", "sticky", "fail_status"])
    def test_failed_or_unconfirmed_removal_stops_the_scheduler_and_executes_nothing(self, batches: Path, candidate: Path, logs, kind: str) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        write_batch(batches, "b", [spec(candidate)])
        container = leave_running(batches, "a", candidate, "smoke-x-2026-09-03T11-00")
        containers = FakeContainers({container: "running"}, **{kind: True})
        executor = StubExecutor()
        before = state_files(batches)
        with pytest.raises(sched.ReconciliationError) as info:
            make_scheduler(batches, executor, logs=logs, containers=containers).run_until_idle()
        message = str(info.value)
        assert container in message or "docker" in message
        assert executor.calls == [], "nothing executes — not even another batch"
        assert state_files(batches) == before, "the run stays recorded as running"
        assert (batches / "runtime" / "a.json").exists(), "runtime metadata is kept for the next attempt"
        assert sched.lock_status(batches).held is False

    def test_replacement_host_recovery_fails_closed_with_an_actionable_diagnostic(self, batches: Path, candidate: Path, logs) -> None:
        """Committed state says running; this host has no runtime metadata
        (the run started elsewhere): nothing runs until --acknowledge-cleanup."""
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        write_batch(batches, "b", [spec(candidate)])
        leave_running(batches, "a", candidate, "smoke-x-2026-09-03T11-00", runtime_host=None)
        containers = FakeContainers()
        executor = StubExecutor()
        with pytest.raises(sched.ReconciliationError) as info:
            make_scheduler(batches, executor, logs=logs, containers=containers).run_until_idle()
        message = str(info.value)
        assert "another host" in message and "silverquillm-smoke-x-2026-09-03T11-00" in message
        assert "--acknowledge-cleanup a" in message
        assert executor.calls == [] and containers.removed == []
        assert load_state(batches, "a").runs[0].state == "running"
        # The views report the same block.
        _, block = sched.inspect_batch(batches, "a", hostname=HOST)
        assert block is not None and block.kind == sched.BLOCK_ABANDONED_RUN and "--acknowledge-cleanup a" in block.message

    def test_runtime_metadata_from_another_host_fails_closed(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)])
        leave_running(batches, "a", candidate, "smoke-x-2026-09-03T11-00", runtime_host="other-host")
        executor = StubExecutor()
        with pytest.raises(sched.ReconciliationError, match="other-host"):
            make_scheduler(batches, executor, logs=logs).run_until_idle()
        assert executor.calls == []

    def test_acknowledged_cleanup_marks_the_remote_run_failed_and_continues(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        leave_running(batches, "a", candidate, "smoke-x-2026-09-03T11-00", runtime_host=None)
        executor = StubExecutor()
        containers = FakeContainers()
        assert make_scheduler(batches, executor, logs=logs, containers=containers, acknowledge_cleanup=("a",)).run_until_idle() == 1
        state = load_state(batches, "a")
        assert state.runs[0].state == "failed" and state.runs[0].failure_class == "abandoned"
        assert "acknowledged by the operator" in state.runs[0].error
        assert state.runs[1].state == "done" and executor.calls[0].index == 1
        assert containers.removed == [], "the operator's word replaces a local reconciliation"

    def test_cleanup_acknowledgement_for_a_batch_with_nothing_running_refuses(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)])
        executor = StubExecutor()
        with pytest.raises(sched.AcknowledgementError, match="nothing to acknowledge"):
            make_scheduler(batches, executor, logs=logs, acknowledge_cleanup=("a",)).run_until_idle()
        assert executor.calls == []

    def test_stale_runtime_metadata_after_a_terminal_transition_is_reconciled(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)])
        state = sched.BatchState(batch="a", batch_file="a.toml")
        state.runs.append(sched.RunState(index=0, spec=consumed(candidate), state="done", run_id="smoke-x-2026-09-03T11-00", ok=True))
        sched.save_state(batches, state, now=T0)
        container = container_name("smoke-x-2026-09-03T11-00")
        sched.save_runtime(batches, runtime_record("a", "smoke-x-2026-09-03T11-00"))
        containers = FakeContainers({container: "exited"})
        assert make_scheduler(batches, StubExecutor(), logs=logs, containers=containers).run_until_idle() == 0
        assert containers.removed == [container] and not (batches / "runtime" / "a.json").exists()
        assert load_state(batches, "a").runs[0].state == "done"


class TestInterruption:
    def test_an_interrupted_run_has_its_container_removed_and_is_recorded_failed(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        containers = FakeContainers()

        def launch_then_interrupt(call: int, resolved: sched.ResolvedRun) -> None:
            containers.present[resolved.container] = "running"
            assert (batches / "runtime" / "a.json").exists()
            raise Interrupted("Ctrl-C")

        executor = StubExecutor(hook=launch_then_interrupt)
        with pytest.raises(Interrupted):
            make_scheduler(batches, executor, logs=logs, containers=containers).run_until_idle()
        state = load_state(batches, "a")
        assert [r.state for r in state.runs] == ["failed"] and state.runs[0].failure_class == "interrupted"
        assert "Interrupted" in state.runs[0].summary and containers.present == {}
        assert not (batches / "runtime" / "a.json").exists()
        assert sched.lock_status(batches).held is False
        # The next scheduler simply continues with entry 1.
        assert make_scheduler(batches, StubExecutor(), logs=logs, containers=containers).run_until_idle() == 1

    def test_sigterm_interrupts_the_run_in_flight_and_unwinds(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)])
        containers = FakeContainers()

        def send_sigterm(call: int, resolved: sched.ResolvedRun) -> None:
            containers.present[resolved.container] = "running"
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)  # the handler raises before this returns

        previous = signal.getsignal(signal.SIGTERM)
        with pytest.raises(sched.SchedulerStopped):
            make_scheduler(batches, StubExecutor(hook=send_sigterm), logs=logs, containers=containers).run_until_idle()
        assert signal.getsignal(signal.SIGTERM) is previous, "the handler is restored"
        state = load_state(batches, "a")
        assert state.runs[0].state == "failed" and state.runs[0].summary == "interrupted (SIGTERM)"
        assert containers.present == {} and not (batches / "runtime" / "a.json").exists()

    def test_an_interrupt_whose_container_cannot_be_removed_leaves_the_run_running_for_startup(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        containers = FakeContainers(fail_remove=True)

        def launch_then_interrupt(call: int, resolved: sched.ResolvedRun) -> None:
            containers.present[resolved.container] = "running"
            raise Interrupted()

        with pytest.raises(Interrupted):
            make_scheduler(batches, StubExecutor(hook=launch_then_interrupt), logs=logs, containers=containers).run_until_idle()
        assert load_state(batches, "a").runs[0].state == "running"
        assert (batches / "runtime" / "a.json").exists()
        # ... and the next startup fails closed until the container is really gone (SIGKILL looks the same).
        with pytest.raises(sched.ReconciliationError):
            make_scheduler(batches, StubExecutor(), logs=logs, containers=containers).run_until_idle()
        containers.fail_remove = False
        assert make_scheduler(batches, StubExecutor(), logs=logs, containers=containers).run_until_idle() == 1
        assert [r.state for r in load_state(batches, "a").runs] == ["failed", "done"]


class TestRuntimeBinding:
    """A runtime record authorizes nothing by itself: it must bind — batch,
    index and run id — to the committed running entry, and the only
    container recovery may touch is ``container_name(<that entry's run id>)``."""

    RUN = "smoke-x-2026-09-03T11-00"
    DECOY = "smoke-decoy-2026-09-03T10-00"

    @pytest.mark.parametrize(
        "tamper",
        [
            {"batch": "b"},
            {"index": 1},
            {"run_id": "smoke-decoy-2026-09-03T10-00"},
            {"container": "silverquillm-smoke-decoy-2026-09-03T10-00"},
            {"index": "0"},
            {"pid": "424242"},
            {"hostname": ""},
            {"schema_version": 2},
            "{not json",
        ],
        ids=["batch", "index", "run-id", "container-field", "index-type", "pid-type", "empty-host", "version", "json"],
    )
    def test_metadata_that_does_not_bind_stops_recovery_before_any_container_or_executor_call(
        self, batches: Path, candidate: Path, logs, tamper: Any
    ) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        write_batch(batches, "b", [spec(candidate)])
        container = leave_running(batches, "a", candidate, self.RUN)
        payload = tamper if isinstance(tamper, str) else runtime_payload("a", self.RUN, tamper)
        path = write_runtime_json(batches, "a", payload)
        containers = FakeContainers({container: "running", container_name(self.DECOY): "running"})
        executor = StubExecutor()
        before = state_files(batches)
        runtime_before = path.read_bytes()
        with pytest.raises(sched.ReconciliationError):
            make_scheduler(batches, executor, logs=logs, containers=containers).run_until_idle()
        assert containers.touched == [], "no docker call: nothing inspected, nothing removed"
        assert executor.calls == [], "nothing executes — not even another batch"
        assert state_files(batches) == before and path.read_bytes() == runtime_before, "the evidence is kept"
        assert load_state(batches, "a").runs[0].state == "running"
        assert sched.lock_status(batches).held is False
        _, block = sched.inspect_batch(batches, "a", hostname=HOST)
        assert block is not None and block.kind == sched.BLOCK_ABANDONED_RUN and "inspected by hand" in block.message

    def test_recovery_removes_only_the_container_of_the_recorded_run(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        container = leave_running(batches, "a", candidate, self.RUN)
        recorded = json.loads(sched.runtime_path(batches, "a").read_text(encoding="utf-8"))
        assert set(recorded) == {"schema_version", "batch", "index", "run_id", "pid", "hostname", "started_at"}
        assert "container" not in recorded and container not in json.dumps(recorded)
        decoy = container_name(self.DECOY)
        containers = FakeContainers({container: "running", decoy: "running"})
        assert make_scheduler(batches, StubExecutor(), logs=logs, containers=containers).run_until_idle() == 1
        assert containers.removed == [container] and containers.inspected == [container, container]
        assert containers.present == {decoy: "running"}
        assert container == container_name(load_state(batches, "a").runs[0].run_id)

    def test_a_runtime_record_without_readable_state_to_bind_to_stops_the_scheduler(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)], admit=False)
        write_batch(batches, "b", [spec(candidate)])
        sched.save_runtime(batches, runtime_record("a", self.RUN))
        containers = FakeContainers({container_name(self.RUN): "running"})
        executor = StubExecutor()
        with pytest.raises(sched.ReconciliationError, match="no readable committed state"):
            make_scheduler(batches, executor, logs=logs, containers=containers).run_until_idle()
        assert containers.touched == [] and executor.calls == []
        assert sched.runtime_path(batches, "a").exists()

    def test_two_running_entries_are_inconsistent_state_and_stop_the_scheduler(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)] * 3)
        state = sched.BatchState(batch="a", batch_file="a.toml")
        for index in range(2):
            state.runs.append(sched.RunState(index=index, spec=consumed(candidate), state="running", run_id=f"{self.RUN}-{index}"))
        sched.save_state(batches, state, now=T0)
        sched.save_runtime(batches, runtime_record("a", f"{self.RUN}-1", index=1))
        containers = FakeContainers({container_name(f"{self.RUN}-1"): "running"})
        executor = StubExecutor()
        with pytest.raises(sched.ReconciliationError, match="one scheduler runs one at a time"):
            make_scheduler(batches, executor, logs=logs, containers=containers).run_until_idle()
        assert containers.touched == [] and executor.calls == []


class TestCleanupAcknowledgement:
    """``--acknowledge-cleanup`` is for a replacement host only."""

    RUN = "smoke-x-2026-09-03T11-00"

    def test_same_host_metadata_refuses_the_acknowledgement_and_requires_reconciliation(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        container = leave_running(batches, "a", candidate, self.RUN)
        containers = FakeContainers({container: "running"})
        executor = StubExecutor()
        before = state_files(batches)
        with pytest.raises(sched.AcknowledgementError, match="reconciled here"):
            make_scheduler(batches, executor, logs=logs, containers=containers, acknowledge_cleanup=("a",)).run_until_idle()
        assert executor.calls == [] and containers.touched == []
        assert sched.runtime_path(batches, "a").exists(), "the runtime metadata is not erased"
        assert state_files(batches) == before and load_state(batches, "a").runs[0].state == "running"
        assert not any(line.startswith("CLEANUP ACKNOWLEDGED") for line in logs)
        # Without the flag, the normal force-remove-and-confirm reconciliation runs.
        assert make_scheduler(batches, executor, logs=logs, containers=containers).run_until_idle() == 1
        assert containers.removed == [container] and load_state(batches, "a").runs[0].failure_class == "abandoned"

    @pytest.mark.parametrize(
        "tamper",
        [{"index": 1}, {"run_id": "smoke-other-2026-09-03T10-00"}, {"batch": "zzz"}, {"container": "silverquillm-x"}, {"pid": 0}, "{not json"],
        ids=["index", "run-id", "batch", "container-field", "pid", "json"],
    )
    def test_unreadable_or_unbound_metadata_cannot_be_bypassed_with_the_flag(self, batches: Path, candidate: Path, logs, tamper: Any) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        container = leave_running(batches, "a", candidate, self.RUN)
        payload = tamper if isinstance(tamper, str) else runtime_payload("a", self.RUN, tamper)
        path = write_runtime_json(batches, "a", payload)
        runtime_before = path.read_bytes()
        containers = FakeContainers({container: "running"})
        executor = StubExecutor()
        with pytest.raises(sched.AcknowledgementError, match="cannot stand in for an inspection"):
            make_scheduler(batches, executor, logs=logs, containers=containers, acknowledge_cleanup=("a",)).run_until_idle()
        assert path.read_bytes() == runtime_before, "the acknowledgement does not erase the metadata"
        assert executor.calls == [] and containers.touched == []
        assert load_state(batches, "a").runs[0].state == "running"

    def test_a_valid_record_from_another_host_is_acknowledged_and_the_batch_continues(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        leave_running(batches, "a", candidate, self.RUN, runtime_host="other-host")
        containers = FakeContainers()
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs, containers=containers, acknowledge_cleanup=("a",)).run_until_idle() == 1
        state = load_state(batches, "a")
        assert state.runs[0].state == "failed" and state.runs[0].failure_class == "abandoned"
        assert "acknowledged by the operator" in state.runs[0].error
        assert state.runs[1].state == "done" and executor.calls[0].index == 1
        assert containers.touched == [] and not sched.runtime_path(batches, "a").exists()
        assert any(line.startswith("CLEANUP ACKNOWLEDGED a") for line in logs)


class TestPortableSpecs:
    def test_an_absolute_candidate_reference_never_enters_committed_state(self, batches: Path, candidate: Path, tmp_path: Path, logs) -> None:
        repo = tmp_path / "repo"
        (repo / "candidates").mkdir(parents=True)
        (repo / "benchmarks").symlink_to(REPO_ROOT / "benchmarks")
        shutil.copytree(candidate, repo / "candidates" / candidate.name)
        write_batch(batches, "a", [spec(candidate), spec(f"candidates/{candidate.name}"), spec(candidate.name)])
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs, repo_root=repo).run_until_idle() == 3
        text = sched.state_path(batches, "a").read_text(encoding="utf-8")
        assert str(candidate) not in text and str(candidate.parent) not in text and str(tmp_path) not in text
        state = load_state(batches, "a")
        assert [r.spec["candidate"] for r in state.runs] == [
            f"<external-candidate>/{candidate.name}", f"candidates/{candidate.name}", candidate.name,
        ]
        assert [r.state for r in state.runs] == ["done"] * 3
        # Execution resolved every reference from the batch file, not from the state.
        assert executor.calls[0].candidate_path == candidate.resolve()
        assert executor.calls[1].candidate_path == (repo / "candidates" / candidate.name).resolve()
        assert [r.candidate_hash for r in state.runs] == [load_candidate_bundle(candidate).candidate_hash] * 3

    def test_portable_spec_keeps_relative_references_verbatim(self) -> None:
        assert sched.portable_spec(sched.RunSpec("candidates/x--12345678", "basic", "smoke", 1))["candidate"] == "candidates/x--12345678"
        assert sched.portable_spec(sched.RunSpec("../elsewhere/x", "basic", "smoke", 1))["candidate"] == "../elsewhere/x"
        assert sched.portable_spec(sched.RunSpec("/home/op/cands/x--12345678", "basic", "smoke", 1)) == {
            "candidate": "<external-candidate>/x--12345678", "mode": "basic", "benchmark": "smoke", "budget_seconds": 1,
        }


class TestSecretRedaction:
    def test_bound_slot_values_of_any_shape_are_absent_from_state_and_logs(self, batches: Path, candidate: Path, logs) -> None:
        """The fixture candidate declares ANTHROPIC_API_KEY.  A bound value
        that matches no generic token shape, an assignment to the declared
        slot, and a generic-shaped key must all be gone from the state and
        the log, while unrelated text survives."""
        odd = "plain7"  # too short and too plain for any shape-based detector
        assigned = "k" * 30
        environ = {"ANTHROPIC_API_KEY": odd, "PATH": "/usr/bin"}
        assert load_candidate_bundle(candidate).secret_slots == ("ANTHROPIC_API_KEY",)
        write_batch(batches, "a", [spec(candidate)] * 3)
        executor = StubExecutor([
            RuntimeError(f"auth failed: got {odd} from the provider; also {FAKE_ANTHROPIC_KEY}; ANTHROPIC_API_KEY={assigned}"),
            sched.RunOutcome(ok=False, summary=f"[auth] at agent: provider rejected {odd}", failure_class="auth"),
            sched.RunOutcome(ok=True, summary=f"phase done; token {odd} echoed by the agent"),
        ])
        assert make_scheduler(batches, executor, logs=logs, environ=environ).run_until_idle() == 3
        text = sched.state_path(batches, "a").read_text(encoding="utf-8")
        joined = "\n".join(logs)
        for forbidden in (odd, assigned, FAKE_ANTHROPIC_KEY):
            assert forbidden not in text, forbidden
            assert forbidden not in joined, forbidden
        state = load_state(batches, "a")
        assert state.runs[0].error == (
            "RuntimeError: auth failed: got [redacted: value bound to secret slot ANTHROPIC_API_KEY]"
            " from the provider; also [redacted: Anthropic API key];"
            " [redacted: a value assigned to secret slot ANTHROPIC_API_KEY]"
        )
        assert state.runs[1].summary == "[auth] at agent: provider rejected [redacted: value bound to secret slot ANTHROPIC_API_KEY]"
        assert state.runs[2].summary == "phase done; token [redacted: value bound to secret slot ANTHROPIC_API_KEY] echoed by the agent"
        assert "Traceback" in joined and "[redacted: value bound to secret slot ANTHROPIC_API_KEY]" in joined
        assert "/usr/bin" not in text, "only the declared slots' values are redacted, and nothing else leaks"

    @pytest.mark.parametrize("form", sorted(SLOT_ASSIGNMENTS))
    def test_a_declared_slot_assignment_of_any_shape_is_absent_from_state_and_logs(self, batches: Path, candidate: Path, logs, form: str) -> None:
        """The bound value is something else entirely, so only the assignment
        shape can catch these: a one-letter bare value, a symbol-laden YAML
        scalar, a quoted JSON pair, a quoted value with spaces — none of them
        reaches the state or the log; the placeholder does."""
        line = SLOT_ASSIGNMENTS[form]
        placeholder = "[redacted: a value assigned to secret slot ANTHROPIC_API_KEY]"
        write_batch(batches, "a", [spec(candidate)])
        executor = StubExecutor([RuntimeError(f"provider config: {line}")])
        runner = make_scheduler(batches, executor, logs=logs, environ={"ANTHROPIC_API_KEY": "bound-elsewhere"})
        assert runner.run_until_idle() == 1
        assert load_state(batches, "a").runs[0].error == f"RuntimeError: provider config: {placeholder}"
        joined = "\n".join(logs)
        assert line not in joined and line not in sched.state_path(batches, "a").read_text(encoding="utf-8")
        assert placeholder in joined and "Traceback" in joined

    @pytest.mark.parametrize("form", sorted(SLOT_MENTIONS))
    def test_a_slot_merely_named_survives_in_state_and_logs(self, batches: Path, candidate: Path, logs, form: str) -> None:
        """A declaration list, a prose mention and an empty assignment carry
        no value, so the redactor leaves them as they are."""
        line = SLOT_MENTIONS[form]
        write_batch(batches, "a", [spec(candidate)])
        executor = StubExecutor([sched.RunOutcome(ok=False, summary=f"note: {line}", failure_class="config")])
        runner = make_scheduler(batches, executor, logs=logs, environ={"ANTHROPIC_API_KEY": "bound-elsewhere"})
        assert runner.run_until_idle() == 1
        expected = " ".join(f"note: {line}".split())
        assert load_state(batches, "a").runs[0].summary == expected
        assert any(entry.startswith("FAILED ") and entry.endswith(expected) for entry in logs), logs

    def test_every_log_line_is_redacted_even_when_the_value_matches_an_identifier(self, batches: Path, candidate: Path, logs) -> None:
        """Bind the fixture candidate's declared slot to text that also occurs
        in the worker type and the run id.  Every STARTED and terminal line
        carries the placeholder and never the value — the identifiers go
        through the same redaction as any other text — while the committed
        identity stays verbatim."""
        value = "fixture-claude"
        placeholder = "[redacted: value bound to secret slot ANTHROPIC_API_KEY]"
        assert load_candidate_bundle(candidate).worker_type == value
        write_batch(batches, "a", [spec(candidate)] * 3)
        executor = StubExecutor([
            sched.RunOutcome(ok=True, summary="stub ok"),
            sched.RunOutcome(ok=False, summary="gate failed", failure_class="gate"),
            RuntimeError(f"executor crashed talking to {value}"),
        ])
        runner = make_scheduler(batches, executor, logs=logs, environ={"ANTHROPIC_API_KEY": value})
        assert runner.run_until_idle() == 3
        started = [line for line in logs if line.startswith("STARTED ")]
        terminal = [line for line in logs if line.startswith(("DONE ", "FAILED ", "EXECUTOR ERROR "))]
        assert len(started) == 3 and len(terminal) == 4, logs
        for line in started + terminal:
            assert value not in line, line
            assert placeholder in line, line
        assert "Traceback" in "\n".join(terminal), "the executor error still carries its redacted traceback"
        assert value not in "\n".join(logs)
        state = load_state(batches, "a")
        assert [run.state for run in state.runs] == ["done", "failed", "failed"]
        assert all(run.run_id and run.run_id.startswith(f"smoke-{value}--") for run in state.runs), "identity is not weakened"
        assert all(run.identity for run in state.runs)

    def test_a_resolution_failure_before_any_bundle_keeps_the_generic_redaction(self, batches: Path, tmp_path: Path, logs) -> None:
        secret_dir = tmp_path / f"cands-{FAKE_ANTHROPIC_KEY}"
        write_batch(batches, "a", [spec(secret_dir / "missing")])
        assert make_scheduler(batches, StubExecutor(), logs=logs).run_until_idle() == 1
        text = sched.state_path(batches, "a").read_text(encoding="utf-8")
        assert FAKE_ANTHROPIC_KEY not in text and "[redacted: Anthropic API key]" in text
        assert str(tmp_path) not in text and "<tmp>" in text
        assert FAKE_ANTHROPIC_KEY not in "\n".join(logs)


# ---------------------------------------------------------------------------
# Resolution, the production executor, git-agnosticism
# ---------------------------------------------------------------------------


class TestResolution:
    def test_candidate_refs(self, tmp_path: Path, candidate: Path) -> None:
        repo = tmp_path / "repo"
        (repo / "candidates").mkdir(parents=True)
        shutil.copytree(candidate, repo / "candidates" / candidate.name)
        assert sched.resolve_candidate_ref(str(candidate), repo_root=repo) == candidate.resolve()
        assert sched.resolve_candidate_ref(f"candidates/{candidate.name}", repo_root=repo) == (repo / "candidates" / candidate.name).resolve()
        assert sched.resolve_candidate_ref(candidate.name, repo_root=repo) == (repo / "candidates" / candidate.name).resolve()
        with pytest.raises(sched.SchedulerError, match="resolves to no directory"):
            sched.resolve_candidate_ref("nope", repo_root=repo)
        with pytest.raises(sched.SchedulerError):
            sched.resolve_candidate_ref("", repo_root=repo)


class TestContractRunExecutor:
    def test_maps_the_driver_result_and_reuses_the_verified_bundle(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, candidate: Path) -> None:
        from types import SimpleNamespace

        from silverquillm import contract as contract_mod
        from silverquillm.jobdir import load_benchmark
        from silverquillm.modes import get_mode

        seen: dict[str, Any] = {}

        def fake_drive(**kwargs):
            seen.update(kwargs)
            seen["loaded"] = kwargs["bundle_loader"](kwargs["candidate"])
            return SimpleNamespace(ok=False, phase="agent", proposal_status=None, failure_class="timeout", record_dir=tmp_path / "rec", failure=SimpleNamespace(failure_class="timeout", phase="agent", reason="agent timed out"))

        monkeypatch.setattr(contract_mod, "drive_contract_run", fake_drive)
        from theozolith_worker import api

        monkeypatch.setattr(api, "DockerEngine", lambda: "engine")
        monkeypatch.setattr(api, "container_session_factory", lambda engine: f"factory({engine})")

        bundle = load_candidate_bundle(candidate)
        resolved = sched.ResolvedRun(
            batch_id="a", index=0, spec=sched.RunSpec(str(candidate), "planned", "smoke", 123),
            run_id="smoke-x", run_dir=tmp_path / "run", candidate_path=candidate, bundle=bundle,
            benchmark=load_benchmark("smoke"), mode=get_mode("planned"), results_repo=tmp_path / "rr",
        )
        outcome = sched.contract_run_executor(container_user="1000:1000")(resolved)
        assert outcome == sched.RunOutcome(ok=False, summary="[timeout] at agent: agent timed out", failure_class="timeout", record_dir=tmp_path / "rec")
        assert seen["loaded"] is bundle
        assert seen["run_id"] == "smoke-x" and seen["budget_seconds"] == 123 and seen["mode"].name == "planned"
        assert seen["session_factory"] == "factory(engine)" and seen["container_user"] == "1000:1000"
        assert seen["results_repo"] == tmp_path / "rr" and seen["candidate"] == candidate


class TestDockerContainerRuntime:
    def test_status_and_remove_map_the_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_run(argv, **kwargs):
            calls.append(list(argv))
            if argv[1] == "container":
                if argv[-1] == "gone":
                    return subprocess.CompletedProcess(argv, 1, "", "Error: No such container: gone")
                if argv[-1] == "broken":
                    return subprocess.CompletedProcess(argv, 1, "", "Cannot connect to the Docker daemon")
                return subprocess.CompletedProcess(argv, 0, "exited\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(subprocess, "run", fake_run)
        runtime = sched.DockerContainerRuntime()
        assert runtime.status("gone") is None and runtime.status("there") == "exited"
        with pytest.raises(sched.ReconciliationError, match="daemon"):
            runtime.status("broken")
        runtime.remove("there")
        assert calls[-1] == ["docker", "rm", "--force", "there"]
        assert sched.reconcile_container(FakeContainers({"x": "running"}), "x") == "removed (running)"
        assert sched.reconcile_container(FakeContainers(), "x") == "absent"


class TestGitAgnostic:
    def test_a_full_scheduler_pass_launches_no_git(self, monkeypatch: pytest.MonkeyPatch, batches: Path, candidate: Path, logs) -> None:
        launched: list[list[str]] = []

        def _guard(real):
            def wrapper(args, *a, **kw):
                argv = [str(x) for x in (args if isinstance(args, (list, tuple)) else [args])]
                launched.append(argv)
                if argv and Path(argv[0]).name == "git":
                    raise AssertionError(f"the scheduler ran git: {argv}")
                return real(args, *a, **kw)

            return wrapper

        for name in ("run", "Popen", "check_output", "check_call", "call"):
            monkeypatch.setattr(subprocess, name, _guard(getattr(subprocess, name)))
        monkeypatch.setattr(os, "system", lambda cmd: (_ for _ in ()).throw(AssertionError(cmd)))
        write_batch(batches, "a", [spec(candidate)], admit=False)
        write_batch(batches, "b", [spec(candidate), spec(candidate)])
        leave_running(batches, "b", candidate, "smoke-x-2026-09-03T11-00")
        containers = FakeContainers({container_name("smoke-x-2026-09-03T11-00"): "running"})
        runner = make_scheduler(batches, StubExecutor([RuntimeError("boom")]), logs=logs, containers=containers, replay_without_state=("a",))
        assert runner.run_until_idle() == 2
        assert not any(Path(argv[0]).name == "git" for argv in launched if argv)

    def test_the_lifecycle_modules_never_name_git(self) -> None:
        for path in (
            REPO_ROOT / "silverquillm" / "scheduler.py",
            REPO_ROOT / "silverquillm" / "queue_view.py",
            REPO_ROOT / "scripts" / "promote_candidate.py",
            REPO_ROOT / "scripts" / "publish_results.py",
        ):
            source = path.read_text(encoding="utf-8")
            assert re.search(r"""["']git["']""", source) is None, f"{path.name} names a git command"
            assert not re.search(r"^\s*(?:import|from)\s+(?:git|dulwich|pygit2)\b", source, re.MULTILINE), path.name
