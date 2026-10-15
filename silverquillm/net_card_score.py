"""The Net Card Score: working cards gained, derived from a grade when read (ADR-020).

``docs/specs/SCORING.md`` defines it::

    (Cards Implemented + Cards Fixed - Cards Broken)
        / (target cards + cards hosting related Known Defects)

It is a pure function of a grade's per-test outcomes and baseline comparison, the
benchmark's Known Defect manifest and its attribution data, so it is never stored: a
corrected attribution changes the score without a regrade. Every derived score names the
digest of the scoring data it used.

A grade is a Run Record (schema 3 keys ``target``/``fdn``/``engine`` and
``baseline_comparison``; schema 2 and earlier ``card_correctness``/``fdn_regression``/
``engine_regression`` and ``combined_regression``) or a regrade output (its ``scores`` and
top-level comparison, either naming).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from silverquillm.attribution import ATTRIBUTION, TARGET_ATTRIBUTION, Attribution, load_attribution
from silverquillm.karn.definition import KarnError, read_regular, strict_json
from silverquillm.known_defects import MANIFEST, KnownDefects, load_known_defects
from silverquillm.results_repo import RETIRED_SUITE_KEYS, suite_keys

SCORING_FILES = (MANIFEST, ATTRIBUTION, TARGET_ATTRIBUTION)
_RETIRED_COMPARISON_KEYS = {old: new for new, old in RETIRED_SUITE_KEYS.items()}
_RETIRED_REASONS = {"regression_not_evaluated": "suite_not_evaluated"}
_GRADING_NOT_RUN = "grading_support_missing"


class ScoringDataError(ValueError):
    """Scoring data that cannot be used; the message says why."""


@dataclass(frozen=True)
class ScoringData:
    """What a benchmark's Net Card Score is derived from besides the grade."""

    benchmark: str
    targets: tuple[str, ...]
    defects: KnownDefects
    attribution: Attribution
    digest: str
    """``sha256:`` over the manifest and both attribution files as read."""


@dataclass(frozen=True)
class Grade:
    """The per-test outcomes of one grading, by suite, with test ids qualified as in the
    manifest: ``<card_id>/<node>`` for card suites, the node id for the engine suite."""

    nodes: Mapping[str, Mapping[str, str]]
    """Suite -> executed test id -> ``pass`` | ``fail``."""
    not_run: Mapping[str, tuple[str, ...]]
    """Suite -> expected test functions that did not run, and collection failures."""
    unevaluated: frozenset[str]
    """Suites the bench could not grade at all."""
    comparison: Mapping[str, Any] | None
    """The baseline comparison under its current names, or None when the grade has none."""


def scoring_data_digest(benchmark_root: Path) -> str:
    digest = hashlib.sha256()
    for relative in SCORING_FILES:
        path = Path(benchmark_root) / relative
        digest.update(str(relative).encode() + b"\0")
        if path.is_file() and not path.is_symlink():
            content = path.read_bytes()
            digest.update(str(len(content)).encode() + b"\0" + content)
        else:
            digest.update(b"absent\0")
    return "sha256:" + digest.hexdigest()


def load_scoring_data(benchmark_root: Path, targets: Iterable[str]) -> ScoringData | None:
    """The benchmark's scoring data, or None for a benchmark the Net Card Score does not
    cover: one without attribution data or a schema version 2 Known Defect manifest.

    Raises ScoringDataError when the data is present but malformed.
    """
    benchmark_root = Path(benchmark_root)
    try:
        attribution = load_attribution(benchmark_root)
        defects = load_known_defects(benchmark_root)
    except ValueError as error:
        raise ScoringDataError(str(error)) from None
    if attribution is None or defects is None or defects.schema_version < 2:
        return None
    return ScoringData(
        benchmark=defects.benchmark,
        targets=tuple(sorted(targets)),
        defects=defects,
        attribution=attribution,
        digest=scoring_data_digest(benchmark_root),
    )


