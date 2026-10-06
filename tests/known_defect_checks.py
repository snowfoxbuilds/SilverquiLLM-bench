"""Platform Test checks of a benchmark against its Known Defect manifest.

Two CI checks apply to every benchmark built from the Known-Best Workspace
(``docs/specs/KNOWN-BEST-ENGINE.md`` → Known Defects):

1. :func:`oracle_problems` — the Test Oracle Workspace passes every Audited Test of all
   three dimensions.
2. :func:`workspace_problems` — the unmodified Workspace fails exactly the Audited Tests
   the manifest lists, and passes the rest of the regression suites.

Each call grades one dimension in-process, so a Platform Test parametrized over
dimensions stays within the pytest timeout. ``[]`` means the check passes.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from silverquillm import evaluator
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
    REGRESSION_DIMENSIONS,
    KnownDefectsError,
    Outcomes,
    card_outcomes,
    engine_outcomes,
    load_known_defects,
)

DIMENSIONS = ("card_correctness", *REGRESSION_DIMENSIONS)


def audited_outcomes(benchmark, workspace: Path, dimension: str, *, timeout: int = 240) -> Outcomes:
    """Grade one dimension's Audited Tests against ``workspace``, as ``evaluate_run`` does."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}")
    paths = resolve_eval_paths(benchmark.root, benchmark.target_set)
    overlay_root = tempfile.mkdtemp(prefix="known_defect_overlay_")
    overlay = Path(overlay_root) / "workspace"
    token = evaluator._BENCHMARK_DATA_ROOT.set(benchmark.root.parent.parent.resolve())
    try:
        shutil.copytree(workspace, overlay, ignore=_GRADING_IGNORE)
        if dimension == "engine_regression":
            return engine_outcomes(
                _eval_engine(
                    overlay / "engine",
                    paths.engine_tests,
                    timeout=timeout,
                    support_dir=paths.engine_support,
                    test_utils=paths.test_utils, test_interface=paths.test_interface,
                )
            )
        if dimension == "card_correctness":
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


def oracle_problems(benchmark, dimension: str, *, timeout: int = 240) -> list[str]:
    """CI check 1 for one dimension: the Test Oracle Workspace passes every Audited Test."""
    oracle = benchmark.root / "data/test_oracle_workspace"
    if not oracle.is_dir():
        return [f"no Test Oracle Workspace at {oracle}"]
    outcomes = audited_outcomes(benchmark, oracle, dimension, timeout=timeout)
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


def workspace_problems(benchmark, dimension: str, *, timeout: int = 240) -> list[str]:
    """CI check 2 for one regression suite: the unmodified Workspace fails exactly the
    manifest's listed Audited Tests and passes the rest."""
    if dimension not in REGRESSION_DIMENSIONS:
        raise ValueError(f"not a regression dimension: {dimension!r}")
    try:
        manifest = load_known_defects(benchmark.root)
    except KnownDefectsError as error:
        return [str(error)]
    if manifest is None:
        return [f"no Known Defect manifest at {benchmark.root / MANIFEST}"]
    outcomes = audited_outcomes(benchmark, benchmark.root / "workspace", dimension, timeout=timeout)
    expected = manifest.failing_tests(dimension)
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
