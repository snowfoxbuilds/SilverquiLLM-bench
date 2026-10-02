"""Check the new oracle against the inherited regression dimensions."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.oracle_support import load_layout
from tests.test_audited_against_reference import _run_audited_tests_against_oracle

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/fra-hard"
ORACLE = BENCH / "data/test_oracle_workspace"


@pytest.mark.parametrize("card_id", load_layout(ROOT, "fra-hard", require_cards=True).cards)
def test_hidden_suite_passes_with_candidate_helper(card_id):
    returncode, stdout, stderr = _run_audited_tests_against_oracle(
        card_id, "fra-hard", test_utils=BENCH / "workspace/test_utils.py",
    )
    assert returncode == 0, stdout + stderr


@pytest.mark.parametrize("card_id", load_layout(ROOT, "fra-hard", require_cards=True).cards)
def test_hidden_suite_rejects_behavior_free_candidate(card_id):
    code = card_id.split("_", 1)[0]
    implementation = BENCH / "workspace/cards" / code / card_id / "card_impl.py"
    returncode, stdout, stderr = _run_audited_tests_against_oracle(
        card_id, "fra-hard", implementation=implementation,
    )
    assert returncode == 1, stdout + stderr
    assert " failed" in stdout and "ERROR collecting" not in stdout, stdout + stderr


@pytest.mark.parametrize("dimension", ("fdn", "engine"))
def test_oracle_preserves_regression_dimension(dimension, tmp_path):
    suites = BENCH / "data/tests/audited/fdn" if dimension == "fdn" else ORACLE / "engine_tests"
    assert list(suites.rglob("*.py")), f"Empty regression dimension: {dimension}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(suites), "-q", "--tb=short",
         "--confcutdir", str(suites.parent), "-c", str(ORACLE / "pytest.ini")],
        cwd=tmp_path,
        env=dict(os.environ, PYTHONPATH=str(ORACLE)),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