def benchmark_scoring_data(bench_root: Path, benchmark_id: str) -> ScoringData | None:
    """``load_scoring_data`` for a benchmark of the bench checkout at ``bench_root``."""
    from silverquillm.benchmark_targets import target_cards
    from silverquillm.evaluator import _target_card_id
    from silverquillm.karn.benchmark import load_benchmark

    benchmark = load_benchmark(bench_root, benchmark_id)
    audited = benchmark.root / "data/tests/audited"
    targets = [
        _target_card_id(card_set, number, audited / card_set)
        for card_set, number in target_cards(benchmark.target_set, benchmark.cards)
    ]
    return load_scoring_data(benchmark.root, targets)


def _mapping(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _card_suite(value: Any) -> tuple[dict[str, str], list[str]]:
    nodes: dict[str, str] = {}
    not_run: list[str] = []
    for card_id, card in _mapping(_mapping(value).get("cards")).items():
        for node in _mapping(card).get("test_nodes") or ():
            _add(nodes, not_run, f"{card_id}/{_mapping(node).get('test_node')}", node)
        for row in _mapping(card).get("not_run") or ():
            if _mapping(row).get("reason") != _GRADING_NOT_RUN:
                not_run.append(f"{card_id}/{_mapping(row).get('test_node')}")
    return nodes, not_run


def _engine_suite(value: Any) -> tuple[dict[str, str], list[str]]:
    nodes: dict[str, str] = {}
    not_run: list[str] = []
    for node in _mapping(value).get("test_nodes") or ():
        _add(nodes, not_run, str(_mapping(node).get("test_node")), node)
    for row in _mapping(value).get("not_run") or ():
        if _mapping(row).get("reason") != _GRADING_NOT_RUN:
            not_run.append(str(_mapping(row).get("test_node")))
    return nodes, not_run


def _add(nodes: dict[str, str], not_run: list[str], test_id: str, node: Any) -> None:
    if "::" not in test_id or "<collection-error>" in test_id:
        not_run.append(test_id)
    elif test_id not in nodes:
        nodes[test_id] = "pass" if _mapping(node).get("outcome") == "pass" else "fail"


def _unevaluated(value: Any) -> bool:
    """A suite the bench could not grade, as opposed to one that scored zero."""
    value = _mapping(value)
    if not value:
        return True
    if value.get("evaluated") is True:
        return False
    rows = list(value.get("not_run") or ())
    for card in _mapping(value.get("cards")).values():
        rows.extend(_mapping(card).get("not_run") or ())
    return not rows or any(_mapping(row).get("reason") == _GRADING_NOT_RUN for row in rows)


def _comparison(value: Any) -> Mapping[str, Any] | None:
    """A baseline comparison under its current names; a schema 2 ``combined_regression``
    keeps ``regressed``/``test_nodes`` under the retired suite keys."""
    if not isinstance(value, Mapping):
        return None
    if value.get("available") is not True:
        reason = value.get("reason")
        return {"available": False, "reason": _RETIRED_REASONS.get(reason, reason)}
    if "broken" in value:
        return {
            "available": True,
            "broken": {suite: list(value["broken"].get(suite, ())) for suite in ("fdn", "engine")},
        }
    retired = _mapping(_mapping(value.get("regressed")).get("test_nodes"))
    broken = {new: list(retired.get(old, ())) for old, new in _RETIRED_COMPARISON_KEYS.items()}
    return {
        "available": True,
        "broken": {suite: broken.get(suite, []) for suite in ("fdn", "engine")},
    }


def _grade(scores: Any, keys: Mapping[str, str], comparison: Any) -> Grade:
    scores = _mapping(scores)
    nodes, not_run, unevaluated = {}, {}, set()
    for suite, key in keys.items():
        reader = _engine_suite if suite == "engine" else _card_suite
        suite_nodes, suite_not_run = reader(scores.get(key))
        nodes[suite], not_run[suite] = suite_nodes, tuple(suite_not_run)
        if _unevaluated(scores.get(key)):
            unevaluated.add(suite)
    return Grade(nodes, not_run, frozenset(unevaluated), _comparison(comparison))


def record_grade(manifest: Any, scores: Any) -> Grade:
    """The grade of a Run Record, keyed by its schema version."""
    manifest = _mapping(manifest)
    metadata = _mapping(manifest.get("run_metadata"))
    comparison = metadata.get("baseline_comparison", metadata.get("combined_regression"))
    return _grade(scores, suite_keys(manifest.get("schema_version")), comparison)


def regrade_grade(output: Any) -> Grade:
    """The grade of a regrade output; outputs carry no schema version, so the suite names
    its scores use decide."""
    output = _mapping(output)
    scores = _mapping(output.get("scores"))
    keys = suite_keys(3 if "target" in scores else 2)
    comparison = output.get("baseline_comparison", output.get("combined_regression"))
    return _grade(scores, keys, comparison)


def _matches(test_id: str, nodes: Mapping[str, str]) -> list[str]:
    """The executed nodes of ``test_id``: itself, or its parametrized cases."""
    if test_id in nodes:
        return [test_id]
    return [node for node in nodes if node.startswith(test_id + "[")]


def _passes(test_id: str, nodes: Mapping[str, str], not_run: frozenset[str]) -> bool:
    matched = _matches(test_id, nodes)
    return (
        bool(matched)
        and all(nodes[node] == "pass" for node in matched)
        and _function(test_id) not in not_run
    )


def _function(test_id: str) -> str:
    return test_id.split("[", 1)[0]


def unavailable(reason: str, data: ScoringData | None = None) -> dict:
    result = {"available": False, "reason": reason}
    if data is not None:
        result["scoring_data_digest"] = data.digest
    return result


def derive(grade: Grade, data: ScoringData | None) -> dict:
    """The Net Card Score of ``grade`` on ``data``'s benchmark, or why it is unavailable."""
    if data is None:
        return unavailable("no_scoring_data")
    if grade.comparison is None:
        return unavailable("no_baseline_comparison", data)
    if grade.comparison.get("available") is not True:
        return unavailable(str(grade.comparison.get("reason")), data)
    if "target" in grade.unevaluated:
        return unavailable("suite_not_evaluated", data)

    defects, attribution, targets = data.defects.defects, data.attribution, set(data.targets)
    unrelated = {
        (suite, test)
        for defect in defects
        if not defect.related
        for suite, tests in defect.failing_tests.items()
        for test in tests
    }
    # Host card -> (suite, test id) of every Dependency Test counting toward it.
    dependencies: dict[str, set[tuple[str, str]]] = {}
    target_dependencies: set[str] = set()
    for defect in defects:
        if not defect.related:
            continue
        hosted = dependencies.setdefault(defect.host_card, set())
        for suite, tests in defect.failing_tests.items():
            hosted.update((suite, test) for test in tests if (suite, test) not in unrelated)
        hosted.update(("target", test) for test in defect.target_tests)
        target_dependencies.update(defect.target_tests)
    left_out = sorted(f"{suite}:{test}" for suite, test in unrelated)

    failing: dict[str, dict[str, list[str]]] = {}

    def fail(card: str, kind: str, test_id: str) -> None:
        failing.setdefault(card, {}).setdefault(kind, []).append(test_id)

    not_run = {
        suite: frozenset(_function(t) for t in grade.not_run[suite]) for suite in grade.nodes
    }

    # Implementation Tests: every target-card test that is not a Dependency Test.
    dependency_functions = {_function(test) for test in target_dependencies}

    def is_dependency(test_id: str) -> bool:
        return _function(test_id) in dependency_functions

    implementation: dict[str, list[tuple[str, bool]]] = {}
    target_nodes = grade.nodes["target"]
    for test_id, outcome in target_nodes.items():
        if not is_dependency(test_id):
            card = attribution.card("target", test_id)
            implementation.setdefault(card, []).append((test_id, outcome == "pass"))
    for test_id in grade.not_run["target"]:
        if not is_dependency(test_id):
            implementation.setdefault(attribution.card("target", test_id), []).append(
                (test_id, False)
            )
    implemented = []
    for card in sorted(targets):
        tests = implementation.get(card, [])
        for test_id, passed in tests:
            if not passed:
                fail(card, "implementation", test_id)
        if tests and all(passed for _, passed in tests):
            implemented.append(card)

    fixed = []
    for host in sorted(dependencies):
        passed = True
        for suite, test_id in sorted(dependencies[host]):
            if not _passes(test_id, grade.nodes[suite], not_run[suite]):
                passed = False
                fail(host, "dependency", f"{suite}:{test_id}")
        if passed:
            fixed.append(host)

    broken = set()
    for suite in ("fdn", "engine"):
        for test_id in grade.comparison["broken"].get(suite, ()):
            card = attribution.card(suite, test_id)
            if card is None:
                card = f"unattributed:{test_id.split('::', 1)[0]}"
            broken.add(card)
            fail(card, "collateral", f"{suite}:{test_id}")

    denominator = len(targets) + len(dependencies)
    return {
        "available": True,
        "score": (len(implemented) + len(fixed) - len(broken)) / denominator,
        "cards_implemented": implemented,
        "cards_fixed": fixed,
        "cards_broken": sorted(broken),
        "implemented": len(implemented),
        "fixed": len(fixed),
        "broken": len(broken),
        "denominator": denominator,
        "targets": sorted(targets),
        "host_cards": sorted(dependencies),
        "failing_tests": {card: failing[card] for card in sorted(failing)},
        "dependency_tests_left_out": left_out,
        "scoring_data_digest": data.digest,
    }


GRADE_LIMIT = 64 * 1024 * 1024
_CANDIDATE_HASH = re.compile(r"[0-9a-f]{64}")


def _read(path: Path) -> Any:
    try:
        return strict_json(read_regular(path, limit=GRADE_LIMIT))
    except (KarnError, OSError, ValueError):
        return None


def _grades(path: Path) -> Iterator[tuple[str, Path]]:
    """Each grade under ``path``: a record directory (``manifest.json`` with ``scores.json``
    beside it), a regrade output (``<candidate hash>/<run id>.json``), or a directory of
    either, such as the Results Repo's ``results/`` or a ``regrades/<hex>/``."""
    if path.is_dir() and (path / "manifest.json").is_file():
        yield "record", path
    elif path.is_file():
        if path.name == "manifest.json":
            yield "record", path.parent
        elif path.suffix == ".json":
            yield "regrade", path
    elif path.is_dir():
        for found in sorted(path.rglob("*.json")):
            if found.is_symlink():
                continue
            if found.name == "manifest.json" and (found.parent / "scores.json").is_file():
                yield "record", found.parent
            elif _CANDIDATE_HASH.fullmatch(found.parent.name) and found.stem != "summary":
                yield "regrade", found


def score_paths(paths: Iterable[Path], bench_root: Path) -> Iterator[dict]:
    """The Net Card Score of every grade under ``paths``, one row each, naming the grade."""
    loaded: dict[str, ScoringData | None | str] = {}

    def scoring(benchmark: Any) -> ScoringData | None | str:
        if not isinstance(benchmark, str):
            return None
        if benchmark not in loaded:
            try:
                loaded[benchmark] = benchmark_scoring_data(bench_root, benchmark)
            except ScoringDataError as error:
                loaded[benchmark] = "scoring_data_invalid: " + str(error)
            except (KarnError, OSError, ValueError):
                loaded[benchmark] = None
        return loaded[benchmark]

    for path in paths:
        for kind, found in _grades(Path(path)):
            if kind == "record":
                manifest, scores = _read(found / "manifest.json"), _read(found / "scores.json")
                document = manifest
            else:
                document = _read(found)
            row = {"path": str(found), "kind": kind}
            if not isinstance(document, dict) or (kind == "record" and scores is None):
                yield {**row, "available": False, "reason": "unreadable_grade"}
                continue
            for field in ("run_id", "candidate_hash", "benchmark"):
                row[field] = document.get(field)
            data = scoring(document.get("benchmark"))
            if isinstance(data, str):
                yield {**row, "available": False, "reason": data}
                continue
            grade = record_grade(manifest, scores) if kind == "record" else regrade_grade(document)
            yield {**row, **derive(grade, data)}
