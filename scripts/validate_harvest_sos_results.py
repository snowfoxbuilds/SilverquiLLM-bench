#python3 scripts/validate_harvest_sos_results.py
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_CONFIG = REPO_ROOT / "benchmarks" / "sos" / "config.json"
RUN_PREFIX = "sos-"

# Top-level entries in a run dir that must NOT be committed:
#  - workspace_final/ is a full engine copy (repo bloat)
#  - snapshots/ is a host-side git repo (nested .git breaks committing)
EXCLUDE_TOP_LEVEL = {"workspace_final", "snapshots"}

# Junk to skip anywhere in the tree.
IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".DS_Store")

TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}-\d{2})(?:-[0-9a-z]+)?$")

def run_timestamp(run_name: str) -> str | None:
    """Extract the trailing UTC timestamp from a run name.

    Works for both `sos-2026-05-16T19-49` and
    `sos-cc-opus-48-single-2026-06-01T08-24` style names.
    """
    m = TIMESTAMP_RE.search(run_name)
    return m.group(1) if m else None

def normalize_card_id(raw: str) -> str | None:
    """Map '001', '1', 'sos_001', 'sos_226' etc. to a canonical numeric string."""
    m = re.search(r"(\d+)$", str(raw))
    return str(int(m.group(1))) if m else None

def load_audited_cards() -> set[str]:
    config = json.loads(BENCH_CONFIG.read_text(encoding="utf-8"))
    cards = {normalize_card_id(c) for c in config["cards"]}
    cards.discard(None)
    if not cards:
        sys.exit(f"error: no audited cards found in {BENCH_CONFIG}")
    return cards

def latest_validated_timestamp(validated_dir: Path) -> str:
    """Newest timestamp among already-validated SOS runs for this image ('' if none)."""
    timestamps = [
        ts
        for d in validated_dir.glob(f"{RUN_PREFIX}*")
        if d.is_dir() and (ts := run_timestamp(d.name))
    ]
    return max(timestamps, default="")

def check_run(run_dir: Path, audited: set[str]) -> str | None:
    """Return a rejection reason, or None if the run qualifies."""
    summary_path = run_dir / "run_summary.json"
    if not summary_path.exists():
        return "no run_summary.json (incomplete or in-flight run)"

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"unreadable run_summary.json ({exc})"

    # A filtered (--cards) run is fine as long as its filter covers every
    # audited card; partial runs that omit audited cards are not eligible.
    card_filter = summary.get("card_filter")
    if card_filter:
        filtered = {normalize_card_id(c) for c in card_filter}
        uncovered = sorted(audited - filtered, key=int)
        if uncovered:
            return f"filtered run omits audited cards: {', '.join(uncovered)}"

    status_path = run_dir / "status.json"
    if not status_path.exists():
        return "no status.json"

    try:
        statuses = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"unreadable status.json ({exc})"

    completed = {
        normalize_card_id(card)
        for card, info in statuses.items()
        if isinstance(info, dict) and info.get("status") == "completed"
    }
    missing = sorted(audited - completed, key=int)
    if missing:
        return f"audited cards not completed: {', '.join(missing)}"

    # Sanity check: each audited card should have an evaluated result.json.
    cards_root = run_dir / "cards"
    have_results = {
        normalize_card_id(d.name)
        for d in cards_root.glob("*")
        if d.is_dir() and (d / "result.json").exists()
    } if cards_root.is_dir() else set()
    no_result = sorted(audited - have_results, key=int)
    if no_result:
        return f"missing cards/<id>/result.json for: {', '.join(no_result)}"

    return None

def copy_validated_subset(run_dir: Path, dest: Path) -> None:
    """Copy the run dir into validated_results/, excluding heavyweight artifacts."""
    dest.mkdir(parents=True)
    for entry in sorted(run_dir.iterdir()):
        if entry.name in EXCLUDE_TOP_LEVEL:
            continue
        if entry.is_dir():
            shutil.copytree(entry, dest / entry.name, ignore=IGNORE_PATTERNS)
        else:
            shutil.copy2(entry, dest / entry.name)

def delete_git_files(path: Path) -> None:
    """Delete .git and .gitignore files from the given path and its subdirs."""
    for git_file in path.glob("**/.git*"):
        if git_file.is_file():
            git_file.unlink()
        elif git_file.is_dir():
            shutil.rmtree(git_file)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be promoted without copying")
    parser.add_argument("--image", default=None,
                        help="only consider this docker/<image_dir>")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="also report why runs were skipped")
    args = parser.parse_args()

    audited = load_audited_cards()
    docker_root = REPO_ROOT / "docker"
    promoted: list[str] = []

    image_dirs = (
        [docker_root / args.image] if args.image
        else sorted(d for d in docker_root.iterdir() if d.is_dir())
    )

    for image_dir in image_dirs:
        results_dir = image_dir / "results"
        if not results_dir.is_dir():
            continue
        validated_dir = image_dir / "validated_results"
        cutoff = latest_validated_timestamp(validated_dir)

        for run_dir in sorted(results_dir.glob(f"{RUN_PREFIX}*")):
            if not run_dir.is_dir():
                continue
            rel = f"{image_dir.name}/{run_dir.name}"

            ts = run_timestamp(run_dir.name)
            if ts is None:
                if args.verbose:
                    print(f"skip  {rel}: cannot parse timestamp from run name")
                continue
            if ts <= cutoff:
                if args.verbose:
                    print(f"skip  {rel}: not newer than last validated run ({cutoff})")
                continue
            if (validated_dir / run_dir.name).exists():
                if args.verbose:
                    print(f"skip  {rel}: already in validated_results/")
                continue

            reason = check_run(run_dir, audited)
            if reason is not None:
                if args.verbose:
                    print(f"skip  {rel}: {reason}")
                continue

            if args.dry_run:
                print(f"would promote  {rel}")
            else:
                copy_validated_subset(run_dir, validated_dir / run_dir.name)
                print(f"promoted  {rel}")
                delete_git_files(validated_dir / run_dir.name)
                print(f"  (copied to {validated_dir / run_dir.name} without .git files)")

            promoted.append(rel)

    if not promoted:
        print("nothing to promote")
    elif not args.dry_run:
        print()
        print(f"{len(promoted)} run(s) promoted. Next steps:")
        print("  git add docker/*/validated_results/")
        print('  git commit -m "Add validated runs: '
              + ", ".join(r.split("/")[1] for r in promoted) + '"')
    return 0

if __name__ == "__main__":
    raise SystemExit(main())