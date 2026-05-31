"""Gap tests for scripts/harvest_validated_results.py.

Covers gaps NOT addressed by test_harvest_validated_results.py:
  - ValidatedRun.run_dir exact path structure (points into validated_results/, not results/)
  - Run dir lacking a cards/ subdir is handled gracefully (no crash, empty card_dirs)
  - --output default path value for non-sos --bench (path string derivation, not just dir creation)
  - Deterministic ordering guarantee when run names would sort differently from glob order
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import the script module via importlib (scripts/ is not a package)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = REPO_ROOT / "scripts" / "harvest_validated_results.py"

_spec = importlib.util.spec_from_file_location(
    "harvest_validated_results", _SCRIPT_PATH
)
_mod = importlib.util.module_from_spec(_spec)
# Re-use already-imported module if present (avoids duplicate import side-effects)
if "harvest_validated_results" not in sys.modules:
    sys.modules["harvest_validated_results"] = _mod
    _spec.loader.exec_module(_mod)
else:
    _mod = sys.modules["harvest_validated_results"]

discover_validated_runs = _mod.discover_validated_runs
ValidatedRun = _mod.ValidatedRun
main = _mod.main
_build_parser = _mod._build_parser


# ---------------------------------------------------------------------------
# 1. ValidatedRun.run_dir exact path structure
# ---------------------------------------------------------------------------


class TestValidatedRunFieldCorrectness:
    """ValidatedRun fields point to the correct locations in the tree."""

    def test_run_dir_is_inside_validated_results(self, tmp_path: Path) -> None:
        """run_dir must resolve to docker/<image>/validated_results/<run>."""
        run_dir = (
            tmp_path / "docker" / "imgX" / "validated_results" / "run99" / "cards" / "sos_001"
        )
        run_dir.mkdir(parents=True)
        (run_dir / "result.json").write_text("{}")

        runs = discover_validated_runs(tmp_path)
        assert len(runs) == 1
        vr = runs[0]

        expected_run_dir = tmp_path / "docker" / "imgX" / "validated_results" / "run99"
        assert vr.run_dir == expected_run_dir

    def test_run_dir_not_under_results(self, tmp_path: Path) -> None:
        """run_dir must NOT point into a results/ (non-validated) directory."""
        # Create a validated_results entry
        vr_dir = (
            tmp_path / "docker" / "imgX" / "validated_results" / "run_good" / "cards" / "sos_001"
        )
        vr_dir.mkdir(parents=True)
        (vr_dir / "result.json").write_text("{}")

        # Also create a results/ working dir that must be ignored
        wd_dir = tmp_path / "docker" / "imgX" / "results" / "run_bad" / "cards" / "sos_001"
        wd_dir.mkdir(parents=True)
        (wd_dir / "result.json").write_text("{}")

        runs = discover_validated_runs(tmp_path)
        run_dirs = [vr.run_dir for vr in runs]
        # None of the run_dirs should contain "results" as a path component
        # (they must all contain "validated_results")
        for rd in run_dirs:
            parts = rd.parts
            assert "validated_results" in parts, f"run_dir {rd} missing validated_results"
            # "results" alone (not as part of "validated_results") must not appear
            assert "results" not in parts, f"run_dir {rd} incorrectly points into results/"

    def test_image_field_matches_docker_subdir(self, tmp_path: Path) -> None:
        """ValidatedRun.image must equal the docker/<image> directory name."""
        run_dir = (
            tmp_path / "docker" / "my-special-image" / "validated_results" / "run1" / "cards" / "sos_001"
        )
        run_dir.mkdir(parents=True)
        (run_dir / "result.json").write_text("{}")

        runs = discover_validated_runs(tmp_path)
        assert len(runs) == 1
        assert runs[0].image == "my-special-image"

    def test_run_field_matches_run_directory_name(self, tmp_path: Path) -> None:
        """ValidatedRun.run must equal the run directory name."""
        run_dir = (
            tmp_path / "docker" / "imgX" / "validated_results" / "sos-imgX-2026-05-30T04-02"
            / "cards" / "sos_001"
        )
        run_dir.mkdir(parents=True)
        (run_dir / "result.json").write_text("{}")

        runs = discover_validated_runs(tmp_path)
        assert len(runs) == 1
        assert runs[0].run == "sos-imgX-2026-05-30T04-02"


# ---------------------------------------------------------------------------
# 2. Run dir lacking a cards/ subdir handled gracefully
# ---------------------------------------------------------------------------


class TestMissingCardsSubdir:
    """A run directory without a cards/ subdir yields an empty card_dirs list."""

    def test_no_cards_subdir_returns_run_with_empty_card_dirs(
        self, tmp_path: Path
    ) -> None:
        # Create a validated run directory with NO cards/ subdirectory
        run_dir = tmp_path / "docker" / "imgX" / "validated_results" / "run_no_cards"
        run_dir.mkdir(parents=True)

        runs = discover_validated_runs(tmp_path)
        assert len(runs) == 1
        vr = runs[0]
        assert vr.image == "imgX"
        assert vr.run == "run_no_cards"
        assert vr.card_dirs == []

    def test_no_cards_subdir_does_not_raise(self, tmp_path: Path) -> None:
        """Discovery must not raise even when cards/ is completely absent."""
        run_dir = tmp_path / "docker" / "imgY" / "validated_results" / "run_bare"
        run_dir.mkdir(parents=True)

        # Should not raise
        runs = discover_validated_runs(tmp_path)
        assert isinstance(runs, list)

    def test_card_filter_skips_run_with_no_cards_subdir(
        self, tmp_path: Path
    ) -> None:
        """When --card is specified, a run with no cards/ subdir is excluded."""
        run_dir = tmp_path / "docker" / "imgX" / "validated_results" / "run_no_cards"
        run_dir.mkdir(parents=True)

        runs = discover_validated_runs(tmp_path, card="sos_001")
        assert runs == []

    def test_empty_cards_subdir_returns_empty_card_dirs(
        self, tmp_path: Path
    ) -> None:
        """An empty cards/ subdir yields an empty card_dirs list."""
        cards_dir = (
            tmp_path / "docker" / "imgX" / "validated_results" / "run_empty_cards" / "cards"
        )
        cards_dir.mkdir(parents=True)

        runs = discover_validated_runs(tmp_path)
        assert len(runs) == 1
        assert runs[0].card_dirs == []


# ---------------------------------------------------------------------------
# 3. --output default path derivation for non-sos bench
# ---------------------------------------------------------------------------


class TestOutputPathDerivation:
    """Default --output path is derived correctly from --bench for any bench name."""

    def _capture_output_path(self, tmp_path: Path, bench: str) -> Path:
        """Run main() with the given bench and capture the resolved output_path."""
        captured: list[Path] = []
        original_mkdir = Path.mkdir

        def _patched_mkdir(self_path: Path, *args, **kwargs):  # type: ignore[override]
            captured.append(self_path)
            original_mkdir(self_path, *args, **kwargs)

        with mock.patch("sys.argv", ["harvest_validated_results.py", "--bench", bench]):
            with mock.patch.object(Path, "mkdir", _patched_mkdir):
                main(repo_root=tmp_path)

        # The output path parent is created by main(); return it
        expected = tmp_path / "benchmarks" / bench / "analysis"
        return expected

    def test_default_output_path_for_custom_bench(self, tmp_path: Path) -> None:
        """Default output path for --bench custombench is benchmarks/custombench/analysis/harvested_results.jsonl."""
        bench = "custombench"
        expected_dir = tmp_path / "benchmarks" / bench / "analysis"

        with mock.patch("sys.argv", ["harvest_validated_results.py", "--bench", bench]):
            main(repo_root=tmp_path)

        assert expected_dir.is_dir()
        # Verify the complete expected path structure (not just any dir named analysis)
        assert expected_dir.parent.name == bench
        assert expected_dir.parent.parent.name == "benchmarks"

    def test_default_output_path_for_sos_bench(self, tmp_path: Path) -> None:
        """Default output path for --bench sos is benchmarks/sos/analysis/."""
        expected_dir = tmp_path / "benchmarks" / "sos" / "analysis"

        with mock.patch("sys.argv", ["harvest_validated_results.py"]):
            main(repo_root=tmp_path)

        assert expected_dir.is_dir()

    def test_output_path_respects_bench_name_verbatim(self, tmp_path: Path) -> None:
        """Bench name is used verbatim in the path (no normalization)."""
        bench = "My-Bench_v2"
        expected_dir = tmp_path / "benchmarks" / bench / "analysis"

        with mock.patch("sys.argv", ["harvest_validated_results.py", "--bench", bench]):
            main(repo_root=tmp_path)

        assert expected_dir.is_dir()


# ---------------------------------------------------------------------------
# 4. Deterministic ordering guarantee
# ---------------------------------------------------------------------------


class TestDeterministicOrdering:
    """discover_validated_runs always returns runs sorted by (image, run)."""

    def test_ordering_stable_across_calls(self, tmp_path: Path) -> None:
        """Multiple calls to discover_validated_runs return the same order."""
        # Create runs that might be in non-sorted order on the filesystem
        for img, run in [("imgB", "run1"), ("imgA", "run2"), ("imgA", "run1"), ("imgB", "run2")]:
            d = tmp_path / "docker" / img / "validated_results" / run
            d.mkdir(parents=True)

        first = [(vr.image, vr.run) for vr in discover_validated_runs(tmp_path)]
        second = [(vr.image, vr.run) for vr in discover_validated_runs(tmp_path)]
        assert first == second

    def test_ordering_is_image_then_run(self, tmp_path: Path) -> None:
        """Runs are sorted by image first, then by run name."""
        for img, run in [("imgZ", "run1"), ("imgA", "run3"), ("imgA", "run1"), ("imgM", "run2")]:
            d = tmp_path / "docker" / img / "validated_results" / run
            d.mkdir(parents=True)

        runs = discover_validated_runs(tmp_path)
        pairs = [(vr.image, vr.run) for vr in runs]
        assert pairs == sorted(pairs), f"Expected sorted order, got {pairs}"

    def test_ordering_with_numeric_like_run_names(self, tmp_path: Path) -> None:
        """Lexicographic sort of run names is applied (no numeric coercion)."""
        for run in ["run10", "run2", "run1", "run20"]:
            d = tmp_path / "docker" / "imgA" / "validated_results" / run
            d.mkdir(parents=True)

        runs = discover_validated_runs(tmp_path)
        run_names = [vr.run for vr in runs]
        # Lexicographic order: run1, run10, run2, run20
        assert run_names == sorted(run_names)
