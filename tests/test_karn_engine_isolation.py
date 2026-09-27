"""Engine grading observes selected code without importing candidate test support."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.evaluator import _BENCHMARK_DATA_ROOT, _eval_engine


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


def _packages(workspace: Path, engine_value: str, card_value: str) -> None:
    _write(workspace / "engine/__init__.py", "")
    _write(workspace / "engine/rules.py", f"VALUE = {engine_value!r}\n")
    _write(workspace / "cards/__init__.py", "")
    _write(workspace / "cards/sample.py", f"VALUE = {card_value!r}\n")


@pytest.fixture
def grading_trees(tmp_path, monkeypatch):
    root = tmp_path / "host"
    host = root / "benchmarks/example/workspace"
    candidate = tmp_path / "candidate"
    _packages(host, "host engine must not be used", "host card must not be used")
    _packages(candidate, "candidate engine", "candidate card")
    _write(host / "test_utils.py", "MARKER = 'authoritative helper'\n")
    _write(host / "engine_tests/__init__.py", "")
    _write(host / "engine_tests/support.py", "MARKER = 'authoritative support'\n")
    _write(
        host / "conftest.py",
        """
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

@pytest.fixture
def authoritative_fixture():
    return "authoritative fixture"
""",
    )
    _write(host / "pytest.ini", "[pytest]\naddopts = --import-mode=importlib\n")
    _write(
        host / "engine_tests/test_grading.py",
        """
import json
from pathlib import Path

from cards import sample
from engine import rules
from engine_tests.support import MARKER
from test_utils import MARKER as HELPER
from silverquillm.replay.parser import load_card_id_map


def test_selected_engine():
    assert rules.VALUE == "candidate engine"


def test_selected_card_and_relative_source():
    workspace = Path(__file__).resolve().parents[1]
    assert sample.VALUE == "candidate card"
    assert Path(sample.__file__).resolve() == workspace / "cards/sample.py"
    assert "candidate card" in (workspace / "cards/sample.py").read_text()
    assert Path(rules.__file__).resolve() == workspace / "engine/rules.py"


def test_authoritative_support(authoritative_fixture):
    assert HELPER == "authoritative helper"
    assert MARKER == "authoritative support"
    assert authoritative_fixture == "authoritative fixture"


def test_external_replay_root_and_relative_fixtures():
    root = Path(__file__).resolve().parents[4]
    assert load_card_id_map() == {7: "External card"}
    assert json.loads((root / "data/replays/golden/example.json").read_text()) == {"host": True}
    assert json.loads((root / "data/replays/token_id_map.json").read_text()) == {"tokens": {}}
    assert "authoritative triage" in (root / "scripts/triage_divergences.py").read_text()
""",
    )
    _write(
        root / "data/replays/card_id_map.json",
        json.dumps({"grpId_to_card": {"7": {"card_name": "External card"}}}),
    )
    _write(root / "data/replays/token_id_map.json", '{"tokens": {}}')
    _write(root / "data/replays/golden/example.json", '{"host": true}')
    _write(root / "scripts/triage_divergences.py", "MARKER = 'authoritative triage'\n")
    for relative in (
        "conftest.py",
        "test_utils.py",
        "engine_tests/conftest.py",
        "engine_tests/test_grading.py",
        "engine_tests/support.py",
        "pytest.py",
        "sitecustomize.py",
    ):
        _write(candidate / relative, "raise AssertionError('candidate grading support executed')\n")
    _write(candidate / "pytest.ini", "[pytest]\naddopts = --ignore=engine_tests\n")
    _write(candidate / "data/replays/golden/example.json", '{"host": false}')
    monkeypatch.setenv("PYTHONPATH", str(host))
    token = _BENCHMARK_DATA_ROOT.set(root)
    try:
        yield host, candidate
    finally:
        _BENCHMARK_DATA_ROOT.reset(token)


@pytest.mark.parametrize("edit", [None, "engine", "cards"])
def test_candidate_edits_are_graded_and_poisoned_support_is_ignored(grading_trees, edit):
    host, candidate = grading_trees
    if edit == "engine":
        _write(candidate / "engine/rules.py", "VALUE = 'broken engine'\n")
    elif edit == "cards":
        _write(candidate / "cards/sample.py", "VALUE = 'broken card'\n")
    source_files = {
        p: p.read_bytes() for root in (host, candidate) for p in root.rglob("*") if p.is_file()
    }

    result = _eval_engine(
        candidate / "engine", host / "engine_tests", test_utils=host / "test_utils.py"
    )

    assert result.tests_total == 4, result.errors
    assert result.tests_failed == int(edit is not None), result.errors
    assert result.tests_passed == 4 - int(edit is not None), result.errors
    assert all(path.read_bytes() == data for path, data in source_files.items())


def test_legacy_engine_only_staging_uses_explicit_reference_cards(grading_trees, tmp_path):
    host, candidate = grading_trees
    engine_only = tmp_path / "engine-only"
    _write(engine_only / "engine/__init__.py", "")
    _write(engine_only / "engine/rules.py", "VALUE = 'candidate engine'\n")

    result = _eval_engine(
        engine_only / "engine", host / "engine_tests", cards_dir=candidate / "cards"
    )

    assert result.tests_total == result.tests_passed == 4, result.errors
    assert result.tests_failed == 0


def test_missing_candidate_packages_do_not_fall_back_to_host(grading_trees):
    host, candidate = grading_trees
    result = _eval_engine(
        candidate / "missing-engine", host / "engine_tests", test_utils=host / "test_utils.py"
    )
    assert result.tests_total == 0
    assert any("selected grading code directory not found" in message for message in result.errors)
