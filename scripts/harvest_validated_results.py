#!/usr/bin/env python3
"""Harvest validated results into a JSONL analysis file.

Discovers all Validated Results by globbing
``docker/*/validated_results/*/`` from the repo root. Validated Results are
runs manually promoted out of ``results/`` after completing cleanly -- this
script never reads from the ``results/`` working directory.

With ``--results-repo <path>`` (or ``$SILVERQUILLM_RESULTS_REPO``) discovery
reads the migrated private results repo instead: each run record's
``legacy-tree`` artifact pointer leads back into the legacy tree for the
per-card ``result.json`` / ``tests.py`` content, and the row's ``image``
column carries the legacy identity. The row shape is identical either way.
The in-repo walk stays the default until the legacy lineage is retired.

Usage::

    python scripts/harvest_validated_results.py
    python scripts/harvest_validated_results.py --image cc-opus-48-bare
    python scripts/harvest_validated_results.py --run sos-cc-opus-48-bare-2026-05-30T04-02
    python scripts/harvest_validated_results.py --card sos_245
    python scripts/harvest_validated_results.py --results-repo /path/to/results-clone

CLI flags:
    --bench         Benchmark name (default: ``sos``).
    --output        Output JSONL path (default:
                    ``benchmarks/<bench>/analysis/harvested_results.jsonl``).
    --image         Filter to a specific docker image name.
    --run           Filter to a specific run name.
    --card          Filter to runs/cards containing a matching card directory.
    --results-repo  Read runs from the migrated results repo (default: the
                    ``$SILVERQUILLM_RESULTS_REPO`` env var; unset = legacy walk).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Repo root resolution
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ValidatedRun:
    """A single discovered validated-result run."""

    image: str
    run: str
    run_dir: Path
    card_dirs: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_validated_runs(
    repo_root: Path,
    *,
    image: Optional[str] = None,
    run: Optional[str] = None,
    card: Optional[str] = None,
    results_repo: Optional[Path] = None,
) -> list[ValidatedRun]:
    """Discover validated runs under ``docker/*/validated_results/*/``.

    Parameters
    ----------
    repo_root:
        Repository root directory.  Defaults to the resolved parent of
        this script's directory when called via ``main()``.
    image:
        If given, restrict to runs under ``docker/<image>/``.
    run:
        If given, restrict to the exact run directory name.
    card:
        If given, restrict to runs whose ``cards/`` subdirectory contains
        a ``<card>/`` entry matching this name.
    results_repo:
        If given, discover runs from the migrated private results repo at
        this path instead of walking ``docker/``: every run record with a
        ``legacy-tree`` artifact pointer is followed back into the legacy
        tree under *repo_root* for its per-card content.  Records without
        such a pointer have no per-card detail to harvest and are skipped.

    Returns
    -------
    list[ValidatedRun]
        Sorted by ``(image, run)`` for deterministic output.
    """
    if results_repo is not None:
        return _discover_from_results_repo(
            repo_root, Path(results_repo), image=image, run=run, card=card
        )

    docker_root = repo_root / "docker"
    if not docker_root.is_dir():
        return []

    results: list[ValidatedRun] = []

    # Glob all validated run directories
    for run_dir in sorted(docker_root.glob("*/validated_results/*/")):
        if not run_dir.is_dir():
            continue

        img_name = run_dir.parent.parent.name  # docker/<image>/validated_results/<run>
        run_name = run_dir.name

        # Apply --image filter
        if image is not None and img_name != image:
            continue

        # Apply --run filter
        if run is not None and run_name != run:
            continue

        matched_card_dirs = _collect_card_dirs(run_dir, card)

        # Apply --card filter: skip runs with no matching cards
        if card is not None and not matched_card_dirs:
            continue

        results.append(ValidatedRun(
            image=img_name,
            run=run_name,
            run_dir=run_dir,
            card_dirs=matched_card_dirs,
        ))

    # Sort by (image, run) for deterministic output
    results.sort(key=lambda vr: (vr.image, vr.run))
    return results


def _collect_card_dirs(run_dir: Path, card: Optional[str]) -> list[Path]:
    """Sorted ``cards/<card>/`` dirs under *run_dir*, narrowed to *card* if given."""
    cards_parent = run_dir / "cards"
    matched: list[Path] = []
    if cards_parent.is_dir():
        for card_dir in sorted(cards_parent.iterdir()):
            if card_dir.is_dir() and (card is None or card_dir.name == card):
                matched.append(card_dir)
    return matched


def _discover_from_results_repo(
    repo_root: Path,
    results_repo: Path,
    *,
    image: Optional[str],
    run: Optional[str],
    card: Optional[str],
) -> list[ValidatedRun]:
    """Discover runs from the migrated results repo (see ``discover_validated_runs``).

    The ``image`` column carries the legacy identity (``legacy:<image-dir>``
    → ``<image-dir>``) so rows are identical to the legacy walk's.  A
    ``legacy-tree`` location must equal the canonical identity-bound path
    (``docker/<image-dir>/validated_results/<run-id>/``) — rechecked here,
    right before the pointer is followed, so per-card content can never be
    harvested under another candidate's label; a mismatch raises rather than
    warns.  A canonical location that no longer exists on disk is reported on
    stderr and skipped.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from silverquillm.results_repo import (
        LEGACY_TREE_KIND,
        InvalidRunRecordError,
        iter_run_records,
        legacy_image_dir,
        legacy_tree_location,
    )

    results: list[ValidatedRun] = []
    for _record_dir, record in iter_run_records(results_repo):
        pointer = next(
            (p for p in record.artifact_pointers if p.get("kind") == LEGACY_TREE_KIND), None
        )
        if pointer is None:
            continue  # no per-card detail source for this record
        img_name = legacy_image_dir(record.candidate)
        if img_name is None:
            continue  # not a legacy identity: run_metadata never substitutes for identity
        run_name = record.run_id
        if image is not None and img_name != image:
            continue
        if run is not None and run_name != run:
            continue

        location = pointer["location"]
        expected = legacy_tree_location(img_name, run_name)
        if location != expected:
            # The pointer is the only bridge from a record to legacy content:
            # following a non-canonical one could emit candidate-A rows from
            # candidate-B artifacts, so this fails loudly, never warn-and-skip.
            raise InvalidRunRecordError(
                f"{img_name}/{run_name}: legacy-tree location {location!r} is not "
                f"the canonical identity-bound path {expected!r}"
            )
        run_dir = repo_root / location
        if not run_dir.is_dir():
            print(
                f"warning: {img_name}/{run_name}: legacy-tree location not found: {run_dir}",
                file=sys.stderr,
            )
            continue

        matched_card_dirs = _collect_card_dirs(run_dir, card)
        if card is not None and not matched_card_dirs:
            continue

        results.append(ValidatedRun(
            image=img_name,
            run=run_name,
            run_dir=run_dir,
            card_dirs=matched_card_dirs,
        ))

    results.sort(key=lambda vr: (vr.image, vr.run))
    return results


