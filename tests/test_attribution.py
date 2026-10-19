"""Attribution data (``silverquillm/attribution.py``) and Known Defect CI check 4.

Check 4 (KNOWN-BEST-ENGINE.md › Known Defects): every FDN, engine and target-card
Audited Test resolves to exactly one Attributed Card, and every related Known Defect
names a host card.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.attribution import (
    ATTRIBUTION,
    TARGET_ATTRIBUTION,
    AttributionError,
    load_attribution,
)
from silverquillm.evaluator import expected_suite_functions, expected_test_functions
from silverquillm.known_defects import load_known_defects
from silverquillm.tools.oracle_support import load_layout

REPO = Path(__file__).resolve().parents[1]
SCORED = ("smoke", "fra-hard-v2")


def _write(root: Path, engine=None, fdn=None, target=None) -> Path:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / ATTRIBUTION).write_text(json.dumps({"schema_version": 1, "engine": engine or {}, "fdn": fdn or {}}))
    if target is not None:
        (root / TARGET_ATTRIBUTION).write_text(json.dumps({"schema_version": 1, "target": target}))
    return root


def test_the_longest_matching_key_wins(tmp_path: Path) -> None:
    attribution = load_attribution(_write(tmp_path, engine={
        "test_combat.py": "fdn_255",
        "test_combat.py::TestCombatDamage": "fdn_26",
        "test_combat.py::TestCombatDamage::test_trample_excess_damage_to_player": "fdn_246",
    }))
    assert attribution.card("engine", "test_combat.py::TestCanBlock::test_normal_block") == "fdn_255"
    assert attribution.card("engine", "test_combat.py::TestCombatDamage::test_lifelink_gains_life") == "fdn_26"
    assert attribution.card("engine", "test_combat.py::TestCombatDamage::test_trample_excess_damage_to_player") == "fdn_246"


def test_a_parametrized_case_counts_as_its_function(tmp_path: Path) -> None:
    attribution = load_attribution(_write(tmp_path, engine={"test_mana.py::TestPay::test_pays": "fdn_278"}))
    assert attribution.card("engine", "test_mana.py::TestPay::test_pays[W-1]") == "fdn_278"


def test_a_key_matches_only_at_a_file_or_class_boundary(tmp_path: Path) -> None:
    attribution = load_attribution(_write(tmp_path, engine={"test_combat.py::TestCombat": "fdn_255"}))
    assert attribution.card("engine", "test_combat.py::TestCombatDamage::test_x") is None


def test_fdn_and_target_tests_default_to_their_own_card(tmp_path: Path) -> None:
    attribution = load_attribution(_write(
        tmp_path,
        fdn={"fdn_66/tests.py::TestNineLives": "fdn_122"},
        target={"hob_76/tests.py::test_a_pact": "fut_78"},
    ))
    assert attribution.card("fdn", "fdn_66/tests.py::TestNineLives::test_dies") == "fdn_122"
    assert attribution.card("fdn", "fdn_66/tests.py::TestOther::test_x") == "fdn_66"
    assert attribution.card("target", "hob_76/tests.py::test_a_pact") == "fut_78"
    assert attribution.card("target", "hob_76/tests.py::test_other") == "hob_76"


def test_no_target_overrides_file_means_none(tmp_path: Path) -> None:
    attribution = load_attribution(_write(tmp_path))
    assert attribution.target == {}


def test_a_benchmark_without_attribution_data_has_none(tmp_path: Path) -> None:
    assert load_attribution(tmp_path) is None


@pytest.mark.parametrize("document", [
    "not json",
    "[]",
    '{"schema_version": 1, "engine": {}}',
    '{"schema_version": 2, "engine": {}, "fdn": {}}',
    '{"schema_version": true, "engine": {}, "fdn": {}}',
    '{"schema_version": 1, "engine": [], "fdn": {}}',
    '{"schema_version": 1, "engine": {"test_x.py": 3}, "fdn": {}}',
    '{"schema_version": 1, "engine": {"test_x.py": "Plains"}, "fdn": {}}',
    '{"schema_version": 1, "engine": {"../test_x.py": "fdn_272"}, "fdn": {}}',
    '{"schema_version": 1, "engine": {"test_x.py::": "fdn_272"}, "fdn": {}}',
    '{"schema_version": 1, "engine": {}, "fdn": {"tests.py": "fdn_272"}}',
    '{"schema_version": 1, "engine": {}, "fdn": {"fdn_66": "fdn_122"}}',
    '{"schema_version": 1, "engine": {"test_x.py": "fdn_272", "test_x.py": "fdn_274"}, "fdn": {}}',
    '{"schema_version": 1, "engine": {}, "fdn": {}, "extra": 1}',
])
def test_malformed_attribution_data_is_refused(tmp_path: Path, document: str) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / ATTRIBUTION).write_text(document)
    with pytest.raises(AttributionError, match="attribution.json"):
        load_attribution(tmp_path)


def test_a_card_directory_key_is_refused_for_target_overrides(tmp_path: Path) -> None:
    """A key ends at a file or class boundary, so a bare card directory is no key."""
    _write(tmp_path, target={"hob_76": "fut_78"})
    with pytest.raises(AttributionError, match="malformed key 'hob_76'"):
        load_attribution(tmp_path)


def test_a_linked_attribution_file_is_refused(tmp_path: Path) -> None:
    real = _write(tmp_path / "real")
    (tmp_path / "linked/data").mkdir(parents=True)
    (tmp_path / "linked" / ATTRIBUTION).symlink_to(real / ATTRIBUTION)
    with pytest.raises(AttributionError, match="symlink"):
        load_attribution(tmp_path / "linked")


# ---------------------------------------------------------------------------
# CI check 4, per benchmark scored by the Net Card Score
# ---------------------------------------------------------------------------


def _suite_ids(directory: Path, card: str) -> list[str]:
    path = directory / "tests.py"
    functions = expected_test_functions(path.read_text(), "tests.py")
    assert functions is not None, path
    return [f"{card}/{function}" for function in functions]


def _audited(benchmark: str) -> tuple[dict[str, list[str]], set[str], set[str]]:
    root = REPO / "benchmarks" / benchmark
    layout = load_layout(REPO, benchmark, require_cards=True)
    targets = set(layout.cards)
    base = {path.name for path in (root / "workspace/cards/fdn").iterdir() if (path / "card_spec.json").is_file()}
    audited = root / "data/tests/audited"
    engine = expected_suite_functions(audited / "engine", ["test_*.py"])
    assert engine, audited / "engine"
    fdn = [
        test_id
        for directory in sorted((audited / "fdn").iterdir())
        if (directory / "tests.py").is_file() and directory.name not in targets
        for test_id in _suite_ids(directory, directory.name)
    ]
    target = [test_id for card in layout.cards for test_id in _suite_ids(layout.suite(card).parent, card)]
    return {"engine": engine, "fdn": fdn, "target": target}, base - targets, targets


@pytest.mark.parametrize("benchmark", SCORED)
def test_every_audited_test_resolves_to_one_attributed_card(benchmark: str) -> None:
    attribution = load_attribution(REPO / "benchmarks" / benchmark)
    assert attribution is not None, f"{benchmark} has no {ATTRIBUTION}"
    suites, hosts, targets = _audited(benchmark)
    problems = []
    for suite, test_ids in suites.items():
        allowed = targets if suite == "target" else hosts
        for test_id in test_ids:
            card = attribution.card(suite, test_id)
            if card not in allowed:
                problems.append(f"{suite}: {test_id} -> {card}")
    assert problems == []


@pytest.mark.parametrize("benchmark", SCORED)
def test_every_attribution_key_names_an_audited_test(benchmark: str) -> None:
    """A stale key, left behind when its tests were renamed or removed, attributes nothing."""
    attribution = load_attribution(REPO / "benchmarks" / benchmark)
    suites, _, _ = _audited(benchmark)
    stale = []
    for suite, keys in (("engine", attribution.engine), ("fdn", attribution.fdn), ("target", attribution.target)):
        ids = [test_id.split("[", 1)[0] for test_id in suites[suite]]
        for key in keys:
            if not any(test_id == key or test_id.startswith(key + "::") for test_id in ids):
                stale.append(f"{suite}: {key}")
    assert stale == []


@pytest.mark.parametrize("benchmark", SCORED)
def test_every_related_known_defect_names_a_host_card(benchmark: str) -> None:
    manifest = load_known_defects(REPO / "benchmarks" / benchmark)
    assert manifest is not None and manifest.schema_version == 2
    _, hosts, targets = _audited(benchmark)
    assert [
        defect.id
        for defect in manifest.defects
        if defect.related and defect.host_card not in (targets if defect.hosted_on_target else hosts)
    ] == []
    assert [defect.id for defect in manifest.defects if not defect.related and defect.host_card is not None] == []


@pytest.mark.parametrize("benchmark", SCORED)
def test_a_related_defects_mechanic_shares_its_host_card(benchmark: str) -> None:
    """A mechanic's Collateral Tests and its own Known Defect's Dependency Tests are one
    mechanic on one card, so the defect's engine tests are attributed to its host card.
    A defect hosted on a target is part of implementing that target instead, and its
    mechanic's Collateral Tests stay on a base Workspace card."""
    root = REPO / "benchmarks" / benchmark
    attribution, manifest = load_attribution(root), load_known_defects(root)
    elsewhere = [
        f"{defect.id}: {test_id} -> {attribution.card('engine', test_id)}, not {defect.host_card}"
        for defect in manifest.defects
        if defect.related and not defect.hosted_on_target
        for test_id in defect.failing_tests.get("engine", ())
        if attribution.card("engine", test_id) != defect.host_card
    ]
    assert elsewhere == []
