"""The Known-Best Workspace passes every regression Audited Test (KNOWN-BEST-ENGINE.md).

Each suite is graded through the same functions that grade a benchmark, against
a throwaway copy of ``known_best/workspace``. The Audited Engine Tests are never
run in place: their directory is named ``engine`` and would shadow the engine
package, so ``_eval_engine`` stages them as ``engine_tests/``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from silverquillm.evaluator import (
    _BENCHMARK_DATA_ROOT,
    _GRADING_IGNORE,
    _eval_engine,
    _grade_audited_card,
    resolve_eval_paths,
)

REPO = Path(__file__).resolve().parents[1]
KNOWN_BEST = REPO / "known_best"
PATHS = resolve_eval_paths(KNOWN_BEST, "fdn")
FDN_CARDS = sorted(path.parent.name for path in PATHS.audited_fdn.glob("*/tests.py"))


@pytest.fixture(scope="module")
def overlay(tmp_path_factory):
    workspace = tmp_path_factory.mktemp("known_best") / "workspace"
    shutil.copytree(KNOWN_BEST / "workspace", workspace, ignore=_GRADING_IGNORE)
    # A benchmark's data root is two levels up from it; known_best/ is top level.
    token = _BENCHMARK_DATA_ROOT.set(REPO)
    try:
        yield workspace
    finally:
        _BENCHMARK_DATA_ROOT.reset(token)


def _failing(nodes: list[dict]) -> list[str]:
    return [node["test_node"] for node in nodes if node["outcome"] != "pass"]


def test_layout():
    for relative in (
        "workspace/engine",
        "workspace/cards/__init__.py",
        "workspace/cards/loader.py",
        "workspace/cards/registry.py",
        "workspace/cards/py.typed",
        "workspace/cards/fdn",
        "workspace/conftest.py",
        "workspace/pytest.ini",
        "workspace/test_utils.py",
        "data/tests/audited/fdn",
        "data/tests/audited/engine",
    ):
        assert (KNOWN_BEST / relative).exists(), relative
    for relative in (
        "config.json",
        "workspace/cards/hob",
        "workspace/engine_tests",
        "data/test_oracle_workspace",
    ):
        assert not (KNOWN_BEST / relative).exists(), relative
    assert not [path for path in KNOWN_BEST.rglob("*") if path.is_symlink()]
    assert PATHS.engine_tests == KNOWN_BEST / "data/tests/audited/engine"
    assert PATHS.engine_support == KNOWN_BEST / "workspace"
    assert PATHS.test_utils == KNOWN_BEST / "workspace/test_utils.py"
    assert len(FDN_CARDS) > 0


@pytest.mark.parametrize("card_id", FDN_CARDS)
def test_fdn_audited_tests_pass_on_known_best(overlay, card_id):
    result = _grade_audited_card(
        card_id, PATHS.audited_fdn / card_id / "tests.py", overlay, 120,
        test_utils=PATHS.test_utils, card_set="fdn",
    )
    failing = _failing(result.test_nodes)
    assert result.tests_total > 0, result.errors
    assert result.tests_failed == 0, failing
    assert all(error.startswith("FAILED ") for error in result.errors), result.errors
    assert not failing, failing


def test_audited_engine_tests_pass_on_known_best(overlay):
    result = _eval_engine(
        overlay / "engine", PATHS.engine_tests, timeout=240,
        support_dir=PATHS.engine_support, test_utils=PATHS.test_utils,
    )
    failing = _failing(result.test_nodes)
    assert result.tests_total > 0, result.errors
    assert result.tests_failed == 0, failing
    assert result.errors == [], result.errors
    assert result.test_nodes and not failing, failing
