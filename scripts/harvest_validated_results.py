#!/usr/bin/env python3
"""Harvest validated results into a JSONL analysis file.

Discovers all Validated Results by globbing
``docker/*/validated_results/*/`` from the repo root. Validated Results are
runs manually promoted out of ``results/`` after completing cleanly -- this
script never reads from the ``results/`` working directory.

Usage::

    python scripts/harvest_validated_results.py
    python scripts/harvest_validated_results.py --image cc-opus-48-bare
    python scripts/harvest_validated_results.py --run sos-cc-opus-48-bare-2026-05-30T04-02
    python scripts/harvest_validated_results.py --card sos_245

CLI flags:
    --bench   Benchmark name (default: ``sos``).
    --output  Output JSONL path (default:
              ``benchmarks/<bench>/analysis/harvested_results.jsonl``).
    --image   Filter to a specific docker image name.
    --run     Filter to a specific run name.
    --card    Filter to runs/cards containing a matching card directory.
"""

from __future__ import annotations

import argparse
import json
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

    Returns
    -------
    list[ValidatedRun]
        Sorted by ``(image, run)`` for deterministic output.
    """
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

        # Collect card dirs
        cards_parent = run_dir / "cards"
        matched_card_dirs: list[Path] = []
        if cards_parent.is_dir():
            for card_dir in sorted(cards_parent.iterdir()):
                if card_dir.is_dir():
                    if card is None or card_dir.name == card:
                        matched_card_dirs.append(card_dir)

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
        Rows with keys: ``image, run, card, test_node, outcome, tests_hash,
        passed, failed, total, complexity_tier, harvested_at``.
    """
    rows: list[dict] = []

    for card_dir in vr.card_dirs:
        result_path = card_dir / "result.json"
        try:
            result_data = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Unreadable result.json — skip gracefully (item 5 may revisit).
            continue

        card_name = card_dir.name

        # Rollup counts — map result.json field names to row field names.
        passed = result_data.get("tests_passed", 0)
        failed = result_data.get("tests_failed", 0)
        total = result_data.get("tests_total", 0)
        tests_hash = result_data.get("tests_hash", None)

        # Modern schema: test_nodes present.
        test_nodes = result_data.get("test_nodes")
        if test_nodes is None:
            # TODO: item 5 fills legacy fallback for result.json lacking
            # test_nodes / tests_hash.
            continue

        # Complexity tier from card_spec.json (if available).
        complexity_tier = _read_complexity_tier(card_dir)

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
    )

    # Build and write rows (truncate-then-write for idempotency).
    row_count = 0
    with open(output_path, "w", encoding="utf-8") as fh:
        for vr in runs:
            rows = build_rows_for_run(vr, harvested_at=harvested_at)
            for row in rows:
                fh.write(json.dumps(row) + "\n")
                row_count += 1

    return row_count


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
    return parser


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

    # Delegate to harvest() so tests can drive the pipeline directly.
    row_count = harvest(
        repo_root,
        bench=args.bench,
        output=args.output,
        image=args.image,
        run=args.run,
        card=args.card,
    )

    # Resolve output path for summary message (mirrors harvest() logic).
    if args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = (
            repo_root / "benchmarks" / args.bench / "analysis"
            / "harvested_results.jsonl"
        )

    # Print summary
    runs = discover_validated_runs(
        repo_root,
        image=args.image,
        run=args.run,
        card=args.card,
    )
    print(f"Discovered {len(runs)} validated run(s):")
    for vr in runs:
        n_cards = len(vr.card_dirs)
        print(f"  {vr.image} / {vr.run}  ({n_cards} card(s))")
    print(f"\nWrote {row_count} row(s) to: {output_path}")


if __name__ == "__main__":
    main()
