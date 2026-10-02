"""Known Defect manifests, per-test outcomes and the Platform Test checks built on them."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult
from silverquillm.karn.benchmark import load_benchmark
from silverquillm.known_defects import (
    KnownDefects,
    KnownDefectsError,
    has_known_defects_manifest,
    load_known_defects,
    regression_outcomes,
)

from . import known_defect_fixture as fixture
from .known_defect_checks import audited_outcomes, oracle_problems, workspace_problems

EXAMPLE = {
    "schema_version": 1,
    "benchmark": "fra-hard",
    "defects": [
        {
            "id": "zone-change-keeps-status",
            "description": "A permanent that changes zones stays the same object.",
            "rules": ["CR 400.7", "CR 603.10a"],
            "kind": "inherited",
            "failing_tests": {
                "engine_regression": ["zone_change/test_lki.py::test_counters_reset"],
                "fdn_regression": ["fdn_66/tests.py::test_dies_returns_with_one_fewer_revival"],
            },
        },
        {
            "id": "seeded-first-strike",
            "description": "First strike damage is dealt in the regular step.",
            "rules": ["CR 510.4"],
            "kind": "seeded",
            "failing_tests": {
                "engine_regression": [
                    "test_combat.py::test_first_strike_damage",
                    "zone_change/test_lki.py::test_counters_reset",
                ],
            },
        },
    ],
}


def manifest_root(tmp_path: Path, value) -> Path:
    root = tmp_path / "fra-hard"
    (root / "data").mkdir(parents=True)
    (root / "data/known_defects.json").write_text(json.dumps(value))
    return root


def test_an_absent_manifest_loads_as_none(tmp_path):
    assert load_known_defects(tmp_path) is None
    assert has_known_defects_manifest(tmp_path) is False


def test_the_example_manifest_loads_and_unions_failing_tests(tmp_path):
    root = manifest_root(tmp_path, EXAMPLE)
    manifest = load_known_defects(root)
    assert isinstance(manifest, KnownDefects)
    assert has_known_defects_manifest(root)
    assert [defect.id for defect in manifest.defects] == [
        "zone-change-keeps-status",
        "seeded-first-strike",
    ]
    assert manifest.defects[0].rules == ("CR 400.7", "CR 603.10a")
    assert manifest.failing_tests("engine_regression") == {
        "zone_change/test_lki.py::test_counters_reset",
        "test_combat.py::test_first_strike_damage",
    }
    assert manifest.failing_tests("fdn_regression") == {
        "fdn_66/tests.py::test_dies_returns_with_one_fewer_revival"
    }


def test_a_manifest_without_defects_is_valid(tmp_path):
    root = manifest_root(tmp_path, {**EXAMPLE, "defects": []})
    assert load_known_defects(root).failing_tests("engine_regression") == frozenset()


def _defect(change):
    def damage(value):
        change(value["defects"][0])

    return damage


def _set(key, item):
    return lambda value: value.__setitem__(key, item)


def _without(key):
    return lambda value: value.pop(key)


def _engine(node):
    return _defect(lambda defect: defect["failing_tests"].__setitem__("engine_regression", [node]))


@pytest.mark.parametrize(
    ("damage", "field"),
    [
        (_set("schema_version", 2), "schema_version"),
        (_set("schema_version", True), "schema_version"),
        (_set("benchmark", "smoke"), "benchmark"),
        (_set("extra", 1), "top level"),
        (_without("defects"), "top level"),
        (_set("defects", {}), "defects must be a list"),
        (_defect(lambda d: d.__setitem__("component", "engine")), "must have exactly"),
        (_defect(lambda d: d.pop("kind")), "must have exactly"),
        (_defect(lambda d: d.__setitem__("id", "Bad Id")), "id must match"),
        (_defect(lambda d: d.__setitem__("id", "seeded-first-strike")), "id is not unique"),
        (_defect(lambda d: d.__setitem__("description", "  ")), "description"),
        (_defect(lambda d: d.__setitem__("rules", [])), "rules"),
        (_defect(lambda d: d.__setitem__("rules", ["400.7"])), "rules"),
        (_defect(lambda d: d.__setitem__("rules", ["CR 400.7", "CR 400.7"])), "rules"),
        (_defect(lambda d: d.__setitem__("kind", "fuzzed")), "kind"),
        (_defect(lambda d: d.__setitem__("failing_tests", {})), "failing_tests"),
        (
            _defect(lambda d: d["failing_tests"].__setitem__("card_correctness", ["x"])),
            "unknown dimension",
        ),
        (
            _defect(lambda d: d["failing_tests"].__setitem__("fdn_regression", [])),
            "failing_tests.fdn_regression",
        ),
        (_engine("test_combat.py"), "malformed Audited Test id"),
        (_engine("../test_combat.py::test_x"), "malformed Audited Test id"),
        (_engine("/abs/test_combat.py::test_x"), "malformed Audited Test id"),
        (_engine("sub\\test_combat.py::test_x"), "malformed Audited Test id"),
        (_engine("test_combat.txt::test_x"), "malformed Audited Test id"),
        (
            _defect(lambda d: d["failing_tests"].__setitem__("fdn_regression", ["fdn_66::test_x"])),
            "malformed Audited Test id",
        ),
        (
            _defect(
                lambda d: d["failing_tests"].__setitem__(
                    "fdn_regression", ["fdn_66/test_other.py::test_x"]
                )
            ),
            "malformed Audited Test id",
        ),
        (
            _defect(
                lambda d: d["failing_tests"].__setitem__(
                    "engine_regression", ["test_a.py::test_x", "test_a.py::test_x"]
                )
            ),
            "unique strings",
        ),
    ],
)
def test_a_malformed_manifest_names_the_field(tmp_path, damage, field):
    value = copy.deepcopy(EXAMPLE)
    damage(value)
    root = manifest_root(tmp_path, value)
    with pytest.raises(KnownDefectsError, match=field) as raised:
        load_known_defects(root)
    assert str(raised.value).startswith(str(root / "data/known_defects.json") + ": ")


def test_a_malformed_defect_names_its_id(tmp_path):
    value = copy.deepcopy(EXAMPLE)
    value["defects"][1]["kind"] = "fuzzed"
    with pytest.raises(KnownDefectsError, match=r"defects\[1\] \(seeded-first-strike\): kind"):
        load_known_defects(manifest_root(tmp_path, value))


def test_duplicate_keys_and_symlinks_are_rejected(tmp_path):
    root = manifest_root(tmp_path, EXAMPLE)
    path = root / "data/known_defects.json"
    path.write_text(
        '{"schema_version": 1, "schema_version": 1, "benchmark": "fra-hard", "defects": []}'
    )
    with pytest.raises(KnownDefectsError, match="duplicate_json_key"):
        load_known_defects(root)
    real = tmp_path / "elsewhere.json"
    real.write_text(json.dumps(EXAMPLE))
    path.unlink()
    path.symlink_to(real)
    with pytest.raises(KnownDefectsError, match="symlink"):
        load_known_defects(root)


def test_regression_outcomes_qualify_ids_relative_to_each_suite_root():
    evaluated = FullEvalResult(
        fdn_results={
            "fdn_1": CardResult(
                "fdn_1",
                errors=["FAILED tests.py::test_b", "ImportError: boom"],
                test_nodes=[
                    {"test_node": "tests.py::TestA::test_a", "outcome": "pass"},
                    {"test_node": "tests.py::test_b", "outcome": "fail"},
                    {"test_node": "tests.py::test_b", "outcome": "pass"},
                ],
            ),
            "fdn_2": CardResult(
                "fdn_2",
                errors=["ImportError: boom"],
                test_nodes=[{"test_node": "tests.py::<collection-error>", "outcome": "fail"}],
            ),
            "fdn_3": CardResult("fdn_3", test_nodes=[{"test_node": "tests.py", "outcome": "fail"}]),
        },
        engine_result=EngineResult(
            errors=["FAILED zone_change/test_lki.py::test_reset", "collection broke"],
            test_nodes=[
                {"test_node": "zone_change/test_lki.py::test_reset", "outcome": "fail"},
                {"test_node": "test_zones.py::TestMove::test_moves", "outcome": "pass"},
                {"test_node": "test_combat.py", "outcome": "fail"},
                {"test_node": "<collection-error>", "outcome": "fail"},
            ],
        ),
    )
    outcomes = regression_outcomes(evaluated)
    assert outcomes["fdn_regression"].nodes == {
        "fdn_1/tests.py::TestA::test_a": "pass",
        "fdn_1/tests.py::test_b": "fail",
    }
    assert outcomes["fdn_regression"].collection_failures == [
        "fdn_2/tests.py::<collection-error>",
        "fdn_3/tests.py",
    ]
    assert outcomes["fdn_regression"].errors == ["ImportError: boom"]
    assert outcomes["engine_regression"].nodes == {
        "zone_change/test_lki.py::test_reset": "fail",
        "test_zones.py::TestMove::test_moves": "pass",
    }
    assert outcomes["engine_regression"].collection_failures == [
        "<collection-error>",
        "test_combat.py",
    ]
    assert outcomes["engine_regression"].errors == ["collection broke"]


# --- Platform Test helper on the fixture benchmark -----------------------------------


@pytest.fixture
def kd(tmp_path):
    return load_benchmark(fixture.build(tmp_path), fixture.BENCHMARK)


@pytest.mark.parametrize("dimension", ["card_correctness", "fdn_regression", "engine_regression"])
def test_the_oracle_passes_every_audited_test(kd, dimension):
    assert oracle_problems(kd, dimension) == []


@pytest.mark.parametrize("dimension", ["fdn_regression", "engine_regression"])
def test_the_workspace_fails_exactly_the_listed_audited_tests(kd, dimension):
    assert workspace_problems(kd, dimension) == []


def test_the_workspace_outcomes_qualify_ids_as_the_manifest_does(kd):
    fdn = audited_outcomes(kd, kd.root / "workspace", "fdn_regression")
    engine = audited_outcomes(kd, kd.root / "workspace", "engine_regression")
    assert fdn.nodes == {fixture.FDN_NODES[0]: "pass", fixture.FDN_DEFECT: "fail"}
    assert engine.nodes == {fixture.ENGINE_NODES[0]: "pass", fixture.ENGINE_DEFECT: "fail"}


def test_an_unlisted_failure_is_reported(kd):
    value = copy.deepcopy(fixture.MANIFEST)
    value["defects"].pop(0)
    fixture.write_manifest(kd.root, value)
    assert workspace_problems(kd, "engine_regression") == [
        "fails but is not listed: " + fixture.ENGINE_DEFECT
    ]


def test_a_listed_passing_or_unknown_test_is_reported(kd):
    value = copy.deepcopy(fixture.MANIFEST)
    value["defects"][1]["failing_tests"]["fdn_regression"] += [
        fixture.FDN_NODES[0],
        "fdn_1/tests.py::test_missing",
    ]
    fixture.write_manifest(kd.root, value)
    assert workspace_problems(kd, "fdn_regression") == [
        "listed but not an Audited Test: fdn_1/tests.py::test_missing",
        "listed but passes: " + fixture.FDN_NODES[0],
    ]


def test_a_broken_oracle_engine_is_reported(kd):
    (kd.root / "data/test_oracle_workspace/engine/rules.py").write_text(
        fixture.RULES.format(" + 1")
    )
    assert oracle_problems(kd, "engine_regression") == [
        "fails on the Test Oracle Workspace: " + fixture.ENGINE_DEFECT
    ]


def test_a_missing_or_malformed_manifest_is_reported_not_raised(kd):
    path = kd.root / "data/known_defects.json"
    path.write_text("{}")
    [problem] = workspace_problems(kd, "fdn_regression")
    assert problem.startswith(str(path) + ": top level")
    path.unlink()
    assert workspace_problems(kd, "fdn_regression") == [f"no Known Defect manifest at {path}"]


def test_a_card_suite_that_executes_nothing_is_a_collection_failure(kd):
    (kd.root / "data/tests/audited/fdn/fdn_1/tests.py").write_text("import missing_module\n")
    problems = oracle_problems(kd, "fdn_regression")
    assert "collection failure: fdn_1: no executed Audited Tests" in problems
    assert "no executed Audited Tests" in problems


def test_only_regression_dimensions_have_a_manifest_check(kd):
    with pytest.raises(ValueError):
        workspace_problems(kd, "card_correctness")
