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
    FullEvalResult,
    _eval_engine,
    _eval_target_cards,
    evaluate_run,
    fdn_target_card_ids,
    resolve_eval_paths,
)
from silverquillm.karn.benchmark import load_benchmark
from silverquillm.karn.execution import _scores

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
        assert p.engine_support == REPO / "benchmarks/sos/workspace"

    @pytest.mark.parametrize("benchmark", ["sos", "hob-medium"])
    def test_frozen_benchmarks_grade_the_host_copy_of_their_engine_tests(
        self, benchmark: str
    ) -> None:
        root = REPO / "benchmarks" / benchmark
        p = resolve_eval_paths(root, "sos" if benchmark == "sos" else "hob")
        assert not (root / "data/tests/audited/engine").exists()
        assert p.engine_tests == root / "workspace/engine_tests"
        assert p.engine_support == root / "workspace"

    def test_smoke_resolves_fdn_target_and_oracle_test_utils(self) -> None:
        p = resolve_eval_paths(REPO / "benchmarks" / "smoke", "fdn")
        assert p.audited_target == REPO / "benchmarks/smoke/data/tests/audited/fdn"
        assert p.test_utils == REPO / "benchmarks/smoke/data/test_oracle_workspace/test_utils.py"
        assert p.engine_tests == REPO / "benchmarks/smoke/data/tests/audited/engine"


SMOKE_TARGETS = {"fdn_129", "fdn_205", "fdn_232"}


class TestFdnTargetExclusion:
    """An FDN target card is graded by card correctness only, never by FDN Card Regression."""

    def test_fdn_target_card_ids(self) -> None:
        audited = REPO / "benchmarks/smoke/data/tests/audited"
        assert fdn_target_card_ids("fdn", ["129", "205", "232"], audited) == SMOKE_TARGETS

    @pytest.mark.parametrize("name", ["hob-medium", "sos", "fra-hard"])
    def test_no_fdn_targets_elsewhere(self, name: str) -> None:
        benchmark = load_benchmark(REPO, name)
        audited = benchmark.root / "data/tests/audited"
        assert fdn_target_card_ids(benchmark.target_set, benchmark.cards, audited) == frozenset()

    def test_fdn_regression_population_excludes_smoke_targets(self) -> None:
        scores = _scores(FullEvalResult(), load_benchmark(REPO, "smoke"))
        population = set(scores["fdn_regression"]["coverage"]["population_cards"])
        assert population
        assert not population & SMOKE_TARGETS


class TestEngineSuiteResolution:
    """The engine suite is the Audited Engine Tests when present, else the staged copy."""

    def _root(self, tmp_path: Path) -> Path:
        root = tmp_path / "bench"
        (root / "workspace/engine_tests").mkdir(parents=True)
        return root

    def test_audited_engine_tests_are_selected_when_present(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        (root / "data/tests/audited/engine").mkdir(parents=True)
        (root / "data/tests/audited/engine/test_a.py").write_text("def test_a():\n    pass\n")
        p = resolve_eval_paths(root, "fdn")
        assert p.engine_tests == root / "data/tests/audited/engine"
        assert p.engine_support == root / "workspace"

    def test_staged_copy_is_the_fallback(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        p = resolve_eval_paths(root, "fdn")
        assert p.engine_tests == root / "workspace/engine_tests"
        assert p.engine_support == root / "workspace"
        assert p.engine_support == p.engine_tests.parent

    def test_empty_audited_engine_dir_is_selected_and_grades_zero(self, tmp_path: Path) -> None:
        root = self._root(tmp_path)
        (root / "data/tests/audited/engine").mkdir(parents=True)
        (root / "workspace/engine_tests/test_staged.py").write_text("def test_s():\n    pass\n")
        (root / "workspace/test_utils.py").write_text("")
        (root / "workspace/engine").mkdir()
        (root / "workspace/cards").mkdir()
        p = resolve_eval_paths(root, "fdn")
        assert p.engine_tests == root / "data/tests/audited/engine"
        result = _eval_engine(
            root / "workspace/engine", p.engine_tests, 60,
            support_dir=p.engine_support, test_utils=p.test_utils,
        )
        assert result.tests_total == 0
        assert result.test_nodes == []


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
        result = evaluate_run(run_dir, load_benchmark(REPO, "smoke"), timeout=120)
        assert set(result.sos_results) == {"fdn_129", "fdn_205", "fdn_232"}
        assert result.sos_results["fdn_129"].tests_passed >= 8
        assert result.sos_results["fdn_129"].tests_failed == 0
        assert result.sos_results["fdn_205"].tests_total > 0
        assert result.fdn_results
        assert not set(result.fdn_results) & SMOKE_TARGETS
        assert result.engine_result.tests_total > 0

    def test_missing_workspace_final_is_reported_not_crashed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "empty-run"
        run_dir.mkdir()
        result = evaluate_run(run_dir, load_benchmark(REPO, "smoke"), timeout=30)
        assert result.engine_result.errors
        assert result.sos_results == {}


@pytest.fixture(scope="module")
def honest(tmp_path_factory):
    """The unpoisoned overlay's grade, computed once for every poison."""
    grading = TestGradingIsolation()
    directory = tmp_path_factory.mktemp("honest")
    yield grading._grade(grading._overlay(directory, "none"))
    shutil.rmtree(directory, ignore_errors=True)


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
    def test_candidate_test_utils_cannot_change_scores(
        self, tmp_path: Path, poison: str, honest: dict
    ) -> None:
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
            support_dir=SMOKE_WS, test_utils=missing,
        )
        assert result.errors and any("test_utils" in e for e in result.errors)

    def test_engine_missing_support_dir_fails_visibly(self, tmp_path: Path) -> None:
        overlay = self._overlay(tmp_path, "none")
        result = _eval_engine(
            overlay / "engine", SMOKE_WS / "engine_tests", 30,
            support_dir=tmp_path / "nope",
        )
        assert result.tests_total == 0
        assert result.errors and any("support" in e for e in result.errors)
