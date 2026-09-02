#!/usr/bin/env python3
"""Regenerate the results repo's derived index, ``runs.jsonl``.

The index is derived purely from ``results/<candidate-hash>/<run-id>/manifest.json``
files: one line per run (candidate hash, run id, benchmark, mode,
``leaderboard_valid``, run date), sorted by ``(candidate_hash, run_id)`` with
sorted keys, so two rebuilds of the same tree are byte-identical.  It is never
hand-edited and never authoritative — when it disagrees with the tree, rebuild.

Usage::

    python scripts/rebuild_results_index.py --results-repo /path/to/results-clone
    SILVERQUILLM_RESULTS_REPO=/path/to/results-clone python scripts/rebuild_results_index.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from silverquillm.results_repo import (  # noqa: E402
    INDEX_FILENAME,
    RESULTS_REPO_ENV,
    ResultsRepoError,
    rebuild_index,
    resolve_results_repo,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--results-repo",
        default=None,
        type=Path,
        help=f"Local clone of the private results repo (default: ${RESULTS_REPO_ENV}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    results_repo = resolve_results_repo(args.results_repo)
    if results_repo is None:
        print(
            f"error: no results repo given; pass --results-repo or set {RESULTS_REPO_ENV}",
            file=sys.stderr,
        )
        return 2
    if not results_repo.is_dir():
        print(f"error: results repo is not a directory: {results_repo}", file=sys.stderr)
        return 2
    try:
        rows = rebuild_index(results_repo)
    except ResultsRepoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("index NOT rebuilt; the previous runs.jsonl is unchanged", file=sys.stderr)
        return 1
    print(f"Indexed {len(rows)} run(s) into {results_repo / INDEX_FILENAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
