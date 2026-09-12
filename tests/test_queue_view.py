"""``silverquillm queue ls`` and ``silverquillm top`` — read-only, accurate (#66 Part B)."""

from __future__ import annotations

import io
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm import queue_view
from silverquillm import scheduler as sched
from silverquillm.cli import main
from tests.candidate_fixtures import make_candidate_dir
from tests.test_scheduler import (
    HOST,
    REPO_ROOT,
    Clock,
    FakeContainers,
    StubExecutor,
    leave_running,
    spec,
    write_batch,
)

T0 = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def tree(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def world(tmp_path: Path) -> dict:
    batches = tmp_path / "batches"
    batches.mkdir()
    candidate = make_candidate_dir(tmp_path / "cands", slug="fixture-claude")
    write_batch(batches, "a", [spec(candidate), spec(candidate, mode="planned")])
    write_batch(batches, "c-later", [spec(candidate, budget=999)], not_before="2027-01-01T00:00:00Z")
    (batches / "b-broken.toml").write_text("runs = 3\n", encoding="utf-8")
    write_batch(batches, "d-nostate", [spec(candidate, budget=5)], admit=False)
    executor = StubExecutor([sched.RunOutcome(ok=False, summary="[timeout] at agent: agent timed out", failure_class="timeout")])
    sched.Scheduler(
        batches, executor=executor, container_runtime=FakeContainers(), repo_root=REPO_ROOT,
        runs_root=tmp_path / "runs", now=Clock(T0), sleep=lambda s: None, log=lambda m: None, hostname=HOST,
    ).run_until_idle()
    return {"batches": batches, "candidate": candidate}


class TestQueueLs:
    def test_shows_every_batch_state_the_malformed_and_the_blocked_without_writing(self, world: dict) -> None:
        batches = world["batches"]
        before = tree(batches)
        view = queue_view.build_queue_view(batches, now=T0, hostname=HOST)
        lines = queue_view.render_queue(view, width=400)
        text = "\n".join(lines)
        assert tree(batches) == before, "queue ls is read-only"
        assert view.scheduler_running is False and "scheduler: not running" in lines[0]
        by_id = {b.id: b for b in view.batches}
        assert list(by_id) == ["a", "b-broken", "c-later", "d-nostate"]
        assert by_id["a"].counts == {"pending": 0, "running": 0, "done": 1, "failed": 1} and by_id["a"].blocked == ""
        assert [r.state for r in by_id["a"].runs] == ["failed", "done"]
        assert by_id["a"].runs[0].hash8 and by_id["a"].runs[0].run_id.startswith("smoke-fixture-claude--")
        assert "MALFORMED" in by_id["b-broken"].error and by_id["b-broken"].runs == []
        assert by_id["c-later"].due is False and by_id["c-later"].not_before == "2027-01-01T00:00:00+00:00"
        assert [r.state for r in by_id["c-later"].runs] == ["pending"] and by_id["c-later"].runs[0].budget_seconds == 999
        # Replay protection: the batch without committed state is blocked, its
        # entries shown pending, and the acknowledgement named.
        assert by_id["d-nostate"].block_kind == sched.BLOCK_MISSING_STATE
        assert [r.state for r in by_id["d-nostate"].runs] == ["pending"]
        assert "a  not_before=- due=yes  pending=0 running=0 done=1 failed=1" in text
        assert "!! MALFORMED (skipped by the scheduler)" in text
        assert "c-later  not_before=2027-01-01T00:00:00+00:00 due=no  pending=1" in text
        assert "d-nostate  not_before=- due=yes  pending=1 running=0 done=0 failed=0  BLOCKED" in text
        assert "!! BLOCKED [missing-state]" in text and "--replay-without-state d-nostate" in text and "REPLAY" in text
        narrow = "\n".join(queue_view.render_queue(view, width=100))
        assert "--replay-without-state d-nostate" in narrow, "a narrow terminal still shows the command"
        assert "agent timed out" in text and "planned" in text
        assert str(os.getpid()) not in text and HOST not in text

    def test_a_fresh_queue_creates_no_state_dir_and_reports_the_block(self, tmp_path: Path) -> None:
        batches = tmp_path / "batches"
        batches.mkdir()
        write_batch(batches, "a", [spec("candidates/nope")], admit=False)
        lines = queue_view.render_queue(queue_view.build_queue_view(batches), width=400)
        assert sorted(p.name for p in batches.iterdir()) == ["a.toml"]
        assert any("BLOCKED [missing-state]" in line for line in lines)

    def test_an_abandoned_run_from_another_host_is_reported(self, tmp_path: Path) -> None:
        batches = tmp_path / "batches"
        batches.mkdir()
        candidate = make_candidate_dir(tmp_path / "cands", slug="fixture-claude")
        write_batch(batches, "a", [spec(candidate), spec(candidate)])
        leave_running(batches, "a", candidate, "smoke-x-2026-09-03T11-00", runtime_host=None)
        before = tree(batches)
        view = queue_view.build_queue_view(batches, now=T0, hostname=HOST)
        item = view.batches[0]
        assert item.block_kind == sched.BLOCK_ABANDONED_RUN and "--acknowledge-cleanup a" in item.blocked
        assert [r.state for r in item.runs] == ["running", "pending"]
        text = "\n".join(queue_view.render_queue(view, width=400))
        assert "BLOCKED [abandoned-run]" in text
        assert tree(batches) == before

    def test_reports_a_running_scheduler(self, world: dict) -> None:
        batches = world["batches"]
        with sched.SchedulerLock(batches):
            view = queue_view.build_queue_view(batches)
            assert view.scheduler_running is True and view.scheduler_holder["pid"] == os.getpid()
            assert f"running (pid {os.getpid()}" in queue_view.render_queue(view)[0]
        assert queue_view.build_queue_view(batches).scheduler_running is False

    def test_missing_directory_and_empty_directory(self, tmp_path: Path) -> None:
        assert queue_view.render_queue(queue_view.build_queue_view(tmp_path / "none")) == [
            f"no batches directory at {tmp_path / 'none'} — nothing queued"
        ]
        (tmp_path / "empty").mkdir()
        assert queue_view.render_queue(queue_view.build_queue_view(tmp_path / "empty"))[1] == "(no batch files)"

    def test_a_file_that_shrank_below_the_cursor_is_flagged(self, world: dict) -> None:
        write_batch(world["batches"], "a", [])
        item = next(b for b in queue_view.build_queue_view(world["batches"]).batches if b.id == "a")
        assert item.recorded == 2 and item.in_file == 0
        assert "(2 started, file now lists 0)" in "\n".join(queue_view.render_queue(queue_view.build_queue_view(world["batches"])))


class TestTop:
    def test_frames_are_read_only_and_q_quits(self, world: dict) -> None:
        batches = world["batches"]
        before = tree(batches)
        out = io.StringIO()
        keys = iter([None, "q"])
        frames = queue_view.run_top(batches, interval=0.01, out=out, read_key=lambda: next(keys), now=lambda: T0)
        assert frames == 2
        text = out.getvalue()
        assert text.count("silverquillm top") == 2 and "q to quit" in text
        assert "done=1 failed=1" in text and "MALFORMED" in text and "BLOCKED [missing-state]" in text
        assert tree(batches) == before

    def test_max_frames_bounds_the_loop(self, world: dict) -> None:
        out = io.StringIO()
        assert queue_view.run_top(world["batches"], interval=0.01, out=out, read_key=lambda: None, max_frames=3) == 3

    def test_without_a_terminal_it_prints_one_frame(self, world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        out = io.StringIO()
        assert queue_view.run_top(world["batches"], interval=0.01, out=out) == 1
        assert out.getvalue().count("silverquillm top") == 1


class TestCli:
    def test_queue_ls_and_top(self, world: dict) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["queue", "ls", "--batches-dir", str(world["batches"])])
        assert result.exit_code == 0, result.output
        assert "done=1 failed=1" in result.output and "MALFORMED" in result.output and "BLOCKED [missing-state]" in result.output
        result = runner.invoke(main, ["top", "--batches-dir", str(world["batches"]), "--interval", "0.01"])
        assert result.exit_code == 0, result.output
        assert result.output.count("silverquillm top") == 1

    def test_scheduler_once_on_an_empty_queue_and_lock_refusal(self, tmp_path: Path) -> None:
        batches = tmp_path / "batches"
        batches.mkdir()
        runner = CliRunner()
        result = runner.invoke(main, ["scheduler", "--once", "--batches-dir", str(batches)])
        assert result.exit_code == 0, result.output
        assert "scheduler idle: 0 run(s) executed" in result.output
        with sched.SchedulerLock(batches):
            result = runner.invoke(main, ["scheduler", "--once", "--batches-dir", str(batches)])
        assert result.exit_code == 1 and "another scheduler holds" in result.output

    def test_scheduler_refuses_a_wrong_acknowledgement_and_executes_nothing(self, tmp_path: Path) -> None:
        batches = tmp_path / "batches"
        batches.mkdir()
        write_batch(batches, "a", [spec("candidates/nope")], admit=False)
        result = CliRunner().invoke(main, ["scheduler", "--once", "--batches-dir", str(batches), "--replay-without-state", "b"])
        assert result.exit_code == 1 and "nothing executed" in result.output and "no batch file" in result.output
        assert not (batches / "state").exists()

    def test_help_lists_the_new_commands_and_flags(self) -> None:
        output = CliRunner().invoke(main, ["--help"]).output
        for command in ("scheduler", "queue", "top"):
            assert command in output
        output = CliRunner().invoke(main, ["scheduler", "--help"]).output
        assert "--replay-without-state" in output and "--acknowledge-cleanup" in output


class TestStateOnly:
    def test_committed_state_without_a_batch_file_is_listed_as_a_record_not_as_work(self, tmp_path: Path) -> None:
        batches = tmp_path / "batches"
        batches.mkdir()
        candidate = make_candidate_dir(tmp_path / "cands", slug="fixture-claude")
        write_batch(batches, "a", [spec(candidate)])
        leave_running(batches, "zz-gone", candidate, "smoke-x-2026-09-03T11-00", runtime_host=None)
        before = tree(batches)
        view = queue_view.build_queue_view(batches, now=T0, hostname=HOST)
        assert [b.id for b in view.batches] == ["a", "zz-gone"]
        item = view.batches[1]
        assert item.state_only and item.in_file == 0 and item.recorded == 1
        assert "STATE ONLY" in item.error and "nothing here is queued" in item.error
        assert item.block_kind == sched.BLOCK_ABANDONED_RUN and "--acknowledge-cleanup zz-gone" in item.blocked
        assert [r.state for r in item.runs] == ["running"], "no pending rows: there is no file to take them from"
        text = "\n".join(queue_view.render_queue(view, width=400))
        assert "zz-gone  not_before=- due=no  pending=0 running=1 done=0 failed=0  BLOCKED" in text
        assert "!! STATE ONLY (no batch file)" in text and "!! BLOCKED [abandoned-run]" in text
        assert "started, file now lists" not in text
        assert tree(batches) == before, "the view is read-only"