# ---------------------------------------------------------------------------
# Legacy helpers
# ---------------------------------------------------------------------------

# Regex matching FAILED/ERROR lines produced by _parse_pytest_output in
# silverquillm/evaluator.py.  Examples:
#   "FAILED tests.py::test_x - AssertionError"
#   "ERROR tests.py::test_y"
#   "FAILED /tmp/eval_sos_abc123/tests.py::test_z - reason"
_FAILED_RE = re.compile(
    r"^(?:FAILED|ERROR)\s+"       # keyword
    r"(\S+?)"                     # node-id (non-greedy, no spaces)
    r"(?:\s+-\s+.*)?$"            # optional " - reason" suffix
)


def _normalize_nodeid(nodeid: str) -> str:
    """Normalize a pytest node ID to ``tests.py::test_x`` form.

    Strips any directory prefix so only the filename and test remain.
    Mirrors the normalizer in ``silverquillm/evaluator.py``.
    """
    if "/" in nodeid:
        if "::" in nodeid:
            path_part, rest = nodeid.split("::", 1)
            filename = path_part.rsplit("/", 1)[-1]
            return f"{filename}::{rest}"
        else:
            return nodeid.rsplit("/", 1)[-1]
    return nodeid


def _extract_fail_nodes_from_errors(errors: list[str]) -> list[str]:
    """Extract de-duplicated, normalized pytest node IDs from error lines.

    Lines that do not contain a parseable ``file::test`` node ID (e.g.
    collection errors without a node) are represented by a synthetic
    ``tests.py::<collection-error>`` entry so the failure remains visible.

    Returns a list of unique node IDs in encounter order.
    """
    seen: set[str] = set()
    result: list[str] = []

    for line in errors:
        m = _FAILED_RE.match(line.strip())
        if m:
            raw = m.group(1)
            normalized = _normalize_nodeid(raw)
            # If the "node id" has no :: separator it's not a real test node
            if "::" not in normalized:
                normalized = "tests.py::<collection-error>"
        else:
            # Unparseable error line — still record as collection error
            normalized = "tests.py::<collection-error>"

        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------


