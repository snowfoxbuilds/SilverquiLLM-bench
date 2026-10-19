"""Platform Tests for the benchmarks ported from the Known-Best Workspace.

Each ported benchmark lists its Known Defects in a manifest, and CI checks the
properties `docs/specs/KNOWN-BEST-ENGINE.md` requires: the unmodified Workspace
fails exactly the manifest's Audited Tests, the Test Oracle Workspace passes
every Audited Test (see ADR-016), and putting each Known Defect back into the
Test Oracle Workspace fails exactly the target-card tests its entry lists.
"""

from __future__ import annotations

import filecmp
from pathlib import Path

import pytest

from silverquillm.benchmark_targets import target_cards
from silverquillm.karn.benchmark import load_benchmark
from silverquillm.known_defects import SUITES, load_known_defects

from .known_defect_checks import defect_problems, oracle_problems, workspace_problems

REPO = Path(__file__).resolve().parents[1]
KNOWN_BEST = REPO / "known_best"
PORTED = ("smoke", "fra-hard", "fra-hard-v2")
SCHEMA_2 = ("smoke", "fra-hard-v2")
"""Ported benchmarks on manifest schema version 2; the frozen fra-hard v1 keeps version 1."""
_CACHES = ["__pycache__", ".pytest_cache"]


@pytest.mark.parametrize("name", PORTED)
def test_known_defect_manifest_is_valid(name: str) -> None:
    manifest = load_known_defects(REPO / "benchmarks" / name)
    assert manifest is not None
    assert manifest.benchmark == name
    assert manifest.defects
    assert all(defect.kind == "inherited" for defect in manifest.defects)
    assert manifest.schema_version == (2 if name in SCHEMA_2 else 1)


@pytest.mark.parametrize("name", SCHEMA_2)
def test_target_tests_and_host_cards_name_real_cards(name: str) -> None:
    """``target_tests`` are target-card tests, and a related defect's host card is a base
    Workspace card other than a target, or the target holding all of them
    (KNOWN-BEST-ENGINE.md → Manifest)."""
    benchmark = load_benchmark(REPO, name)
    targets = {f"{code}_{number}" for code, number in target_cards(benchmark.target_set, benchmark.cards)}
    cards = {path.name for path in (benchmark.root / "workspace/cards").glob("*/*") if path.is_dir()}
    for defect in load_known_defects(benchmark.root).defects:
        assert {node.split("/", 1)[0] for node in defect.target_tests} <= targets, defect.id
        if defect.hosted_on_target:
            assert defect.host_card in targets, defect.id
        elif defect.related:
            assert defect.host_card in cards - targets, defect.id


def _defects(names):
    return [
        (name, defect.id)
        for name in names
        for defect in load_known_defects(REPO / "benchmarks" / name).defects
    ]


@pytest.mark.parametrize(("name", "defect_id"), _defects(SCHEMA_2))
def test_each_known_defect_put_back_fails_exactly_its_target_tests(
    name: str, defect_id: str, tmp_path: Path
) -> None:
    problems = defect_problems(load_benchmark(REPO, name), defect_id, tmp_path)
    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize("suite", SUITES)
@pytest.mark.parametrize("name", PORTED)
def test_unmodified_workspace_fails_exactly_the_manifest(name: str, suite: str) -> None:
    problems = workspace_problems(load_benchmark(REPO, name), suite)
    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize("name", PORTED)
def test_oracle_passes_every_target_audited_test(name: str) -> None:
    problems = oracle_problems(load_benchmark(REPO, name), "target")
    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize("suite", SUITES)
@pytest.mark.parametrize("name", ("fra-hard", "fra-hard-v2"))
def test_fra_hard_oracle_passes_every_fdn_and_engine_audited_test(name: str, suite: str) -> None:
    problems = oracle_problems(load_benchmark(REPO, name), suite)
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


@pytest.mark.parametrize("name", ("smoke", "fra-hard-v2"))
def test_workspaces_carry_the_known_best_rulebook(name: str) -> None:
    """Every ported Workspace and Test Oracle Workspace stages Known-Best's
    Comprehensive Rules byte for byte, so no benchmark falls behind a rules
    update (#190); the frozen fra-hard v1 keeps its own."""
    rulebook = (KNOWN_BEST / "workspace/RULEBOOK.txt").read_bytes()
    assert rulebook.startswith(b"Magic: The Gathering Comprehensive Rules\n")
    benchmark = REPO / "benchmarks" / name
    for root in (benchmark / "workspace", benchmark / "data/test_oracle_workspace"):
        assert (root / "RULEBOOK.txt").read_bytes() == rulebook, root


def test_smoke_oracle_is_the_known_best_workspace() -> None:
    """With identical grading inputs, `test_known_best_workspace.py` already shows
    smoke's oracle passes the FDN and engine suites (CI check 1)."""
    smoke = REPO / "benchmarks/smoke"
    for item in (
        "engine", "cards", "conftest.py", "pytest.ini", "test_utils.py",
        "test_interface.py", "test_interface.md", "test_test_interface.py", "RULEBOOK.txt",
    ):
        _assert_same_tree(KNOWN_BEST / "workspace" / item, smoke / "data/test_oracle_workspace" / item)
    audited = KNOWN_BEST / "data/tests/audited"
    _assert_same_tree(audited / "engine", smoke / "data/tests/audited/engine")
    for card in sorted(p for p in (audited / "fdn").iterdir() if p.is_dir() and p.name not in _CACHES):
        _assert_same_tree(card, smoke / "data/tests/audited/fdn" / card.name)
