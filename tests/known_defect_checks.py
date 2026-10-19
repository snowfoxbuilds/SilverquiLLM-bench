"""Platform Test checks of a benchmark against its Known Defect manifest.

CI checks that apply to every benchmark built from the Known-Best Workspace
(``docs/specs/KNOWN-BEST-ENGINE.md`` → Known Defects):

1. :func:`oracle_problems` — the Test Oracle Workspace passes every Audited Test of all
   three suites.
2. :func:`workspace_problems` — the unmodified Workspace fails exactly the Audited Tests
   the manifest lists, and passes the rest of the FDN and engine suites.
3. :func:`defect_problems` — putting one Known Defect back into the Test Oracle
   Workspace fails exactly the target-card tests its entry lists.
5. :func:`implementation_problems` — every target card has at least one test counting
   toward it that the unmodified Workspace fails, so the unmodified Workspace scores 0.

Each call grades one suite, or one defect's target-card suite, in-process, so a
Platform Test parametrized over them stays within the pytest timeout. ``[]`` means the
check passes.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from silverquillm import evaluator
from silverquillm.attribution import AttributionError, load_attribution
from silverquillm.benchmark_targets import target_cards
from silverquillm.evaluator import (
    _GRADING_IGNORE,
    _eval_audited_dir,
    _eval_engine,
    _eval_target_cards,
    fdn_target_card_ids,
    resolve_eval_paths,
)
from silverquillm.known_defects import (
    MANIFEST,
    SUITES,
    KnownDefectsError,
    Outcomes,
    card_outcomes,
    engine_outcomes,
    load_known_defects,
)
from silverquillm.tools.port_from_known_best import DEFECT_PATCHES, PortError, apply_patch

ORACLE_DEFECT_PATCHES = DEFECT_PATCHES / "oracle"

GRADED_SUITES = ("target", *SUITES)


def audited_outcomes(benchmark, workspace: Path, suite: str, *, timeout: int = 240) -> Outcomes:
    """Grade one suite's Audited Tests against ``workspace``, as ``evaluate_run`` does."""
    if suite not in GRADED_SUITES:
        raise ValueError(f"unknown suite {suite!r}")
    paths = resolve_eval_paths(benchmark.root, benchmark.target_set)
    overlay_root = tempfile.mkdtemp(prefix="known_defect_overlay_")
    overlay = Path(overlay_root) / "workspace"
    token = evaluator._BENCHMARK_DATA_ROOT.set(benchmark.root.parent.parent.resolve())
    try:
        shutil.copytree(workspace, overlay, ignore=_GRADING_IGNORE)
        if suite == "engine":
            return engine_outcomes(
                _eval_engine(
                    overlay / "engine",
                    paths.engine_tests,
                    timeout=timeout,
                    support_dir=paths.engine_support,
                    test_utils=paths.test_utils, test_interface=paths.test_interface,
                )
            )
        if suite == "target":
            results = _eval_target_cards(
                overlay,
                benchmark.target_set,
                list(benchmark.cards),
                paths.audited_target,
                timeout,
                test_utils=paths.test_utils, test_interface=paths.test_interface,
            )
        else:
            results = _eval_audited_dir(
                overlay,
                paths.audited_fdn,
                timeout,
                test_utils=paths.test_utils, test_interface=paths.test_interface,
                exclude=fdn_target_card_ids(
                    benchmark.target_set, benchmark.cards, paths.audited_fdn.parent
                ),
            )
    finally:
        shutil.rmtree(overlay_root, ignore_errors=True)
        evaluator._BENCHMARK_DATA_ROOT.reset(token)
    outcomes = card_outcomes(results)
    silent = [
        f"{card_id}: no executed Audited Tests"
        for card_id in sorted(results)
        if not any(node.startswith(card_id + "/") for node in outcomes.nodes)
    ]
    return Outcomes(
        nodes=outcomes.nodes,
        collection_failures=sorted({*outcomes.collection_failures, *silent}),
        errors=outcomes.errors,
    )


def _grading_problems(outcomes: Outcomes) -> list[str]:
    problems = [] if outcomes.nodes else ["no executed Audited Tests"]
    problems += ["collection failure: " + node for node in outcomes.collection_failures]
    problems += ["grading error: " + error for error in outcomes.errors]
    return problems


def oracle_problems(benchmark, suite: str, *, timeout: int = 240) -> list[str]:
    """CI check 1 for one suite: the Test Oracle Workspace passes every Audited Test."""
    oracle = benchmark.root / "data/test_oracle_workspace"
    if not oracle.is_dir():
        return [f"no Test Oracle Workspace at {oracle}"]
    outcomes = audited_outcomes(benchmark, oracle, suite, timeout=timeout)
    return sorted(
        [
            *_grading_problems(outcomes),
            *(
                "fails on the Test Oracle Workspace: " + node
                for node, outcome in outcomes.nodes.items()
                if outcome == "fail"
            ),
        ]
    )


def workspace_problems(benchmark, suite: str, *, timeout: int = 240) -> list[str]:
    """CI check 2 for the FDN or engine suite: the unmodified Workspace fails exactly the
    manifest's listed Audited Tests and passes the rest."""
    if suite not in SUITES:
        raise ValueError(f"not the FDN or engine suite: {suite!r}")
    try:
        manifest = load_known_defects(benchmark.root)
    except KnownDefectsError as error:
        return [str(error)]
    if manifest is None:
        return [f"no Known Defect manifest at {benchmark.root / MANIFEST}"]
    outcomes = audited_outcomes(benchmark, benchmark.root / "workspace", suite, timeout=timeout)
    expected = manifest.failing_tests(suite)
    return sorted(
        [
            *_grading_problems(outcomes),
            *(
                "listed but not an Audited Test: " + node
                for node in expected
                if node not in outcomes.nodes
            ),
            *(
                "listed but passes: " + node
                for node in expected
                if outcomes.nodes.get(node) == "pass"
            ),
            *(
                "fails but is not listed: " + node
                for node, outcome in outcomes.nodes.items()
                if outcome == "fail" and node not in expected
            ),
        ]
    )


