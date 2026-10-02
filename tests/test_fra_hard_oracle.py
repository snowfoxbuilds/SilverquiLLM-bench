"""Check the fra-hard oracle against its target Audited Tests."""

from pathlib import Path

import pytest

from scripts.oracle_support import load_layout
from tests.test_audited_against_reference import _run_audited_tests_against_oracle

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/fra-hard"


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
