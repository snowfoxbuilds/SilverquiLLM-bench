#!/usr/bin/env python3
"""Discovery-to-promotion bar gate for a single rewritten candidate test.

Runs three checks before a human merges a candidate test into the audited suite:

1. **Tier check** (ADR-011): refuse promotion if ``benchmarks/<bench>/config.json``
   ``tier`` is ``released`` (or missing/unreadable).  Only ``beta`` and
   ``benchmarking`` tiers allow promotion.
2. **Canonical-API check**: reject if the candidate test references engine
   symbols that exist *only* in the Test Oracle Workspace engine and are absent
   from the canonical engine.
3. **Oracle gate** (ADR-010): run the candidate against the matching Test Oracle
   Implementation via the Phase 18 validation harness mechanism; must pass.

Exit 0 if all three checks pass (candidate is allowed for human merge).
Exit non-zero (1) with clear reasons on any failure.

This is an *operational gate* a human runs; it never edits, commits, or
promotes anything automatically.

MAINTAINER NOTE: repo-wide ADR-011 Benchmark Tier lock CI enforcement on the
base branch is a SEPARATE concern not implemented here.  If that CI check does
not yet exist, please create it as a separate task.

Usage::

    python scripts/check_promotion_candidate.py path/to/candidate/tests.py --card sos_245
    python scripts/check_promotion_candidate.py path/to/tests.py --card sos_1 --bench sos

Stdlib only: ast, pathlib, argparse, json, subprocess, dataclasses, os, sys.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Repo root (when run as a script)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Result of a single gate check."""

    name: str
    ok: bool
    reason: str


