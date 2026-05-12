"""Tests for TODO item 8: Move all evaluation to post-run.

Tests verify:
- run_post_eval returns a CardEvalResult for each card directory.
- Self-eval runs in impl_test mode when card has tests.py + card_impl.py.
- Self-eval is skipped in blind mode.
- Audited eval with set_code-based lookup: audited_dir/{set_code}/{collector}/tests.py.
- Audited eval falls back to flat layout: audited_dir/{card_id}/tests.py.
- Cards without card_impl.py are handled (error reported, not crash).
- engine_dir is passed through to run_tests for PYTHONPATH.
- result.json uses existing nested schema (self_eval.passed, audited_eval.passed).
- result.json is compatible with save_run_summary consumer.
- CardEvalResult dataclass has expected fields and defaults.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch, call

import pytest

from silverquillm.post_eval import CardEvalResult, run_post_eval


# ---------------------------------------------------------------------------
# Shared fixture code
# ---------------------------------------------------------------------------

SIMPLE_IMPL = textwrap.dedent("""\
    def add(a, b):
        return a + b
""")

SIMPLE_TESTS = textwrap.dedent("""\
    from card_impl import add

    def test_add_positive():
        assert add(2, 3) == 5

    def test_add_zero():
        assert add(0, 0) == 0
""")


def _make_card(
    cards_dir: Path,
    card_id: str,
    *,
    impl: bool = True,
    tests: bool = True,
    set_code: str | None = None,
) -> Path:
    """Create a card directory with optional impl, tests, and result.json metadata."""
    card_dir = cards_dir / card_id
    card_dir.mkdir(parents=True, exist_ok=True)
    if impl:
        (card_dir / "card_impl.py").write_text(SIMPLE_IMPL)
    if tests:
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)
    if set_code is not None:
        (card_dir / "result.json").write_text(
            json.dumps({"card_id": card_id, "set_code": set_code})
        )
    return card_dir


def _make_run_dir(tmp_path: Path, card_ids: list[str], *, with_engine: bool = True) -> Path:
    """Create a run directory with cards and optionally an engine dir."""
    run_dir = tmp_path / "run"
    cards_dir = run_dir / "cards"
    cards_dir.mkdir(parents=True)
    if with_engine:
        (run_dir / "engine").mkdir()
    for cid in card_ids:
        _make_card(cards_dir, cid)
    return run_dir


# ---------------------------------------------------------------------------
# CardEvalResult dataclass
# ---------------------------------------------------------------------------


class TestCardEvalResultDataclass:
    """Verify CardEvalResult dataclass shape and defaults."""

    def test_has_card_id_field(self):
        r = CardEvalResult(card_id="001")
        assert r.card_id == "001"

    def test_defaults_to_zero_counts(self):
        r = CardEvalResult(card_id="x")
        assert r.self_eval_passed == 0
        assert r.self_eval_failed == 0
        assert r.self_eval_total == 0
        assert r.audited_passed == 0
        assert r.audited_failed == 0
        assert r.audited_total == 0

    def test_errors_default_empty_list(self):
        r = CardEvalResult(card_id="x")
        assert r.errors == []


# ---------------------------------------------------------------------------
# run_post_eval — basic flow
# ---------------------------------------------------------------------------


class TestRunPostEvalBasicFlow:
    """run_post_eval returns one CardEvalResult per card in run_dir/cards/."""

    def test_returns_result_per_card(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-a", "card-b"])
        results = run_post_eval(run_dir, mode="impl_test")
        assert len(results) == 2

    def test_result_card_ids_match_directories(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["001", "002", "003"])
        results = run_post_eval(run_dir, mode="impl_test")
        card_ids = {r.card_id for r in results}
        assert card_ids == {"001", "002", "003"}

    def test_returns_list_of_card_eval_result(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-x"])
        results = run_post_eval(run_dir, mode="impl_test")
        assert all(isinstance(r, CardEvalResult) for r in results)

    def test_empty_cards_dir_returns_empty(self, tmp_path: Path):
        run_dir = tmp_path / "run"
        (run_dir / "cards").mkdir(parents=True)
        results = run_post_eval(run_dir, mode="impl_test")
        assert results == []

    def test_no_cards_dir_returns_empty(self, tmp_path: Path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        results = run_post_eval(run_dir, mode="impl_test")
        assert results == []


# ---------------------------------------------------------------------------
# Self-eval in impl_test mode
# ---------------------------------------------------------------------------


class TestSelfEvalImplTestMode:
    """Self-eval runs card's tests.py against card_impl.py in impl_test mode."""

    def test_self_eval_runs_and_reports_passes(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        results = run_post_eval(run_dir, mode="impl_test")
        r = results[0]
        assert r.self_eval_passed == 2
        assert r.self_eval_failed == 0
        assert r.self_eval_total == 2

    def test_self_eval_reports_failures(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, [], with_engine=True)
        cards_dir = run_dir / "cards"
        card_dir = cards_dir / "card-buggy"
        card_dir.mkdir()
        (card_dir / "card_impl.py").write_text("def add(a, b):\n    return a - b\n")
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)

        results = run_post_eval(run_dir, mode="impl_test")
        r = results[0]
        assert r.self_eval_failed > 0
        assert r.self_eval_total == 2


