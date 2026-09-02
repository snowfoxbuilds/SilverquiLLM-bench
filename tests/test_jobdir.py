"""Platform tests for silverquillm.jobdir — benchmark loading + job-dir staging.

Pins the substrate-parity job-dir layout, the manifest fields, byte-identical
determinism, the empty-pool refusal, and that the rendered task enumerates every
card in the benchmark's config.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.jobdir import (
    BenchmarkNotFoundError,
    BenchmarkNotRunnableError,
    load_benchmark,
    pointer_prompt,
    stage_job_dir,
)
from silverquillm.modes import get_mode


def _staged_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True)
    (ws / "marker").write_text("ws", encoding="utf-8")
    return ws


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
        # BenchmarkNotFoundError is a BenchmarkNotRunnableError subclass.
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
    def _stage(self, tmp_path: Path, mode_name: str = "basic") -> Path:
        b = load_benchmark("smoke")
        ws = _staged_workspace(tmp_path)
        return stage_job_dir(tmp_path, ws, b, get_mode(mode_name), 3600)

    def test_tree_shape(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        assert (job / "input" / "manifest.json").is_file()
        assert (job / "input" / "prompt.md").is_file()
        assert (job / "input" / "issue.json").is_file()
        assert (job / "input" / "issue" / "body.md").is_file()
        assert (job / "input" / "issue" / "comments" / "INDEX.md").is_file()
        assert (job / "input" / "issue" / "timeline.md").is_file()

    def test_output_dir_present_and_empty(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        out = job / "output"
        assert out.is_dir()
        assert not any(out.iterdir())

    def test_manifest_fields(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        manifest = json.loads((job / "input" / "manifest.json").read_text())
        assert manifest["schema_version"] == 1
        assert manifest["mode"] == "basic"
        assert manifest["benchmark"] == "smoke"
        assert manifest["adapter"] == "claude"
        assert manifest["agent_timeout_seconds"] == 3600
        assert manifest["task_path"] == "input/prompt.md"

    def test_manifest_is_sorted(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        text = (job / "input" / "manifest.json").read_text()
        keys = list(json.loads(text).keys())
        assert keys == sorted(keys), "manifest keys must be deterministically sorted"
        assert text.endswith("\n")

    def test_issue_carries_title_and_body(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        issue = json.loads((job / "input" / "issue.json").read_text())
        assert issue["title"] == "Implement the Smoke (FDN pipeline validation) card pool"
        assert issue["number"] == 0 and issue["round"] == 0 and issue["labels"] == []
        body_md = (job / "input" / "issue" / "body.md").read_text()
        assert issue["body"] in body_md

    def test_task_enumerates_every_config_card(self, tmp_path: Path) -> None:
        job = self._stage(tmp_path)
        prompt = (job / "input" / "prompt.md").read_text()
        for cn in load_benchmark("smoke").cards:
            assert cn in prompt, f"prompt.md omits target card {cn}"

    def test_staging_is_byte_identical(self, tmp_path: Path) -> None:
        job1 = self._stage(tmp_path / "a")
        job2 = self._stage(tmp_path / "b")
        files1 = sorted(p.relative_to(job1) for p in job1.rglob("*") if p.is_file())
        files2 = sorted(p.relative_to(job2) for p in job2.rglob("*") if p.is_file())
        assert files1 == files2
        for rel in files1:
            assert (job1 / rel).read_bytes() == (job2 / rel).read_bytes(), rel

    def test_missing_workspace_raises(self, tmp_path: Path) -> None:
        b = load_benchmark("smoke")
        with pytest.raises(FileNotFoundError):
            stage_job_dir(tmp_path, tmp_path / "nope", b, get_mode("basic"), 3600)


def test_pointer_prompt_points_at_job_input_prompt() -> None:
    pp = pointer_prompt()
    assert "/job/input/prompt.md" in pp
    assert pp.startswith("Work on the task specified in")
