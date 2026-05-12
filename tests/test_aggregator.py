"""Tests for silverquillm.aggregator — run_summary.json aggregation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm.aggregator import (
    RunSummary,
    TierBreakdown,
    CardSummary,
    aggregate_run,
    save_run_summary_v2,
)
from silverquillm.cli import main


def _make_result_v2(
    card_id: str,
    status: str = "completed",
    complexity_tier: str = "simple",
    mode: str = "impl_test",
    model_name: str = "test-model",
    adapter: str = "opencode",
    self_passed: int = 3,
    self_failed: int = 1,
    audited_passed: int = 2,
    audited_failed: int = 2,
    tokens_total: int = 1000,
    runtime_ms: float = 5000.0,
) -> dict:
    """Build a minimal v2 result.json dict."""
    result = {
        "schema_version": 2,
        "card_id": card_id,
        "status": status,
        "complexity_tier": complexity_tier,
        "mode": mode,
        "model_name": model_name,
        "adapter": adapter,
        "implementation": {
            "tokens": {"input": tokens_total // 2, "output": tokens_total // 2, "total": tokens_total},
            "runtime_ms": runtime_ms,
        },
        "self_eval": {"passed": self_passed, "failed": self_failed, "total": self_passed + self_failed},
        "audited_eval": {"passed": audited_passed, "failed": audited_failed, "total": audited_passed + audited_failed},
    }
    return result


def _write_card_result(run_dir: Path, card_id: str, result: dict) -> None:
    """Write a result.json into run_dir/cards/<card_id>/."""
    card_dir = run_dir / "cards" / card_id
    card_dir.mkdir(parents=True, exist_ok=True)
    (card_dir / "result.json").write_text(json.dumps(result, indent=2))


class TestAggregateRun:
    """Tests for aggregate_run() pure function."""

    def test_empty_run_dir(self, tmp_path: Path) -> None:
        """aggregate_run on an empty dir produces zero-count summary."""
        summary = aggregate_run(tmp_path)
        assert isinstance(summary, RunSummary)
        assert summary.total_cards == 0
        assert summary.cards_completed == 0
        assert summary.card_summaries == []
        assert summary.tier_breakdown == []

    def test_single_card(self, tmp_path: Path) -> None:
        result = _make_result_v2("card_001")
        _write_card_result(tmp_path, "card_001", result)

        summary = aggregate_run(tmp_path)
        assert summary.total_cards == 1
        assert summary.cards_completed == 1
        assert summary.cards_timeout == 0
        assert summary.cards_no_output == 0
        assert summary.model_name == "test-model"
        assert summary.adapter == "opencode"
        assert len(summary.card_summaries) == 1
        assert summary.card_summaries[0].card_id == "card_001"
        assert summary.card_summaries[0].status == "completed"

    def test_multiple_cards_mixed_status(self, tmp_path: Path) -> None:
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001", status="completed"))
        _write_card_result(tmp_path, "card_002", _make_result_v2("card_002", status="timeout"))
        _write_card_result(tmp_path, "card_003", _make_result_v2("card_003", status="no_output"))

        summary = aggregate_run(tmp_path)
        assert summary.total_cards == 3
        assert summary.cards_completed == 1
        assert summary.cards_timeout == 1
        assert summary.cards_no_output == 1

    def test_tier_breakdown(self, tmp_path: Path) -> None:
        _write_card_result(tmp_path, "card_001", _make_result_v2(
            "card_001", complexity_tier="simple", audited_passed=4, audited_failed=0,
        ))
        _write_card_result(tmp_path, "card_002", _make_result_v2(
            "card_002", complexity_tier="simple", audited_passed=2, audited_failed=2,
        ))
        _write_card_result(tmp_path, "card_003", _make_result_v2(
            "card_003", complexity_tier="complex", audited_passed=1, audited_failed=3,
        ))

        summary = aggregate_run(tmp_path)
        assert len(summary.tier_breakdown) == 2

        tier_map = {t.tier: t for t in summary.tier_breakdown}
        assert "simple" in tier_map
        assert "complex" in tier_map
        assert tier_map["simple"].card_count == 2
        assert tier_map["complex"].card_count == 1
        # simple: avg of 1.0 and 0.5 = 0.75
        assert abs(tier_map["simple"].avg_audited_pass_rate - 0.75) < 0.01

    def test_aggregate_token_stats(self, tmp_path: Path) -> None:
        _write_card_result(tmp_path, "card_001", _make_result_v2(
            "card_001", tokens_total=1000, runtime_ms=2000.0,
        ))
        _write_card_result(tmp_path, "card_002", _make_result_v2(
            "card_002", tokens_total=3000, runtime_ms=4000.0,
        ))

        summary = aggregate_run(tmp_path)
        assert summary.total_tokens == 4000
        assert summary.total_runtime_ms == 6000.0
        assert summary.avg_tokens_per_card == 2000.0
        assert summary.avg_runtime_per_card == 3000.0

    def test_per_card_pass_rates(self, tmp_path: Path) -> None:
        _write_card_result(tmp_path, "card_001", _make_result_v2(
            "card_001", self_passed=3, self_failed=1, audited_passed=2, audited_failed=2,
        ))

        summary = aggregate_run(tmp_path)
        cs = summary.card_summaries[0]
        assert cs.self_eval_pass_rate == pytest.approx(0.75)
        assert cs.audited_eval_pass_rate == pytest.approx(0.5)

    def test_idempotency_including_timestamp(self, tmp_path: Path) -> None:
        """Running aggregate_run twice produces fully identical RunSummary including timestamp."""
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001"))
        _write_card_result(tmp_path, "card_002", _make_result_v2("card_002", status="timeout"))

        summary1 = aggregate_run(tmp_path)
        summary2 = aggregate_run(tmp_path)

        # Full equality — timestamp is deterministic (derived from mtime, not now())
        from dataclasses import asdict
        assert asdict(summary1) == asdict(summary2)

    def test_timestamp_derived_from_result_mtime(self, tmp_path: Path) -> None:
        """Timestamp should be non-empty and derived from result.json file mtime."""
        import os
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001"))

        # Set a known mtime on the result.json
        result_path = tmp_path / "cards" / "card_001" / "result.json"
        known_mtime = 1700000000.0  # 2023-11-14T22:13:20+00:00
        os.utime(result_path, (known_mtime, known_mtime))

        summary = aggregate_run(tmp_path)
        assert summary.timestamp != ""
        assert "2023-11-14" in summary.timestamp

    def test_integer_tokens(self, tmp_path: Path) -> None:
        """result.json with implementation.tokens as plain integer → correct total_tokens."""
        result = _make_result_v2("card_001")
        result["implementation"]["tokens"] = 2500  # plain int, not dict
        _write_card_result(tmp_path, "card_001", result)

        summary = aggregate_run(tmp_path)
        assert summary.total_tokens == 2500

    def test_legacy_status_ok_normalized(self, tmp_path: Path) -> None:
        """result.json with status 'ok' is counted as completed."""
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001", status="ok"))

        summary = aggregate_run(tmp_path)
        assert summary.cards_completed == 1
        assert summary.card_summaries[0].status == "completed"

    def test_legacy_status_success_normalized(self, tmp_path: Path) -> None:
        """result.json with status 'success' is counted as completed."""
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001", status="success"))

        summary = aggregate_run(tmp_path)
        assert summary.cards_completed == 1
        assert summary.card_summaries[0].status == "completed"

    def test_mixed_token_shapes(self, tmp_path: Path) -> None:
        """Mix of dict tokens and integer tokens produces correct aggregate."""
        result_dict_tokens = _make_result_v2("card_001", tokens_total=1000)
        # card_001 has dict tokens {"input": 500, "output": 500, "total": 1000}

        result_int_tokens = _make_result_v2("card_002")
        result_int_tokens["implementation"]["tokens"] = 3000  # plain int

        _write_card_result(tmp_path, "card_001", result_dict_tokens)
        _write_card_result(tmp_path, "card_002", result_int_tokens)

        summary = aggregate_run(tmp_path)
        assert summary.total_tokens == 4000
        assert summary.avg_tokens_per_card == 2000.0


class TestSaveRunSummaryV2:
    """Tests for save_run_summary_v2() persistence."""

    def test_writes_json(self, tmp_path: Path) -> None:
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001"))
        summary = aggregate_run(tmp_path)
        out = save_run_summary_v2(tmp_path, summary)

        assert out == tmp_path / "run_summary.json"
        assert out.exists()

        data = json.loads(out.read_text())
        assert data["total_cards"] == 1
        assert data["cards_completed"] == 1
        assert len(data["card_summaries"]) == 1
        assert data["card_summaries"][0]["card_id"] == "card_001"

    def test_overwrite_on_rerun(self, tmp_path: Path) -> None:
        """save_run_summary_v2 overwrites existing file (idempotent)."""
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001"))

        summary = aggregate_run(tmp_path)
        save_run_summary_v2(tmp_path, summary)
        save_run_summary_v2(tmp_path, summary)

        data = json.loads((tmp_path / "run_summary.json").read_text())
        assert data["total_cards"] == 1


class TestMissingFields:
    """Tests for graceful handling of result.json with missing optional fields."""

    def test_missing_self_eval(self, tmp_path: Path) -> None:
        """result.json without self_eval → pass rate is None."""
        result = _make_result_v2("card_001")
        del result["self_eval"]
        _write_card_result(tmp_path, "card_001", result)

        summary = aggregate_run(tmp_path)
        assert summary.total_cards == 1
        cs = summary.card_summaries[0]
        assert cs.self_eval_pass_rate is None

    def test_missing_audited_eval(self, tmp_path: Path) -> None:
        """result.json without audited_eval → pass rate is None."""
        result = _make_result_v2("card_001")
        del result["audited_eval"]
        _write_card_result(tmp_path, "card_001", result)

        summary = aggregate_run(tmp_path)
        cs = summary.card_summaries[0]
        assert cs.audited_eval_pass_rate is None

    def test_missing_implementation(self, tmp_path: Path) -> None:
        """result.json without implementation → tokens/runtime are zero."""
        result = _make_result_v2("card_001")
        del result["implementation"]
        _write_card_result(tmp_path, "card_001", result)

        summary = aggregate_run(tmp_path)
        assert summary.total_tokens == 0
        assert summary.total_runtime_ms == 0.0

    def test_zero_total_eval(self, tmp_path: Path) -> None:
        """Eval with total=0 → pass rate is None (avoid division by zero)."""
        result = _make_result_v2("card_001")
        result["self_eval"] = {"passed": 0, "failed": 0, "total": 0}
        result["audited_eval"] = {"passed": 0, "failed": 0, "total": 0}
        _write_card_result(tmp_path, "card_001", result)

        summary = aggregate_run(tmp_path)
        cs = summary.card_summaries[0]
        assert cs.self_eval_pass_rate is None
        assert cs.audited_eval_pass_rate is None


class TestSelfEvalPassRate:
    """Dedicated tests for self-eval pass rate calculation."""

    def test_self_eval_pass_rate_all_pass(self, tmp_path: Path) -> None:
        _write_card_result(tmp_path, "card_001", _make_result_v2(
            "card_001", self_passed=5, self_failed=0,
        ))
        summary = aggregate_run(tmp_path)
        assert summary.card_summaries[0].self_eval_pass_rate == pytest.approx(1.0)

    def test_self_eval_pass_rate_all_fail(self, tmp_path: Path) -> None:
        _write_card_result(tmp_path, "card_001", _make_result_v2(
            "card_001", self_passed=0, self_failed=4,
        ))
        summary = aggregate_run(tmp_path)
        assert summary.card_summaries[0].self_eval_pass_rate == pytest.approx(0.0)


class TestAuditedEvalPassRate:
    """Dedicated tests for audited eval pass rate calculation."""

    def test_audited_eval_pass_rate_partial(self, tmp_path: Path) -> None:
        _write_card_result(tmp_path, "card_001", _make_result_v2(
            "card_001", audited_passed=3, audited_failed=1,
        ))
        summary = aggregate_run(tmp_path)
        assert summary.card_summaries[0].audited_eval_pass_rate == pytest.approx(0.75)


class TestCLIAggregateSubcommand:
    """Tests for `benchmark aggregate` CLI subcommand."""

    def test_aggregate_subcommand_produces_summary(self, tmp_path: Path) -> None:
        """Running `benchmark aggregate <run_dir>` writes run_summary.json."""
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001"))

        runner = CliRunner()
        result = runner.invoke(main, ["aggregate", str(tmp_path)])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        summary_path = tmp_path / "run_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert data["total_cards"] == 1

    def test_aggregate_subcommand_output(self, tmp_path: Path) -> None:
        """CLI aggregate prints summary stats to stdout."""
        _write_card_result(tmp_path, "card_001", _make_result_v2("card_001"))
        _write_card_result(tmp_path, "card_002", _make_result_v2("card_002", status="timeout"))

        runner = CliRunner()
        result = runner.invoke(main, ["aggregate", str(tmp_path)])

        assert result.exit_code == 0
        assert "Total cards: 2" in result.output
        assert "Completed: 1" in result.output
        assert "Timeout: 1" in result.output
