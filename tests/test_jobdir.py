"""Platform tests for silverquillm.jobdir — benchmark loading + job-dir staging.

Pins that the bench stages a job directory the *production* manifest parser
accepts (``mode: run``, stamped ``schema_version``, ``workdir: checkout``, no
unknown keys), that the task is the production-rendered prompt enumerating every
config card, and that staging is atomic and retry-safe (an existing job dir is a
loud conflict).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from theozolith_worker import api

from silverquillm.jobdir import (
    BenchmarkNotFoundError,
    BenchmarkNotRunnableError,
    BenchmarkRef,
    JobDirConflictError,
    load_benchmark,
    pointer_prompt,
    stage_job_dir,
)
from silverquillm.modes import get_mode

_SMOKE_TITLE = "Implement the Smoke (FDN pipeline validation) card pool"


# ---------------------------------------------------------------------------
# load_benchmark
# ---------------------------------------------------------------------------


class TestLoadBenchmark:
    def test_smoke_is_runnable(self) -> None:
        b = load_benchmark("smoke")
        assert b.id == "smoke"
        assert b.cards == ["129", "205", "232"]
        assert b.target_set == "fdn"

    def test_hob_medium_empty_pool_refuses(self) -> None:
        with pytest.raises(BenchmarkNotRunnableError):
            load_benchmark("hob-medium")

    def test_unknown_id_lists_available(self) -> None:
        with pytest.raises(BenchmarkNotFoundError) as exc:
            load_benchmark("does-not-exist")
        msg = str(exc.value)
        assert isinstance(exc.value, BenchmarkNotRunnableError)
        for name in ("smoke", "sos", "hob-medium"):
            assert name in msg

    def test_invalid_id_is_rejected(self) -> None:
        with pytest.raises(BenchmarkNotFoundError):
            load_benchmark("../etc")


# ---------------------------------------------------------------------------
# stage_job_dir
# ---------------------------------------------------------------------------


class TestStageJobDir:
    def _stage(self, run_dir: Path, mode_name: str = "basic", run_id: str = "run-1") -> Path:
        return stage_job_dir(
            run_dir, load_benchmark("smoke"), get_mode(mode_name),
            run_id=run_id, budget_seconds=3600,
        )

    def test_tree_shape(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        assert (job / "input" / "manifest.json").is_file()
        assert (job / "input" / "prompt.md").is_file()
        assert (job / "input" / "issue.json").is_file()
        assert (job / "input" / "issue" / "body.md").is_file()
        assert (job / "input" / "issue" / "comments" / "INDEX.md").is_file()
        assert (job / "input" / "issue" / "timeline.md").is_file()
        # The checkout the agent works in lives inside the job dir.
        assert (job / "checkout" / "cards").is_dir()
        assert (job / "checkout" / "engine").is_dir()

    def test_manifest_is_accepted_by_the_production_parser(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        # No adapters, no shims: the real read_manifest accepts it as-is.
        manifest = api.read_manifest(job)
        assert manifest.mode == api.MODE_RUN  # production execution mode
        assert manifest.schema_version == api.SCHEMA_VERSION
        assert manifest.workdir == "checkout"
        assert manifest.adapter == "claude"
        assert manifest.round == 1 and manifest.round_budget == 0
        assert manifest.agent_timeout_seconds == 3600

    def test_manifest_has_no_bench_only_keys(self, tmp_path: Path) -> None:
        """The Benchmark Mode and benchmark id never ride the production
        manifest (unknown keys would make the real parser reject it)."""
        job = self._stage(tmp_path, "planned")
        raw = json.loads((job / "input" / "manifest.json").read_text())
        assert "benchmark" not in raw
        assert "task_path" not in raw
        assert raw["mode"] == "run"  # never the Benchmark Mode name

    def test_output_has_no_pending_state(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        out = job / "output"
        assert out.is_dir()
        assert not (out / "proposal.json").exists()
        assert not (out / "status.json").exists()
        assert not (out / "transcript.txt").exists()

    def test_checkout_is_git_seeded(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=job / "checkout",
            capture_output=True, text=True, check=True,
        )
        assert head.stdout.strip()

    def test_prompt_is_the_production_renderer(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        prompt = (job / "input" / "prompt.md").read_text()
        assert "Implementer in TheOzolith" in prompt
        assert "format-output" in prompt
        # Every target card is enumerated (the task rides the issue body).
        for cn in load_benchmark("smoke").cards:
            assert cn in prompt, f"prompt.md omits target card {cn}"

    def test_planned_mode_varies_only_the_task(self, tmp_path: Path) -> None:
        basic = (self._stage(tmp_path / "b") / "input" / "prompt.md").read_text()
        planned = (self._stage(tmp_path / "p", "planned") / "input" / "prompt.md").read_text()
        assert "## Approach" not in basic
        assert "## Approach" in planned  # the plan-first addendum, in the task

    def test_issue_metadata_shape(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        issue = json.loads((job / "input" / "issue.json").read_text())
        assert issue["title"] == _SMOKE_TITLE
        assert issue["number"] == 0 and issue["round"] == 1 and issue["labels"] == []
        assert issue["body"] in (job / "input" / "issue" / "body.md").read_text()

    def test_same_run_id_is_reproducible(self, tmp_path: Path) -> None:
        a = self._stage(tmp_path / "a", run_id="run-x")
        b = self._stage(tmp_path / "b", run_id="run-x")
        for rel in ("input/manifest.json", "input/prompt.md", "input/issue.json"):
            assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel

    def test_existing_job_dir_is_a_loud_conflict(self, tmp_path: Path) -> None:
        self._stage(tmp_path)
        with pytest.raises(JobDirConflictError):
            self._stage(tmp_path)  # a retry never overwrites another attempt

    def test_missing_workspace_raises(self, tmp_path: Path) -> None:
        fake: Any = BenchmarkRef(
            id="x", root=tmp_path / "noroot",
            config={"cards": ["1"], "draft_set": {"primary_set_code": "fdn"}},
        )
        with pytest.raises(FileNotFoundError):
            stage_job_dir(tmp_path / "run", fake, get_mode("basic"), run_id="r", budget_seconds=60)


def test_pointer_prompt_points_at_job_input_prompt() -> None:
    pp = pointer_prompt()
    assert "/job/input/prompt.md" in pp
    assert pp.startswith("Work on the task specified in")
