"""The benchmark id and set code remain distinct in oracle/promotion tools."""

import importlib.util
import sys
from pathlib import Path

from scripts.oracle_support import load_layout, readiness_errors

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "promotion_hob_test", ROOT / "scripts/check_promotion_candidate.py"
)
PROMOTION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PROMOTION
SPEC.loader.exec_module(PROMOTION)


def test_hob_paths_use_the_primary_set():
    layout = load_layout(ROOT, "hob-medium", require_cards=True)
    assert layout.target_set == "hob"
    assert len(layout.cards) == 5
    for card in layout.cards:
        assert layout.implementation(card).parent.parent.name == "hob"
        assert layout.audited.name == "hob"
        assert not readiness_errors(layout, card)


def test_promotion_executes_real_hob_oracle_without_a_hob_medium_set_directory():
    layout = load_layout(ROOT, "hob-medium")
    ok, reason = PROMOTION.check_oracle_gate(
        layout.suite("hob_12"), "hob_12", ROOT, bench="hob-medium"
    )
    assert ok, reason


def test_promotion_checks_v2_target_and_helper_imports():
    layout = load_layout(ROOT, "hob-medium")
    ok, reason = PROMOTION.check_canonical_api(layout.suite("hob_12"), ROOT, bench="hob-medium")
    assert ok, reason
