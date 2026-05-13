"""Tests for TODO item 14: Result recording and output artifacts.

Tests verify:
- generate_run_name returns {model_name}_{ISO-timestamp} format.
- generate_run_name uses config.output_dir as override when set.
- init_results_dir creates per-run directory with config.yaml and cards/ subdir.
- init_results_dir with two different run names creates separate directories.
- init_results_dir uses generate_run_name when run_name=None.
- ssave_card_result writes blind_impl.py, tested_impl.py, tests.py, result.json (flat, no iterations/).
- save_card_result result.json is valid JSON with expected schema.
- save_card_result with EvalResult objects populates eval fields correctly.
- save_card_result with empty/None inputs writes minimal artifacts.
- save_run_summary writes valid summary.json with correct card count.
- save_run_summary with empty results writes card_count=0.
- save_aggregates writes leaderboard.md, cross_eval_matrix.json, summary.json.
- save_aggregates summary.json has correct card count and leaderboard data.
- save_aggregates leaderboard.md content matches generate_leaderboard output.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from silverquillm.config import BenchmarkConfig
from silverquillm.evaluator import EvalResult
from silverquillm.results import (
    generate_run_name,
    init_results_dir,
    save_aggregates,
    save_card_result,
    save_run_summary,
)
from silverquillm.scorer import (
    AgentCat1Scores,
    AgentCat2Scores,
    Leaderboard,
    generate_leaderboard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> BenchmarkConfig:
    """Create a BenchmarkConfig with sensible defaults for testing."""
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
    }
    defaults.update(overrides)
    return defaults


def _make_eval_result(card_id: str = "card_a", eval_type: str = "self") -> EvalResult:
    return EvalResult(
        card_id=card_id,
        agent="agent-alpha",
        eval_type=eval_type,
        blind_passed=3,
        blind_failed=1,
        blind_total=4,
        tested_passed=4,
        tested_failed=0,
        tested_total=4,
        errors=[],
    )


# ---------------------------------------------------------------------------
# generate_run_name
# ---------------------------------------------------------------------------


class TestGenerateRunName:
    """Tests for generate_run_name()."""

    def test_format_model_name_and_timestamp(self):
        """Run name starts with model name followed by underscore and ISO-ish timestamp."""
        config = _make_config(model_name="gpt-4o")
        name = generate_run_name(config)
        # Should match pattern: gpt-4o_YYYY-MM-DDTHH-MM
        assert name.startswith("gpt-4o_")
        ts_part = name[len("gpt-4o_"):]
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}", ts_part), (
            f"Timestamp part '{ts_part}' doesn't match expected ISO format"
        )

    def test_output_dir_not_used_as_run_name(self):
        """output_dir is the parent results directory, NOT a run-name override.

        generate_run_name should always produce {model_name}_{timestamp}
        regardless of output_dir.  The run_name parameter (on init_results_dir)
        is the proper override mechanism.
        """
        config = _make_config(model_name="gpt-4o", output_dir="/some/parent/dir")
        name = generate_run_name(config)
        # Should still be model_timestamp format, NOT the output_dir value
        assert name.startswith("gpt-4o_")
        assert name != "/some/parent/dir"

    def test_output_dir_used_as_parent_in_init_results_dir(self, tmp_path: Path):
        """config.output_dir is used as the parent directory for runs."""
        parent = tmp_path / "my_results"
        parent.mkdir()
        config = _make_config(output_dir=str(parent))
        run_dir = init_results_dir(config, run_name="explicit-run")
        assert run_dir.parent == parent
        assert run_dir.name == "explicit-run"

    def test_run_name_parameter_overrides_generated_name(self, tmp_path: Path):
        """run_name parameter on init_results_dir is the override mechanism."""
        config = _make_config(model_name="gpt-4o")
        run_dir = init_results_dir(config, run_name="my-custom-run", base_dir=tmp_path)
        assert run_dir.name == "my-custom-run"

    def test_empty_output_dir_generates_name(self):
        """When output_dir is empty string, a name is generated."""
        config = _make_config(output_dir="")
        name = generate_run_name(config)
        assert "claude-sonnet-4" in name
        assert name != ""

    def test_no_colons_in_generated_name(self):
        """Colons are filesystem-unfriendly; generated name must not contain them."""
        config = _make_config()
        name = generate_run_name(config)
        assert ":" not in name


# ---------------------------------------------------------------------------
# init_results_dir
# ---------------------------------------------------------------------------


class TestInitResultsDir:
    """Tests for init_results_dir()."""

    def test_creates_run_directory(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)
        assert run_dir.is_dir()
        assert run_dir.name == "run-1"

    def test_creates_config_yaml(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)
        config_file = run_dir / "config.yaml"
        assert config_file.exists()
        data = yaml.safe_load(config_file.read_text())
        assert data["model_name"] == "claude-sonnet-4"
        assert data["set_code"] == "FDN"

    def test_creates_cards_subdir(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)
        assert (run_dir / "cards").is_dir()

    def test_two_different_run_names_create_separate_dirs(self, tmp_path: Path):
        """Calling init_results_dir twice with different names creates separate dirs."""
        config = _make_config()
        run1 = init_results_dir(config, run_name="run-alpha", base_dir=tmp_path)
        run2 = init_results_dir(config, run_name="run-beta", base_dir=tmp_path)
        assert run1 != run2
        assert run1.is_dir()
        assert run2.is_dir()
        assert (run1 / "config.yaml").exists()
        assert (run2 / "config.yaml").exists()

    def test_uses_generate_run_name_when_none(self, tmp_path: Path):
        """When run_name is None, generate_run_name is called."""
        config = _make_config(model_name="test-model")
        run_dir = init_results_dir(config, run_name=None, base_dir=tmp_path)
        assert "test-model" in run_dir.name

    def test_idempotent_second_call_same_name(self, tmp_path: Path):
        """Calling with the same run_name twice doesn't raise."""
        config = _make_config()
        run1 = init_results_dir(config, run_name="same-run", base_dir=tmp_path)
        run2 = init_results_dir(config, run_name="same-run", base_dir=tmp_path)
        assert run1 == run2


