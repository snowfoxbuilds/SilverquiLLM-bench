"""Tests for scripts/harvest_validated_results.py — discovery + CLI + output path.

Validates the ``discover_validated_runs()`` function discovers the correct
``(image, run)`` pairs from a fixture tree, that CLI filters (``--image``,
``--run``, ``--card``) narrow the results as expected, and that ``main()``
creates the analysis output directory.
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
sys.modules["harvest_validated_results"] = _mod  # needed for @dataclass introspection
_spec.loader.exec_module(_mod)

discover_validated_runs = _mod.discover_validated_runs
ValidatedRun = _mod.ValidatedRun
main = _mod.main
_build_parser = _mod._build_parser


# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------


def _build_fixture_tree(root: Path) -> None:
    """Build a multi-image, multi-run fixture tree under *root*.

    Layout::

        docker/
            imgA/
                validated_results/
                    run1/
                        cards/
                            sos_001/result.json
                            sos_002/result.json
                    run2/
                        cards/
                            sos_003/result.json
            imgB/
                validated_results/
                    run3/
                        cards/
                            sos_001/result.json
                            sos_004/result.json
            imgC/
                results/          # <-- working dir, NOT validated_results
                    run4/
                        cards/
                            sos_005/result.json
    """
    # imgA / run1
    for card in ("sos_001", "sos_002"):
        d = root / "docker" / "imgA" / "validated_results" / "run1" / "cards" / card
        d.mkdir(parents=True, exist_ok=True)
        (d / "result.json").write_text("{}")

    # imgA / run2
    d = root / "docker" / "imgA" / "validated_results" / "run2" / "cards" / "sos_003"
    d.mkdir(parents=True, exist_ok=True)
    (d / "result.json").write_text("{}")

    # imgB / run3
    for card in ("sos_001", "sos_004"):
        d = root / "docker" / "imgB" / "validated_results" / "run3" / "cards" / card
        d.mkdir(parents=True, exist_ok=True)
        (d / "result.json").write_text("{}")

    # imgC — a results/ working dir (should NOT be discovered)
    d = root / "docker" / "imgC" / "results" / "run4" / "cards" / "sos_005"
    d.mkdir(parents=True, exist_ok=True)
    (d / "result.json").write_text("{}")


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """Return a tmp_path populated with the fixture tree."""
    _build_fixture_tree(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Full discovery — no filters
# ---------------------------------------------------------------------------


class TestDiscoveryNoFilters:
    """discover_validated_runs with no filters returns all validated runs."""

    def test_returns_expected_image_run_pairs(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root)
        pairs = [(vr.image, vr.run) for vr in runs]
        assert ("imgA", "run1") in pairs
        assert ("imgA", "run2") in pairs
        assert ("imgB", "run3") in pairs

    def test_does_not_include_results_working_dir(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root)
        pairs = [(vr.image, vr.run) for vr in runs]
        assert ("imgC", "run4") not in pairs

    def test_total_count(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root)
        assert len(runs) == 3

    def test_card_dirs_populated(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root)
        by_key = {(vr.image, vr.run): vr for vr in runs}
        # imgA/run1 has 2 cards
        assert len(by_key[("imgA", "run1")].card_dirs) == 2
        # imgA/run2 has 1 card
        assert len(by_key[("imgA", "run2")].card_dirs) == 1
        # imgB/run3 has 2 cards
        assert len(by_key[("imgB", "run3")].card_dirs) == 2

    def test_run_dir_paths_are_correct(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root)
        for vr in runs:
            assert vr.run_dir.is_dir()
            assert "validated_results" in str(vr.run_dir)

    def test_results_sorted_by_image_run(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root)
        pairs = [(vr.image, vr.run) for vr in runs]
        assert pairs == sorted(pairs)


# ---------------------------------------------------------------------------
# 2. --image filter
# ---------------------------------------------------------------------------


class TestImageFilter:
    """--image filter narrows to only the specified image's runs."""

    def test_image_filter_narrows_to_single_image(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root, image="imgA")
        images = {vr.image for vr in runs}
        assert images == {"imgA"}
        assert len(runs) == 2  # run1 and run2

    def test_image_filter_nonexistent_returns_empty(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root, image="nonexistent")
        assert runs == []


# ---------------------------------------------------------------------------
# 3. --run filter
# ---------------------------------------------------------------------------


class TestRunFilter:
    """--run filter narrows to only the matching run name."""

    def test_run_filter_narrows_to_single_run(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root, run="run1")
        assert len(runs) == 1
        assert runs[0].image == "imgA"
        assert runs[0].run == "run1"

    def test_run_filter_nonexistent_returns_empty(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root, run="run_missing")
        assert runs == []


# ---------------------------------------------------------------------------
# 4. --card filter
# ---------------------------------------------------------------------------


class TestCardFilter:
    """--card filter narrows to runs containing a matching card dir."""

    def test_card_filter_narrows_to_matching_runs(self, fixture_root: Path) -> None:
        # sos_001 exists in imgA/run1 and imgB/run3, but NOT imgA/run2
        runs = discover_validated_runs(fixture_root, card="sos_001")
        pairs = [(vr.image, vr.run) for vr in runs]
        assert ("imgA", "run1") in pairs
        assert ("imgB", "run3") in pairs
        assert ("imgA", "run2") not in pairs

    def test_card_filter_card_dirs_only_matching(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root, card="sos_001")
        for vr in runs:
            card_names = [cd.name for cd in vr.card_dirs]
            assert card_names == ["sos_001"]

    def test_card_filter_unique_card(self, fixture_root: Path) -> None:
        # sos_004 only in imgB/run3
        runs = discover_validated_runs(fixture_root, card="sos_004")
        assert len(runs) == 1
        assert runs[0].image == "imgB"
        assert runs[0].run == "run3"

    def test_card_filter_nonexistent_returns_empty(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root, card="sos_999")
        assert runs == []


