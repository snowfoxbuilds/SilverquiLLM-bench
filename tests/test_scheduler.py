"""``silverquillm.scheduler`` — the batch queue and single-writer scheduler (#66 Part B).

A stubbed executor stands in for the bundle run path; everything else is
real: batch files on disk, TheOzolith-exported fixture candidates verified at
run start, the ``smoke`` benchmark's config, the ``flock`` lock, and the
scheduler-owned state files.  The tests prove the #39 §5 semantics: file
order, ``not_before`` gating, re-read before each not-yet-started run,
identity resolved at run start, a failed run continuing the batch, lock
exclusivity, and that a batch file is never written by the scheduler.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from silverquillm import scheduler as sched
from silverquillm.candidate import load_candidate_bundle
from silverquillm.results_repo import candidate_hash
from tests.candidate_fixtures import export_bundle, make_candidate_dir

REPO_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


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


def write_batch(batches: Path, name: str, runs: list[dict[str, Any]], *, not_before: str | None = None) -> Path:
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
    return path


def spec(candidate: Path | str, mode: str = "basic", benchmark: str = "smoke", budget: int = 600) -> dict[str, Any]:
    return {"candidate": str(candidate), "mode": mode, "benchmark": benchmark, "budget_seconds": budget}


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """Every regular file's bytes and mtime_ns under *root* (batch files only —
    state/ and the lock are the scheduler's)."""
    return {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(root.iterdir())
        if p.is_file() and p.suffix == ".toml"
    }


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


def make_scheduler(batches: Path, executor, *, clock: Clock | None = None, logs: list[str] | None = None, tmp: Path | None = None, **kwargs) -> sched.Scheduler:
    clock = clock or Clock()
    kwargs.setdefault("runs_root", (tmp or batches.parent) / "runs")
    return sched.Scheduler(
        batches,
        executor=executor,
        repo_root=REPO_ROOT,
        now=clock,
        sleep=lambda seconds: None,
        log=(logs if logs is not None else []).append,
        **kwargs,
    )


def load_state(batches: Path, batch_id: str) -> sched.BatchState:
    return sched.load_state(batches, batch_id)


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


class TestState:
    def test_round_trip_and_defaults(self, batches: Path) -> None:
        assert sched.load_state(batches, "b").runs == []
        state = sched.BatchState(batch="b", batch_file="b.toml")
        state.runs.append(sched.RunState(index=0, spec=spec("c"), state="done", run_id="r0", identity={"scheme": "ozolith-v1"}))
        path = sched.save_state(batches, state, now=T0)
        assert path == batches / "state" / "b.json"
        loaded = sched.load_state(batches, "b")
        assert loaded.consumed == 1 and loaded.runs[0].run_id == "r0" and loaded.runs[0].identity == {"scheme": "ozolith-v1"}
        assert loaded.updated_at == "2026-09-03T12:00:00+00:00"
        assert json.loads(path.read_text())["schema_version"] == sched.STATE_SCHEMA_VERSION

    @pytest.mark.parametrize(
        "payload, message",
        [
            ("{not json", "Expecting"),
            ('{"schema_version": 2, "batch": "b", "runs": []}', "schema_version"),
            ('{"schema_version": 1, "batch": "other", "runs": []}', "records batch"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 1, "spec": {}, "state": "done"}]}', "cursor"),
            ('{"schema_version": 1, "batch": "b", "runs": [{"index": 0, "spec": {}, "state": "flying"}]}', "unknown run state"),
        ],
    )
    def test_unreadable_state_raises(self, batches: Path, payload: str, message: str) -> None:
        (batches / "state").mkdir()
        (batches / "state" / "b.json").write_text(payload, encoding="utf-8")
        with pytest.raises(sched.StateError, match=message):
            sched.load_state(batches, "b")


# ---------------------------------------------------------------------------
# The lock
# ---------------------------------------------------------------------------


class TestLock:
    def test_a_second_scheduler_instance_refuses_to_start(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate)])
        executor = StubExecutor()
        with sched.SchedulerLock(batches):
            status = sched.lock_status(batches)
            assert status.held is True and status.holder["pid"] == os.getpid()
            with pytest.raises(sched.SchedulerLockedError, match=f"pid {os.getpid()}"):
                make_scheduler(batches, executor, logs=logs).run_until_idle()
            assert executor.calls == []
            assert not (batches / "state").exists()
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
        assert state.batch_file == str(path)
        bundle = load_candidate_bundle(candidate)
        for run, resolved in zip(state.runs, executor.calls, strict=True):
            assert run.candidate_hash == bundle.candidate_hash == resolved.bundle.candidate_hash
            assert run.identity == bundle.identity.to_dict()
            assert run.run_id == resolved.run_id and run.run_id.startswith("smoke-fixture-claude--")
            assert Path(run.run_dir) == resolved.run_dir == tmp_path / "runs" / candidate.name / run.run_id
            assert resolved.run_dir.is_dir()
            assert run.started_at == "2026-09-03T12:00:00+00:00" and run.finished_at
            assert run.ok is True and run.summary == "stub ok" and run.pid == os.getpid()
        assert state.runs[0].run_id != state.runs[1].run_id
        assert any("STARTED a #0" in line for line in logs) and any("DONE a #1" in line for line in logs)

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
        assert state.runs[1].failure_class == "scheduler" and "executor exploded" in state.runs[1].error
        assert "Traceback" in state.runs[1].error
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
        assert not (batches / "state" / "a.json").exists()
        clock.advance(hours=12)
        assert runner.run_until_idle() == 1 and len(executor.calls) == 1

    def test_batches_execute_serially_in_name_order(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "b", [spec(candidate, budget=2)])
        write_batch(batches, "a", [spec(candidate, budget=1), spec(candidate, budget=11)])
        write_batch(batches, "c", [spec(candidate, budget=3)], not_before="2027-01-01T00:00:00Z")
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 3
        assert [(c.batch_id, c.index, c.spec.budget_seconds) for c in executor.calls] == [("a", 0, 1), ("a", 1, 11), ("b", 0, 2)]
        assert not (batches / "state" / "c.json").exists()

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

    def test_recover_marks_a_run_left_running_by_a_dead_scheduler_failed(self, batches: Path, candidate: Path, logs) -> None:
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        stale = sched.BatchState(batch="a", batch_file="a.toml")
        stale.runs.append(sched.RunState(index=0, spec=spec(candidate), state="running", run_id="smoke-x-2026-09-03T11-00", pid=424242))
        sched.save_state(batches, stale)
        executor = StubExecutor()
        assert make_scheduler(batches, executor, logs=logs).run_until_idle() == 1
        state = load_state(batches, "a")
        assert state.runs[0].state == "failed" and "pid 424242" in state.runs[0].error
        assert state.runs[1].state == "done" and executor.calls[0].index == 1
        assert any(line.startswith("RECOVERED a") for line in logs)

    def test_serve_polls_when_idle(self, batches: Path, logs) -> None:
        naps: list[float] = []

        def sleep(seconds: float) -> None:
            naps.append(seconds)
            if len(naps) == 2:
                raise KeyboardInterrupt

        runner = sched.Scheduler(batches, executor=StubExecutor(), repo_root=REPO_ROOT, poll_seconds=7, sleep=sleep, log=logs.append)
        with pytest.raises(KeyboardInterrupt):
            runner.serve()
        assert naps == [7, 7]
        assert sched.lock_status(batches).held is False


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
