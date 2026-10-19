"""Attribution data: the card each Audited Test counts toward.

A benchmark scored by the Net Card Score records, host-only, the Attributed Card
of its tests (``docs/specs/SCORING.md`` › Attributed Cards,
``docs/specs/KNOWN-BEST-ENGINE.md`` › Attribution data):

- ``data/attribution.json``, ported from the Known-Best Workspace: the host card of
  every Audited Engine Test, and of each FDN Audited Test that does not count toward
  its own card;
- ``data/target_attribution.json``, the benchmark's own: the card each target-card
  test counts toward when that is not the card whose suite holds it.

A key is an Audited Test id, or a prefix of one ending at a file or class boundary;
the longest matching key wins. Dependency Tests are not listed: they count toward
their Known Defect's ``host_card``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from silverquillm.karn.definition import KarnError, read_regular, strict_json

ATTRIBUTION = Path("data/attribution.json")
TARGET_ATTRIBUTION = Path("data/target_attribution.json")
LIMIT = 1024 * 1024
SUITES = ("engine", "fdn", "target")
CARD_ID = re.compile(r"[a-z][a-z0-9]*_[0-9]+[a-z]?")
_ENGINE_KEY = re.compile(r"(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\.py(?:::[A-Za-z0-9_]+)*")
_CARD_KEY = re.compile(r"[a-z][a-z0-9]*_[0-9]+[a-z]?/tests\.py(?:::[A-Za-z0-9_]+)*")


class AttributionError(ValueError):
    """Attribution data that breaks the schema; the message names the file and field."""


@dataclass(frozen=True)
class Attribution:
    engine: Mapping[str, str]
    fdn: Mapping[str, str]
    target: Mapping[str, str]

    def card(self, suite: str, test_id: str) -> str | None:
        """The Attributed Card of ``test_id`` in ``suite``; None for an Audited Engine
        Test no key matches. FDN and target-card tests default to their own card."""
        keys = {"engine": self.engine, "fdn": self.fdn, "target": self.target}[suite]
        for boundary in boundaries(test_id):
            if boundary in keys:
                return keys[boundary]
        return None if suite == "engine" else test_id.split("/", 1)[0]


def boundaries(test_id: str) -> Iterator[str]:
    """``test_id`` and its prefixes ending at a file or class boundary, longest first.

    A parametrized case counts as its test function.
    """
    parts = test_id.split("[", 1)[0].split("::")
    for count in range(len(parts), 0, -1):
        yield "::".join(parts[:count])


def load_attribution(benchmark_root: Path) -> Attribution | None:
    """The benchmark's validated attribution data, or None when it has none."""
    benchmark_root = Path(benchmark_root)
    shared = _read(benchmark_root / ATTRIBUTION, {"engine", "fdn"})
    if shared is None:
        return None
    own = _read(benchmark_root / TARGET_ATTRIBUTION, {"target"})
    return Attribution(
        engine=shared["engine"],
        fdn=shared["fdn"],
        target=own["target"] if own is not None else MappingProxyType({}),
    )


def _read(path: Path, maps: set[str]) -> dict[str, Mapping[str, str]] | None:
    if not os.path.lexists(path):
        return None

    def fail(what: str):
        raise AttributionError(f"{path}: {what}")

    if path.is_symlink():
        fail("must be a regular file, not a symlink")
    try:
        document = strict_json(read_regular(path, limit=LIMIT))
    except KarnError as error:
        fail(str(error))
    expected = {"schema_version", *maps}
    if not isinstance(document, dict) or set(document) != expected:
        fail("top level must have exactly " + ", ".join(sorted(expected)))
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        fail("schema_version must be 1")
    validated = {}
    for name in sorted(maps):
        entries = document[name]
        if not isinstance(entries, dict):
            fail(f"{name} must be an object")
        key_pattern = _ENGINE_KEY if name == "engine" else _CARD_KEY
        for key, card in entries.items():
            if not key_pattern.fullmatch(key):
                fail(f"{name}: malformed key {key!r}")
            if not isinstance(card, str) or not CARD_ID.fullmatch(card):
                fail(f"{name}.{key}: value must be a card id like 'fdn_272'")
        validated[name] = MappingProxyType(dict(entries))
    return validated
