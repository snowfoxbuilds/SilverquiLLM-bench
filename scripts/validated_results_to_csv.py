#!/usr/bin/env python3
"""Flatten all Validated Results' ``run_summary.json`` into a CSV table.

Discovers every run by globbing ``docker/*/validated_results/*/run_summary.json``
from the repo root (the same population the harvester reads) and emits one CSV
row per run with:

    run_id, image_name, benchmark, timestamp,
    sos_card_correctness.*, fdn_regression.*, engine_regression.*

The three metric blocks are flattened dynamically: the column set is the union
of keys actually present across all discovered ``run_summary.json`` files, so
the table adapts if a metric is added or removed.

Usage::

    python scripts/validated_results_to_csv.py                       # -> stdout
    python scripts/validated_results_to_csv.py --output runs.csv
    python scripts/validated_results_to_csv.py --image cc-opus-48-bare
    python scripts/validated_results_to_csv.py --bench sos --run sos-cc-opus-48-bare-2026-05-30T04-02

CLI flags:
    --output  CSV output path (default: stdout).
    --image   Filter to a specific docker image directory name.
    --run     Filter to a specific run directory name.
    --bench   Filter to a benchmark name (matched against the run-id prefix).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent

# Metric blocks to flatten, in output order. Each becomes a group of
# ``<block>.<key>`` columns.
METRIC_BLOCKS = ("sos_card_correctness", "fdn_regression", "engine_regression")

# Fixed identity columns that always lead the table.
IDENTITY_COLUMNS = ("run_id", "image_name", "benchmark", "timestamp")


def discover_summaries(
    repo_root: Path,
    *,
    image: Optional[str] = None,
    run: Optional[str] = None,
    bench: Optional[str] = None,
) -> list[dict]:
    """Load every ``run_summary.json`` under ``docker/*/validated_results/*/``.

    Returns a list of records, each with ``run_id``, ``image_name``,
    ``benchmark``, ``timestamp`` and the raw metric blocks. Sorted by
    ``(image_name, run_id)`` for deterministic output. Unreadable files are
    skipped with a warning on stderr.
    """
    docker_root = repo_root / "docker"
    records: list[dict] = []
    if not docker_root.is_dir():
        return records

    for summary_path in sorted(docker_root.glob("*/validated_results/*/run_summary.json")):
        run_dir = summary_path.parent
        # docker/<image>/validated_results/<run>/run_summary.json
        image_name = run_dir.parent.parent.name
        run_id = run_dir.name
        # Run ids are "<bench>-<image>-<timestamp>"; the leading token is bench.
        benchmark = run_id.split("-", 1)[0]

        if image is not None and image_name != image:
            continue
        if run is not None and run_id != run:
            continue
        if bench is not None and benchmark != bench:
            continue

        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: skipping unreadable {summary_path}: {exc}", file=sys.stderr)
            continue

        timestamp = ""
        meta = data.get("run_metadata")
        if isinstance(meta, dict):
            timestamp = meta.get("timestamp", "") or ""

        records.append({
            "run_id": run_id,
            "image_name": image_name,
            "benchmark": benchmark,
            "timestamp": timestamp,
            "blocks": {b: data.get(b) if isinstance(data.get(b), dict) else {}
                       for b in METRIC_BLOCKS},
        })

    records.sort(key=lambda r: (r["image_name"], r["run_id"]))
    return records


def build_columns(records: list[dict]) -> tuple[list[str], dict[str, list[str]]]:
    """Compute the flattened column order from the union of metric keys.

    Returns ``(columns, per_block_keys)`` where ``columns`` is the full header
    list and ``per_block_keys`` maps each metric block to its sorted key list.
    """
    per_block_keys: dict[str, list[str]] = {}
    for block in METRIC_BLOCKS:
        keys: set[str] = set()
        for rec in records:
            keys.update(rec["blocks"].get(block, {}).keys())
        per_block_keys[block] = sorted(keys)

    columns = list(IDENTITY_COLUMNS)
    for block in METRIC_BLOCKS:
        columns.extend(f"{block}.{k}" for k in per_block_keys[block])
    return columns, per_block_keys


def write_csv(records: list[dict], out) -> int:
    """Write ``records`` as CSV to the file-like ``out``. Returns row count."""
    columns, per_block_keys = build_columns(records)
    writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for rec in records:
        row = {k: rec[k] for k in IDENTITY_COLUMNS}
        for block in METRIC_BLOCKS:
            block_data = rec["blocks"].get(block, {})
            for key in per_block_keys[block]:
                row[f"{block}.{key}"] = block_data.get(key, "")
        writer.writerow(row)
    return len(records)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=None, help="CSV output path (default: stdout).")
    parser.add_argument("--image", default=None, help="Filter to a docker image directory name.")
    parser.add_argument("--run", default=None, help="Filter to a run directory name.")
    parser.add_argument("--bench", default=None, help="Filter to a benchmark name (run-id prefix).")
    return parser


def main(*, repo_root: Optional[Path] = None) -> None:
    if repo_root is None:
        repo_root = REPO_ROOT
    args = _build_parser().parse_args()

    records = discover_summaries(
        repo_root, image=args.image, run=args.run, bench=args.bench,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            n = write_csv(records, fh)
        print(f"Wrote {n} run(s) to: {out_path}", file=sys.stderr)
    else:
        write_csv(records, sys.stdout)


if __name__ == "__main__":
    main()
