"""Tests for TODO item 15: Per-card audited test discovery and evaluation.

Tests verify:
- run_audited_eval_per_card discovers {audited_dir}/{card_id}/tests.py.
- Returns (passed, failed, total, errors) tuple.
- Missing test file returns zeros with descriptive error.
- Missing impl returns zeros with descriptive error.
- Correct impl passes per-card audited tests.
- CLI --audited-dir option wires into per-card evaluation.
- CLI --audited-tests still works (backward compat).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.evaluator import run_audited_eval_per_card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUN_CONFIG = {
    "name": "test-run",
    "set_code": "SOS",
    "model_name": "test-agent",
    "model_provider": "test-provider",
}


def _make_audited_dir(base: Path, card_ids: list[str]) -> Path:
    """Create a per-card audited test directory structure."""
    audited_dir = base / "audited"
    audited_dir.mkdir(parents=True, exist_ok=True)
    for card_id in card_ids:
        card_test_dir = audited_dir / card_id
        card_test_dir.mkdir(parents=True, exist_ok=True)
        (card_test_dir / "__init__.py").write_text("")
        (card_test_dir / "tests.py").write_text(
            textwrap.dedent("""\
                from card_impl import solve

                def test_solve():
                    assert solve() == 42
            """)
        )
    return audited_dir


def _make_run_dir(base: Path, card_ids: list[str] | None = None) -> Path:
    """Create a run directory with config.yaml and card subdirs."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "config.yaml").write_text(yaml.dump(_RUN_CONFIG))
    cards_dir = base / "cards"
    cards_dir.mkdir(exist_ok=True)

    for card_id in (card_ids or ["001"]):
        card_dir = cards_dir / card_id
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "blind_impl.py").write_text("def solve(): return 42\n")
        (card_dir / "tested_impl.py").write_text("def solve(): return 42\n")
        (card_dir / "tests.py").write_text(
            textwrap.dedent("""\
                from card_impl import solve

                def test_solve():
                    assert solve() == 42
            """)
        )
    return base


# ---------------------------------------------------------------------------
# Unit tests: run_audited_eval_per_card
# ---------------------------------------------------------------------------


class TestRunAuditedEvalPerCard:
    """Tests for run_audited_eval_per_card function."""

    def test_correct_impl_passes(self, tmp_path):
        """Correct implementation passes per-card audited tests."""
        audited_dir = _make_audited_dir(tmp_path, ["001"])
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("def solve(): return 42\n")

        passed, failed, total, errors = run_audited_eval_per_card(
            impl_file, "001", audited_dir
        )

        assert passed >= 1
        assert failed == 0
        assert total >= 1
        assert errors == []

    def test_buggy_impl_has_failures(self, tmp_path):
        """Buggy implementation fails per-card audited tests."""
        audited_dir = _make_audited_dir(tmp_path, ["001"])
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("def solve(): return 99\n")

        passed, failed, total, errors = run_audited_eval_per_card(
            impl_file, "001", audited_dir
        )

        assert failed >= 1

    def test_missing_tests_returns_error(self, tmp_path):
        """Missing per-card test file returns zeros and an error message."""
        audited_dir = tmp_path / "audited"
        audited_dir.mkdir()
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("def solve(): return 42\n")

        passed, failed, total, errors = run_audited_eval_per_card(
            impl_file, "nonexistent", audited_dir
        )

        assert passed == 0
        assert failed == 0
        assert total == 0
        assert len(errors) == 1
        assert "No audited tests found" in errors[0]

    def test_missing_impl_returns_error(self, tmp_path):
        """Missing implementation file returns zeros and an error message."""
        audited_dir = _make_audited_dir(tmp_path, ["001"])
        impl_file = tmp_path / "missing_impl.py"  # Does not exist

        passed, failed, total, errors = run_audited_eval_per_card(
            impl_file, "001", audited_dir
        )

        assert passed == 0
        assert failed == 0
        assert total == 0
        assert len(errors) == 1
        assert "Missing implementation" in errors[0]

    def test_returns_four_tuple(self, tmp_path):
        """Return value is a 4-tuple (passed, failed, total, errors)."""
        audited_dir = _make_audited_dir(tmp_path, ["001"])
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("def solve(): return 42\n")

        result = run_audited_eval_per_card(impl_file, "001", audited_dir)

        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_set_prefixed_collector_keys(self, tmp_path):
        """Works with set-prefixed collector keys like soa_1, spg_155."""
        audited_dir = _make_audited_dir(tmp_path, ["soa_1", "spg_155"])
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("def solve(): return 42\n")

        p1, f1, t1, e1 = run_audited_eval_per_card(impl_file, "soa_1", audited_dir)
        assert p1 >= 1
        assert e1 == []

        p2, f2, t2, e2 = run_audited_eval_per_card(impl_file, "spg_155", audited_dir)
        assert p2 >= 1
        assert e2 == []

    def test_total_equals_passed_plus_failed(self, tmp_path):
        """Total always equals passed + failed."""
        audited_dir = _make_audited_dir(tmp_path, ["001"])
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("def solve(): return 42\n")

        passed, failed, total, _ = run_audited_eval_per_card(
            impl_file, "001", audited_dir
        )

        assert total == passed + failed