def build_rows_for_run(
    vr: ValidatedRun,
    *,
    harvested_at: str,
) -> list[dict]:
    """Build one JSONL row per ``(card, test_node)`` for a validated run.

    Parameters
    ----------
    vr:
        A discovered :class:`ValidatedRun`.
    harvested_at:
        ISO-8601 timestamp shared across all rows of one harvest invocation.

    Returns
    -------
    list[dict]
        Rows with keys ``image, run, card, test_node, outcome, tests_hash,
        passed, failed, total, complexity_tier, harvested_at``.

        For legacy cards (``test_nodes`` key absent from result.json), fail
        rows are derived from ``errors`` and a single ``__rollup__`` row with
        ``outcome="rollup"`` is emitted.  ``tests_hash`` is ``None`` for all
        legacy rows.
    """
    rows: list[dict] = []

    for card_dir in vr.card_dirs:
        result_path = card_dir / "result.json"
        try:
            result_data = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Unreadable result.json — skip gracefully.
            continue

        card_name = card_dir.name

        # Rollup counts — map result.json field names to row field names.
        passed = result_data.get("tests_passed", 0)
        failed = result_data.get("tests_failed", 0)
        total = result_data.get("tests_total", 0)

        # Complexity tier from card_spec.json (if available).
        complexity_tier = _read_complexity_tier(card_dir)

        # Legacy detection: key *absent* from the dict triggers legacy path.
        # A modern card with an empty test_nodes list is NOT legacy.
        if "test_nodes" not in result_data:
            # ---- Legacy path (item 5) ----
            tests_hash = None  # always null for legacy

            # Derive fail rows from errors list.
            errors = result_data.get("errors") or []
            fail_nodes = _extract_fail_nodes_from_errors(errors)

            base = {
                "image": vr.image,
                "run": vr.run,
                "card": card_name,
                "tests_hash": tests_hash,
                "passed": passed,
                "failed": failed,
                "total": total,
                "complexity_tier": complexity_tier,
                "harvested_at": harvested_at,
            }

            for nodeid in fail_nodes:
                rows.append({**base, "test_node": nodeid, "outcome": "fail"})

            # Rollup row — outcome is "rollup" (neither "pass" nor "fail") so
            # downstream breadth metrics do not miscount it as a failing node.
            rows.append({**base, "test_node": "__rollup__", "outcome": "rollup"})
            continue

        # ---- Modern path (item 4) ----
        tests_hash = result_data.get("tests_hash", None)
        test_nodes = result_data["test_nodes"]

        for node in test_nodes:
            rows.append({
                "image": vr.image,
                "run": vr.run,
                "card": card_name,
                "test_node": node.get("test_node", ""),
                "outcome": node.get("outcome", ""),
                "tests_hash": tests_hash,
                "passed": passed,
                "failed": failed,
                "total": total,
                "complexity_tier": complexity_tier,
                "harvested_at": harvested_at,
            })

    return rows


def _read_complexity_tier(card_dir: Path) -> Optional[str]:
    """Read ``complexity_tier`` from ``card_spec.json`` in *card_dir*.

    Returns ``None`` when the file or key is absent or unreadable.
    """
    spec_path = card_dir / "card_spec.json"
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        return spec.get("complexity_tier", None)
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Harvest orchestrator
# ---------------------------------------------------------------------------


