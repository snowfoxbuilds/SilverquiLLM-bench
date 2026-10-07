"""Grading pairs the benchmark's own Test Interface and ``table`` helpers with
the candidate's engine (TEST-INTERFACE.md › Ownership): a candidate that
rewrites, deletes or corrupts its staged ``test_interface.py`` or ``table.py``
changes no score.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from silverquillm.evaluator import (
    _GRADING_IGNORE,
    _eval_engine,
    _grade_audited_card,
    resolve_eval_paths,
)

REPO = Path(__file__).resolve().parents[1]
SMOKE = REPO / "benchmarks/smoke"
PATHS = resolve_eval_paths(SMOKE, "fdn")

# A suite that only passes against the benchmark's Test Interface and table.
PROBE = '''
import table
import test_interface


def test_the_benchmark_copy_is_imported():
    assert not hasattr(test_interface, "TAMPERED")
    assert callable(test_interface.run) and callable(test_interface.view)
    assert not hasattr(table, "TAMPERED")
    assert callable(table.Table)
'''


def _overlay(tmp_path: Path, poison: str, name: str = "test_interface.py") -> Path:
    overlay = tmp_path / "workspace"
    shutil.copytree(SMOKE / "workspace", overlay, ignore=_GRADING_IGNORE)
    staged = overlay / name
    if poison == "rewrite":
        staged.write_text("TAMPERED = True\ndef run(*a, **k):\n    return None\ndef view(*a):\n    return None\n")
    elif poison == "delete":
        staged.unlink()
    elif poison == "corrupt":
        staged.write_text("this is not valid python !!!\n")
    return overlay


@pytest.mark.parametrize("name", ["test_interface.py", "table.py"])
@pytest.mark.parametrize("poison", ["rewrite", "delete", "corrupt"])
def test_a_candidate_test_interface_never_reaches_a_card_suite(tmp_path, poison, name):
    probe = tmp_path / "suite" / "tests.py"
    probe.parent.mkdir()
    probe.write_text(PROBE)
    result = _grade_audited_card(
        "fdn_129", probe, _overlay(tmp_path, poison, name), 120,
        test_utils=PATHS.test_utils, test_interface=PATHS.test_interface,
    )
    assert (result.tests_passed, result.tests_failed) == (1, 0), result.errors


@pytest.mark.parametrize("name", ["test_interface.py", "table.py"])
@pytest.mark.parametrize("poison", ["rewrite", "delete"])
def test_a_candidate_test_interface_never_reaches_the_engine_suite(tmp_path, poison, name):
    suite = tmp_path / "engine_suite"
    suite.mkdir()
    (suite / "test_probe.py").write_text(PROBE)
    overlay = _overlay(tmp_path, poison, name)
    result = _eval_engine(
        overlay / "engine", suite, 120, support_dir=PATHS.engine_support,
        test_utils=PATHS.test_utils, test_interface=PATHS.test_interface,
    )
    assert (result.tests_passed, result.tests_failed) == (1, 0), result.errors


def test_a_missing_benchmark_test_interface_fails_visibly(tmp_path):
    probe = tmp_path / "tests.py"
    probe.write_text(PROBE)
    missing = tmp_path / "nope" / "test_interface.py"
    result = _grade_audited_card(
        "fdn_129", probe, _overlay(tmp_path, "none"), 120, test_utils=None, test_interface=missing,
    )
    assert result.skipped and any("test_interface" in error for error in result.errors)
