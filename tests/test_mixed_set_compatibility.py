import json

import pytest

from scripts.check_promotion_candidate import check_oracle_gate


@pytest.mark.parametrize(
    "bench,primary,card",
    [("fra-hard", "FRA", "hob_33"), ("sos", "SOS", "sos_1"), ("hob-hard", "HOB", "hob_33")],
)
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