# ---------------------------------------------------------------------------
# save_card_result
# ---------------------------------------------------------------------------


class TestSaveCardResult:
    """Tests for save_card_result()."""

    def test_writes_all_expected_files(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        card_dir = save_card_result(
            run_dir,
            card_id="card_alpha",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
            eval_results=[_make_eval_result("card_alpha")],
        )

        assert (card_dir / "blind_impl.py").exists()
        assert (card_dir / "tested_impl.py").exists()
        assert (card_dir / "tests.py").exists()
        assert not (card_dir / "iterations").exists()
        assert (card_dir / "result.json").exists()

    def test_result_json_is_valid(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        card_dir = save_card_result(
            run_dir,
            card_id="card_beta",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
            eval_results=[_make_eval_result("card_beta", eval_type="self")],
        )

        result = json.loads((card_dir / "result.json").read_text())
        assert result["card_id"] == "card_beta"
        assert "implementation" in result
        assert "self_eval" in result

    def test_result_json_has_eval_data(self, tmp_path: Path):
        """EvalResult data flows through to result.json correctly."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        eval_r = _make_eval_result("card_c", eval_type="self")
        card_dir = save_card_result(
            run_dir,
            card_id="card_c",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
            eval_results=[eval_r],
        )

        result = json.loads((card_dir / "result.json").read_text())
        # Nested-by-phase schema: self_eval.blind.passed, self_eval.tested.passed
        assert result["self_eval"]["blind"]["passed"] == 3
        assert result["self_eval"]["blind"]["failed"] == 1
        assert result["self_eval"]["blind"]["total"] == 4
        assert result["self_eval"]["tested"]["passed"] == 4
        assert result["self_eval"]["tested"]["failed"] == 0
        assert result["self_eval"]["tested"]["total"] == 4

    def test_cross_eval_results(self, tmp_path: Path):
        """Cross-eval results keyed by test agent."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        cross_eval = EvalResult(
            card_id="card_d",
            agent="agent-alpha",
            eval_type="cross:agent-beta",
            blind_passed=2, blind_failed=1, blind_total=3,
            tested_passed=3, tested_failed=0, tested_total=3,
        )
        card_dir = save_card_result(
            run_dir,
            card_id="card_d",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
            eval_results=[cross_eval],
        )

        result = json.loads((card_dir / "result.json").read_text())
        # cross_eval is a list of objects with nested-by-phase format
        assert isinstance(result["cross_eval"], list)
        assert len(result["cross_eval"]) == 1
        entry = result["cross_eval"][0]
        assert entry["impl_agent"] == "agent-alpha"
        assert entry["test_agent"] == "agent-beta"
        assert entry["blind"]["passed"] == 2
        assert entry["blind"]["failed"] == 1
        assert entry["blind"]["total"] == 3
        assert entry["tested"]["passed"] == 3
        assert entry["tested"]["failed"] == 0
        assert entry["tested"]["total"] == 3

    def test_blind_impl_content(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        blind = _make_blind_result(impl_source="# blind code\n")
        card_dir = save_card_result(
            run_dir, card_id="card_e", blind_result=blind,
        )
        assert (card_dir / "blind_impl.py").read_text() == "# blind code\n"

    def test_no_iterations_dir(self, tmp_path: Path):
        """Result directory is flat — no iterations/ subdirectory is created."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        blind = _make_blind_result(iterations=[{"a": 1}])
        test = _make_test_result(iterations=[{"b": 1}, {"b": 2}])
        card_dir = save_card_result(
            run_dir, card_id="card_f", blind_result=blind, test_result=test,
        )
        assert not (card_dir / "iterations").exists()

    def test_implementation_metrics_preserved(self, tmp_path: Path):
        """Implementation metrics (tokens, runtime, peak_context, etc.) flow through to result.json."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        blind = _make_blind_result(
            tokens=1500,
            runtime=12.5,
            peak_context=50000,
            test_iterations=0,
            rules_lookups=3,
        )
        test = _make_test_result(
            tokens=3200,
            runtime=25.0,
            peak_context=80000,
            test_iterations=2,
            rules_lookups=5,
        )
        card_dir = save_card_result(
            run_dir,
            card_id="card_metrics",
            blind_result=blind,
            test_result=test,
        )
        result = json.loads((card_dir / "result.json").read_text())
        impl = result["implementation"]
        assert impl["blind"]["tokens"] == 1500
        assert impl["blind"]["runtime"] == 12.5
        assert impl["blind"]["peak_context"] == 50000
        assert impl["blind"]["rules_lookups"] == 3
        assert impl["tested"]["tokens"] == 3200
        assert impl["tested"]["runtime"] == 25.0
        assert impl["tested"]["peak_context"] == 80000
        assert impl["tested"]["test_iterations"] == 2
        assert impl["tested"]["rules_lookups"] == 5

    def test_empty_inputs_no_crash(self, tmp_path: Path):
        """Calling with None/empty inputs writes minimal artifacts."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        card_dir = save_card_result(
            run_dir,
            card_id="card_empty",
            blind_result=None,
            test_result=None,
            eval_results=None,
        )

        assert card_dir.is_dir()
        assert (card_dir / "result.json").exists()
        result = json.loads((card_dir / "result.json").read_text())
        assert result["card_id"] == "card_empty"

    def test_dict_eval_results_accepted(self, tmp_path: Path):
        """eval_results can be plain dicts (not just EvalResult)."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        eval_dict = {
            "eval_type": "audited",
            "blind_passed": 5,
            "blind_failed": 0,
            "blind_total": 5,
            "tested_passed": 5,
            "tested_failed": 0,
            "tested_total": 5,
            "errors": [],
        }
        card_dir = save_card_result(
            run_dir, card_id="card_dict",
            blind_result=_make_blind_result(),
            eval_results=[eval_dict],
        )
        result = json.loads((card_dir / "result.json").read_text())
        # audited_eval uses nested-by-phase format
        assert result["audited_eval"]["blind"]["passed"] == 5
        assert result["audited_eval"]["blind"]["failed"] == 0
        assert result["audited_eval"]["blind"]["total"] == 5
        assert result["audited_eval"]["tested"]["passed"] == 5
        assert result["audited_eval"]["tested"]["failed"] == 0
        assert result["audited_eval"]["tested"]["total"] == 5


