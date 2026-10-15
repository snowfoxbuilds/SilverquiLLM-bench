"""Known Defect manifests and the per-test outcomes they are checked against.

A benchmark built from the Known-Best Workspace lists the Known Defects its Workspace
carries in the host-only ``data/known_defects.json`` (``docs/specs/KNOWN-BEST-ENGINE.md``).
Every per-test id here is qualified relative to its suite's graded root, so the manifest,
the baseline reference grade and the baseline comparison all name a test the same way.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult
from silverquillm.karn.definition import KarnError, read_regular, strict_json

SUITES = ("fdn", "engine")
"""The suites a Known Defect's failing tests sit in: the ``failing_tests`` keys of a
schema version 2 manifest."""
SCHEMA_1_SUITE_KEYS = {"fdn_regression": "fdn", "engine_regression": "engine"}
"""Schema version 1, which fra-hard v1 froze with, keyed ``failing_tests`` by the retired
names (ADR-021)."""
SCHEMA_VERSIONS = (1, 2)
MANIFEST = Path("data/known_defects.json")
MANIFEST_LIMIT = 1024 * 1024
KINDS = ("inherited", "seeded")
DEFECT_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
RULE = re.compile(r"CR \d{3}(\.\d+[a-z]?)?")
FDN_NODE = re.compile(r"[A-Za-z0-9_]+/tests\.py::\S.*")
CARD_ID = re.compile(r"[a-z0-9]+_[0-9]+[a-z]?")


@dataclass(frozen=True)
class Outcomes:
    nodes: Mapping[str, str]
    """Executed qualified id -> ``"pass"`` | ``"fail"``."""
    collection_failures: list[str]
    """Qualified ids that did not execute a test, sorted."""
    errors: list[str]
    """Every error not starting with ``FAILED ``, sorted and de-duplicated."""


def executed(test_node: str) -> bool:
    """The filter ``execution._scores`` applies before counting a node as a test case."""
    return "::" in test_node and "<collection-error>" not in test_node


def _outcomes(qualified_nodes, errors) -> Outcomes:
    nodes: dict[str, str] = {}
    failures: set[str] = set()
    for test_node, outcome in qualified_nodes:
        if not executed(test_node):
            failures.add(test_node)
        elif test_node not in nodes:
            nodes[test_node] = outcome
    return Outcomes(
        nodes=nodes,
        collection_failures=sorted(failures),
        errors=sorted({error for error in errors if not error.startswith("FAILED ")}),
    )


def card_outcomes(results: Mapping[str, CardResult]) -> Outcomes:
    """Card suites' nodes, qualified as ``<card_id>/<test_node>``."""
    return _outcomes(
        (
            (f"{card_id}/{node['test_node']}", node["outcome"])
            for card_id, result in results.items()
            for node in result.test_nodes
        ),
        (error for result in results.values() for error in result.errors),
    )


def engine_outcomes(result: EngineResult) -> Outcomes:
    """The engine suite's nodes, already relative to its root."""
    return _outcomes(
        ((node["test_node"], node["outcome"]) for node in result.test_nodes), result.errors
    )


def suite_outcomes(evaluated: FullEvalResult) -> dict[str, Outcomes]:
    """The FDN and engine suites' outcomes, by suite."""
    return {
        "fdn": card_outcomes(evaluated.fdn_results),
        "engine": engine_outcomes(evaluated.engine_result),
    }


@dataclass(frozen=True)
class KnownDefect:
    id: str
    description: str
    rules: tuple[str, ...]
    kind: str
    failing_tests: Mapping[str, tuple[str, ...]]
    """Suite (``fdn`` | ``engine``) -> the Audited Tests the defect makes fail."""
    target_tests: tuple[str, ...] = ()
    """Target-card tests that fail once the defect is put back into the Test Oracle
    Workspace; always empty in a schema version 1 manifest."""
    host_card: str | None = None
    """The card hosting the defect's Dependency Tests; set exactly when it is related."""

    @property
    def related(self) -> bool:
        """At least one target-card test depends on the defect (SCORING.md → Test classes)."""
        return bool(self.target_tests)


@dataclass(frozen=True)
class KnownDefects:
    benchmark: str
    defects: tuple[KnownDefect, ...]
    schema_version: int = 2

    def failing_tests(self, suite: str) -> frozenset[str]:
        """The Audited Tests the unmodified Workspace fails in ``suite`` (``fdn`` | ``engine``)."""
        if suite not in SUITES:
            raise ValueError(f"unknown suite {suite!r}")
        return frozenset(
            node for defect in self.defects for node in defect.failing_tests.get(suite, ())
        )

    def defect(self, defect_id: str) -> KnownDefect:
        for defect in self.defects:
            if defect.id == defect_id:
                return defect
        raise KeyError(defect_id)


class KnownDefectsError(ValueError):
    """A Known Defect manifest that breaks the schema; the message names the field."""