def defect_patch(benchmark_root: Path, defect_id: str) -> Path:
    """The patch that puts ``defect_id`` back into the Test Oracle Workspace: its
    oracle variant when an oracle extension rewrote the code the Workspace patch edits."""
    oracle_variant = benchmark_root / ORACLE_DEFECT_PATCHES / f"{defect_id}.patch"
    if oracle_variant.is_file():
        return oracle_variant
    return benchmark_root / DEFECT_PATCHES / f"{defect_id}.patch"


def defect_problems(benchmark, defect_id: str, scratch: Path, *, timeout: int = 240) -> list[str]:
    """CI check 3 for one Known Defect: put back into a copy of the Test Oracle Workspace
    under ``scratch``, it fails exactly the target-card tests its entry lists."""
    try:
        manifest = load_known_defects(benchmark.root)
    except KnownDefectsError as error:
        return [str(error)]
    if manifest is None:
        return [f"no Known Defect manifest at {benchmark.root / MANIFEST}"]
    if manifest.schema_version < 2:
        return [f"schema version {manifest.schema_version} lists no target_tests"]
    defect = manifest.defect(defect_id)
    oracle = benchmark.root / "data/test_oracle_workspace"
    if not oracle.is_dir():
        return [f"no Test Oracle Workspace at {oracle}"]
    patched = Path(scratch) / f"oracle-with-{defect_id}"
    shutil.copytree(oracle, patched, ignore=_GRADING_IGNORE)
    patch = defect_patch(benchmark.root, defect_id)
    try:
        apply_patch(patched, patch)
    except PortError as error:
        return [
            f"{patch.relative_to(benchmark.root)} does not apply to the Test Oracle Workspace: {error}"
        ]
    try:
        outcomes = audited_outcomes(benchmark, patched, "target", timeout=timeout)
    finally:
        shutil.rmtree(patched, ignore_errors=True)
    expected = set(defect.target_tests)
    return sorted(
        [
            *_grading_problems(outcomes),
            *(
                "listed but not an Audited Test: " + node
                for node in expected
                if node not in outcomes.nodes
            ),
            *(
                "listed but passes: " + node
                for node in expected
                if outcomes.nodes.get(node) == "pass"
            ),
            *(
                "fails but is not listed: " + node
                for node, outcome in outcomes.nodes.items()
                if outcome == "fail" and node not in expected
            ),
        ]
    )


def implementation_problems(benchmark, *, timeout: int = 240) -> list[str]:
    """CI check 5: every target card has at least one test counting toward it that the
    unmodified Workspace fails, so the unmodified Workspace implements no target card.

    A target's counted tests are its Implementation Tests (target-card tests no Known
    Defect makes fail) and, for a related Known Defect hosted on it, that defect's
    Dependency Tests; check 2 holds that the unmodified Workspace fails the latter's FDN
    and engine tests."""
    try:
        manifest = load_known_defects(benchmark.root)
        attribution = load_attribution(benchmark.root)
    except (KnownDefectsError, AttributionError) as error:
        return [str(error)]
    if manifest is None:
        return [f"no Known Defect manifest at {benchmark.root / MANIFEST}"]
    if manifest.schema_version < 2:
        return [f"schema version {manifest.schema_version} lists no target_tests"]
    # As derive counts them: an FDN or engine Dependency Test also listed under an
    # unrelated defect counts toward nothing, and a target-card Dependency Test counts
    # toward the host of every defect listing it.
    unrelated = {
        (suite, test)
        for defect in manifest.defects
        if not defect.related
        for suite, tests in defect.failing_tests.items()
        for test in tests
    }
    target_hosts: dict[str, set[str]] = {}
    for defect in manifest.defects:
        for node in defect.target_tests:
            hosts = target_hosts.setdefault(node, set())
            if defect.hosted_on_target:
                hosts.add(defect.host_card)
    failing: dict[str, int] = {}
    for defect in manifest.defects:
        if defect.hosted_on_target:
            counted = sum(
                (suite, test) not in unrelated
                for suite, tests in defect.failing_tests.items()
                for test in tests
            )
            if counted:
                failing[defect.host_card] = failing.get(defect.host_card, 0) + counted
    outcomes = audited_outcomes(benchmark, benchmark.root / "workspace", "target", timeout=timeout)
    for node, outcome in outcomes.nodes.items():
        listed = node if node in target_hosts else _function(node)
        if listed in target_hosts:
            cards = target_hosts[listed]
        else:
            cards = {attribution.card("target", node) if attribution else node.split("/", 1)[0]}
        for card in cards:
            failing[card] = failing.get(card, 0) + (outcome == "fail")
    targets = sorted(
        f"{code}_{number}" for code, number in target_cards(benchmark.target_set, benchmark.cards)
    )
    return sorted(
        [
            *_grading_problems(outcomes),
            *(f"{card}: no test counts toward it" for card in targets if card not in failing),
            *(
                f"{card}: no test counting toward it fails on the unmodified Workspace"
                for card in targets
                if failing.get(card) == 0
            ),
        ]
    )


def _function(node: str) -> str:
    """A parametrized case counts as its test function."""
    return node.split("[", 1)[0]
