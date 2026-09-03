"""Platform tests for silverquillm.jobdir — benchmark loading + job-dir staging.

Pins that the bench stages a job directory the *production* manifest parser
accepts (``mode: run``, stamped ``schema_version``, the production default
``workdir``, no unknown keys), that the task is the production-rendered prompt
enumerating every config card, that staging is atomic and retry-safe (an
existing job dir or driver repository is a loud conflict), and that the
driver-owned repository beside the job dir is seeded from the same tree and is
the only git the driver ever runs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from theozolith_worker import api

from silverquillm.jobdir import (
    CHECKOUT_DIRNAME,
    BenchmarkNotFoundError,
    BenchmarkNotRunnableError,
    BenchmarkRef,
    JobDirConflictError,
    driver_git,
    driver_git_dir,
    load_benchmark,
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


def _stage(
    run_dir: Path, mode_name: str = "basic", run_id: str = "run-1", adapter: str = "claude"
) -> Path:
    return stage_job_dir(
        run_dir, load_benchmark("smoke"), get_mode(mode_name),
        run_id=run_id, budget_seconds=3600, adapter=adapter,
    )


class TestStageJobDir:
    def test_adapter_is_the_candidates_stamped_verbatim(self, tmp_path: Path) -> None:
        """The manifest's adapter is the Candidate Bundle's, opaque to the
        bench: an adapter the bench has never heard of stages exactly like
        claude does — no allowlist anywhere on the bench side."""
        job = _stage(tmp_path / "codex", adapter="codex")
        assert api.read_manifest(job).adapter == "codex"
        job = _stage(tmp_path / "pi", adapter="pi")
        assert api.read_manifest(job).adapter == "pi"

    def test_adapter_is_required(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError):
            stage_job_dir(
                tmp_path, load_benchmark("smoke"), get_mode("basic"),
                run_id="r", budget_seconds=1,
            )
        with pytest.raises(ValueError, match="adapter"):
            _stage(tmp_path, adapter="")

    def test_tree_shape(self, tmp_path: Path) -> None:
        job = _stage(tmp_path)
        assert (job / "input" / "manifest.json").is_file()
        assert (job / "input" / "prompt.md").is_file()
        assert (job / "input" / "issue.json").is_file()
        assert (job / "input" / "issue" / "body.md").is_file()
        assert (job / "input" / "issue" / "comments" / "INDEX.md").is_file()
        assert (job / "input" / "issue" / "timeline.md").is_file()
        # The jobs channel, empty, on both sides.
        assert (job / "input" / "jobs").is_dir() and not any((job / "input" / "jobs").iterdir())
        assert (job / "output" / "jobs").is_dir() and not any((job / "output" / "jobs").iterdir())
        # The checkout the agent works in lives inside the job dir.
        assert (job / CHECKOUT_DIRNAME / "cards").is_dir()
        assert (job / CHECKOUT_DIRNAME / "engine").is_dir()

    def test_manifest_is_accepted_by_the_production_parser(self, tmp_path: Path) -> None:
        job = _stage(tmp_path)
        # No adapters, no shims: the real read_manifest accepts it as-is.
        manifest = api.read_manifest(job)
        assert manifest.mode == api.MODE_RUN  # production execution mode
        assert manifest.schema_version == api.SCHEMA_VERSION
        assert manifest.workdir == CHECKOUT_DIRNAME == "checkout"  # the production default
        assert manifest.adapter == "claude"
        assert manifest.round == 1 and manifest.round_budget == 0
        assert manifest.agent_timeout_seconds == 3600
        assert manifest.serve_jobs  # the gate rides the jobs channel

    def test_manifest_has_no_bench_only_keys(self, tmp_path: Path) -> None:
        """The Benchmark Mode and benchmark id never ride the production
        manifest (unknown keys would make the real parser reject it)."""
        job = _stage(tmp_path, "planned")
        raw = json.loads((job / "input" / "manifest.json").read_text())
        assert "benchmark" not in raw
        assert "task_path" not in raw
        assert raw["mode"] == "run"  # never the Benchmark Mode name

    def test_output_has_no_pending_state(self, tmp_path: Path) -> None:
        job = _stage(tmp_path)
        out = job / "output"
        assert out.is_dir()
        assert not (out / "proposal.json").exists()
        assert not (out / "status.json").exists()
        assert not (out / "transcript.txt").exists()

    def test_checkout_is_git_seeded(self, tmp_path: Path) -> None:
        job = _stage(tmp_path)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=job / CHECKOUT_DIRNAME,
            capture_output=True, text=True, check=True,
        )
        assert head.stdout.strip()

    def test_prompt_is_the_production_renderer(self, tmp_path: Path) -> None:
        job = _stage(tmp_path)
        prompt = (job / "input" / "prompt.md").read_text()
        assert "Implementer in TheOzolith" in prompt
        assert "format-output" in prompt
        # Every target card is enumerated (the task rides the issue body).
        for cn in load_benchmark("smoke").cards:
            assert cn in prompt, f"prompt.md omits target card {cn}"

    def test_planned_mode_varies_only_the_task(self, tmp_path: Path) -> None:
        basic = (_stage(tmp_path / "b") / "input" / "prompt.md").read_text()
        planned = (_stage(tmp_path / "p", "planned") / "input" / "prompt.md").read_text()
        assert "## Approach" not in basic
        assert "## Approach" in planned  # the plan-first addendum, in the task

    def test_issue_metadata_shape(self, tmp_path: Path) -> None:
        job = _stage(tmp_path)
        issue = json.loads((job / "input" / "issue.json").read_text())
        assert issue["title"] == _SMOKE_TITLE
        assert issue["number"] == 0 and issue["round"] == 1 and issue["labels"] == []
        assert issue["body"] in (job / "input" / "issue" / "body.md").read_text()

    def test_same_run_id_is_reproducible(self, tmp_path: Path) -> None:
        a = _stage(tmp_path / "a", run_id="run-x")
        b = _stage(tmp_path / "b", run_id="run-x")
        for rel in ("input/manifest.json", "input/prompt.md", "input/issue.json"):
            assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel

    def test_existing_job_dir_is_a_loud_conflict(self, tmp_path: Path) -> None:
        _stage(tmp_path)
        with pytest.raises(JobDirConflictError):
            _stage(tmp_path)  # a retry never overwrites another attempt

    def test_existing_driver_repository_is_a_loud_conflict(self, tmp_path: Path) -> None:
        driver_git_dir(tmp_path).mkdir(parents=True)
        with pytest.raises(JobDirConflictError):
            _stage(tmp_path)
        assert not (tmp_path / "job").exists()

    def test_missing_workspace_raises_and_leaves_nothing(self, tmp_path: Path) -> None:
        fake: Any = BenchmarkRef(
            id="x", root=tmp_path / "noroot",
            config={"cards": ["1"], "draft_set": {"primary_set_code": "fdn"}},
        )
        with pytest.raises(FileNotFoundError):
            stage_job_dir(
                tmp_path / "run", fake, get_mode("basic"), run_id="r", budget_seconds=60,
                adapter="claude",
            )
        assert not (tmp_path / "run" / "job").exists()
        assert not driver_git_dir(tmp_path / "run").exists()


class TestDriverRepository:
    """The driver-owned repository beside the job dir: seeded from the same
    tree, outside the mount, and the only git the driver runs."""

    def test_seeded_from_the_checkout_tree(self, tmp_path: Path) -> None:
        job = _stage(tmp_path)
        driver = driver_git_dir(tmp_path)
        assert driver.is_dir() and driver.parent == job.parent  # beside, never inside
        assert not driver.is_relative_to(job)
        tree = subprocess.run(
            ["git", "--git-dir", str(driver), "ls-tree", "-r", "--name-only", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        assert "test_utils.py" in tree and "cards/fdn/fdn_129/card_impl.py" in tree
        # The checkout's own repository is never tracked (its .gitignore is).
        assert not any(name.startswith(".git/") for name in tree)
        # Same content as the agent-visible seed inside the checkout.
        agent_tree = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=job / CHECKOUT_DIRNAME,
            capture_output=True, text=True, check=True,
        ).stdout.split()
        assert sorted(tree) == sorted(agent_tree)

    def test_driver_git_never_touches_the_checkouts_own_repository(self, tmp_path: Path) -> None:
        job = _stage(tmp_path)
        checkout = job / CHECKOUT_DIRNAME
        agent_head_before = (checkout / ".git" / "HEAD").read_text()
        (checkout / "new.txt").write_text("agent work")
        driver_git(tmp_path, checkout, "add", "-A")
        driver_git(tmp_path, checkout, "commit", "-q", "-m", "driver commit")
        sha = driver_git(tmp_path, checkout, "rev-parse", "HEAD").stdout.strip()
        assert len(sha) == 40
        # The driver repository advanced; the checkout's own repository did not.
        agent_log = subprocess.run(
            ["git", "log", "--format=%s"], cwd=checkout, capture_output=True, text=True, check=True,
        ).stdout.split("\n")
        assert "driver commit" not in agent_log
        assert (checkout / ".git" / "HEAD").read_text() == agent_head_before
