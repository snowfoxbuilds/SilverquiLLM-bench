"""Tests for the benchmark-parameterized Audited Eval (Contract Run path).

Pins that the SOS path resolution is byte-for-byte the set of paths the legacy
``evaluate`` hardcoded (the no-behavior-change guarantee), and that
``evaluate_run`` computes all three dimensions against a harvested workspace.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from silverquillm.evaluator import evaluate_run, resolve_eval_paths
from silverquillm.jobdir import load_benchmark

REPO = Path(__file__).resolve().parents[1]
_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git")


class TestSosResolutionUnchanged:
    """AC: SOS resolution reproduces the paths ``evaluate`` used to hardcode."""

    def test_paths_match_legacy_constants(self) -> None:
        p = resolve_eval_paths(REPO / "benchmarks" / "sos", "sos")
        assert p.audited_target == REPO / "benchmarks/sos/data/tests/audited/sos"
        assert p.audited_fdn == REPO / "benchmarks/sos/data/tests/audited/fdn"
        assert p.engine_tests == REPO / "benchmarks/sos/workspace/engine_tests"
        assert p.cards_dir == REPO / "benchmarks/sos/workspace/cards"
        assert p.engine_dir == REPO / "benchmarks/sos/workspace/engine"
        # SOS ships the oracle-workspace test_utils the legacy path copied.
        assert p.test_utils == REPO / "benchmarks/sos/data/test_oracle_workspace/test_utils.py"

    def test_smoke_resolves_fdn_target_and_workspace_test_utils(self) -> None:
        p = resolve_eval_paths(REPO / "benchmarks" / "smoke", "fdn")
        assert p.audited_target == REPO / "benchmarks/smoke/data/tests/audited/fdn"
        # smoke ships only the workspace test_utils (no oracle workspace).
        assert p.test_utils == REPO / "benchmarks/smoke/workspace/test_utils.py"


class TestEvaluateRun:
    def _harvest(self, tmp_path: Path, *, implement: list[str]) -> Path:
        """A harvested workspace_final: the smoke workspace with the named FDN
        targets replaced by hob-medium's known-good implementations."""
        run_dir = tmp_path / "run"
        wf = run_dir / "workspace_final"
        shutil.copytree(REPO / "benchmarks/smoke/workspace", wf, ignore=_IGNORE)
        for card_id in implement:
            shutil.copy2(
                REPO / f"benchmarks/hob-medium/workspace/cards/fdn/{card_id}/card_impl.py",
                wf / f"cards/fdn/{card_id}/card_impl.py",
            )
        return run_dir

    def test_three_dimensions_computed(self, tmp_path: Path) -> None:
        run_dir = self._harvest(tmp_path, implement=["fdn_129"])
        result = evaluate_run(run_dir, load_benchmark("smoke"), timeout=120)
        # Dimension 1: the target cards.
        assert set(result.sos_results) == {"fdn_129", "fdn_205", "fdn_232"}
        # The implemented target is green; the untouched stubs still computed.
        assert result.sos_results["fdn_129"].tests_passed >= 8
        assert result.sos_results["fdn_129"].tests_failed == 0
        assert result.sos_results["fdn_205"].tests_total > 0
        # Dimension 2 (FDN regression) and 3 (engine) both produced results.
        assert result.fdn_results
        assert result.engine_result.tests_total > 0

    def test_missing_workspace_final_is_reported_not_crashed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "empty-run"
        run_dir.mkdir()
        result = evaluate_run(run_dir, load_benchmark("smoke"), timeout=30)
        assert result.engine_result.errors
        assert result.sos_results == {}
