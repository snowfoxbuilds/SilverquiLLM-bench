"""Platform tests for the Benchmark Mode registry and mode-parameterized staging."""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.jobdir import load_benchmark, stage_job_dir
from silverquillm.modes import (
    DRIVER_REF,
    EVALUATION_METHOD,
    MODES,
    UnknownModeError,
    get_mode,
)


class TestRegistry:
    def test_registers_exactly_basic_and_planned(self) -> None:
        assert set(MODES) == {"basic", "planned"}

    def test_get_mode_returns_named_mode(self) -> None:
        assert get_mode("planned").name == "planned"

    def test_unknown_mode_lists_registered(self) -> None:
        with pytest.raises(UnknownModeError) as exc:
            get_mode("reviewer")
        msg = str(exc.value)
        assert "basic" in msg and "planned" in msg

    def test_constant_driver_and_eval_refs(self) -> None:
        for mode in MODES.values():
            assert mode.driver_ref == DRIVER_REF == "bench:jobdir-v1"
            assert mode.evaluation_method == EVALUATION_METHOD == "audited_eval"


class TestTaskVariation:
    def test_basic_adds_nothing(self) -> None:
        assert get_mode("basic").issue_addendum == ""

    def test_planned_adds_a_plan_first_clause(self) -> None:
        assert "plan" in get_mode("planned").issue_addendum.lower()


class TestModeVariesOnlyTheTask:
    """A Benchmark Mode varies only the synthetic task the production renderer
    wraps — never the manifest (both modes stamp the same ``mode: run``), never
    the candidate identity."""

    def _stage(self, run_dir: Path, mode_name: str) -> Path:
        return stage_job_dir(
            run_dir, load_benchmark("smoke"), get_mode(mode_name),
            run_id="run-1", budget_seconds=1800, adapter="claude",
        )

    def test_manifest_is_identical_across_modes(self, tmp_path: Path) -> None:
        basic = self._stage(tmp_path / "basic", "basic")
        planned = self._stage(tmp_path / "planned", "planned")
        assert (basic / "input" / "manifest.json").read_bytes() == (
            planned / "input" / "manifest.json"
        ).read_bytes()

    def test_only_task_and_synthetic_issue_differ(self, tmp_path: Path) -> None:
        basic = self._stage(tmp_path / "basic", "basic")
        planned = self._stage(tmp_path / "planned", "planned")

        def input_rels(job: Path) -> set[Path]:
            root = job / "input"
            return {p.relative_to(job) for p in root.rglob("*") if p.is_file()}

        assert input_rels(basic) == input_rels(planned)
        differing = {
            rel for rel in input_rels(basic)
            if (basic / rel).read_bytes() != (planned / rel).read_bytes()
        }
        # Only the prompt and the synthetic issue (whose body carries the mode's
        # plan-first addendum) differ; the manifest and the empty Context Tree
        # index surfaces are byte-identical.
        assert differing == {
            Path("input/prompt.md"),
            Path("input/issue.json"),
            Path("input/issue/body.md"),
        }
