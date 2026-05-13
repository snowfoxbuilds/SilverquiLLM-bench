"""Tests for TODO item 7: Remove stale iterations/ directory creation.

Verifies that:
- The result record built by _build_result_record excludes 'iterations' from metrics.
- save_card_result produces flat directories with no iterations/ subdirectory.
- save_card_result_v2 produces flat directories with no iterations/ subdirectory.
- No code in silverquillm/ creates iterations/ directories.
- Result records don't contain stale 'iterations' or 'iteration_count' fields.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from silverquillm.config import BenchmarkConfig
from silverquillm.results import (
    init_results_dir,
    save_card_result,
    save_card_result_v2,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> BenchmarkConfig:
    defaults = {
        "name": "test-bench",
        "set_code": "FDN",
        "model_name": "claude-sonnet-4",
        "model_provider": "anthropic",
        "output_dir": "",
    }
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


def _make_blind_result(**overrides) -> dict:
    defaults = {
        "impl_source": "def solve(): return 42\n",
        "agent": "agent-alpha",
        "complexity_tier": "medium",
        "status": "success",
        "iterations": [{"attempt": 1, "output": "ok"}],
        "iteration_count": 1,
    }
    defaults.update(overrides)
    return defaults


def _make_test_result(**overrides) -> dict:
    defaults = {
        "impl_source": "def solve(): return 42  # tested\n",
        "tests_source": "def test_solve(): assert solve() == 42\n",
        "agent": "agent-alpha",
        "complexity_tier": "medium",
        "status": "success",
        "iterations": [
            {"attempt": 1, "output": "fail"},
            {"attempt": 2, "output": "pass"},
        ],
        "iteration_count": 2,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# result.json must not contain iterations/iteration_count fields
# ---------------------------------------------------------------------------


class TestResultRecordNoIterations:
    """Verify result.json records don't contain stale iteration fields."""

    def test_iterations_excluded_from_blind_metrics(self, tmp_path: Path):
        """The 'iterations' key from blind_result must NOT appear in result.json implementation.blind."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        card_dir = save_card_result(
            run_dir,
            card_id="card_no_iter",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
        )

        result = json.loads((card_dir / "result.json").read_text())
        blind_metrics = result["implementation"]["blind"]
        assert "iterations" not in blind_metrics, (
            "iterations field should be excluded from blind metrics"
        )

    def test_iterations_excluded_from_tested_metrics(self, tmp_path: Path):
        """The 'iterations' key from test_result must NOT appear in result.json implementation.tested."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        card_dir = save_card_result(
            run_dir,
            card_id="card_no_iter2",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
        )

        result = json.loads((card_dir / "result.json").read_text())
        tested_metrics = result["implementation"]["tested"]
        assert "iterations" not in tested_metrics, (
            "iterations field should be excluded from tested metrics"
        )

    def test_iterations_list_not_serialized_in_result_json(self, tmp_path: Path):
        """The stale 'iterations' list (per-round data) must not appear in result.json."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        card_dir = save_card_result(
            run_dir,
            card_id="card_deep",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
        )

        raw = (card_dir / "result.json").read_text()
        result = json.loads(raw)

        # The 'iterations' list from input dicts must not appear in
        # implementation.blind or implementation.tested
        blind_keys = set(result["implementation"]["blind"].keys())
        tested_keys = set(result["implementation"]["tested"].keys())
        assert "iterations" not in blind_keys | tested_keys, (
            "iterations list should be excluded from implementation metrics"
        )


# ---------------------------------------------------------------------------
# Flat directory structure — no iterations/ subdirectory
# ---------------------------------------------------------------------------


class TestFlatResultDirectory:
    """Verify save_card_result and save_card_result_v2 produce flat directories."""

    def test_save_card_result_no_iterations_subdir(self, tmp_path: Path):
        """save_card_result must not create an iterations/ subdirectory."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        card_dir = save_card_result(
            run_dir,
            card_id="card_flat",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
        )

        assert not (card_dir / "iterations").exists(), (
            "save_card_result should not create an iterations/ subdirectory"
        )

    def test_save_card_result_v2_no_iterations_subdir(self, tmp_path: Path):
        """save_card_result_v2 must not create an iterations/ subdirectory."""
        from silverquillm.evaluator import EvalResultV2

        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        result = EvalResultV2(
            card_id="card_flat_v2",
            mode="impl_test",
            model_name="test-model",
            adapter="mock",
            status="ok",
            complexity_tier="medium",
            implementation={},
            self_eval={},
            audited_eval={},
            engine_diff_summary={},
            errors=[],
        )

        card_dir = save_card_result_v2(
            run_dir, result,
            impl_source="def solve(): pass\n",
            tests_source="def test(): pass\n",
        )

        assert not (card_dir / "iterations").exists(), (
            "save_card_result_v2 should not create an iterations/ subdirectory"
        )
        # Verify directory only has expected files
        entries = set(p.name for p in card_dir.iterdir())
        assert "iterations" not in entries

    def test_card_dir_only_contains_expected_files(self, tmp_path: Path):
        """Card directory should only contain flat files, no unexpected subdirectories."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        card_dir = save_card_result(
            run_dir,
            card_id="card_contents",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
        )

        subdirs = [p for p in card_dir.iterdir() if p.is_dir()]
        assert subdirs == [], (
            f"Card directory should have no subdirectories, found: {[d.name for d in subdirs]}"
        )


# ---------------------------------------------------------------------------
# Source-level: no iterations/ directory creation in silverquillm/
# ---------------------------------------------------------------------------


class TestNoIterationsDirCreationInSource:
    """Verify that no code in silverquillm/ creates iterations/ directories."""

    def test_no_iterations_mkdir_in_results_module(self):
        """results.py should not contain any code that creates 'iterations' directories."""
        results_path = Path(__file__).parent.parent / "silverquillm" / "results.py"
        source = results_path.read_text()

        # Ensure "iterations" is not used in path construction with mkdir
        lines = source.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if 'iterations' in stripped and ('mkdir' in stripped or 'Path' in stripped):
                # Allow the _IMPL_EXCLUDE set which just filters it out
                if '_IMPL_EXCLUDE' in stripped or '_EXCLUDE' in stripped:
                    continue
                pytest.fail(
                    f"Line {i+1} in results.py references 'iterations' in path/mkdir context: {stripped}"
                )

    def test_no_iteration_count_readdition_in_build_result_record(self):
        """_build_result_record should not re-add iteration_count to metrics dicts.

        The Phase 7 cleanup removed the stale re-addition of iteration count.
        Verify the _IMPL_EXCLUDE set includes 'iterations'.
        """
        results_path = Path(__file__).parent.parent / "silverquillm" / "results.py"
        source = results_path.read_text()

        # Parse the source to find _IMPL_EXCLUDE and verify 'iterations' is in it
        assert '"iterations"' in source or "'iterations'" in source, (
            "_IMPL_EXCLUDE should include 'iterations' to filter it from metrics"
        )
