#!/usr/bin/env python3
"""Mine discovery candidates from agent-written tests.

Scans agent-written ``tests.py`` files stored in each Validated Results
``cards/<card>/`` subtree and surfaces test behaviors not represented in the
canonical audited suite at ``benchmarks/<bench>/data/tests/audited/<set>/<card>/tests.py``.

This is the Discovery-mode input for the test-investigation skill — it **never
promotes anything automatically**.  Output is a human-reviewable list of
promotion candidates.

Heuristic
---------
Each ``tests.py`` is parsed with :mod:`ast`.  For every test function
(``def test_*`` or ``async def test_*``), the miner extracts:

1. **Normalized name** — the function name lowered and stripped of a leading
   ``test_`` prefix, then further stripped of common suffixes (``_test``,
   ``_case``) and common prefixes (``test_``).  This produces a "behavior
   token" that can be compared across files.
2. **Docstring** — the first expression statement if it is a string literal.
3. **Referenced engine APIs** — attribute names (``ast.Attribute.attr``) and
   simple call names used in the function body.  These are the "asserted
   public engine APIs" the test exercises.

A **behavior signature** = ``(normalized_name, frozenset(engine_apis))``.

An agent test function is a **candidate** (i.e. novel behavior not in the
audited file) when **none** of the following conditions hold for any audited
test function:

* **Name match** — the normalized names are identical, OR
* **API-overlap match** — the engine-API sets share ≥ 80 % Jaccard similarity
  AND the docstrings share a non-trivial keyword overlap (≥ 1 meaningful
  keyword in common, where "meaningful" = length > 3 to skip ``the``, ``is``,
  etc.).

If no audited file exists for a card, all agent test functions are surfaced
as candidates with a ``"no audited baseline"`` note.

Usage::

    python scripts/mine_promotion_candidates.py
    python scripts/mine_promotion_candidates.py --bench sos --card sos_245

CLI flags:
    --bench   Benchmark name (default: ``sos``).
    --card    Filter to a specific card.
    --image   Filter to a specific docker image name.
    --run     Filter to a specific run name.
    --format  Output format: ``text`` (default) or ``json``.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Import harvest discovery (scripts/ is not a package — use importlib)
# ---------------------------------------------------------------------------

import importlib.util

_SCRIPT_DIR = Path(__file__).resolve().parent
_HARVEST_PATH = _SCRIPT_DIR / "harvest_validated_results.py"

if "harvest_validated_results" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "harvest_validated_results", _HARVEST_PATH
    )
    _harvest_mod = importlib.util.module_from_spec(_spec)
    sys.modules["harvest_validated_results"] = _harvest_mod
    _spec.loader.exec_module(_harvest_mod)
else:
    _harvest_mod = sys.modules["harvest_validated_results"]

discover_validated_runs = _harvest_mod.discover_validated_runs
ValidatedRun = _harvest_mod.ValidatedRun

# ---------------------------------------------------------------------------
# Repo root
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TestBehavior:
    """Extracted behavior signature for a single test function."""

    name: str
    """Original function name (e.g. ``test_card_is_creature``)."""

    normalized_name: str
    """Lowered, prefix/suffix-stripped name for comparison."""

    docstring: str
    """First-line docstring, or empty string."""

    engine_apis: frozenset[str]
    """Attribute / call names referenced in the function body."""

    source_snippet: str
    """Source text of the function (for human review)."""

    start_line: int
    """1-based starting line in the source file."""

    end_line: int
    """1-based ending line in the source file."""


@dataclass
class Candidate:
    """A promotion candidate — an agent test behavior not in the audited suite."""

    card: str
    image: str
    run: str
    test_name: str
    normalized_name: str
    docstring: str
    engine_apis: list[str]
    source_snippet: str
    note: str = ""
    """Optional note (e.g. 'no audited baseline')."""


# ---------------------------------------------------------------------------
# AST extraction
# ---------------------------------------------------------------------------


def _normalize_test_name(name: str) -> str:
    """Normalize a test function name to a comparable behavior token.

    Strips leading ``test_``, converts to lowercase, and removes common
    trailing noise (``_test``, ``_case``).
    """
    n = name.lower()
    if n.startswith("test_"):
        n = n[5:]
    for suffix in ("_test", "_case"):
        if n.endswith(suffix):
            n = n[: -len(suffix)]
    return n


def _extract_engine_apis(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Extract attribute names and simple call names from a function body.

    This is a transparent approximation of "asserted public engine APIs":
    we collect every ``ast.Attribute.attr`` and every ``ast.Name.id`` that
    appears as the function in an ``ast.Call`` node.
    """
    apis: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute):
            apis.add(child.attr)
        elif isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                apis.add(func.id)
            elif isinstance(func, ast.Attribute):
                apis.add(func.attr)
    return frozenset(apis)