def harvest(
    repo_root: Path,
    *,
    bench: str = "sos",
    output: Optional[str] = None,
    image: Optional[str] = None,
    run: Optional[str] = None,
    card: Optional[str] = None,
    harvested_at: Optional[str] = None,
    results_repo: Optional[Path] = None,
) -> int:
    """Run the full harvest pipeline and write JSONL rows.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    bench:
        Benchmark name (used only for the default output path).
    output:
        Explicit output JSONL path.  When *None*, defaults to
        ``benchmarks/<bench>/analysis/harvested_results.jsonl`` under
        *repo_root*.
    image, run, card:
        Optional filters forwarded to :func:`discover_validated_runs`.
    harvested_at:
        ISO-8601 timestamp for all rows.  Computed automatically when *None*.
    results_repo:
        Optional migrated results repo to discover runs from instead of the
        in-repo ``docker/`` walk (see :func:`discover_validated_runs`).

    Returns
    -------
    int
        Number of rows written.
    """
    if harvested_at is None:
        harvested_at = datetime.now(timezone.utc).isoformat()

    # Resolve output path.
    if output is not None:
        output_path = Path(output)
    else:
        output_path = (
            repo_root / "benchmarks" / bench / "analysis"
            / "harvested_results.jsonl"
        )

    # Ensure parent directory exists.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Discover runs.
    runs = discover_validated_runs(
        repo_root,
        image=image,
        run=run,
        card=card,
        results_repo=results_repo,
    )

    # Build and write rows (truncate-then-write for idempotency).
    row_count = 0
    with open(output_path, "w", encoding="utf-8") as fh:
        for vr in runs:
            rows = build_rows_for_run(vr, harvested_at=harvested_at)
            for row in rows:
                fh.write(json.dumps(row) + "\n")
                row_count += 1
            # Detect legacy-ness by checking for __rollup__ rows.
            if any(r.get("test_node") == "__rollup__" for r in rows):
                print(
                    f"[legacy] {vr.image}/{vr.run}: contributed "
                    f"fail-node + rollup rows only (no per-node pass data)"
                )

    return row_count


# ---------------------------------------------------------------------------
# Breadth summary (item 6)
# ---------------------------------------------------------------------------
# NOTE: Grouping uses stdlib only (collections.defaultdict + set).
# Loading into DuckDB or emitting a Parquet sibling is an optional future
# optimization — see TODO item 6 spec.


def load_rows(jsonl_path: Path) -> list[dict]:
    """Load rows from a JSONL file, tolerating blank lines.

    Parameters
    ----------
    jsonl_path:
        Path to a ``harvested_results.jsonl`` file.

    Returns
    -------
    list[dict]
        Parsed rows.
    """
    rows: list[dict] = []
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def summarize_breadth(rows: list[dict]) -> list[dict]:
    """Compute cross-implementation breadth per ``(card, test_node, tests_hash)``.

    Breadth is the count of distinct ``image`` values with ``outcome == "fail"``
    within each group.  Rows with outcome ``"pass"`` or ``"rollup"`` do NOT
    contribute to breadth.

    Parameters
    ----------
    rows:
        Harvested result rows (as produced by :func:`harvest` / :func:`load_rows`).

    Returns
    -------
    list[dict]
        One dict per group with keys ``card``, ``test_node``, ``tests_hash``,
        ``breadth``, ``failing_images`` (sorted list of distinct failing images).
        Ranked descending by ``breadth``; ties broken by
        ``(card, test_node, tests_hash)`` with ``None`` sorting last.
    """
    # Group: (card, test_node, tests_hash) → set of failing images
    groups: dict[tuple, set[str]] = defaultdict(set)
    # Track all groups (including pass-only ones)
    all_groups: set[tuple] = set()

    for row in rows:
        key = (row.get("card", ""), row.get("test_node", ""), row.get("tests_hash"))
        all_groups.add(key)
        if row.get("outcome") == "fail":
            groups[key].add(row.get("image", ""))

    # Build result list
    result: list[dict] = []
    for key in all_groups:
        card, test_node, tests_hash = key
        failing = groups.get(key, set())
        result.append({
            "card": card,
            "test_node": test_node,
            "tests_hash": tests_hash,
            "breadth": len(failing),
            "failing_images": sorted(failing),
        })

    # Sort: descending by breadth, then ascending by (card, test_node,
    # tests_hash) with None sorting after all strings for stability.
    def _sort_key(entry: dict) -> tuple:
        # Negate breadth for descending order
        th = entry["tests_hash"]
        # None sorts last: use (1, "") so it comes after (0, any_string)
        th_sort = (1, "") if th is None else (0, th)
        return (-entry["breadth"], entry["card"], entry["test_node"], th_sort)

    result.sort(key=_sort_key)
    return result


