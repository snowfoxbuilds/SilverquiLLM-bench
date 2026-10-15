"""The Net Card Score derivation (SCORING.md, Net Card Score through Deriving the score)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.net_card_score import (
    benchmark_scoring_data,
    derive,
    load_scoring_data,
    record_grade,
    regrade_grade,
    scoring_data_digest,
)

REPO = Path(__file__).resolve().parents[1]

# A bench of two targets (tgt_1, tgt_2) and four existing cards:
# - zone-change is related: it breaks fdn_10's and an engine test, and tgt_2's second test;
#   fdn_10 hosts it.
# - lonely is unrelated: it breaks fdn_30's test, and shares fdn_10's second test, which
#   therefore counts toward nothing.
# - the engine's combat file is hosted on fdn_20, its zones file on fdn_10.
MANIFEST = {
    "schema_version": 2,
    "benchmark": "bench",
    "defects": [
        {
            "id": "zone-change",
            "description": "Objects keep state across zones.",
            "rules": ["CR 400.7"],
            "kind": "inherited",
            "failing_tests": {
                "fdn": ["fdn_10/tests.py::test_returns_new", "fdn_10/tests.py::test_shared"],
                "engine": ["test_zones.py::test_counters_reset"],
            },
            "target_tests": ["tgt_2/tests.py::test_returns_again"],
            "host_card": "fdn_10",
        },
        {
            "id": "lonely",
            "description": "Something no target needs.",
            "rules": ["CR 702.19"],
            "kind": "seeded",
            "failing_tests": {
                "fdn": ["fdn_30/tests.py::test_unrelated", "fdn_10/tests.py::test_shared"]
            },
            "target_tests": [],
            "host_card": None,
        },
    ],
}
ATTRIBUTION = {
    "schema_version": 1,
    "engine": {"test_combat.py": "fdn_20", "test_zones.py": "fdn_10"},
    "fdn": {},
}
TARGET_ATTRIBUTION = {
    "schema_version": 1,
    "target": {"tgt_2/tests.py::test_with_tgt_1": "tgt_1"},
}

TARGET_NODES = {
    "tgt_1": ["tests.py::test_one", "tests.py::test_two"],
    "tgt_2": ["tests.py::test_own", "tests.py::test_returns_again", "tests.py::test_with_tgt_1"],
}
FDN_NODES = {
    "fdn_10": ["tests.py::test_returns_new", "tests.py::test_shared", "tests.py::test_plain"],
    "fdn_20": ["tests.py::test_attacks"],
    "fdn_30": ["tests.py::test_unrelated"],
}
ENGINE_NODES = [
    "test_combat.py::test_first_strike",
    "test_combat.py::test_trample[2]",
    "test_zones.py::test_counters_reset",
]
BASELINE_FAILS = {
    "fdn_10/tests.py::test_returns_new",
    "fdn_10/tests.py::test_shared",
    "fdn_30/tests.py::test_unrelated",
    "test_zones.py::test_counters_reset",
}


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "bench"
    (root / "data").mkdir(parents=True)
    for name, document in (
        ("known_defects.json", MANIFEST),
        ("attribution.json", ATTRIBUTION),
        ("target_attribution.json", TARGET_ATTRIBUTION),
    ):
        (root / "data" / name).write_text(json.dumps(document))
    return load_scoring_data(root, ["tgt_1", "tgt_2"])


def _scores(failing=(), not_run=()):
    """Schema 3 scores where every test passes except ``failing`` (qualified ids)."""

    def nodes(prefix, tests):
        return [
            {"test_node": node, "outcome": "fail" if f"{prefix}{node}" in failing else "pass"}
            for node in tests
            if f"{prefix}{node}" not in not_run
        ]

    def cards(table):
        return {
            card: {
                "test_nodes": nodes(f"{card}/", tests),
                "not_run": [
                    {"test_node": node, "reason": "import_error"}
                    for node in tests
                    if f"{card}/{node}" in not_run
                ],
            }
            for card, tests in table.items()
        }

    return {
        "target": {"evaluated": True, "cards": cards(TARGET_NODES)},
        "fdn": {"evaluated": True, "cards": cards(FDN_NODES)},
        "engine": {"evaluated": True, "test_nodes": nodes("", ENGINE_NODES), "not_run": []},
    }


def _all_tests():
    return {
        *(f"{card}/{node}" for card, tests in FDN_NODES.items() for node in tests),
        *ENGINE_NODES,
    }


def _record(scores, comparison):
    manifest = {"schema_version": 3, "run_metadata": {"baseline_comparison": comparison}}
    return record_grade(manifest, scores)


def _comparison(failing):
    """The comparison of a run failing ``failing`` against the BASELINE_FAILS baseline."""
    fdn, engine = [], []
    for test in sorted(_all_tests() - BASELINE_FAILS):
        if test in failing:
            (fdn if test.startswith("fdn_") else engine).append(test)
    return {
        "available": True,
        "fixed": {"fdn": [], "engine": []},
        "broken": {"fdn": fdn, "engine": engine},
    }


def _score(data, failing=(), not_run=()):
    failing = set(failing)
    return derive(
        _record(_scores(failing, set(not_run)), _comparison(failing | set(not_run))), data
    )


UNMODIFIED = {
    *BASELINE_FAILS,
    "tgt_1/tests.py::test_one",
    "tgt_1/tests.py::test_two",
    "tgt_2/tests.py::test_own",
    "tgt_2/tests.py::test_returns_again",
    "tgt_2/tests.py::test_with_tgt_1",
}


def test_the_oracle_scores_one(data):
    result = _score(
        data, failing={"fdn_30/tests.py::test_unrelated", "fdn_10/tests.py::test_shared"}
    )
    assert result["score"] == 1
    assert result["cards_implemented"] == ["tgt_1", "tgt_2"]
    assert result["cards_fixed"] == ["fdn_10"]
    assert result["denominator"] == 3
    assert result["host_cards"] == ["fdn_10"]


def test_the_unmodified_workspace_scores_zero(data):
    result = _score(data, failing=UNMODIFIED)
    assert result["score"] == 0
    assert (result["implemented"], result["fixed"], result["broken"]) == (0, 0, 0)


def test_a_collateral_mistake_breaks_the_host_of_the_mechanic(data):
    result = _score(data, failing={*BASELINE_FAILS, "test_combat.py::test_first_strike"})
    assert result["cards_broken"] == ["fdn_20"]
    assert result["failing_tests"]["fdn_20"] == {
        "collateral": ["engine:test_combat.py::test_first_strike"]
    }
    assert result["score"] == (2 + 0 - 1) / 3


def test_a_broken_parametrized_case_breaks_its_card(data):
    result = _score(data, failing={*BASELINE_FAILS, "test_combat.py::test_trample[2]"})
    assert result["cards_broken"] == ["fdn_20"]


def test_fixing_the_related_defect_earns_its_host(data):
    result = _score(
        data, failing={"fdn_30/tests.py::test_unrelated", "fdn_10/tests.py::test_shared"}
    )
    assert result["fixed"] == 1
    partly = _score(
        data, failing={"fdn_30/tests.py::test_unrelated", "test_zones.py::test_counters_reset"}
    )
    assert partly["fixed"] == 0
    assert partly["failing_tests"]["fdn_10"] == {
        "dependency": ["engine:test_zones.py::test_counters_reset"]
    }


def test_the_target_dependency_test_counts_toward_the_host_not_the_target(data):
    result = _score(data, failing={*BASELINE_FAILS, "tgt_2/tests.py::test_returns_again"})
    assert "tgt_2" in result["cards_implemented"]
    assert result["cards_fixed"] == []
    assert result["failing_tests"]["fdn_10"]["dependency"] == [
        "engine:test_zones.py::test_counters_reset",
        "fdn:fdn_10/tests.py::test_returns_new",
        "target:tgt_2/tests.py::test_returns_again",
    ]


def test_fixing_an_unrelated_defect_earns_nothing(data):
    fixed = _score(data, failing={"fdn_10/tests.py::test_shared"})
    unfixed = _score(
        data, failing={"fdn_10/tests.py::test_shared", "fdn_30/tests.py::test_unrelated"}
    )
    assert fixed["score"] == unfixed["score"] == 1
    assert "fdn:fdn_30/tests.py::test_unrelated" in fixed["dependency_tests_left_out"]


def test_a_dependency_test_shared_with_an_unrelated_defect_counts_toward_nothing(data):
    result = _score(data, failing={"fdn_10/tests.py::test_shared"})
    assert result["cards_fixed"] == ["fdn_10"]
    assert "fdn:fdn_10/tests.py::test_shared" in result["dependency_tests_left_out"]


def test_a_test_that_did_not_run_fails_its_class(data):
    result = _score(
        data,
        failing={"fdn_30/tests.py::test_unrelated", "fdn_10/tests.py::test_shared"},
        not_run={"tgt_1/tests.py::test_two", "fdn_20/tests.py::test_attacks"},
    )
    assert result["cards_implemented"] == ["tgt_2"]
    assert result["failing_tests"]["tgt_1"] == {"implementation": ["tgt_1/tests.py::test_two"]}
    assert result["cards_broken"] == ["fdn_20"]


def test_a_cross_card_target_test_counts_toward_the_main_card(data):
    result = _score(data, failing={*BASELINE_FAILS, "tgt_2/tests.py::test_with_tgt_1"})
    assert result["cards_implemented"] == ["tgt_2"]
    assert result["failing_tests"]["tgt_1"] == {
        "implementation": ["tgt_2/tests.py::test_with_tgt_1"]
    }


def test_a_card_can_be_fixed_and_broken_at_once(data):
    result = _score(
        data,
        failing={
            "fdn_30/tests.py::test_unrelated",
            "fdn_10/tests.py::test_shared",
            "fdn_10/tests.py::test_plain",
        },
    )
    assert result["cards_fixed"] == ["fdn_10"]
    assert result["cards_broken"] == ["fdn_10"]


def test_there_is_no_floor(data):
    wrecked = UNMODIFIED | {
        "fdn_10/tests.py::test_plain",
        "fdn_20/tests.py::test_attacks",
        "test_combat.py::test_first_strike",
    }
    result = _score(data, failing=wrecked)
    assert result["score"] == -2 / 3


def test_an_unattributed_engine_breakage_still_counts(data):
    grade = _record(
        _scores(),
        {
            "available": True,
            "fixed": {"fdn": [], "engine": []},
            "broken": {"fdn": [], "engine": ["test_new.py::test_x"]},
        },
    )
    assert derive(grade, data)["cards_broken"] == ["unattributed:test_new.py"]


@pytest.mark.parametrize(
    ("comparison", "reason"),
    [
        (None, "no_baseline_comparison"),
        ({"available": False, "reason": "baseline_incomplete"}, "baseline_incomplete"),
    ],
)
def test_unavailable_with_the_comparisons_reason(data, comparison, reason):
    result = derive(_record(_scores(), comparison), data)
    assert result == {
        "available": False,
        "reason": reason,
        "scoring_data_digest": data.digest,
    }


def test_unavailable_when_the_target_suite_was_not_graded(data):
    scores = _scores()
    scores["target"] = {
        "evaluated": False,
        "cards": {
            "tgt_1": {
                "test_nodes": [],
                "not_run": [
                    {"test_node": "tests.py::test_one", "reason": "grading_support_missing"}
                ],
            }
        },
    }
    result = derive(_record(scores, _comparison(set())), data)
    assert result["reason"] == "suite_not_evaluated"


def test_a_benchmark_without_scoring_data_has_none(tmp_path):
    assert load_scoring_data(tmp_path, ["tgt_1"]) is None
    assert derive(_record(_scores(), _comparison(set())), None) == {
        "available": False,
        "reason": "no_scoring_data",
    }


def test_a_schema_2_record_reads_its_retired_names(data):
    scores = _scores(failing={*BASELINE_FAILS, "test_combat.py::test_first_strike"})
    retired = {
        "card_correctness": scores["target"],
        "fdn_regression": scores["fdn"],
        "engine_regression": scores["engine"],
    }
    manifest = {
        "schema_version": 2,
        "run_metadata": {
            "combined_regression": {
                "available": True,
                "fixed": {"count": 0, "test_nodes": {}},
                "regressed": {
                    "count": 1,
                    "test_nodes": {"engine_regression": ["test_combat.py::test_first_strike"]},
                },
            }
        },
    }
    assert derive(record_grade(manifest, retired), data)["cards_broken"] == ["fdn_20"]
    unavailable = {"available": False, "reason": "regression_not_evaluated"}
    manifest["run_metadata"]["combined_regression"] = unavailable
    assert derive(record_grade(manifest, retired), data)["reason"] == "suite_not_evaluated"


def test_a_regrade_output_reads_either_naming(data):
    failing = {*BASELINE_FAILS, "test_combat.py::test_first_strike"}
    output = {"scores": _scores(failing), "baseline_comparison": _comparison(failing)}
    assert derive(regrade_grade(output), data)["cards_broken"] == ["fdn_20"]


def test_the_digest_covers_every_scoring_file(tmp_path, data):
    root = tmp_path / "bench"
    before = scoring_data_digest(root)
    assert before == data.digest
    (root / "data" / "target_attribution.json").write_text(
        json.dumps({"schema_version": 1, "target": {}})
    )
    assert scoring_data_digest(root) != before


@pytest.mark.parametrize("benchmark", ["smoke", "fra-hard-v2"])
def test_the_real_scoring_data_loads(benchmark):
    data = benchmark_scoring_data(REPO, benchmark)
    assert data is not None and data.targets
    assert set(data.targets).isdisjoint(
        {defect.host_card for defect in data.defects.defects if defect.related}
    )


@pytest.mark.parametrize("benchmark", ["hob-medium", "fra-hard", "sos"])
def test_earlier_benchmarks_have_no_scoring_data(benchmark):
    if not (REPO / "benchmarks" / benchmark).is_dir():
        pytest.skip(f"{benchmark} is not in this checkout")
    try:
        data = benchmark_scoring_data(REPO, benchmark)
    except Exception:  # noqa: BLE001 -- an unloadable benchmark has no scoring data either.
        data = None
    assert data is None


def test_fra_hard_v2_denominator_counts_both_related_defects():
    data = benchmark_scoring_data(REPO, "fra-hard-v2")
    hosts = {defect.host_card for defect in data.defects.defects if defect.related}
    assert hosts == {"fdn_122", "fdn_236"}


# --- Reading it: the command, `top` history and the regrade summary -------------------


def _write_record(directory: Path, scores: dict, comparison: dict, benchmark="bench") -> Path:
    directory.mkdir(parents=True)
    manifest = {
        "schema_version": 3,
        "run_id": directory.name,
        "candidate_hash": directory.parent.name,
        "benchmark": benchmark,
        "run_metadata": {"baseline_comparison": comparison},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    (directory / "scores.json").write_text(json.dumps(scores))
    return directory


CANDIDATE = "c" * 64
ORACLE_FAILS = {"fdn_30/tests.py::test_unrelated", "fdn_10/tests.py::test_shared"}


def test_score_paths_reads_records_and_regrade_outputs(tmp_path, data, monkeypatch):
    import silverquillm.net_card_score as module

    monkeypatch.setattr(module, "benchmark_scoring_data", lambda root, benchmark: data)
    results = tmp_path / "results" / CANDIDATE
    _write_record(results / "run1", _scores(ORACLE_FAILS), _comparison(ORACLE_FAILS))
    regrades = tmp_path / "regrades" / ("d" * 64) / CANDIDATE
    regrades.mkdir(parents=True)
    output = {
        "run_id": "run2",
        "candidate_hash": CANDIDATE,
        "benchmark": "bench",
        "scores": _scores(UNMODIFIED),
        "baseline_comparison": _comparison(UNMODIFIED),
    }
    (regrades / "run2.json").write_text(json.dumps(output))
    (regrades.parent / "summary.json").write_text("{}")

    rows = list(module.score_paths([tmp_path / "results", tmp_path / "regrades"], tmp_path))
    assert [(row["kind"], row["run_id"], row["score"]) for row in rows] == [
        ("record", "run1", 1),
        ("regrade", "run2", 0),
    ]
    assert rows[0]["scoring_data_digest"] == data.digest
    (single,) = module.score_paths([results / "run1"], tmp_path)
    assert single["run_id"] == "run1"


def test_the_command_prints_one_json_line_per_grade(tmp_path):
    from click.testing import CliRunner

    from silverquillm.cli import main

    record = _write_record(
        tmp_path / CANDIDATE / "run1", _scores(), _comparison(set()), benchmark="hob-medium"
    )
    outcome = CliRunner().invoke(main, ["net-card-score", "--bench-root", str(REPO), str(record)])
    assert outcome.exit_code == 0, outcome.output
    (line,) = outcome.output.splitlines()
    assert json.loads(line) == {
        "available": False,
        "benchmark": "hob-medium",
        "candidate_hash": CANDIDATE,
        "kind": "record",
        "path": str(record),
        "reason": "no_scoring_data",
        "run_id": "run1",
    }


def test_history_derives_the_score_and_follows_the_scoring_data(tmp_path, data, monkeypatch):
    from silverquillm.monitor import history

    calls = []

    def scoring(root, benchmark):
        calls.append(benchmark)
        return data

    monkeypatch.setattr(history, "benchmark_scoring_data", scoring)
    repo, bench = tmp_path / "repo", tmp_path / "checkout"
    failing = {*ORACLE_FAILS, "test_combat.py::test_first_strike"}
    _write_record(repo / "results" / CANDIDATE / "run1", _scores(failing), _comparison(failing))
    store = history.HistoryStore(repo, bench)

    (run,) = store.runs()
    assert run.net_card["cards_broken"] == ["fdn_20"]
    store.runs()
    assert calls == ["bench"]
    (bench / "benchmarks" / "bench" / "data").mkdir(parents=True)
    (bench / "benchmarks" / "bench" / "data" / "attribution.json").write_text("{}")
    store.runs()
    assert calls == ["bench", "bench"]
    assert history.HistoryStore(repo).runs()[0].net_card is None


def test_the_monitor_shows_the_score_and_its_counts(data):
    from silverquillm.top import format as fmt
    from silverquillm.top.theme import THEMES

    theme = next(iter(THEMES.values()))
    value = _score(data, failing={*BASELINE_FAILS, "test_combat.py::test_first_strike"})
    assert fmt.net_card(value, theme).plain == "+0.33 2+0-1/3"
    assert fmt.net_card(None, theme).plain == fmt.DASH
    unavailable = {"available": False, "reason": "suite_not_evaluated"}
    assert fmt.net_card(unavailable, theme).plain == f"{fmt.DASH} suite not graded"


def test_the_regrade_summary_reports_each_cohorts_mean_score(data):
    from silverquillm.karn import regrade

    def output(run_id, failing):
        return {
            "run_id": run_id,
            "candidate_hash": CANDIDATE,
            "candidate_name": "candidate",
            "source": {
                "grading_inputs_digest": "sha256:" + "a" * 64,
                "scores": {name: {"pass_rate": None} for name in ("target", "fdn", "engine")},
            },
            "scores": _scores(failing),
            "baseline_comparison": _comparison(failing),
        }

    summary = regrade.summarize(
        [output("r1", ORACLE_FAILS), output("r2", UNMODIFIED)], {}, "bench", scoring=data
    )
    (cohort,) = summary["cohorts"]
    assert cohort["net_card_score"] == {
        "mean_score": 0.5,
        "mean_implemented": 1.0,
        "mean_fixed": 0.5,
        "mean_broken": 0.0,
        "scored_runs": 2,
    }
    assert summary["scoring_data_digest"] == data.digest
    assert (
        "net_card_score" not in regrade.summarize([output("r1", set())], {}, "bench")["cohorts"][0]
    )
