"""Platform tests for the Benchmark Mode registry and mode-parameterized staging."""

from __future__ import annotations

import json
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


class TestTemplates:
    def test_templates_differ_only_in_the_plan_section(self) -> None:
        basic = get_mode("basic").task_template.read_text()
        planned = get_mode("planned").task_template.read_text()
        assert basic != planned
        # planned is basic with a contiguous "## Plan first" section inserted
        # before "## Workspace layout" — removing exactly that span recovers basic.
        i = planned.index("## Plan first")
        j = planned.index("## Workspace layout")
        assert planned[:i] + planned[j:] == basic
        assert "plan" in planned[i:j].lower()


class TestStagedManifestCarriesMode:
    def _stage(self, tmp_path: Path, mode_name: str) -> Path:
        b = load_benchmark("smoke")
        ws = tmp_path / mode_name / "workspace"
        ws.mkdir(parents=True)
        return stage_job_dir(tmp_path / mode_name, ws, b, get_mode(mode_name), 1800)

    def test_mode_name_in_staged_manifest(self, tmp_path: Path) -> None:
        for name in ("basic", "planned"):
            job = self._stage(tmp_path, name)
            manifest = json.loads((job / "input" / "manifest.json").read_text())
            assert manifest["mode"] == name

    def test_two_modes_differ_only_in_task_content(self, tmp_path: Path) -> None:
        basic_job = self._stage(tmp_path, "basic")
        planned_job = self._stage(tmp_path, "planned")

        def rels(job: Path) -> set[Path]:
            return {p.relative_to(job) for p in job.rglob("*") if p.is_file()}

        assert rels(basic_job) == rels(planned_job)
        differing = {
            rel for rel in rels(basic_job)
            if (basic_job / rel).read_bytes() != (planned_job / rel).read_bytes()
        }
        # Only the task file and the manifest's mode tag differ; the Context
        # Tree (issue.json / body.md / index surfaces) is byte-identical.
        assert differing == {Path("input/prompt.md"), Path("input/manifest.json")}
        m_basic = json.loads((basic_job / "input" / "manifest.json").read_text())
        m_planned = json.loads((planned_job / "input" / "manifest.json").read_text())
        assert m_basic.pop("mode") == "basic"
        assert m_planned.pop("mode") == "planned"
        assert m_basic == m_planned, "manifests differ beyond the mode tag"
