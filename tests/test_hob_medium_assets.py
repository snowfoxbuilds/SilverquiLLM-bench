"""Integrity and coverage of the selected HOB-medium benchmark artifacts."""

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/hob-medium"
CARDS = (12, 36, 70, 131, 169)


def test_pool_matches_config_and_pinned_first_printings():
    config = json.loads((BENCH / "config.json").read_text())
    assert config["cards"] == [str(n) for n in CARDS]
    assert config["draft_set"]["primary_set_code"] == "HOB"
    pool = json.loads((BENCH / "data/pool.json").read_text())
    raw = {c["collector_number"]: c for c in json.loads((ROOT / "data/sets/hob.json").read_text())}
    assert [c["collector_number"] for c in pool] == config["cards"]
    for card in pool:
        assert card["name"] == raw[card["collector_number"]]["name"]
        assert card["oracle_text"] == raw[card["collector_number"]]["oracle_text"]


@pytest.mark.parametrize("number", CARDS)
def test_candidates_are_behavior_free_and_instructions_are_present(number):
    directory = BENCH / f"workspace/cards/hob/hob_{number}"
    tree = ast.parse((directory / "card_impl.py").read_text())
    methods = [
        n.name
        for cls in tree.body
        if isinstance(cls, ast.ClassDef)
        for n in cls.body
        if isinstance(n, ast.FunctionDef)
    ]
    assert methods == ["__init__"]
    assert len((directory / "instructions.md").read_text()) > 300
    assert (directory / "card_spec.json").read_bytes() == (
        BENCH / f"data/test_oracle_workspace/cards/hob/hob_{number}/card_spec.json"
    ).read_bytes()


def test_fdn_coverage_is_explicit_and_matches_real_suites():
    coverage = json.loads((BENCH / "data/fdn_regression_coverage.json").read_text())
    covered = {p.parent.name for p in (BENCH / "data/tests/audited/fdn").glob("*/tests.py")}
    all_cards = {p.parent.name for p in (BENCH / "workspace/cards/fdn").glob("*/card_impl.py")}
    assert covered == set(coverage["covered_card_ids"])
    assert all_cards - covered == set(coverage["uncovered_card_ids"])
    assert len(covered) == 86 and len(all_cards) == 286
    for card in covered:
        canonical = BENCH / f"data/tests/audited/fdn/{card}/tests.py"
        assert (
            canonical.read_bytes()
            == (
                BENCH / f"data/test_oracle_workspace/tests/audited/fdn/{card}/tests.py"
            ).read_bytes()
        )


def test_oracle_is_independent_and_never_staged():
    workspace = BENCH / "workspace"
    assert not (workspace / "test_oracle_workspace").exists()
    assert not (workspace / "data/tests/audited").exists()
    assert (BENCH / "data/test_oracle_workspace/engine/hob_support.py").is_file()
    assert not (workspace / "engine/hob_support.py").exists()
    assert not any(p.is_symlink() for p in (BENCH / "data/test_oracle_workspace").rglob("*"))