# ---------------------------------------------------------------------------
# Self-eval skipped in blind mode
# ---------------------------------------------------------------------------


class TestSelfEvalBlindMode:
    """Self-eval is NOT run when mode is 'blind'."""

    def test_self_eval_zeros_in_blind_mode(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        results = run_post_eval(run_dir, mode="blind")
        r = results[0]
        assert r.self_eval_passed == 0
        assert r.self_eval_failed == 0
        assert r.self_eval_total == 0

    def test_self_eval_not_called_in_blind_mode(self, tmp_path: Path):
        """Verify run_tests is NOT called for self-eval in blind mode."""
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        with patch("silverquillm.post_eval.run_tests", return_value=(0, 0, 0, [])) as mock_rt:
            run_post_eval(run_dir, mode="blind", audited_dir=None)
            # run_tests should not have been called at all (no audited dir either)
            mock_rt.assert_not_called()


# ---------------------------------------------------------------------------
# Audited eval — set_code-based lookup
# ---------------------------------------------------------------------------


class TestAuditedEvalSetCodeLookup:
    """Audited tests are found at audited_dir/{set_code}/{collector_number}/tests.py."""

    def test_audited_lookup_uses_set_code_from_result_json(self, tmp_path: Path):
        """When result.json has set_code, audited tests are found at
        audited_dir/{set_code}/{card_id}/tests.py."""
        run_dir = tmp_path / "run"
        cards_dir = run_dir / "cards"
        cards_dir.mkdir(parents=True)
        (run_dir / "engine").mkdir()

        # Card "042" with set_code "neo" in its result.json
        _make_card(cards_dir, "042", set_code="neo")

        # Audited tests at audited_dir/neo/042/tests.py
        audited_dir = tmp_path / "audited"
        (audited_dir / "neo" / "042").mkdir(parents=True)
        (audited_dir / "neo" / "042" / "tests.py").write_text(SIMPLE_TESTS)

        results = run_post_eval(run_dir, mode="impl_test", audited_dir=audited_dir)
        r = results[0]
        assert r.audited_passed == 2
        assert r.audited_total == 2

    def test_audited_lookup_set_code_multiple_cards_different_sets(self, tmp_path: Path):
        """Multiple cards from different sets each find their own audited tests."""
        run_dir = tmp_path / "run"
        cards_dir = run_dir / "cards"
        cards_dir.mkdir(parents=True)
        (run_dir / "engine").mkdir()

        _make_card(cards_dir, "001", set_code="neo")
        _make_card(cards_dir, "002", set_code="mir")

        audited_dir = tmp_path / "audited"
        for set_code, cid in [("neo", "001"), ("mir", "002")]:
            (audited_dir / set_code / cid).mkdir(parents=True)
            (audited_dir / set_code / cid / "tests.py").write_text(SIMPLE_TESTS)

        results = run_post_eval(run_dir, mode="impl_test", audited_dir=audited_dir)
        assert len(results) == 2
        for r in results:
            assert r.audited_passed == 2, f"card {r.card_id} should have 2 audited passes"
            assert r.audited_total == 2

    def test_audited_lookup_falls_back_to_flat_layout(self, tmp_path: Path):
        """When no set_code in result.json, falls back to audited_dir/{card_id}/tests.py."""
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        # No set_code in result.json — flat layout fallback
        audited_dir = tmp_path / "audited"
        (audited_dir / "card-a").mkdir(parents=True)
        (audited_dir / "card-a" / "tests.py").write_text(SIMPLE_TESTS)

        results = run_post_eval(run_dir, mode="impl_test", audited_dir=audited_dir)
        r = results[0]
        assert r.audited_passed == 2
        assert r.audited_total == 2

    def test_audited_lookup_set_code_preferred_over_flat(self, tmp_path: Path):
        """set_code path takes priority when both set_code and flat layouts exist."""
        run_dir = tmp_path / "run"
        cards_dir = run_dir / "cards"
        cards_dir.mkdir(parents=True)
        (run_dir / "engine").mkdir()

        _make_card(cards_dir, "099", set_code="rix")

        audited_dir = tmp_path / "audited"
        # set_code path — tests that PASS
        (audited_dir / "rix" / "099").mkdir(parents=True)
        (audited_dir / "rix" / "099" / "tests.py").write_text(SIMPLE_TESTS)
        # flat path — tests that FAIL (different impl expectation)
        (audited_dir / "099").mkdir(parents=True)
        (audited_dir / "099" / "tests.py").write_text(
            "from card_impl import add\ndef test_wrong():\n    assert add(2, 3) == 999\n"
        )

        results = run_post_eval(run_dir, mode="impl_test", audited_dir=audited_dir)
        r = results[0]
        # Should use set_code path (passing tests), not flat path (failing tests)
        assert r.audited_passed == 2
        assert r.audited_failed == 0


# ---------------------------------------------------------------------------
# Audited eval — general behavior
# ---------------------------------------------------------------------------


class TestAuditedEval:
    """Audited eval general behavior tests."""

    def test_audited_eval_skipped_when_no_matching_tests(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        audited_dir = tmp_path / "audited"
        audited_dir.mkdir()

        results = run_post_eval(run_dir, mode="impl_test", audited_dir=audited_dir)
        r = results[0]
        assert r.audited_passed == 0
        assert r.audited_total == 0

    def test_audited_eval_runs_in_blind_mode_too(self, tmp_path: Path):
        """Audited eval should run regardless of mode (only self-eval is mode-dependent)."""
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        audited_dir = tmp_path / "audited"
        (audited_dir / "card-a").mkdir(parents=True)
        (audited_dir / "card-a" / "tests.py").write_text(SIMPLE_TESTS)

        results = run_post_eval(run_dir, mode="blind", audited_dir=audited_dir)
        r = results[0]
        assert r.audited_passed == 2
        assert r.audited_total == 2

    def test_no_audited_dir_means_no_audited_eval(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        results = run_post_eval(run_dir, mode="impl_test", audited_dir=None)
        r = results[0]
        assert r.audited_passed == 0
        assert r.audited_total == 0

    def test_audited_missing_impl_reports_error_not_crash(self, tmp_path: Path):
        """Card without card_impl.py reports error for audited eval, doesn't crash."""
        run_dir = _make_run_dir(tmp_path, [], with_engine=True)
        card_dir = run_dir / "cards" / "no-impl"
        card_dir.mkdir()
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)
        # No card_impl.py

        audited_dir = tmp_path / "audited"
        (audited_dir / "no-impl").mkdir(parents=True)
        (audited_dir / "no-impl" / "tests.py").write_text(SIMPLE_TESTS)

        results = run_post_eval(run_dir, mode="blind", audited_dir=audited_dir)
        r = results[0]
        assert r.audited_passed == 0
        assert any("impl" in e.lower() or "Missing" in e for e in r.errors)


# ---------------------------------------------------------------------------
# Missing card_impl.py
# ---------------------------------------------------------------------------


class TestMissingCardImpl:
    """Card directory without card_impl.py should be handled gracefully."""

    def test_missing_impl_reports_error(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, [], with_engine=True)
        cards_dir = run_dir / "cards"
        card_dir = cards_dir / "card-no-impl"
        card_dir.mkdir()
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)
        # No card_impl.py

        results = run_post_eval(run_dir, mode="impl_test")
        r = results[0]
        assert r.self_eval_passed == 0
        assert r.self_eval_total == 0
        assert any("card_impl" in e.lower() or "Missing" in e for e in r.errors)

    def test_missing_impl_does_not_crash(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, [], with_engine=True)
        card_dir = run_dir / "cards" / "no-impl"
        card_dir.mkdir()
        # No files at all
        results = run_post_eval(run_dir, mode="impl_test")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# engine_dir parameter passed to run_tests
# ---------------------------------------------------------------------------


class TestEngineDirPassThrough:
    """Verify run_tests receives engine_dir for PYTHONPATH configuration."""

    def test_engine_dir_passed_to_run_tests(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-a"], with_engine=True)
        engine_dir = run_dir / "engine"

        with patch("silverquillm.post_eval.run_tests", return_value=(2, 0, 2, [])) as mock_rt:
            run_post_eval(run_dir, mode="impl_test")
            # Should have been called with engine_dir kwarg
            assert mock_rt.called
            _, kwargs = mock_rt.call_args
            assert kwargs.get("engine_dir") == engine_dir

    def test_engine_dir_none_when_no_engine_directory(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-a"], with_engine=False)

        with patch("silverquillm.post_eval.run_tests", return_value=(2, 0, 2, [])) as mock_rt:
            run_post_eval(run_dir, mode="impl_test")
            assert mock_rt.called
            _, kwargs = mock_rt.call_args
            assert kwargs.get("engine_dir") is None


# ---------------------------------------------------------------------------
# result.json schema — must match existing nested format
# ---------------------------------------------------------------------------


class TestResultJsonSchema:
    """Post-eval writes result.json using existing schema, compatible with consumers."""

    def test_result_json_created(self, tmp_path: Path):
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        run_post_eval(run_dir, mode="impl_test")

        result_json = run_dir / "cards" / "card-a" / "result.json"
        assert result_json.exists()

    def test_result_json_self_eval_has_passed_failed_total(self, tmp_path: Path):
        """self_eval must have passed/failed/total at the expected nesting."""
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        run_post_eval(run_dir, mode="impl_test")

        record = json.loads((run_dir / "cards" / "card-a" / "result.json").read_text())
        assert "self_eval" in record
        se = record["self_eval"]
        assert se["passed"] == 2
        assert se["failed"] == 0
        assert se["total"] == 2

    def test_result_json_audited_eval_has_passed_failed_total(self, tmp_path: Path):
        """audited_eval must have passed/failed/total at the expected nesting."""
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        audited_dir = tmp_path / "audited"
        (audited_dir / "card-a").mkdir(parents=True)
        (audited_dir / "card-a" / "tests.py").write_text(SIMPLE_TESTS)

        run_post_eval(run_dir, mode="impl_test", audited_dir=audited_dir)

        record = json.loads((run_dir / "cards" / "card-a" / "result.json").read_text())
        assert "audited_eval" in record
        ae = record["audited_eval"]
        assert ae["passed"] == 2
        assert ae["failed"] == 0
        assert ae["total"] == 2

    def test_result_json_errors_only_present_when_nonempty(self, tmp_path: Path):
        """eval_errors key should only appear if there are actual errors."""
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        run_post_eval(run_dir, mode="impl_test")

        record = json.loads((run_dir / "cards" / "card-a" / "result.json").read_text())
        # No errors expected for a passing card
        assert "eval_errors" not in record

    def test_result_json_preserves_existing_fields_on_merge(self, tmp_path: Path):
        """Post-eval merges into existing result.json, preserving prior fields."""
        run_dir = _make_run_dir(tmp_path, ["card-a"])
        result_json_path = run_dir / "cards" / "card-a" / "result.json"
        result_json_path.write_text(json.dumps({
            "card_id": "card-a",
            "status": "success",
            "agent": "test-model",
            "set_code": "neo",
            "complexity_tier": "mythic",
        }))

        run_post_eval(run_dir, mode="impl_test")

        record = json.loads(result_json_path.read_text())
        # Original fields preserved
        assert record["status"] == "success"
        assert record["agent"] == "test-model"
        assert record["set_code"] == "neo"
        assert record["complexity_tier"] == "mythic"
        # Eval fields added
        assert "self_eval" in record
        assert "audited_eval" in record

    def test_result_json_eval_errors_recorded_for_missing_impl(self, tmp_path: Path):
        """When impl is missing, eval_errors list is populated in result.json."""
        run_dir = _make_run_dir(tmp_path, [], with_engine=True)
        card_dir = run_dir / "cards" / "broken-card"
        card_dir.mkdir()
        (card_dir / "tests.py").write_text(SIMPLE_TESTS)
        # No card_impl.py

        run_post_eval(run_dir, mode="impl_test")

        record = json.loads((card_dir / "result.json").read_text())
        assert "eval_errors" in record
        assert len(record["eval_errors"]) > 0


# ---------------------------------------------------------------------------
# Consumer compatibility — save_run_summary
# ---------------------------------------------------------------------------


class TestConsumerCompatibility:
    """result.json from post-eval must be consumable by save_run_summary."""

    def test_result_json_consumable_by_save_run_summary(self, tmp_path: Path):
        """save_run_summary aggregates self_eval and audited_eval from result records.

        It reads record["self_eval"] and record["audited_eval"] — the schema
        written by _merge_result_json must be compatible.
        """
        from silverquillm.results import save_run_summary

        run_dir = _make_run_dir(tmp_path, ["card-a", "card-b"])
        audited_dir = tmp_path / "audited"
        for cid in ["card-a", "card-b"]:
            (audited_dir / cid).mkdir(parents=True)
            (audited_dir / cid / "tests.py").write_text(SIMPLE_TESTS)

        run_post_eval(run_dir, mode="impl_test", audited_dir=audited_dir)

        # Collect result.json records as save_run_summary would
        all_results = []
        for card_path in sorted((run_dir / "cards").iterdir()):
            rj = card_path / "result.json"
            if rj.exists():
                all_results.append(json.loads(rj.read_text()))

        # save_run_summary should not crash on these records
        summary_path = save_run_summary(run_dir, all_results)
        assert summary_path.exists()

        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 2


# ---------------------------------------------------------------------------
# CLI no longer runs per-card eval in the loop
# ---------------------------------------------------------------------------


class TestCliNoPerCardEval:
    """Verify cli.py run loop does not call evaluation functions inline."""

    def test_cli_imports_run_post_eval(self):
        """cli.py should import run_post_eval from post_eval module."""
        import silverquillm.cli as cli_mod
        assert hasattr(cli_mod, "run_post_eval")

    def test_run_command_uses_post_eval_not_inline_eval(self):
        """The run command body should call run_post_eval, not run_self_eval_flat.

        The eval subcommand may still use run_self_eval_flat — that's fine.
        We check the run function's source specifically.
        """
        cli_source = Path(__file__).resolve().parent.parent / "silverquillm" / "cli.py"
        source = cli_source.read_text()

        # Find the run function body (between @main.command() def run and the next @main.command())
        # Simple heuristic: look for "def run(" and verify run_post_eval is called
        assert "run_post_eval(" in source, "cli.py should call run_post_eval()"

        # Extract just the run function body to check it doesn't call run_self_eval_flat
        lines = source.split("\n")
        in_run = False
        run_body = []
        for line in lines:
            if "def run(" in line:
                in_run = True
                continue
            if in_run:
                # Next top-level function or command definition means end of run()
                if (line.startswith("@main.") or line.startswith("def ")) and run_body:
                    break
                run_body.append(line)

        run_source = "\n".join(run_body)
        assert "run_self_eval_flat(" not in run_source, (
            "run() should not call run_self_eval_flat inline — evaluation moved to post_eval"
        )
