from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from scripts.oracle_support import load_layout
from silverquillm.benchmark_targets import target_cards
from silverquillm.evaluator import evaluate_run
from silverquillm.karn.benchmark import load_benchmark, stage_benchmark
from silverquillm.karn.definition import KarnError
from silverquillm.karn.execution import _scores
from silverquillm.karn.grading_inputs import grading_inputs

from .grader_fixtures import local_grader
from .test_karn_execution import benchmark_data


@pytest.fixture
def mixed(tmp_path):
    repository = benchmark_data(tmp_path)
    root = repository / "benchmarks/example"
    config = {"id": "example", "cards": ["fra:001", "hob:1"],
              "draft_set": {"primary_set_code": "FRA"}}
    (root / "config.json").write_text(json.dumps(config))
    for code, value in (("fra", 7), ("hob", 9)):
        directory = root / f"workspace/cards/{code}/{code}_1"
        directory.mkdir(parents=True)
        (directory.parent / "__init__.py").write_text("")
        (directory / "__init__.py").write_text("")
        (directory / "card_spec.json").write_text('{"collector_number":"001"}')
        (directory / "card_impl.py").write_text(f"value = {value}\n")
        suite = root / f"data/tests/audited/{code}/{code}_1/tests.py"
        suite.parent.mkdir(parents=True)
        suite.write_text(f"from card_impl import value\ndef test_value(): assert value == {value}\n")
    return load_benchmark(repository, "example")


def test_mixed_staging_selects_each_set(mixed, tmp_path):
    prompt, identity = stage_benchmark(mixed, tmp_path / "stage")
    assert "- cards/fra/fra_1" in prompt
    assert "- cards/hob/hob_1" in prompt
    assert "- cards/fdn/" not in prompt
    assert identity["cards"] == ["fra:001", "hob:1"]


def test_duplicate_directories_cannot_mask_a_missing_set_target(mixed, tmp_path):
    duplicate = mixed.root / "workspace/cards/fra/fra_001"
    duplicate.mkdir()
    (duplicate / "card_spec.json").write_text('{"collector_number":"1"}')
    (mixed.root / "workspace/cards/hob/hob_1/card_spec.json").unlink()
    with pytest.raises(KarnError, match="benchmark_selected_card_ambiguous"):
        stage_benchmark(mixed, tmp_path / "stage")


def test_mixed_grading_and_scores_preserve_set_identity(mixed, tmp_path):
    result = evaluate_run(tmp_path, mixed, workspace_source=mixed.root / "workspace")
    assert set(result.sos_results) == {"fra_1", "hob_1"}
    assert all(card.tests_passed == 1 for card in result.sos_results.values())
    assert result.fdn_results["fdn_1"].tests_passed == 1
    assert result.engine_result.tests_passed == 1
    scores = _scores(result, mixed)
    assert scores["card_correctness"]["complete"]
    assert scores["card_correctness"]["tests_passed"] == 2
    (mixed.root / "workspace/cards/hob/hob_1/card_impl.py").write_text("value = 0\n")
    broken = evaluate_run(tmp_path, mixed, workspace_source=mixed.root / "workspace")
    assert broken.sos_results["fra_1"].tests_passed == 1
    assert broken.sos_results["hob_1"].tests_failed == 1


def test_grading_mounts_and_fingerprints_include_both_sets(mixed, tmp_path):
    grader = local_grader()
    grader._grade = Mock(return_value=None)
    grader.evaluate_run(tmp_path, mixed, workspace_source=mixed.root / "workspace")
    job, mounts = grader._grade.call_args.args
    assert job["cards"] == mixed.cards
    sources = {source for source, _, _ in mounts}
    assert mixed.root / "data/tests/audited/fra" in sources
    assert mixed.root / "data/tests/audited/hob" in sources
    inputs = grading_inputs(mixed)
    paths = {item["path"] for item in inputs["files"] if item["kind"] == "target"}
    assert paths == {f"benchmarks/example/data/tests/audited/{code}/{code}_1/tests.py"
                     for code in ("fra", "hob")}
    layout = load_layout(mixed.root.parent.parent, "example")
    assert layout.cards == ("fra_1", "hob_1")
    assert layout.suite("hob_1") == mixed.root / "data/tests/audited/hob/hob_1/tests.py"
    assert layout.implementation("hob_1") == mixed.root / "data/test_oracle_workspace/cards/hob/hob_1/card_impl.py"


def test_legacy_numbers_remain_primary_set():
    assert target_cards("HOB", ["001", "76"]) == [("hob", "001"), ("hob", "76")]


def test_legacy_padded_directory_fallback(mixed, tmp_path):
    config = dict(mixed.config, cards=["001"])
    (mixed.root / "config.json").write_text(json.dumps(config))
    for base in ("workspace/cards/fra", "data/tests/audited/fra"):
        directory = mixed.root / base
        (directory / "fra_1").rename(directory / "fra_001")
    benchmark = load_benchmark(mixed.root.parent.parent, mixed.id)
    result = evaluate_run(tmp_path, benchmark, workspace_source=mixed.root / "workspace")
    assert set(result.sos_results) == {"fra_001"}
    assert result.sos_results["fra_001"].tests_passed == 1
    assert _scores(result, benchmark)["card_correctness"]["complete"]


@pytest.mark.parametrize("cards", [["fra:1", "FRA:001"], ["fra:../1"], ["fra:1:2"]])
def test_invalid_or_duplicate_targets_rejected(mixed, cards):
    config = dict(mixed.config, cards=cards)
    (mixed.root / "config.json").write_text(json.dumps(config))
    with pytest.raises(KarnError, match="benchmark_unavailable"):
        load_benchmark(mixed.root.parent.parent, mixed.id)