@dataclass
class PromotionResult:
    """Aggregate result of all promotion-bar checks."""

    allowed: bool
    checks: list[CheckResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Check 1 — Tier lock (ADR-011)
# ---------------------------------------------------------------------------

_ALLOWED_TIERS = {"beta", "benchmarking"}


def check_tier(repo_root: Path, bench: str = "sos") -> tuple[bool, str]:
    """Read ``benchmarks/<bench>/config.json`` and enforce the tier lock.

    Returns ``(ok, reason)``.  OK only if tier is ``beta`` or ``benchmarking``
    (case-insensitive).  Fail-closed: missing config or missing ``tier`` key
    results in rejection.
    """
    config_path = repo_root / "benchmarks" / bench / "config.json"
    if not config_path.is_file():
        return False, f"config.json not found at {config_path} — cannot verify tier (fail-closed)"

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"Failed to read/parse {config_path}: {exc} (fail-closed)"

    tier = data.get("tier")
    if tier is None:
        return False, f"'tier' key missing in {config_path} — cannot verify tier (fail-closed)"

    tier_lower = str(tier).strip().lower()
    if tier_lower in _ALLOWED_TIERS:
        return True, f"Tier '{tier}' allows promotion"
    else:
        return False, f"Tier '{tier}' does not allow promotion (only {sorted(_ALLOWED_TIERS)} are permitted)"


# ---------------------------------------------------------------------------
# Check 2 — Canonical-API check
# ---------------------------------------------------------------------------


def _is_public(name: str) -> bool:
    """A name is part of the public surface if it does not start with ``_``."""
    return bool(name) and not name.startswith("_")


def _plain_target_names(target: ast.expr) -> list[str]:
    """Return bare ``Name`` ids from an assignment target (recursing tuples/lists)."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in target.elts:
            names.extend(_plain_target_names(elt))
        return names
    return []


def _add_class_attr_names(stmt: ast.stmt, symbols: set[str]) -> None:
    """Add public class-body attribute names from a class-level Assign/AnnAssign.

    Catches class variables and dataclass fields such as
    ``StackObject.mana_spent`` (``mana_spent: int = 0``).
    """
    if isinstance(stmt, ast.AnnAssign):
        targets: list[ast.expr] = [stmt.target]
    elif isinstance(stmt, ast.Assign):
        targets = list(stmt.targets)
    else:
        return
    for target in targets:
        for name in _plain_target_names(target):
            if _is_public(name):
                symbols.add(name)


def _add_self_attr_names(node: ast.Assign | ast.AnnAssign, symbols: set[str]) -> None:
    """Add public attribute names assigned via ``self.<name>``/``cls.<name>``.

    Catches instance attributes such as ``game.rng`` (``self.rng = ...``).
    """
    if isinstance(node, ast.AnnAssign):
        targets: list[ast.expr] = [node.target]
    else:
        targets = list(node.targets)
    for target in targets:
        if isinstance(target, ast.Attribute):
            value = target.value
            if (
                isinstance(value, ast.Name)
                and value.id in {"self", "cls"}
                and _is_public(target.attr)
            ):
                symbols.add(target.attr)


def _collect_module_symbols(tree: ast.AST, symbols: set[str]) -> None:
    """Walk an engine module AST and add its public symbol names to ``symbols``.

    See :func:`_collect_public_symbols` for the categories collected.
    """
    for node in ast.walk(tree):
        # def / class / method / property / nested-class names
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if _is_public(node.name):
                symbols.add(node.name)

        # Class-body attributes (class vars, dataclass fields)
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                _add_class_attr_names(stmt, symbols)

        # Instance/class attributes assigned via self.<name> / cls.<name>
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            _add_self_attr_names(node, symbols)


def _collect_public_symbols(engine_dir: Path) -> set[str]:
    """Collect the public symbol surface of an engine directory.

    Recurses ``engine_dir`` (``rglob("*.py")`` — so engine subpackages are
    covered) and, for each module, collects the public names a candidate test
    could legitimately reference as an engine API:

    - **Module names** — the stem of each ``.py`` file (excluding ``__init__``
      and modules starting with ``_``).
    - **``def`` / ``class`` names** at any nesting level — functions, classes,
      and methods/properties (e.g. the ``ManaPool.restricted_mana`` property).
    - **Class-body attributes** — ``Assign`` / ``AnnAssign`` targets defined
      directly in a class body, e.g. the dataclass field
      ``StackObject.mana_spent``.
    - **Instance/class attributes** — names assigned via ``self.<name>`` or
      ``cls.<name>`` anywhere in the module, e.g. ``game.rng``.

    Names beginning with ``_`` are treated as private and skipped.

    Collecting attribute/method/property names — not just module/class/function
    names — is what lets :func:`check_canonical_api` see oracle-only primitives
    that live *inside* a class.  Those are exactly the symbols the Phase 18
    cleanup added only to the oracle engine (``mana_spent``, ``restricted_mana``,
    ``rng``); a coarser top-level-only scan would let a candidate depending on
    them slip through both this check and the oracle gate.

    Heuristic limits (acceptable for a name-based gate): attributes created
    dynamically (``setattr``, ``__dict__`` writes, metaclass injection) are not
    visible, and matching is on bare names rather than fully-qualified owners.
    The oracle gate plus human review remain the backstop.
    """
    symbols: set[str] = set()

    if not engine_dir.is_dir():
        return symbols

    for py_file in sorted(engine_dir.rglob("*.py")):
        stem = py_file.stem
        # Module names (excluding __init__ and private modules)
        if not stem.startswith("_"):
            symbols.add(stem)

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError):
            continue

        _collect_module_symbols(tree, symbols)

    return symbols


def _extract_candidate_symbols(candidate_path: Path) -> set[str]:
    """AST-extract engine symbols referenced by the candidate test file.

    Collects:
    - ``ast.Attribute.attr`` — attribute accesses like ``card.power``.
    - ``ast.Name.id`` used as the function in an ``ast.Call`` — direct calls
      like ``Game()``.

    This is the same transparent heuristic used by ``mine_promotion_candidates.py``.
    """
    source = candidate_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(candidate_path))

    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            symbols.add(node.attr)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                symbols.add(func.id)
            elif isinstance(func, ast.Attribute):
                symbols.add(func.attr)
    return symbols


def check_canonical_api(
    candidate_path: Path, repo_root: Path, bench: str = "sos"
) -> tuple[bool, str]:
    """Check that the candidate does not depend on oracle-only engine primitives.

    The rule: REJECT if the candidate references a symbol that is present in
    the Oracle engine (``benchmarks/<bench>/data/test_oracle_workspace/engine/``)
    but ABSENT from the canonical engine (``benchmarks/<bench>/workspace/engine/``).

    Symbols not recognizable as engine APIs at all (i.e. not in either engine's
    public symbol set) are ignored — they are presumably stdlib, pytest, or
    test-local names.

    Returns ``(ok, reason)``.
    """
    canonical_dir = repo_root / "benchmarks" / bench / "workspace" / "engine"
    oracle_dir = repo_root / "benchmarks" / bench / "data" / "test_oracle_workspace" / "engine"

    canonical_symbols = _collect_public_symbols(canonical_dir)
    oracle_symbols = _collect_public_symbols(oracle_dir)

    try:
        candidate_symbols = _extract_candidate_symbols(candidate_path)
    except (SyntaxError, OSError) as exc:
        return False, f"Failed to parse candidate {candidate_path}: {exc}"

    # Oracle-only symbols: in oracle engine but not canonical engine
    oracle_only = oracle_symbols - canonical_symbols

    # Candidate references to oracle-only symbols
    violations = candidate_symbols & oracle_only

    if violations:
        return False, (
            f"Candidate references oracle-only engine symbols not in canonical engine: "
            f"{sorted(violations)}"
        )

    return True, "Candidate uses only canonical engine APIs (or non-engine symbols)"


# ---------------------------------------------------------------------------
# Check 3 — Oracle gate (ADR-010)
# ---------------------------------------------------------------------------


def check_oracle_gate(
    candidate_path: Path, card: str, repo_root: Path, bench: str = "sos"
) -> tuple[bool, str]:
    """Run the candidate test against the Test Oracle Implementation.

    Follows the Phase 18 mechanism from ``tests/test_audited_against_reference.py``:
    copies the oracle ``card_impl.py`` and the candidate ``tests.py`` into a
    temp directory, sets PYTHONPATH to include the oracle workspace engine,
    and runs pytest on the candidate.

    Returns ``(ok, reason)``.  OK iff the candidate PASSES.
    Fail-closed: subprocess errors or missing oracle files result in rejection.
    """
    oracle_workspace = repo_root / "benchmarks" / bench / "data" / "test_oracle_workspace"
    oracle_cards_dir = oracle_workspace / "cards" / bench
    audited_dir = repo_root / "benchmarks" / bench / "data" / "tests" / "audited" / bench

    # Locate oracle card_impl.py
    oracle_impl = oracle_cards_dir / card / "card_impl.py"
    if not oracle_impl.is_file():
        return False, f"Oracle card_impl.py not found at {oracle_impl} (fail-closed)"

    # Validate candidate exists
    if not candidate_path.is_file():
        return False, f"Candidate test file not found at {candidate_path} (fail-closed)"

    tmp_dir = tempfile.mkdtemp(prefix=f"promo_gate_{card}_")
    try:
        tmp = Path(tmp_dir)

        # Copy oracle impl as card_impl.py
        shutil.copy2(oracle_impl, tmp / "card_impl.py")

        # Copy test_utils.py from oracle workspace if present
        oracle_test_utils = oracle_workspace / "test_utils.py"
        if oracle_test_utils.exists():
            shutil.copy2(oracle_test_utils, tmp / "test_utils.py")

        # Copy candidate tests as tests.py
        shutil.copy2(candidate_path, tmp / "tests.py")

        # Copy conftest from audited dir if present
        conftest = audited_dir / "conftest.py"
        if conftest.exists():
            shutil.copy2(conftest, tmp / "conftest.py")

        # Build PYTHONPATH: tmp first, then oracle workspace (for engine), then repo root
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        parts = [str(tmp), str(oracle_workspace), str(repo_root)]
        if existing:
            parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(parts)

        cmd = [
            sys.executable, "-m", "pytest",
            str(tmp / "tests.py"),
            "--tb=short", "-q", "--no-header",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if result.returncode == 0:
            return True, "Candidate passes against oracle implementation"
        else:
            stdout_tail = result.stdout[-500:] if result.stdout else "(no stdout)"
            stderr_tail = result.stderr[-500:] if result.stderr else "(no stderr)"
            return False, (
                f"Candidate FAILED against oracle implementation (exit {result.returncode}).\n"
                f"stdout (last 500 chars): {stdout_tail}\n"
                f"stderr (last 500 chars): {stderr_tail}"
            )

    except subprocess.TimeoutExpired:
        return False, "Oracle gate subprocess timed out after 120s (fail-closed)"
    except OSError as exc:
        return False, f"Oracle gate subprocess error: {exc} (fail-closed)"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def check_promotion_candidate(
    candidate_path: Path,
    card: str,
    repo_root: Path,
    bench: str = "sos",
) -> PromotionResult:
    """Evaluate all promotion-bar checks for a single candidate test.

    Check order (with short-circuiting on tier):
    1. Tier lock — cheap; if Released or missing, refuse immediately.
    2. Canonical-API check — AST-based, no subprocess.
    3. Oracle gate — runs pytest subprocess against oracle impl.

    Parameters
    ----------
    candidate_path:
        Path to the candidate test file (``tests.py``).
    card:
        Card name (e.g. ``sos_245``).
    repo_root:
        Repository root directory.
    bench:
        Benchmark name (default ``sos``).

    Returns
    -------
    PromotionResult
        ``allowed=True`` only if all three checks pass.
    """
    result = PromotionResult(allowed=False)

    # 1. Tier check (cheap hard-lock — short-circuit on failure)
    tier_ok, tier_reason = check_tier(repo_root, bench)
    result.checks.append(CheckResult(name="tier", ok=tier_ok, reason=tier_reason))
    if not tier_ok:
        # Short-circuit: Released tier → refuse immediately, don't run expensive checks
        return result

    # 2. Canonical-API check
    api_ok, api_reason = check_canonical_api(candidate_path, repo_root, bench)
    result.checks.append(CheckResult(name="canonical_api", ok=api_ok, reason=api_reason))

    # 3. Oracle gate (only if API check passed — optional short-circuit for efficiency,
    #    but per spec we run all remaining checks and aggregate)
    oracle_ok, oracle_reason = check_oracle_gate(candidate_path, card, repo_root, bench)
    result.checks.append(CheckResult(name="oracle_gate", ok=oracle_ok, reason=oracle_reason))

    result.allowed = tier_ok and api_ok and oracle_ok
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_MAINTAINER_NOTE = (
    "NOTE: repo-wide ADR-011 Benchmark Tier lock CI enforcement on the base "
    "branch is a SEPARATE concern not implemented here.  If that CI check does "
    "not yet exist, please create it as a separate task."
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Promotion bar gate: run tier, canonical-API, and oracle checks "
            "on a single candidate test before human merge.  "
            "Never edits, commits, or promotes anything.\n\n"
            + _MAINTAINER_NOTE
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "candidate",
        type=str,
        help="Path to the candidate test file.",
    )
    parser.add_argument(
        "--card",
        required=True,
        help="Card name (e.g. sos_245).",
    )
    parser.add_argument(
        "--bench",
        default="sos",
        help="Benchmark name (default: sos).",
    )
    return parser


def main(*, repo_root: Optional[Path] = None) -> None:
    """Entry point for CLI invocation."""
    if repo_root is None:
        repo_root = REPO_ROOT

    parser = _build_parser()
    args = parser.parse_args()

    candidate_path = Path(args.candidate).resolve()

    # Print maintainer note to stderr
    print(_MAINTAINER_NOTE, file=sys.stderr)

    result = check_promotion_candidate(
        candidate_path=candidate_path,
        card=args.card,
        repo_root=repo_root,
        bench=args.bench,
    )

    # Print each check's result
    for check in result.checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.reason}")

    # Final verdict
    print()
    if result.allowed:
        print("VERDICT: ALLOWED — candidate may be promoted (human review required)")
        sys.exit(0)
    else:
        print("VERDICT: REJECTED — candidate does NOT meet the promotion bar")
        sys.exit(1)


if __name__ == "__main__":
    main()