# ---------------------------------------------------------------------------
# save_run_summary
# ---------------------------------------------------------------------------


class TestSaveRunSummary:
    """Tests for save_run_summary()."""

    def test_writes_valid_summary_json(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        all_results = [
            {
                "card_id": "card_a",
                "agent": "agent-alpha",
                "complexity_tier": "simple",
                "self_eval": {
                    "blind": {"passed": 2, "failed": 2, "total": 4},
                    "tested": {"passed": 3, "failed": 1, "total": 4},
                },
                "audited_eval": {
                    "blind": {"passed": 1, "failed": 3, "total": 4},
                    "tested": {"passed": 2, "failed": 2, "total": 4},
                },
            },
            {
                "card_id": "card_b",
                "agent": "agent-alpha",
                "complexity_tier": "complex",
                "self_eval": {
                    "blind": {"passed": 5, "failed": 0, "total": 5},
                    "tested": {"passed": 5, "failed": 0, "total": 5},
                },
                "audited_eval": {},
            },
        ]

        summary_path = save_run_summary(run_dir, all_results)
        assert summary_path.exists()

        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 2
        assert "agent-alpha" in summary["agents"]
        assert summary["tier_counts"]["simple"] == 1
        assert summary["tier_counts"]["complex"] == 1

    def test_empty_results(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        summary_path = save_run_summary(run_dir, [])
        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 0
        assert summary["agents"] == []

    def test_aggregates_eval_stats(self, tmp_path: Path):
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-1", base_dir=tmp_path)

        all_results = [
            {
                "card_id": "c1",
                "agent": "a1",
                "complexity_tier": "medium",
                "self_eval": {
                    "blind": {"passed": 2, "failed": 3, "total": 5},
                    "tested": {"passed": 3, "failed": 2, "total": 5},
                },
                "audited_eval": {
                    "blind": {"passed": 1, "failed": 4, "total": 5},
                    "tested": {"passed": 2, "failed": 3, "total": 5},
                },
            },
            {
                "card_id": "c2",
                "agent": "a1",
                "complexity_tier": "medium",
                "self_eval": {
                    "blind": {"passed": 3, "failed": 2, "total": 5},
                    "tested": {"passed": 4, "failed": 1, "total": 5},
                },
                "audited_eval": {
                    "blind": {"passed": 2, "failed": 3, "total": 5},
                    "tested": {"passed": 3, "failed": 2, "total": 5},
                },
            },
        ]

        summary_path = save_run_summary(run_dir, all_results)
        summary = json.loads(summary_path.read_text())
        assert summary["self_eval"]["total_passed"] == 7
        assert summary["self_eval"]["total_tests"] == 10
        assert summary["audited_eval"]["total_passed"] == 5
        assert summary["audited_eval"]["total_tests"] == 10

    def test_handles_none_audited_eval(self, tmp_path: Path):
        """save_run_summary must not crash when audited_eval is None (not missing).

        Regression test: v2 result.json can write audited_eval: null. The
        previous code used `r.get("audited_eval", {})` which returns None
        (key present, value None), causing AttributeError on `.get()`.
        """
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-null", base_dir=tmp_path)

        all_results = [
            {
                "card_id": "c1",
                "agent": "a1",
                "complexity_tier": "simple",
                "self_eval": None,
                "audited_eval": None,
            },
        ]

        summary_path = save_run_summary(run_dir, all_results)
        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 1
        assert summary["self_eval"]["total_passed"] == 0
        assert summary["audited_eval"]["total_passed"] == 0

    def test_handles_missing_eval_keys(self, tmp_path: Path):
        """save_run_summary must handle results with no self_eval/audited_eval keys."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-missing", base_dir=tmp_path)

        all_results = [
            {
                "card_id": "c1",
                "agent": "a1",
                "complexity_tier": "simple",
            },
        ]

        summary_path = save_run_summary(run_dir, all_results)
        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 1
        assert summary["self_eval"]["total_passed"] == 0
        assert summary["audited_eval"]["total_passed"] == 0


# ---------------------------------------------------------------------------
# save_aggregates
# ---------------------------------------------------------------------------


class TestSaveAggregates:
    """Tests for save_aggregates()."""

    def _setup_run_with_summary(self, base_dir: Path, run_name: str, card_count: int) -> Path:
        """Create a run dir with a summary.json."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name=run_name, base_dir=base_dir)

        summary = {
            "card_count": card_count,
            "agents": ["agent-alpha"],
            "tier_counts": {"medium": card_count},
        }
        (run_dir / "summary.json").write_text(json.dumps(summary))
        return run_dir

    def _make_leaderboard(self) -> Leaderboard:
        lb = Leaderboard()
        lb.category1["agent-alpha"] = AgentCat1Scores(
            weighted_score=0.85,
            audited_pass_rate=0.9,
        )
        lb.category2["agent-alpha"] = AgentCat2Scores(
            weighted_score=0.92,
            audited_pass_rate=0.95,
        )
        return lb

    def test_writes_all_three_files(self, tmp_path: Path):
        run1 = self._setup_run_with_summary(tmp_path, "run-1", 3)
        results_dir = tmp_path / "aggregates"

        save_aggregates(results_dir, [run1], self._make_leaderboard())

        assert (results_dir / "leaderboard.md").exists()
        assert (results_dir / "cross_eval_matrix.json").exists()
        assert (results_dir / "summary.json").exists()

    def test_summary_json_has_correct_card_count(self, tmp_path: Path):
        run1 = self._setup_run_with_summary(tmp_path, "run-1", 3)
        run2 = self._setup_run_with_summary(tmp_path, "run-2", 5)
        results_dir = tmp_path / "aggregates"

        save_aggregates(results_dir, [run1, run2], self._make_leaderboard())

        summary = json.loads((results_dir / "summary.json").read_text())
        assert summary["card_count"] == 8  # 3 + 5
        assert summary["total_runs"] == 2

    def test_summary_json_has_leaderboard_data(self, tmp_path: Path):
        run1 = self._setup_run_with_summary(tmp_path, "run-1", 2)
        results_dir = tmp_path / "aggregates"

        save_aggregates(results_dir, [run1], self._make_leaderboard())

        summary = json.loads((results_dir / "summary.json").read_text())
        assert "leaderboard" in summary
        assert "category1" in summary["leaderboard"]
        cat1 = summary["leaderboard"]["category1"]
        assert cat1["agent-alpha"]["weighted_score"] == 0.85

    def test_leaderboard_md_matches_scorer_output(self, tmp_path: Path):
        """leaderboard.md should contain the output of generate_leaderboard."""
        run1 = self._setup_run_with_summary(tmp_path, "run-1", 2)
        results_dir = tmp_path / "aggregates"
        lb = self._make_leaderboard()

        save_aggregates(results_dir, [run1], lb)

        written = (results_dir / "leaderboard.md").read_text()
        expected = generate_leaderboard(lb)
        assert written == expected

    def test_cross_eval_matrix_valid_json(self, tmp_path: Path):
        run1 = self._setup_run_with_summary(tmp_path, "run-1", 1)
        results_dir = tmp_path / "aggregates"

        save_aggregates(results_dir, [run1], self._make_leaderboard())

        matrix = json.loads((results_dir / "cross_eval_matrix.json").read_text())
        assert isinstance(matrix, dict)

    def test_empty_run_dirs(self, tmp_path: Path):
        """save_aggregates with empty run_dirs list still writes files."""
        results_dir = tmp_path / "aggregates"
        save_aggregates(results_dir, [], self._make_leaderboard())

        summary = json.loads((results_dir / "summary.json").read_text())
        assert summary["total_runs"] == 0
        assert summary["card_count"] == 0

    def test_cross_eval_matrix_populated(self, tmp_path: Path):
        """When cards have cross_eval data, it appears in the matrix."""
        config = _make_config()
        run_dir = init_results_dir(config, run_name="run-cross", base_dir=tmp_path)

        # Write a card result with cross-eval data
        cross_eval = EvalResult(
            card_id="card_x",
            agent="agent-alpha",
            eval_type="cross:agent-beta",
            blind_passed=2, blind_failed=1, blind_total=3,
            tested_passed=3, tested_failed=0, tested_total=3,
        )
        save_card_result(
            run_dir,
            card_id="card_x",
            blind_result=_make_blind_result(),
            test_result=_make_test_result(),
            eval_results=[cross_eval],
        )

        # Set up summary for the run
        summary = {"card_count": 1, "agents": ["agent-alpha"], "tier_counts": {"medium": 1}}
        (run_dir / "summary.json").write_text(json.dumps(summary))

        results_dir = tmp_path / "agg"
        save_aggregates(results_dir, [run_dir], self._make_leaderboard())

        matrix = json.loads((results_dir / "cross_eval_matrix.json").read_text())
        assert "card_x" in matrix
        assert "agent-alpha" in matrix["card_x"]
        assert "agent-beta" in matrix["card_x"]["agent-alpha"]
        assert matrix["card_x"]["agent-alpha"]["agent-beta"]["passed"] == 3


# ---------------------------------------------------------------------------
# Violations annotation in result.json  (Item 5)
# ---------------------------------------------------------------------------


class TestViolationsInResultJson:
    """save_card_result must propagate violations into result.json."""

    def test_violations_appear_in_result_json(self, tmp_path):
        cfg = _make_config()
        run_dir = init_results_dir(cfg, run_name="violation-run", base_dir=tmp_path)
        violations = ["docs/hack.py was created", "engine/core.py was modified"]
        blind = _make_blind_result(violations=violations)
        save_card_result(run_dir, "card_v", blind_result=blind)

        result = json.loads((run_dir / "cards" / "card_v" / "result.json").read_text())
        assert result["violations"] == violations

    def test_no_violations_yields_empty_list(self, tmp_path):
        cfg = _make_config()
        run_dir = init_results_dir(cfg, run_name="clean-run", base_dir=tmp_path)
        blind = _make_blind_result()
        save_card_result(run_dir, "card_clean", blind_result=blind)

        result = json.loads((run_dir / "cards" / "card_clean" / "result.json").read_text())
        assert result["violations"] == []

    def test_violations_and_files_coexist(self, tmp_path):
        """Violations annotate result.json while impl files are still saved."""
        cfg = _make_config()
        run_dir = init_results_dir(cfg, run_name="coexist-run", base_dir=tmp_path)
        violations = ["tests/existing.py was modified"]
        blind = _make_blind_result(impl_source="class Card: pass\n", violations=violations)
        test = _make_test_result(impl_source="class CardTested: pass\n")
        card_dir = save_card_result(run_dir, "card_co", blind_result=blind, test_result=test)

        result = json.loads((card_dir / "result.json").read_text())
        assert result["violations"] == violations
        assert (card_dir / "blind_impl.py").read_text() == "class Card: pass\n"
        assert (card_dir / "tested_impl.py").read_text() == "class CardTested: pass\n"