# ---------------------------------------------------------------------------
# CLI integration tests: --audited-dir
# ---------------------------------------------------------------------------


class TestCliAuditedDir:
    """Tests for CLI --audited-dir option."""

    def test_audited_dir_adds_audited_results(self, tmp_path):
        """--audited-dir produces audited eval results in results.json."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["001"])
        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        data = json.loads((run_dir / "results.json").read_text())
        eval_types = [r["eval_type"] for r in data]
        assert "audited" in eval_types

    def test_audited_dir_result_structure(self, tmp_path):
        """Per-card audited results have proper EvalResult fields."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["001"])
        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0
        data = json.loads((run_dir / "results.json").read_text())
        audited_entries = [r for r in data if r["eval_type"] == "audited"]
        assert len(audited_entries) >= 1
        entry = audited_entries[0]
        assert entry["card_id"] == "001"
        assert entry["agent"] == "test-agent"
        assert "blind_passed" in entry
        assert "tested_passed" in entry

    def test_audited_dir_missing_card_tests_handled(self, tmp_path):
        """Cards without per-card tests are handled gracefully (errors reported)."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["001", "002"])
        # Only create audited tests for 001, not 002
        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        data = json.loads((run_dir / "results.json").read_text())
        audited_entries = [r for r in data if r["eval_type"] == "audited"]
        # Card 002 should have errors about missing tests
        card_002_entries = [e for e in audited_entries if e["card_id"] == "002"]
        assert len(card_002_entries) >= 1
        assert any("No audited tests found" in err for err in card_002_entries[0]["errors"])

    def test_backward_compat_audited_tests_still_works(self, tmp_path):
        """--audited-tests (single file) still works for backward compat."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["card-001"])
        audited_file = tmp_path / "audited_tests.py"
        audited_file.write_text(
            textwrap.dedent("""\
                from card_impl import solve

                def test_solve_audited():
                    assert solve() == 42
            """)
        )

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self, \
             patch("silverquillm.evaluator.run_tests", return_value=(2, 0, 2, [])):
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="card-001", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-tests", str(audited_file)],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        data = json.loads((run_dir / "results.json").read_text())
        eval_types = [r["eval_type"] for r in data]
        assert "audited" in eval_types


# ---------------------------------------------------------------------------
# Additional tests: strengthen coverage for per-card audited eval
# ---------------------------------------------------------------------------


class TestRunAuditedEvalPerCardExtended:
    """Additional tests for run_audited_eval_per_card edge cases."""

    def test_conftest_is_copied_when_present(self, tmp_path):
        """conftest.py from audited_dir is copied to temp dir if present."""
        audited_dir = tmp_path / "audited"
        audited_dir.mkdir()
        card_dir = audited_dir / "001"
        card_dir.mkdir()
        # conftest provides a fixture used by tests.py
        (audited_dir / "conftest.py").write_text(
            textwrap.dedent("""\
                import pytest

                @pytest.fixture
                def magic_number():
                    return 42
            """)
        )
        (card_dir / "tests.py").write_text(
            textwrap.dedent("""\
                from card_impl import solve

                def test_with_fixture(magic_number):
                    assert solve() == magic_number
            """)
        )
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("def solve(): return 42\n")

        passed, failed, total, errors = run_audited_eval_per_card(
            impl_file, "001", audited_dir
        )
        assert passed >= 1
        assert failed == 0
        assert errors == []

    def test_timeout_returns_error(self, tmp_path):
        """Timeout in per-card eval returns zeros and timeout error."""
        audited_dir = _make_audited_dir(tmp_path, ["001"])
        impl_file = tmp_path / "impl.py"
        impl_file.write_text(
            textwrap.dedent("""\
                import time
                def solve():
                    time.sleep(120)
                    return 42
            """)
        )

        passed, failed, total, errors = run_audited_eval_per_card(
            impl_file, "001", audited_dir, timeout=2
        )

        assert passed == 0
        assert total == 0
        assert len(errors) >= 1
        assert any("timeout" in e.lower() for e in errors)

    def test_numeric_collector_keys(self, tmp_path):
        """Plain numeric collector numbers like 001, 42, 271 work."""
        for key in ["001", "42", "271"]:
            audited_dir = _make_audited_dir(tmp_path / key, [key])
            impl_file = tmp_path / f"impl_{key}.py"
            impl_file.write_text("def solve(): return 42\n")

            passed, _, _, errors = run_audited_eval_per_card(
                impl_file, key, audited_dir
            )
            assert passed >= 1, f"Failed for collector key {key}"
            assert errors == [], f"Unexpected errors for key {key}: {errors}"

    def test_does_not_crash_on_import_error_in_impl(self, tmp_path):
        """Impl with import errors should report failure, not crash."""
        audited_dir = _make_audited_dir(tmp_path, ["001"])
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("import nonexistent_module_xyz\ndef solve(): return 42\n")

        passed, failed, total, errors = run_audited_eval_per_card(
            impl_file, "001", audited_dir
        )
        # Should not raise; should report errors
        assert passed == 0