def write_summary(summary: list[dict], path: Path) -> None:
    """Write a breadth summary to ``harvested_summary.json``.

    Parameters
    ----------
    summary:
        Output of :func:`summarize_breadth`.
    path:
        Target file path (typically ``harvested_summary.json`` in the
        analysis directory).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
        fh.write("\n")


def _print_breadth_report(summary: list[dict]) -> None:
    """Print a human-readable ranked breadth report to stdout."""
    print("Cross-implementation breadth report")
    print("=" * 72)
    print(f"{'Breadth':>7}  {'Card':<20}  {'Test Node':<30}  Hash")
    print("-" * 72)
    for entry in summary:
        th = entry["tests_hash"]
        th_short = (th[:8] + "...") if (th and len(th) > 8) else (th or "None")
        print(
            f"{entry['breadth']:>7}  "
            f"{entry['card']:<20}  "
            f"{entry['test_node']:<30}  "
            f"{th_short}"
        )
    print("-" * 72)
    n_failing = sum(1 for e in summary if e["breadth"] > 0)
    print(f"Total groups: {len(summary)}  |  Groups with failures: {n_failing}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Harvest validated results into a JSONL analysis file.",
    )
    parser.add_argument(
        "--bench",
        default="sos",
        help="Benchmark name (default: sos).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output JSONL path. "
            "Default: benchmarks/<bench>/analysis/harvested_results.jsonl"
        ),
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
        "--card",
        default=None,
        help="Filter to runs/cards containing a matching card directory.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        default=False,
        help=(
            "Summary mode: load existing harvested_results.jsonl, compute "
            "cross-impl breadth ranking, write harvested_summary.json, and "
            "print a ranked report. Does NOT re-harvest."
        ),
    )
    parser.add_argument(
        "--results-repo",
        default=None,
        type=Path,
        help=(
            "Discover runs from the migrated private results repo at this path "
            "instead of walking docker/*/validated_results/. Default: the "
            "SILVERQUILLM_RESULTS_REPO env var; unset means the legacy walk."
        ),
    )
    return parser


def _resolve_results_repo(flag: Optional[Path]) -> Optional[Path]:
    """``--results-repo`` if given, else ``$SILVERQUILLM_RESULTS_REPO``, else ``None``."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from silverquillm.results_repo import resolve_results_repo

    return resolve_results_repo(flag)


def main(*, repo_root: Optional[Path] = None) -> None:
    """Entry point for CLI invocation.

    Parameters
    ----------
    repo_root:
        Override the repository root (useful for testing).  Defaults to
        the resolved repo root derived from this file's location.
    """
    if repo_root is None:
        repo_root = REPO_ROOT

    parser = _build_parser()
    args = parser.parse_args()
    results_repo = _resolve_results_repo(args.results_repo)

    # Resolve output path (mirrors harvest() logic).
    if args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = (
            repo_root / "benchmarks" / args.bench / "analysis"
            / "harvested_results.jsonl"
        )

    # --summary mode: load existing JSONL, compute breadth, write summary.
    if args.summary:
        if not output_path.is_file():
            print(
                f"Nothing to summarize: {output_path} does not exist. "
                "Run without --summary first to harvest results.",
                file=sys.stderr,
            )
            sys.exit(1)

        rows = load_rows(output_path)
        summary = summarize_breadth(rows)

        summary_path = output_path.parent / "harvested_summary.json"
        write_summary(summary, summary_path)

        _print_breadth_report(summary)
        print(f"\nSummary written to: {summary_path}")
        return

    # Normal harvest mode.
    row_count = harvest(
        repo_root,
        bench=args.bench,
        output=args.output,
        image=args.image,
        run=args.run,
        card=args.card,
        results_repo=results_repo,
    )

    # Print harvest summary
    runs = discover_validated_runs(
        repo_root,
        image=args.image,
        run=args.run,
        card=args.card,
        results_repo=results_repo,
    )
    source = f"results repo {results_repo}" if results_repo else "docker/*/validated_results/"
    print(f"Discovered {len(runs)} validated run(s) from {source}:")
    for vr in runs:
        n_cards = len(vr.card_dirs)
        print(f"  {vr.image} / {vr.run}  ({n_cards} card(s))")
    print(f"\nWrote {row_count} row(s) to: {output_path}")


if __name__ == "__main__":
    main()
