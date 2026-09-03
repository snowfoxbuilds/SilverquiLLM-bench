"""Tests for the benchmark-parameterized Audited Eval (Contract Run path).

Pins that SOS path resolution is byte-for-byte the set of paths the legacy
``evaluate`` hardcoded (the no-behavior-change guarantee), that ``evaluate_run``
computes all three dimensions, and — the security property — that grading tests
and grading support code are host-authoritative and candidate-immutable: a
candidate cannot influence its score by tampering with its own ``test_utils``,
and missing authoritative support fails visibly rather than scoring as zero.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from silverquillm.evaluator import (
    _eval_engine,
    _eval_target_cards,
    evaluate_run,
    resolve_eval_paths,
)
from silverquillm.jobdir import load_benchmark

REPO = Path(__file__).resolve().parents[1]
SMOKE_WS = REPO / "benchmarks/smoke/workspace"
HOB = REPO / "benchmarks/hob-medium/workspace/cards/fdn"
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
        assert p.test_utils == REPO / "benchmarks/sos/data/test_oracle_workspace/test_utils.py"

    def test_smoke_resolves_fdn_target_and_workspace_test_utils(self) -> None:
        p = resolve_eval_paths(REPO / "benchmarks" / "smoke", "fdn")
        assert p.audited_target == REPO / "benchmarks/smoke/data/tests/audited/fdn"
        assert p.test_utils == REPO / "benchmarks/smoke/workspace/test_utils.py"


class TestEvaluateRun:
    def _harvest(self, tmp_path: Path, *, implement: list[str]) -> Path:
        run_dir = tmp_path / "run"
        wf = run_dir / "workspace_final"
        shutil.copytree(SMOKE_WS, wf, ignore=_IGNORE)
        for card_id in implement:
            shutil.copy2(
                HOB / card_id / "card_impl.py",
                wf / f"cards/fdn/{card_id}/card_impl.py",
            )
        return run_dir

    def test_three_dimensions_computed(self, tmp_path: Path) -> None:
        run_dir = self._harvest(tmp_path, implement=["fdn_129"])
        result = evaluate_run(run_dir, load_benchmark("smoke"), timeout=120)
        assert set(result.sos_results) == {"fdn_129", "fdn_205", "fdn_232"}
        assert result.sos_results["fdn_129"].tests_passed >= 8
        assert result.sos_results["fdn_129"].tests_failed == 0
        assert result.sos_results["fdn_205"].tests_total > 0
        assert result.fdn_results
        assert result.engine_result.tests_total > 0

    def test_missing_workspace_final_is_reported_not_crashed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "empty-run"
        run_dir.mkdir()
        result = evaluate_run(run_dir, load_benchmark("smoke"), timeout=30)
        assert result.engine_result.errors
        assert result.sos_results == {}


class TestGradingIsolation:
    """The candidate's own ``test_utils`` never influences the score."""

    _AUTHORITATIVE = SMOKE_WS / "test_utils.py"
    _AUDITED = REPO / "benchmarks/smoke/data/tests/audited/fdn"
    # fdn_129 is implemented (green); fdn_205 stays a stub (fails) — a broken
    # isolation would let an always-pass test_utils flip fdn_205 to green.
    _CARDS = ("129", "205")

    def _overlay(self, tmp_path: Path, poison: str) -> Path:
        overlay = tmp_path / "overlay"
        shutil.copytree(SMOKE_WS, overlay, ignore=_IGNORE)
        shutil.copy2(HOB / "fdn_129" / "card_impl.py", overlay / "cards/fdn/fdn_129/card_impl.py")
        tu = overlay / "test_utils.py"
        if poison == "always-pass":
            tu.write_text(
                "def __getattr__(name):\n"
                "    def _any(*a, **k):\n        return True\n"
                "    return _any\n"
            )
        elif poison == "delete":
            tu.unlink()
        elif poison == "corrupt":
            tu.write_text("this is not valid python !!!\n")
        return overlay

    def _grade(self, overlay: Path) -> dict:
        return _eval_target_cards(
            overlay, "fdn", list(self._CARDS), self._AUDITED, 120,
            test_utils=self._AUTHORITATIVE,
        )

    @pytest.mark.parametrize("poison", ["always-pass", "delete", "corrupt"])
    def test_candidate_test_utils_cannot_change_scores(self, tmp_path: Path, poison: str) -> None:
        honest = self._grade(self._overlay(tmp_path / "honest", "none"))
        tampered = self._grade(self._overlay(tmp_path / poison, poison))
        # The stub target still fails under every poison; the green target stays green.
        assert honest["fdn_205"].tests_failed > 0
        for card in ("fdn_129", "fdn_205"):
            assert tampered[card].tests_passed == honest[card].tests_passed
            assert tampered[card].tests_failed == honest[card].tests_failed

    def test_missing_authoritative_support_fails_visibly(self, tmp_path: Path) -> None:
        overlay = self._overlay(tmp_path, "none")
        missing = tmp_path / "nope" / "test_utils.py"
        cards = _eval_target_cards(overlay, "fdn", ["129"], self._AUDITED, 120, test_utils=missing)
        assert cards["fdn_129"].skipped
        assert any("test_utils" in e for e in cards["fdn_129"].errors)

    def test_engine_missing_authoritative_support_fails_visibly(self, tmp_path: Path) -> None:
        overlay = self._overlay(tmp_path, "none")
        missing = tmp_path / "nope" / "test_utils.py"
        result = _eval_engine(
            overlay / "engine", SMOKE_WS.parent / "workspace/engine_tests", 30,
            test_utils=missing,
        )
        assert result.errors and any("test_utils" in e for e in result.errors)
