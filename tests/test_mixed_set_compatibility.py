import json

import pytest

from scripts.check_promotion_candidate import check_oracle_gate
from silverquillm.results_repo import leaderboard_validity_reasons


@pytest.mark.parametrize("card_filter", [None, ["FRA:001", "hob_001"], [1, "hob:1"]])
def test_mixed_results_preserve_set_identity(card_filter):
    config = {"cards": ["fra:1", "hob:1"], "draft_set": {"primary_set_code": "FRA"}}
    assert leaderboard_validity_reasons(config, card_filter, None, ["fra_001", "hob_1"]) == []


def test_mixed_results_do_not_collapse_same_collector_number():
    config = {"cards": ["fra:1", "hob:1"], "draft_set": {"primary_set_code": "FRA"}}
    reasons = leaderboard_validity_reasons(config, ["fra_1"], None, ["fra_1", "fra_001"])
    assert len(reasons) == 2


def test_legacy_result_normalization_is_unchanged():
    assert leaderboard_validity_reasons({"cards": ["001"]}, [1], None, ["sos_001"]) == []


@pytest.mark.parametrize("bench,primary,card", [("fra-hard", "FRA", "hob_33"), ("sos", "SOS", "sos_1"), ("hob-hard", "HOB", "hob_33")])
def test_oracle_gate_uses_card_set(tmp_path, bench, primary, card):
    benchmark = tmp_path / "benchmarks" / bench
    oracle = benchmark / "data" / "test_oracle_workspace"
    card_dir = oracle / "cards" / card.split("_")[0] / card
    card_dir.mkdir(parents=True)
    (benchmark / "config.json").write_text(json.dumps({"draft_set": {"primary_set_code": primary}}))
    (card_dir / "card_impl.py").write_text("VALUE = 42\n")
    candidate = tmp_path / "candidate.py"
    candidate.write_text("from card_impl import VALUE\ndef test_value():\n    assert VALUE == 42\n")
    ok, reason = check_oracle_gate(candidate, card, tmp_path, bench)
    assert ok, reason