class TestRunAuditedEvalPerCardExport:
    """Verify run_audited_eval_per_card is properly exported."""

    def test_in_all(self):
        """run_audited_eval_per_card should be in evaluator's __all__."""
        import silverquillm.evaluator as mod
        assert "run_audited_eval_per_card" in mod.__all__

    def test_run_audited_eval_backward_compat_in_all(self):
        """run_audited_eval (monolithic) should still be in __all__."""
        import silverquillm.evaluator as mod
        assert "run_audited_eval" in mod.__all__


class TestCliAuditedDirExtended:
    """Extended CLI tests for --audited-dir."""

    def test_audited_dir_with_set_prefixed_card_ids(self, tmp_path):
        """CLI --audited-dir works with set-prefixed card IDs like soa_1."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["soa_1", "spg_149"])
        audited_dir = _make_audited_dir(tmp_path, ["soa_1", "spg_149"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="soa_1", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        data = json.loads((run_dir / "results.json").read_text())
        audited_entries = [r for r in data if r["eval_type"] == "audited"]
        audited_card_ids = {e["card_id"] for e in audited_entries}
        assert "soa_1" in audited_card_ids
        assert "spg_149" in audited_card_ids

    def test_missing_blind_impl_still_runs_tested(self, tmp_path):
        """Card missing blind_impl.py still gets tested_impl evaluated."""
        run_dir = tmp_path / "run1"
        run_dir.mkdir(parents=True)
        (run_dir / "config.yaml").write_text(yaml.dump(_RUN_CONFIG))
        cards_dir = run_dir / "cards"
        cards_dir.mkdir()
        card_dir = cards_dir / "001"
        card_dir.mkdir()
        # Only tested_impl, no blind_impl
        (card_dir / "tested_impl.py").write_text("def solve(): return 42\n")
        (card_dir / "tests.py").write_text("def test_x(): pass\n")

        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=0, blind_failed=0, blind_total=0,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=["Missing blind_impl"],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        data = json.loads((run_dir / "results.json").read_text())
        audited_entries = [r for r in data if r["eval_type"] == "audited"]
        assert len(audited_entries) >= 1
        entry = audited_entries[0]
        # tested_impl should have been evaluated successfully
        assert entry["tested_passed"] >= 1

    def test_missing_blind_impl_records_error_in_audited(self, tmp_path):
        """Missing blind_impl.py records 'Missing implementation' error in audited results."""
        run_dir = tmp_path / "run1"
        run_dir.mkdir(parents=True)
        (run_dir / "config.yaml").write_text(yaml.dump(_RUN_CONFIG))
        cards_dir = run_dir / "cards"
        cards_dir.mkdir()
        card_dir = cards_dir / "001"
        card_dir.mkdir()
        # Only tested_impl, no blind_impl
        (card_dir / "tested_impl.py").write_text("def solve(): return 42\n")
        (card_dir / "tests.py").write_text("def test_x(): pass\n")

        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=0, blind_failed=0, blind_total=0,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        data = json.loads((run_dir / "results.json").read_text())
        audited_entries = [r for r in data if r["eval_type"] == "audited"]
        assert len(audited_entries) >= 1
        entry = audited_entries[0]
        # The missing blind_impl should be recorded as an error
        assert any("Missing implementation" in err for err in entry["errors"]), \
            f"Expected 'Missing implementation' error, got: {entry['errors']}"


# ---------------------------------------------------------------------------
# Tests for per-card result.json audited_eval persistence (review issue #1)
# ---------------------------------------------------------------------------


class TestPerCardResultJsonPersistence:
    """Tests that audited_eval is written into each card's result.json."""

    def test_card_result_json_contains_audited_eval(self, tmp_path):
        """Per-card result.json should contain audited_eval after eval."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["001"])
        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        card_result = json.loads((run_dir / "cards" / "001" / "result.json").read_text())
        assert "audited_eval" in card_result, \
            f"result.json missing audited_eval key. Keys: {list(card_result.keys())}"

    def test_card_result_json_audited_eval_has_blind_tested_shape(self, tmp_path):
        """audited_eval in result.json has blind/tested nested sub-objects."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["001"])
        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0
        card_result = json.loads((run_dir / "cards" / "001" / "result.json").read_text())
        ae = card_result["audited_eval"]
        # Must have blind and tested sub-objects
        assert "blind" in ae, f"audited_eval missing 'blind'. Keys: {list(ae.keys())}"
        assert "tested" in ae, f"audited_eval missing 'tested'. Keys: {list(ae.keys())}"
        # Each sub-object must have passed/failed/total/errors
        for phase in ("blind", "tested"):
            for field in ("passed", "failed", "total", "errors"):
                assert field in ae[phase], \
                    f"audited_eval['{phase}'] missing '{field}'. Keys: {list(ae[phase].keys())}"

    def test_card_result_json_audited_eval_values_correct(self, tmp_path):
        """audited_eval values in result.json match actual test results."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["001"])
        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0
        card_result = json.loads((run_dir / "cards" / "001" / "result.json").read_text())
        ae = card_result["audited_eval"]
        # Both impls return 42, tests expect 42, so both phases should pass
        assert ae["blind"]["passed"] >= 1
        assert ae["blind"]["failed"] == 0
        assert ae["tested"]["passed"] >= 1
        assert ae["tested"]["failed"] == 0

    def test_card_result_json_audited_eval_has_errors_key(self, tmp_path):
        """audited_eval has a top-level 'errors' list."""
        run_dir = _make_run_dir(tmp_path / "run1", card_ids=["001"])
        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=1, blind_failed=0, blind_total=1,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0
        card_result = json.loads((run_dir / "cards" / "001" / "result.json").read_text())
        ae = card_result["audited_eval"]
        assert "errors" in ae
        assert isinstance(ae["errors"], list)

    def test_missing_impl_error_in_card_result_json(self, tmp_path):
        """Missing blind_impl records error in card's result.json audited_eval.blind."""
        run_dir = tmp_path / "run1"
        run_dir.mkdir(parents=True)
        (run_dir / "config.yaml").write_text(yaml.dump(_RUN_CONFIG))
        cards_dir = run_dir / "cards"
        cards_dir.mkdir()
        card_dir = cards_dir / "001"
        card_dir.mkdir()
        # Only tested_impl, no blind_impl
        (card_dir / "tested_impl.py").write_text("def solve(): return 42\n")
        (card_dir / "tests.py").write_text("def test_x(): pass\n")

        audited_dir = _make_audited_dir(tmp_path, ["001"])

        runner = CliRunner()
        with patch("silverquillm.evaluator.run_self_eval_flat") as mock_self:
            from silverquillm.evaluator import EvalResult
            mock_self.return_value = EvalResult(
                card_id="001", agent="test-agent", eval_type="self",
                blind_passed=0, blind_failed=0, blind_total=0,
                tested_passed=1, tested_failed=0, tested_total=1,
                errors=[],
            )
            result = runner.invoke(
                main,
                ["eval", "--results-dir", str(run_dir), "--audited-dir", str(audited_dir)],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        card_result = json.loads((card_dir / "result.json").read_text())
        assert "audited_eval" in card_result
        ae = card_result["audited_eval"]
        # blind should have error about missing implementation
        assert ae["blind"]["passed"] == 0
        assert ae["blind"]["total"] == 0
        assert any("Missing implementation" in err for err in ae["blind"]["errors"]), \
            f"Expected missing impl error in blind.errors, got: {ae['blind']['errors']}"
        # top-level errors should also contain the missing impl error
        assert any("Missing implementation" in err for err in ae["errors"])
