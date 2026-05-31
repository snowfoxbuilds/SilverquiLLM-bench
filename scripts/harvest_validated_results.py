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
from dataclasses import dataclass, field
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

    # Resolve output path
    if args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = (
            repo_root / "benchmarks" / args.bench / "analysis"
            / "harvested_results.jsonl"
        )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run discovery
    runs = discover_validated_runs(
        repo_root,
        image=args.image,
        run=args.run,
        card=args.card,
    )

    # Print summary
    print(f"Discovered {len(runs)} validated run(s):")
    for vr in runs:
        n_cards = len(vr.card_dirs)
        print(f"  {vr.image} / {vr.run}  ({n_cards} card(s))")
    print(f"\nOutput would be written to: {output_path}")


if __name__ == "__main__":
    main()