def has_known_defects_manifest(benchmark_root: Path) -> bool:
    return (Path(benchmark_root) / MANIFEST).is_file()


def load_known_defects(benchmark_root: Path) -> KnownDefects | None:
    """The benchmark's validated manifest, or None when it has none."""
    benchmark_root = Path(benchmark_root)
    path = benchmark_root / MANIFEST
    if not os.path.lexists(path):
        return None

    def fail(what: str):
        raise KnownDefectsError(f"{path}: {what}")

    if path.is_symlink():
        fail("must be a regular file, not a symlink")
    try:
        document = strict_json(read_regular(path, limit=MANIFEST_LIMIT))
    except KarnError as error:
        fail(str(error))
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "benchmark",
        "defects",
    }:
        fail("top level must have exactly schema_version, benchmark and defects")
    version = document["schema_version"]
    if type(version) is not int or version not in SCHEMA_VERSIONS:
        fail("schema_version must be 1 or 2")
    if document["benchmark"] != benchmark_root.name:
        fail(f"benchmark must be {benchmark_root.name!r}")
    if not isinstance(document["defects"], list):
        fail("defects must be a list")
    defects, seen = [], set()
    for index, entry in enumerate(document["defects"]):
        name = f"defects[{index}]"
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            name += f" ({entry['id']})"
        defects.append(
            _defect(entry, lambda what, name=name: fail(f"{name}: {what}"), seen, version)
        )
    return KnownDefects(
        benchmark=document["benchmark"], defects=tuple(defects), schema_version=version
    )


def _defect(entry, fail, seen: set[str], version: int) -> KnownDefect:
    keys = {"id", "description", "rules", "kind", "failing_tests"}
    if version >= 2:
        keys |= {"target_tests", "host_card"}
    suite_of = {suite: suite for suite in SUITES} if version >= 2 else SCHEMA_1_SUITE_KEYS
    if not isinstance(entry, dict) or set(entry) != keys:
        fail("must have exactly " + ", ".join(sorted(keys)))
    if not isinstance(entry["id"], str) or not DEFECT_ID.fullmatch(entry["id"]):
        fail("id must match " + DEFECT_ID.pattern)
    if entry["id"] in seen:
        fail("id is not unique")
    seen.add(entry["id"])
    if not isinstance(entry["description"], str) or not entry["description"].strip():
        fail("description must be a non-empty string")
    rules = entry["rules"]
    if (
        not isinstance(rules, list)
        or not rules
        or not all(isinstance(rule, str) and RULE.fullmatch(rule) for rule in rules)
        or len(set(rules)) != len(rules)
    ):
        fail("rules must be a non-empty list of unique rule citations like 'CR 400.7'")
    if entry["kind"] not in KINDS:
        fail("kind must be one of " + ", ".join(KINDS))
    failing = entry["failing_tests"]
    if not isinstance(failing, dict) or not failing:
        fail("failing_tests must be a non-empty object")
    for key, nodes in failing.items():
        if key not in suite_of:
            fail(f"failing_tests: unknown suite {key!r}")
        if (
            not isinstance(nodes, list)
            or not nodes
            or not all(isinstance(node, str) for node in nodes)
            or len(set(nodes)) != len(nodes)
        ):
            fail(f"failing_tests.{key} must be a non-empty list of unique strings")
        valid = _engine_node if suite_of[key] == "engine" else FDN_NODE.fullmatch
        for node in nodes:
            if not valid(node):
                fail(f"failing_tests.{key}: malformed Audited Test id {node!r}")
    target_tests: list[str] = []
    host_card = None
    if version >= 2:
        target_tests = entry["target_tests"]
        if (
            not isinstance(target_tests, list)
            or not all(isinstance(node, str) for node in target_tests)
            or len(set(target_tests)) != len(target_tests)
        ):
            fail("target_tests must be a list of unique strings")
        for node in target_tests:
            if not FDN_NODE.fullmatch(node):
                fail(f"target_tests: malformed Audited Test id {node!r}")
        host_card = entry["host_card"]
        if target_tests:
            if not isinstance(host_card, str) or not CARD_ID.fullmatch(host_card):
                fail("host_card must be a card id like 'fdn_122' when target_tests is non-empty")
        elif host_card is not None:
            fail("host_card must be null when target_tests is empty")
    return KnownDefect(
        id=entry["id"],
        description=entry["description"],
        rules=tuple(rules),
        kind=entry["kind"],
        failing_tests=MappingProxyType(
            {
                suite_of[key]: tuple(value)
                for key, value in failing.items()
            }
        ),
        target_tests=tuple(target_tests),
        host_card=host_card,
    )


def _engine_node(node: str) -> bool:
    """``<relative/path>.py::<test>``, relative to the Audited Engine Tests root."""
    if "::" not in node:
        return False
    module = node.split("::", 1)[0]
    segments = module.split("/")
    return (
        module.endswith(".py")
        and "\\" not in module
        and not module.startswith("/")
        and all(segment not in ("", ".", "..") for segment in segments)
    )
