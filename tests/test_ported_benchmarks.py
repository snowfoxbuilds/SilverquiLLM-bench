"""Platform Tests for the benchmarks ported from the Known-Best Workspace.

Each ported benchmark lists its Known Defects in a manifest, and CI checks the
two properties `docs/specs/KNOWN-BEST-ENGINE.md` requires: the unmodified
Workspace fails exactly the manifest's Audited Tests, and the Test Oracle
Workspace passes every Audited Test (see ADR-016).
"""

from __future__ import annotations

import filecmp
from pathlib import Path

import pytest

from silverquillm.karn.benchmark import load_benchmark
from silverquillm.known_defects import REGRESSION_DIMENSIONS, load_known_defects

from .known_defect_checks import oracle_problems, workspace_problems

REPO = Path(__file__).resolve().parents[1]
KNOWN_BEST = REPO / "known_best"
PORTED = ("smoke", "fra-hard", "fra-hard-v2")
_CACHES = ["__pycache__", ".pytest_cache"]


@pytest.mark.parametrize("name", PORTED)
def test_known_defect_manifest_is_valid(name: str) -> None:
    manifest = load_known_defects(REPO / "benchmarks" / name)
    assert manifest is not None
    assert manifest.benchmark == name
    assert manifest.defects
    assert all(defect.kind == "inherited" for defect in manifest.defects)


@pytest.mark.parametrize("dimension", REGRESSION_DIMENSIONS)
@pytest.mark.parametrize("name", PORTED)
def test_unmodified_workspace_fails_exactly_the_manifest(name: str, dimension: str) -> None:
    problems = workspace_problems(load_benchmark(REPO, name), dimension)
    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize("name", PORTED)
def test_oracle_passes_every_target_audited_test(name: str) -> None:
    problems = oracle_problems(load_benchmark(REPO, name), "card_correctness")
    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize("dimension", REGRESSION_DIMENSIONS)
@pytest.mark.parametrize("name", ("fra-hard", "fra-hard-v2"))
def test_fra_hard_oracle_passes_every_regression_audited_test(name: str, dimension: str) -> None:
    problems = oracle_problems(load_benchmark(REPO, name), dimension)
    assert problems == [], "\n".join(problems)


def _assert_same_tree(left: Path, right: Path) -> None:
    assert not left.is_symlink() and not right.is_symlink()
    if left.is_file():
        assert filecmp.cmp(left, right, shallow=False), f"{right} differs from {left}"
        return
    compared = filecmp.dircmp(left, right, ignore=_CACHES)
    assert not (compared.left_only or compared.right_only or compared.funny_files), (
        f"{right}: {compared.left_only} {compared.right_only} {compared.funny_files}"
    )
    _, mismatch, errors = filecmp.cmpfiles(left, right, compared.common_files, shallow=False)
    assert not (mismatch or errors), f"{right}: {mismatch} {errors}"
    for sub in compared.common_dirs:
        _assert_same_tree(left / sub, right / sub)


@pytest.mark.parametrize("name", ("smoke", "fra-hard-v2"))
def test_workspaces_carry_no_directory_summaries(name: str) -> None:
    """Per-directory summaries went stale and misled candidates (#182); the
    frozen fra-hard v1 keeps its own."""
    benchmark = REPO / "benchmarks" / name
    roots = (KNOWN_BEST / "workspace", benchmark / "workspace", benchmark / "data/test_oracle_workspace")
    found = [path for root in roots for path in root.rglob("DIRECTORY_SUMMARY.md")]
    assert not found, found


def test_smoke_oracle_is_the_known_best_workspace() -> None:
    """With identical grading inputs, `test_known_best_workspace.py` already shows
    smoke's oracle passes both regression dimensions (CI check 1)."""
    smoke = REPO / "benchmarks/smoke"
    for item in (
        "engine", "cards", "conftest.py", "pytest.ini", "test_utils.py",
        "test_interface.py", "test_interface.md", "test_test_interface.py",
    ):
        _assert_same_tree(KNOWN_BEST / "workspace" / item, smoke / "data/test_oracle_workspace" / item)
    audited = KNOWN_BEST / "data/tests/audited"
    _assert_same_tree(audited / "engine", smoke / "data/tests/audited/engine")
    for card in sorted(p for p in (audited / "fdn").iterdir() if p.is_dir() and p.name not in _CACHES):
        _assert_same_tree(card, smoke / "data/tests/audited/fdn" / card.name)