# ---------------------------------------------------------------------------
# 5. Composed filters (image + card)
# ---------------------------------------------------------------------------


class TestComposedFilters:
    """Multiple filters compose conjunctively."""

    def test_image_plus_card(self, fixture_root: Path) -> None:
        # sos_001 is in imgA/run1 and imgB/run3; restricting to imgA
        runs = discover_validated_runs(fixture_root, image="imgA", card="sos_001")
        assert len(runs) == 1
        assert runs[0].image == "imgA"
        assert runs[0].run == "run1"
        assert [cd.name for cd in runs[0].card_dirs] == ["sos_001"]

    def test_image_plus_run(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root, image="imgA", run="run2")
        assert len(runs) == 1
        assert runs[0].run == "run2"

    def test_all_three_filters(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(
            fixture_root, image="imgA", run="run1", card="sos_001"
        )
        assert len(runs) == 1
        assert runs[0].image == "imgA"
        assert runs[0].run == "run1"
        assert [cd.name for cd in runs[0].card_dirs] == ["sos_001"]

    def test_conflicting_filters_return_empty(self, fixture_root: Path) -> None:
        # imgB has no run1
        runs = discover_validated_runs(fixture_root, image="imgB", run="run1")
        assert runs == []


# ---------------------------------------------------------------------------
# 6. results/ working dir is NOT discovered
# ---------------------------------------------------------------------------


class TestResultsDirIgnored:
    """docker/<img>/results/<run>/ must NOT be discovered."""

    def test_results_dir_excluded(self, fixture_root: Path) -> None:
        runs = discover_validated_runs(fixture_root)
        all_images = {vr.image for vr in runs}
        # imgC only has results/ (not validated_results/), so must be absent
        assert "imgC" not in all_images

    def test_results_dir_excluded_even_with_image_filter(
        self, fixture_root: Path
    ) -> None:
        runs = discover_validated_runs(fixture_root, image="imgC")
        assert runs == []


# ---------------------------------------------------------------------------
# 7. CLI / main() creates analysis directory
# ---------------------------------------------------------------------------


class TestMainCLI:
    """main() creates the analysis output directory and does not crash."""

    def test_main_creates_analysis_dir(self, fixture_root: Path) -> None:
        analysis_dir = fixture_root / "benchmarks" / "sos" / "analysis"
        assert not analysis_dir.exists()

        # Patch sys.argv to avoid picking up pytest's own arguments
        with mock.patch("sys.argv", ["harvest_validated_results.py"]):
            main(repo_root=fixture_root)

        assert analysis_dir.is_dir()

    def test_main_creates_analysis_dir_custom_bench(
        self, fixture_root: Path
    ) -> None:
        analysis_dir = fixture_root / "benchmarks" / "mybench" / "analysis"
        assert not analysis_dir.exists()

        with mock.patch(
            "sys.argv", ["harvest_validated_results.py", "--bench", "mybench"]
        ):
            main(repo_root=fixture_root)

        assert analysis_dir.is_dir()

    def test_main_with_custom_output(self, fixture_root: Path) -> None:
        out_path = fixture_root / "custom" / "output.jsonl"
        assert not out_path.parent.exists()

        with mock.patch(
            "sys.argv",
            ["harvest_validated_results.py", "--output", str(out_path)],
        ):
            main(repo_root=fixture_root)

        assert out_path.parent.is_dir()

    def test_main_does_not_crash_with_filters(self, fixture_root: Path) -> None:
        with mock.patch(
            "sys.argv",
            [
                "harvest_validated_results.py",
                "--image",
                "imgA",
                "--run",
                "run1",
                "--card",
                "sos_001",
            ],
        ):
            # Should complete without raising
            main(repo_root=fixture_root)


# ---------------------------------------------------------------------------
# 8. Edge: empty / missing docker/ tree
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Discovery with empty or missing docker/ tree returns empty list."""

    def test_missing_docker_dir(self, tmp_path: Path) -> None:
        # tmp_path has no docker/ subdirectory
        runs = discover_validated_runs(tmp_path)
        assert runs == []

    def test_empty_docker_dir(self, tmp_path: Path) -> None:
        (tmp_path / "docker").mkdir()
        runs = discover_validated_runs(tmp_path)
        assert runs == []

    def test_docker_dir_with_no_validated_results(self, tmp_path: Path) -> None:
        (tmp_path / "docker" / "someimage").mkdir(parents=True)
        runs = discover_validated_runs(tmp_path)
        assert runs == []


# ---------------------------------------------------------------------------
# Parser structure
# ---------------------------------------------------------------------------


class TestParser:
    """_build_parser returns a parser with the expected flags."""

    def test_parser_defaults(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.bench == "sos"
        assert args.output is None
        assert args.image is None
        assert args.run is None
        assert args.card is None

    def test_parser_accepts_all_flags(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([
            "--bench", "mybench",
            "--output", "/tmp/out.jsonl",
            "--image", "img1",
            "--run", "run1",
            "--card", "sos_001",
        ])
        assert args.bench == "mybench"
        assert args.output == "/tmp/out.jsonl"
        assert args.image == "img1"
        assert args.run == "run1"
        assert args.card == "sos_001"