def _get_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract the docstring from a function node, or return ''."""
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, (ast.Constant,))
        and isinstance(node.body[0].value.value, str)
    ):
        return node.body[0].value.value.strip()
    return ""


def extract_test_behaviors(source: str, filepath: str = "<unknown>") -> list[TestBehavior]:
    """Parse a tests.py source and extract behavior signatures for all test functions.

    Parameters
    ----------
    source:
        Python source code.
    filepath:
        Used only for error context.

    Returns
    -------
    list[TestBehavior]
        One entry per ``def test_*`` or ``async def test_*``, including those
        inside classes.

    Raises
    ------
    SyntaxError
        If the source cannot be parsed.
    """
    tree = ast.parse(source, filename=filepath)
    source_lines = source.splitlines(keepends=True)

    behaviors: list[TestBehavior] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("test"):
                continue

            start = node.lineno
            end = node.end_lineno or start
            snippet = "".join(source_lines[start - 1 : end])

            behaviors.append(TestBehavior(
                name=node.name,
                normalized_name=_normalize_test_name(node.name),
                docstring=_get_docstring(node),
                engine_apis=_extract_engine_apis(node),
                source_snippet=snippet.rstrip(),
                start_line=start,
                end_line=end,
            ))

    return behaviors


# ---------------------------------------------------------------------------
# Matching heuristic
# ---------------------------------------------------------------------------


def _docstring_keywords(doc: str) -> set[str]:
    """Extract meaningful keywords (len > 3) from a docstring."""
    return {w.lower() for w in doc.split() if len(w) > 3}


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity between two sets.  Returns 0.0 if both empty."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def is_behavior_covered(
    agent: TestBehavior,
    audited_behaviors: list[TestBehavior],
    *,
    api_jaccard_threshold: float = 0.8,
) -> bool:
    """Determine whether *agent* behavior is already represented in *audited_behaviors*.

    Matching rules (any match → covered):

    1. **Name match**: normalized names are identical.
    2. **API-overlap match**: engine-API Jaccard ≥ *api_jaccard_threshold* AND
       the docstrings share at least 1 meaningful keyword (length > 3).

    Parameters
    ----------
    agent:
        The agent-written test behavior to check.
    audited_behaviors:
        All behaviors extracted from the audited tests file.
    api_jaccard_threshold:
        Minimum Jaccard similarity for the API-overlap rule.

    Returns
    -------
    bool
        ``True`` if the behavior is considered covered.
    """
    agent_kw = _docstring_keywords(agent.docstring)

    for audited in audited_behaviors:
        # Rule 1: name match
        if agent.normalized_name == audited.normalized_name:
            return True

        # Rule 2: API overlap + docstring keyword overlap
        j = _jaccard(agent.engine_apis, audited.engine_apis)
        if j >= api_jaccard_threshold:
            aud_kw = _docstring_keywords(audited.docstring)
            if agent_kw & aud_kw:
                return True

    return False


# ---------------------------------------------------------------------------
# Core mining function
# ---------------------------------------------------------------------------


def mine_candidates(
    repo_root: Path,
    *,
    bench: str = "sos",
    card: Optional[str] = None,
    image: Optional[str] = None,
    run: Optional[str] = None,
) -> list[Candidate]:
    """Scan agent-written tests and surface novel behaviors not in the audited suite.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    bench:
        Benchmark name (default ``sos``).  Used to locate the audited suite
        at ``benchmarks/<bench>/data/tests/audited/<bench>/<card>/tests.py``.
    card:
        If given, restrict to this card name.
    image:
        If given, restrict to this docker image.
    run:
        If given, restrict to this run name.

    Returns
    -------
    list[Candidate]
        Promotion candidates with per-source provenance (one entry per
        ``(image, run, card, test_name)`` tuple).  Never promotes anything.
    """
    audited_root = repo_root / "benchmarks" / bench / "data" / "tests" / "audited" / bench

    # Discover validated runs (reuses the harvest module's discovery).
    runs = discover_validated_runs(
        repo_root,
        image=image,
        run=run,
        card=card,
    )

    # Cache audited behaviors per card.
    _audited_cache: dict[str, list[TestBehavior] | None] = {}

    def _get_audited(card_name: str) -> list[TestBehavior] | None:
        """Return audited behaviors for *card_name*, or None if absent/unparseable."""
        if card_name in _audited_cache:
            return _audited_cache[card_name]

        audited_path = audited_root / card_name / "tests.py"
        if not audited_path.is_file():
            _audited_cache[card_name] = None
            return None

        try:
            source = audited_path.read_text(encoding="utf-8")
            behaviors = extract_test_behaviors(source, str(audited_path))
        except SyntaxError:
            _audited_cache[card_name] = None
            return None

        _audited_cache[card_name] = behaviors
        return behaviors

    candidates: list[Candidate] = []

    for vr in runs:
        for card_dir in vr.card_dirs:
            card_name = card_dir.name
            agent_tests_path = card_dir / "tests.py"

            if not agent_tests_path.is_file():
                # No agent tests — nothing to mine.
                continue

            try:
                agent_source = agent_tests_path.read_text(encoding="utf-8")
                agent_behaviors = extract_test_behaviors(
                    agent_source, str(agent_tests_path)
                )
            except SyntaxError:
                # Unparseable agent tests — skip with a note.
                continue

            if not agent_behaviors:
                continue

            audited = _get_audited(card_name)

            for ab in agent_behaviors:
                if audited is None:
                    # No audited baseline — all agent behaviors are candidates.
                    candidates.append(Candidate(
                        card=card_name,
                        image=vr.image,
                        run=vr.run,
                        test_name=ab.name,
                        normalized_name=ab.normalized_name,
                        docstring=ab.docstring,
                        engine_apis=sorted(ab.engine_apis),
                        source_snippet=ab.source_snippet,
                        note="no audited baseline",
                    ))
                elif not is_behavior_covered(ab, audited):
                    candidates.append(Candidate(
                        card=card_name,
                        image=vr.image,
                        run=vr.run,
                        test_name=ab.name,
                        normalized_name=ab.normalized_name,
                        docstring=ab.docstring,
                        engine_apis=sorted(ab.engine_apis),
                        source_snippet=ab.source_snippet,
                    ))

    return candidates


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_candidates_text(candidates: list[Candidate]) -> str:
    """Format candidates as a human-readable text report."""
    if not candidates:
        return "No promotion candidates found.\n"

    lines: list[str] = []
    lines.append("Promotion Candidates")
    lines.append("=" * 72)
    lines.append(f"Total candidates: {len(candidates)}")
    lines.append("")

    for i, c in enumerate(candidates, 1):
        lines.append(f"--- Candidate {i} ---")
        lines.append(f"Card:       {c.card}")
        lines.append(f"Source:     {c.image}/{c.run}")
        lines.append(f"Test:       {c.test_name}")
        if c.docstring:
            lines.append(f"Summary:    {c.docstring.splitlines()[0]}")
        if c.note:
            lines.append(f"Note:       {c.note}")
        lines.append(f"Engine APIs: {', '.join(c.engine_apis) if c.engine_apis else '(none)'}")
        lines.append("Snippet:")
        for sl in c.source_snippet.splitlines():
            lines.append(f"    {sl}")
        lines.append("")

    return "\n".join(lines)


def format_candidates_json(candidates: list[Candidate]) -> str:
    """Format candidates as a JSON array."""
    return json.dumps([asdict(c) for c in candidates], indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mine promotion candidates from agent-written tests.  "
            "Surfaces behaviors not represented in the canonical audited suite.  "
            "Never promotes anything automatically."
        ),
    )
    parser.add_argument(
        "--bench",
        default="sos",
        help="Benchmark name (default: sos).",
    )
    parser.add_argument(
        "--card",
        default=None,
        help="Filter to a specific card.",
    )
    parser.add_argument(
        "--image",
        default=None,
        help="Filter to a specific docker image name.",
    )
    parser.add_argument(
        "--run",
        default=None,
        help="Filter to a specific run name.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    return parser


def main(*, repo_root: Optional[Path] = None) -> None:
    """Entry point for CLI invocation."""
    if repo_root is None:
        repo_root = REPO_ROOT

    parser = _build_parser()
    args = parser.parse_args()

    candidates = mine_candidates(
        repo_root,
        bench=args.bench,
        card=args.card,
        image=args.image,
        run=args.run,
    )

    if args.format == "json":
        print(format_candidates_json(candidates))
    else:
        print(format_candidates_text(candidates))


if __name__ == "__main__":
    main()
