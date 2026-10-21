"""The Net Card Score: working cards gained, derived from a grade when read (ADR-020).

``docs/specs/SCORING.md`` defines it::

    (Cards Implemented + Cards Fixed - Cards Broken)
        / (target cards + other cards hosting related Known Defects)

A related Known Defect hosted on a target card is part of implementing that card, so its
Dependency Tests count toward Cards Implemented rather than Cards Fixed.

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


class MalformedGrade(ValueError):
    """A grade whose nested structure is not the shape its readers consume."""


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


def _mapping(value: Any, where: str) -> Mapping:
    """``value`` as an object; an omitted (``None``) value reads as empty."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise MalformedGrade(f"{where} must be an object")
    return value


def _rows(value: Any, where: str) -> list[Mapping]:
    """``value`` as a list of objects; an omitted (``None``) value reads as empty."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise MalformedGrade(f"{where} must be a list")
    for i, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise MalformedGrade(f"{where}[{i}] must be an object")
    return list(value)


def _test_node(row: Mapping, where: str) -> str:
    node = row.get("test_node")
    if not isinstance(node, str):
        raise MalformedGrade(f"{where}.test_node must be a string")
    return node


def _card_suite(value: Any, where: str) -> tuple[dict[str, str], list[str]]:
    nodes: dict[str, str] = {}
    not_run: list[str] = []
    cards = _mapping(_mapping(value, where).get("cards"), f"{where}.cards")
    for card_id, card in cards.items():
        at = f"{where}.cards.{card_id}"
        card = _mapping(card, at)
        for i, node in enumerate(_rows(card.get("test_nodes"), f"{at}.test_nodes")):
            _add(nodes, not_run, f"{card_id}/{_test_node(node, f'{at}.test_nodes[{i}]')}", node)
        for i, row in enumerate(_rows(card.get("not_run"), f"{at}.not_run")):
            if row.get("reason") != _GRADING_NOT_RUN:
                not_run.append(f"{card_id}/{_test_node(row, f'{at}.not_run[{i}]')}")
    return nodes, not_run


def _engine_suite(value: Any, where: str) -> tuple[dict[str, str], list[str]]:
    nodes: dict[str, str] = {}
    not_run: list[str] = []
    value = _mapping(value, where)
    for i, node in enumerate(_rows(value.get("test_nodes"), f"{where}.test_nodes")):
        _add(nodes, not_run, _test_node(node, f"{where}.test_nodes[{i}]"), node)
    for i, row in enumerate(_rows(value.get("not_run"), f"{where}.not_run")):
        if row.get("reason") != _GRADING_NOT_RUN:
            not_run.append(_test_node(row, f"{where}.not_run[{i}]"))
    return nodes, not_run


def _add(nodes: dict[str, str], not_run: list[str], test_id: str, node: Mapping) -> None:
    if "::" not in test_id or "<collection-error>" in test_id:
        not_run.append(test_id)
    elif test_id not in nodes:
        nodes[test_id] = "pass" if node.get("outcome") == "pass" else "fail"


def _unevaluated(value: Any, where: str) -> bool:
    """A suite the bench could not grade, as opposed to one that scored zero."""
    value = _mapping(value, where)
    if not value:
        return True
    if value.get("evaluated") is True:
        return False
    rows = _rows(value.get("not_run"), f"{where}.not_run")
    for card_id, card in _mapping(value.get("cards"), f"{where}.cards").items():
        rows.extend(
            _rows(
                _mapping(card, f"{where}.cards.{card_id}").get("not_run"),
                f"{where}.cards.{card_id}.not_run",
            )
        )
    return not rows or any(row.get("reason") == _GRADING_NOT_RUN for row in rows)


def _comparison(value: Any) -> Mapping[str, Any] | None:
    """A baseline comparison under its current names; a schema 2 ``combined_regression``
    keeps ``regressed``/``test_nodes`` under the retired suite keys.

    Only a grade with no comparison at all reads as None, and a suite the broken tests
    omit broke nothing. Every value present must have the shape the bench writes, so a
    damaged comparison is never read as one that found nothing broken.
    """
    if value is None:
        return None
    where = "baseline comparison"
    if not isinstance(value, Mapping):
        raise MalformedGrade(f"{where} must be an object")
    available = value.get("available")
    if not isinstance(available, bool):
        raise MalformedGrade(f"{where}.available must be a boolean")
    if not available:
        reason = value.get("reason")
        if not isinstance(reason, str):
            raise MalformedGrade(f"{where}.reason must be a string")
        return {"available": False, "reason": _RETIRED_REASONS.get(reason, reason)}
    if "broken" in value:
        broken = _container(value["broken"], f"{where}.broken")
        suites = {suite: (suite, f"{where}.broken.{suite}") for suite in ("fdn", "engine")}
    elif "regressed" in value:
        regressed = _container(value["regressed"], f"{where}.regressed")
        if "test_nodes" not in regressed:
            raise MalformedGrade(f"{where}.regressed.test_nodes is missing")
        broken = _container(regressed["test_nodes"], f"{where}.regressed.test_nodes")
        suites = {
            new: (old, f"{where}.regressed.test_nodes.{old}")
            for old, new in _RETIRED_COMPARISON_KEYS.items()
        }
    else:
        raise MalformedGrade(f"{where} has no broken tests")
    return {
        "available": True,
        "broken": {suite: _ids(broken, key, at) for suite, (key, at) in suites.items()},
    }


def _container(value: Any, where: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise MalformedGrade(f"{where} must be an object")
    return value


def _ids(container: Mapping, key: str, where: str) -> list[str]:
    """The test ids under ``key``; a suite the container omits broke nothing."""
    if key not in container:
        return []
    value = container[key]
    if not isinstance(value, list) or not all(isinstance(test, str) for test in value):
        raise MalformedGrade(f"{where} must be a list of test ids")
    return list(value)


def _grade(scores: Any, keys: Mapping[str, str], comparison: Any) -> Grade:
    scores = _mapping(scores, "scores")
    nodes, not_run, unevaluated = {}, {}, set()
    for suite, key in keys.items():
        reader = _engine_suite if suite == "engine" else _card_suite
        suite_nodes, suite_not_run = reader(scores.get(key), f"scores.{key}")
        nodes[suite], not_run[suite] = suite_nodes, tuple(suite_not_run)
        if _unevaluated(scores.get(key), f"scores.{key}"):
            unevaluated.add(suite)
    return Grade(nodes, not_run, frozenset(unevaluated), _comparison(comparison))


def record_grade(manifest: Any, scores: Any) -> Grade:
    """The grade of a Run Record, keyed by its schema version.

    Raises MalformedGrade when a structure the score reads has the wrong shape.
    """
    manifest = _mapping(manifest, "manifest")
    metadata = _mapping(manifest.get("run_metadata"), "manifest.run_metadata")
    comparison = metadata.get("baseline_comparison", metadata.get("combined_regression"))
    return _grade(scores, suite_keys(manifest.get("schema_version")), comparison)


def regrade_grade(output: Any) -> Grade:
    """The grade of a regrade output; outputs carry no schema version, so the suite names
    its scores use decide.

    Raises MalformedGrade when a structure the score reads has the wrong shape.
    """
    output = _mapping(output, "regrade output")
    scores = _mapping(output.get("scores"), "scores")
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
    # Card -> (suite, test id) of every Dependency Test counting toward it.
    dependencies: dict[str, set[tuple[str, str]]] = {}
    target_dependencies: set[str] = set()
    for defect in defects:
        if not defect.related:
            continue
        hosted = dependencies.setdefault(defect.host_card, set())
        for suite, tests in defect.failing_tests.items():
            hosted.update((suite, test) for test in tests if (suite, test) not in unrelated)
        for test in defect.target_tests:
            # A defect hosted on a target is part of implementing the targets, so each
            # of its target-card tests counts toward the target doing most of the work.
            card = attribution.card("target", test) if defect.host_card in targets else defect.host_card
            dependencies.setdefault(card, set()).add(("target", test))
        target_dependencies.update(defect.target_tests)
    left_out = sorted(f"{suite}:{test}" for suite, test in unrelated)

    failing: dict[str, dict[str, list[str]]] = {}

    def fail(card: str, kind: str, test_id: str) -> None:
        failing.setdefault(card, {}).setdefault(kind, []).append(test_id)

    not_run = {
        suite: frozenset(_function(t) for t in grade.not_run[suite]) for suite in grade.nodes
    }

    # Implementation Tests: every target-card test that is not a Dependency Test. A
    # manifest entry naming a parametrized case covers that case only; a bare function
    # covers all its cases, and is the only entry that covers the function not running.
    dependency_functions = {test for test in target_dependencies if "[" not in test}

    def is_dependency(test_id: str) -> bool:
        return test_id in target_dependencies or _function(test_id) in dependency_functions

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
    dependencies_pass = {}
    for host in sorted(dependencies):
        dependencies_pass[host] = True
        for suite, test_id in sorted(dependencies[host]):
            if not _passes(test_id, grade.nodes[suite], not_run[suite]):
                dependencies_pass[host] = False
                fail(host, "dependency", f"{suite}:{test_id}")

    implemented = []
    for card in sorted(targets):
        tests = implementation.get(card, [])
        for test_id, passed in tests:
            if not passed:
                fail(card, "implementation", test_id)
        if (
            (tests or card in dependencies)
            and all(passed for _, passed in tests)
            and dependencies_pass.get(card, True)
        ):
            implemented.append(card)

    hosts = sorted(set(dependencies) - targets)
    fixed = [host for host in hosts if dependencies_pass[host]]

    broken = set()
    for suite in ("fdn", "engine"):
        for test_id in grade.comparison["broken"].get(suite, ()):
            card = attribution.card(suite, test_id)
            if card is None:
                card = f"unattributed:{test_id.split('::', 1)[0]}"
            broken.add(card)
            fail(card, "collateral", f"{suite}:{test_id}")

    denominator = len(targets) + len(hosts)
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
        "host_cards": hosts,
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
            try:
                grade = (
                    record_grade(manifest, scores) if kind == "record" else regrade_grade(document)
                )
            except MalformedGrade:
                yield {**row, **unavailable("unreadable_grade", data)}
                continue
            yield {**row, **derive(grade, data)}
