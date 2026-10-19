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
    suite_outcomes,
)

from . import known_defect_fixture as fixture
from .known_defect_checks import (
    audited_outcomes,
    defect_problems,
    implementation_problems,
    oracle_problems,
    workspace_problems,
)

EXAMPLE = {
    "schema_version": 2,
    "benchmark": "fra-hard",
    "defects": [
        {
            "id": "zone-change-keeps-status",
            "description": "A permanent that changes zones stays the same object.",
            "rules": ["CR 400.7", "CR 603.10a"],
            "kind": "inherited",
            "failing_tests": {
                "engine": ["zone_change/test_lki.py::test_counters_reset"],
                "fdn": ["fdn_66/tests.py::test_dies_returns_with_one_fewer_revival"],
            },
            "target_tests": ["hob_86/tests.py::test_a_sacrificed_food_is_a_creature_card_again"],
            "host_card": "fdn_122",
        },
        {
            "id": "seeded-first-strike",
            "description": "First strike damage is dealt in the regular step.",
            "rules": ["CR 510.4"],
            "kind": "seeded",
            "failing_tests": {
                "engine": [
                    "test_combat.py::test_first_strike_damage",
                    "zone_change/test_lki.py::test_counters_reset",
                ],
            },
            "target_tests": [],
            "host_card": None,
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
    assert manifest.schema_version == 2
    assert manifest.failing_tests("engine") == {
        "zone_change/test_lki.py::test_counters_reset",
        "test_combat.py::test_first_strike_damage",
    }
    assert manifest.failing_tests("fdn") == {
        "fdn_66/tests.py::test_dies_returns_with_one_fewer_revival"
    }
    related, unrelated = manifest.defects
    assert related.related and related.host_card == "fdn_122"
    assert related.target_tests == (
        "hob_86/tests.py::test_a_sacrificed_food_is_a_creature_card_again",
    )
    assert not unrelated.related and unrelated.host_card is None
    assert not related.hosted_on_target and not unrelated.hosted_on_target
    with pytest.raises(ValueError):
        manifest.failing_tests("fdn_regression")


def test_a_target_may_host_a_defect_its_own_tests_depend_on(tmp_path: Path):
    value = copy.deepcopy(EXAMPLE)
    value["defects"][0].update(
        target_tests=["hob_76/tests.py::test_x_two_exiles_two", "hob_76/tests.py::test_x_paid"],
        host_card="hob_76",
    )
    defect = load_known_defects(manifest_root(tmp_path, value)).defects[0]
    assert defect.related and defect.hosted_on_target and defect.host_card == "hob_76"


def test_a_schema_version_1_manifest_keeps_its_keys_and_has_no_related_defects(tmp_path):
    """fra-hard v1 froze with schema version 1 (KNOWN-BEST-ENGINE.md → Manifest)."""
    value = copy.deepcopy(SCHEMA_1)
    manifest = load_known_defects(manifest_root(tmp_path, value))
    assert manifest.schema_version == 1
    assert manifest.failing_tests("engine") == {"test_combat.py::test_first_strike_damage"}
    assert manifest.failing_tests("fdn") == {"fdn_66/tests.py::test_x"}
    assert not any(defect.related for defect in manifest.defects)


SCHEMA_1 = {
    "schema_version": 1,
    "benchmark": "fra-hard",
    "defects": [
        {
            "id": "seeded-first-strike",
            "description": "First strike damage is dealt in the regular step.",
            "rules": ["CR 510.4"],
            "kind": "seeded",
            "failing_tests": {
                "engine_regression": ["test_combat.py::test_first_strike_damage"],
                "fdn_regression": ["fdn_66/tests.py::test_x"],
            },
        }
    ],
}


@pytest.mark.parametrize(
    ("damage", "field"),
    [
        (lambda d: d.__setitem__("target_tests", []), "must have exactly"),
        (lambda d: d["failing_tests"].__setitem__("fdn", ["fdn_66/tests.py::test_y"]), "unknown suite"),
    ],
)
def test_a_schema_version_1_manifest_rejects_schema_version_2_fields(tmp_path, damage, field):
    value = copy.deepcopy(SCHEMA_1)
    damage(value["defects"][0])
    with pytest.raises(KnownDefectsError, match=field):
        load_known_defects(manifest_root(tmp_path, value))


def test_a_manifest_without_defects_is_valid(tmp_path):
    root = manifest_root(tmp_path, {**EXAMPLE, "defects": []})
    assert load_known_defects(root).failing_tests("engine") == frozenset()


def _defect(change):
    def damage(value):
        change(value["defects"][0])

    return damage


def _set(key, item):
    return lambda value: value.__setitem__(key, item)


def _without(key):
    return lambda value: value.pop(key)


def _engine(node):
    return _defect(lambda defect: defect["failing_tests"].__setitem__("engine", [node]))


@pytest.mark.parametrize(
    ("damage", "field"),
    [
        (_set("schema_version", 3), "schema_version"),
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
            "unknown suite",
        ),
        (
            _defect(lambda d: d["failing_tests"].__setitem__("fdn_regression", ["fdn_66/tests.py::t"])),
            "unknown suite",
        ),
        (
            _defect(lambda d: d["failing_tests"].__setitem__("fdn", [])),
            "failing_tests.fdn",
        ),
        (_defect(lambda d: d.pop("target_tests")), "must have exactly"),
        (_defect(lambda d: d.pop("host_card")), "must have exactly"),
        (_defect(lambda d: d.__setitem__("target_tests", "hob_86/tests.py::t")), "target_tests"),
        (_defect(lambda d: d.__setitem__("target_tests", ["hob_86::t"])), "target_tests: malformed"),
        (
            _defect(lambda d: d.__setitem__("target_tests", ["hob_86/tests.py::t", "hob_86/tests.py::t"])),
            "target_tests must be a list of unique strings",
        ),
        (_defect(lambda d: d.__setitem__("host_card", None)), "host_card must be a card id"),
        (_defect(lambda d: d.__setitem__("host_card", "Kykar")), "host_card must be a card id"),
        (
            lambda value: value["defects"][1].__setitem__("host_card", "fdn_1"),
            "host_card must be null",
        ),
        (
            _defect(
                lambda d: d.update(
                    target_tests=["hob_86/tests.py::t", "hob_76/tests.py::t"], host_card="hob_86"
                )
            ),
            "a target host_card must hold every one",
        ),
        (_engine("test_combat.py"), "malformed Audited Test id"),
        (_engine("../test_combat.py::test_x"), "malformed Audited Test id"),
        (_engine("/abs/test_combat.py::test_x"), "malformed Audited Test id"),
        (_engine("sub\\test_combat.py::test_x"), "malformed Audited Test id"),
        (_engine("test_combat.txt::test_x"), "malformed Audited Test id"),
        (
            _defect(lambda d: d["failing_tests"].__setitem__("fdn", ["fdn_66::test_x"])),
            "malformed Audited Test id",
        ),
        (
            _defect(
                lambda d: d["failing_tests"].__setitem__(
                    "fdn", ["fdn_66/test_other.py::test_x"]
                )
            ),
            "malformed Audited Test id",
        ),
        (
            _defect(
                lambda d: d["failing_tests"].__setitem__(
                    "engine", ["test_a.py::test_x", "test_a.py::test_x"]
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


def test_suite_outcomes_qualify_ids_relative_to_each_suite_root():
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
    outcomes = suite_outcomes(evaluated)
    assert outcomes["fdn"].nodes == {
        "fdn_1/tests.py::TestA::test_a": "pass",
        "fdn_1/tests.py::test_b": "fail",
    }
    assert outcomes["fdn"].collection_failures == [
        "fdn_2/tests.py::<collection-error>",
        "fdn_3/tests.py",
    ]
    assert outcomes["fdn"].errors == ["ImportError: boom"]
    assert outcomes["engine"].nodes == {
        "zone_change/test_lki.py::test_reset": "fail",
        "test_zones.py::TestMove::test_moves": "pass",
    }
    assert outcomes["engine"].collection_failures == [
        "<collection-error>",
        "test_combat.py",
    ]
    assert outcomes["engine"].errors == ["collection broke"]


# --- Platform Test helper on the fixture benchmark -----------------------------------


@pytest.fixture
def kd(tmp_path):
    return load_benchmark(fixture.build(tmp_path), fixture.BENCHMARK)


@pytest.mark.parametrize("suite", ["target", "fdn", "engine"])
def test_the_oracle_passes_every_audited_test(kd, suite):
    assert oracle_problems(kd, suite) == []


@pytest.mark.parametrize("suite", ["fdn", "engine"])
def test_the_workspace_fails_exactly_the_listed_audited_tests(kd, suite):
    assert workspace_problems(kd, suite) == []


def test_the_workspace_outcomes_qualify_ids_as_the_manifest_does(kd):
    fdn = audited_outcomes(kd, kd.root / "workspace", "fdn")
    engine = audited_outcomes(kd, kd.root / "workspace", "engine")
    assert fdn.nodes == {fixture.FDN_NODES[0]: "pass", fixture.FDN_DEFECT: "fail"}
    assert engine.nodes == {fixture.ENGINE_NODES[0]: "pass", fixture.ENGINE_DEFECT: "fail"}


def test_an_unlisted_failure_is_reported(kd):
    value = copy.deepcopy(fixture.MANIFEST)
    value["defects"].pop(0)
    fixture.write_manifest(kd.root, value)
    assert workspace_problems(kd, "engine") == [
        "fails but is not listed: " + fixture.ENGINE_DEFECT
    ]


def test_a_listed_passing_or_unknown_test_is_reported(kd):
    value = copy.deepcopy(fixture.MANIFEST)
    value["defects"][1]["failing_tests"]["fdn"] += [
        fixture.FDN_NODES[0],
        "fdn_1/tests.py::test_missing",
    ]
    fixture.write_manifest(kd.root, value)
    assert workspace_problems(kd, "fdn") == [
        "listed but not an Audited Test: fdn_1/tests.py::test_missing",
        "listed but passes: " + fixture.FDN_NODES[0],
    ]


def test_a_broken_oracle_engine_is_reported(kd):
    (kd.root / "data/test_oracle_workspace/engine/rules.py").write_text(
        fixture.RULES.format(" + 1")
    )
    assert oracle_problems(kd, "engine") == [
        "fails on the Test Oracle Workspace: " + fixture.ENGINE_DEFECT
    ]


def test_a_missing_or_malformed_manifest_is_reported_not_raised(kd):
    path = kd.root / "data/known_defects.json"
    path.write_text("{}")
    [problem] = workspace_problems(kd, "fdn")
    assert problem.startswith(str(path) + ": top level")
    path.unlink()
    assert workspace_problems(kd, "fdn") == [f"no Known Defect manifest at {path}"]


def test_a_card_suite_that_executes_nothing_is_a_collection_failure(kd):
    (kd.root / "data/tests/audited/fdn/fdn_1/tests.py").write_text("import missing_module\n")
    problems = oracle_problems(kd, "fdn")
    assert "collection failure: fdn_1: no executed Audited Tests" in problems
    assert "no executed Audited Tests" in problems


def test_only_the_fdn_and_engine_suites_have_a_manifest_check(kd):
    with pytest.raises(ValueError):
        workspace_problems(kd, "target")


# --- CI check 3: each Known Defect put back into the Test Oracle Workspace ------------

TARGET_TESTS = (
    "from card_impl import effect\nfrom engine.rules import lifegain\n\n\n"
    "def test_effect():\n    assert effect() == 'done'\n\n\n"
    "def test_effect_gains_life():\n    assert lifegain(3) == 3\n"
)
LIFEGAIN_TARGET = "hob_1/tests.py::test_effect_gains_life"


@pytest.fixture
def related(kd, tmp_path):
    """``kd`` with a target-card test that depends on the lifegain defect, which is listed."""
    fixture.write_defect_patches(kd.root)
    (kd.root / "data/tests/audited/hob/hob_1/tests.py").write_text(TARGET_TESTS)
    value = copy.deepcopy(fixture.MANIFEST)
    value["defects"][0].update(target_tests=[LIFEGAIN_TARGET], host_card="fdn_2")
    fixture.write_manifest(kd.root, value)
    return kd


@pytest.mark.parametrize("defect_id", ["lifegain-loses-one", "fdn-1-toughness"])
def test_each_defect_put_back_fails_exactly_its_target_tests(related, tmp_path, defect_id):
    assert defect_problems(related, defect_id, tmp_path) == []


def test_an_unlisted_target_failure_is_reported(related, tmp_path):
    value = copy.deepcopy(fixture.MANIFEST)
    fixture.write_manifest(related.root, value)
    assert defect_problems(related, "lifegain-loses-one", tmp_path) == [
        "fails but is not listed: " + LIFEGAIN_TARGET
    ]


def test_a_listed_target_test_that_passes_is_reported(related, tmp_path):
    value = copy.deepcopy(fixture.MANIFEST)
    value["defects"][1].update(target_tests=["hob_1/tests.py::test_effect"], host_card="fdn_2")
    value["defects"][0].update(target_tests=[LIFEGAIN_TARGET], host_card="fdn_2")
    fixture.write_manifest(related.root, value)
    assert defect_problems(related, "fdn-1-toughness", tmp_path) == [
        "listed but passes: hob_1/tests.py::test_effect"
    ]


def test_an_oracle_variant_patch_takes_precedence(related, tmp_path):
    oracle_variant = related.root / "data/known_defects/oracle/lifegain-loses-one.patch"
    oracle_variant.parent.mkdir()
    oracle_variant.write_text(fixture.DEFECT_PATCHES["fdn-1-toughness"])
    assert defect_problems(related, "lifegain-loses-one", tmp_path) == [
        "listed but passes: " + LIFEGAIN_TARGET
    ]


def test_a_patch_that_does_not_apply_is_reported(related, tmp_path):
    (related.root / "data/known_defects/lifegain-loses-one.patch").write_text(
        fixture.DEFECT_PATCHES["lifegain-loses-one"].replace("return amount\n+", "return 0\n+")
    )
    [problem] = defect_problems(related, "lifegain-loses-one", tmp_path)
    assert "does not apply to the Test Oracle Workspace" in problem


# --- CI check 5: every target card has a counted test the Workspace fails ------------


def test_every_target_fails_a_counted_test_on_the_workspace(kd):
    assert implementation_problems(kd) == []


def test_a_target_the_workspace_already_implements_is_reported(kd):
    (kd.root / "workspace/cards/hob/hob_1/card_impl.py").write_text(fixture.TARGET)
    assert implementation_problems(kd) == [
        "hob_1: no test counting toward it fails on the unmodified Workspace"
    ]


def test_a_target_whose_tests_all_depend_on_a_defect_is_reported(related):
    value = copy.deepcopy(fixture.MANIFEST)
    value["defects"][0].update(
        target_tests=["hob_1/tests.py::test_effect", LIFEGAIN_TARGET], host_card="fdn_2"
    )
    fixture.write_manifest(related.root, value)
    assert implementation_problems(related) == ["hob_1: no test counts toward it"]


def test_a_target_hosting_the_defect_its_tests_depend_on_passes(related):
    (related.root / "workspace/cards/hob/hob_1/card_impl.py").write_text(fixture.TARGET)
    value = copy.deepcopy(fixture.MANIFEST)
    value["defects"][0].update(
        target_tests=["hob_1/tests.py::test_effect", LIFEGAIN_TARGET], host_card="hob_1"
    )
    fixture.write_manifest(related.root, value)
    assert implementation_problems(related) == []
