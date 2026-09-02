#!/usr/bin/env python3
"""Backfill the legacy Validated Results corpus into the private results repo.

Walks every ``docker/<image>/validated_results/<run>/`` in the bench repo and
writes one immutable run record (``manifest.json`` + ``scores.json``) per run
into ``results/<candidate-hash>/<run-id>/`` of the results repo, then rebuilds
the derived index.  Nothing under ``docker/`` is modified.

How a legacy run maps onto a record:

- **candidate**: the ``legacy`` identity scheme, ``legacy:<image-dir>`` — the
  image was the whole agent configuration.  The candidate hash (directory key)
  is the sanitized image dir name.
- **mode**: ``"legacy"`` for every run.  The legacy lineage encoded variants in
  image names; that is a different concept from the new mode registry, so
  nothing is parsed — the image dir in the identity is the discriminator.
- **benchmark**: the manifest's ``benchmark_set``, ``"sos"`` when absent.
- **leaderboard_valid**: :func:`silverquillm.results_repo.derive_leaderboard_valid`
  (Resume Legs, narrower or different card filters, and a scored set that is
  not the benchmark's card set are all ``false``; collector numbers are compared
  after integer normalization because legacy manifests store ``"1"`` where
  ``config.json`` stores ``"001"``).  A false record carries the reasons in
  ``run_metadata.validity_note``.
- **scores**: the ``run_summary.json`` blocks under the neutral keys
  (``sos_card_correctness`` → ``card_correctness``).
- **artifact_pointers**: one ``legacy-tree`` pointer at the run directory, in
  place.  Heavy artifacts never enter the results repo.

Runs lacking ``run_manifest.json``, ``run_summary.json`` or ``eval_result.json``
are unparseable: they are listed loudly and skipped, never guessed.  Re-running
is idempotent: a destination whose existing record is byte-identical to the one
this run would write is skipped, while anything else already sitting there —
an unreadable, incomplete, or differing record — is a conflict that aborts the
whole apply before a single record is written.  Conflicting records are never
overwritten or deleted.

Usage::

    python scripts/migrate_validated_results.py --results-repo <clone> --dry-run
    python scripts/migrate_validated_results.py --results-repo <clone>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from silverquillm.results_repo import (  # noqa: E402
    LEGACY_TREE_KIND,
    MANIFEST_FILENAME,
    RESULTS_DIRNAME,
    RESULTS_REPO_ENV,
    RUN_SUMMARY_SCORE_KEYS,
    SCORES_FILENAME,
    CandidateIdentity,
    ResultsRepoError,
    RunRecord,
    candidate_hash,
    leaderboard_validity_reasons,
    load_benchmark_config,
    read_run_record,
    rebuild_index,
    record_file_texts,
    resolve_results_repo,
    write_run_record,
)

DEFAULT_BENCHMARK = "sos"
LEGACY_MODE = "legacy"
REQUIRED_FILES = ("run_manifest.json", "run_summary.json", "eval_result.json")

ConfigLoader = Callable[[str], Mapping[str, Any]]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class LegacyRunUnparseable(Exception):
    """The run directory lacks what a faithful record needs."""


@dataclass(frozen=True)
class LegacyRun:
    image: str
    run: str
    run_dir: Path

    @property
    def location(self) -> str:
        """Bench-repo-relative location used in the ``legacy-tree`` pointer."""
        return f"docker/{self.image}/validated_results/{self.run}/"


@dataclass(frozen=True)
class PlannedRecord:
    legacy: LegacyRun
    record: RunRecord
    already_present: bool


@dataclass(frozen=True)
class SkippedRun:
    legacy: LegacyRun
    reason: str


@dataclass(frozen=True)
class MigrationConflict:
    """A planned destination already exists but does not hold the planned record."""

    legacy: LegacyRun
    reason: str


@dataclass
class MigrationPlan:
    planned: list[PlannedRecord] = field(default_factory=list)
    skipped: list[SkippedRun] = field(default_factory=list)
    conflicts: list[MigrationConflict] = field(default_factory=list)

    @property
    def to_write(self) -> list[PlannedRecord]:
        return [p for p in self.planned if not p.already_present]

    @property
    def already_present(self) -> list[PlannedRecord]:
        return [p for p in self.planned if p.already_present]


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_legacy_runs(repo_root: Path) -> list[LegacyRun]:
    """Every ``docker/<image>/validated_results/<run>/``, sorted by ``(image, run)``."""
    docker_root = Path(repo_root) / "docker"
    if not docker_root.is_dir():
        return []
    runs: list[LegacyRun] = []
    for run_dir in sorted(docker_root.glob("*/validated_results/*/")):
        if run_dir.is_dir():
            runs.append(
                LegacyRun(image=run_dir.parent.parent.name, run=run_dir.name, run_dir=run_dir)
            )
    runs.sort(key=lambda lr: (lr.image, lr.run))
    return runs


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------


def _load_json_object(path: Path, name: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyRunUnparseable(f"{name} unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise LegacyRunUnparseable(f"{name} is not a JSON object")
    return data


def _legacy_card_filter(
    manifest: Mapping[str, Any], summary: Mapping[str, Any]
) -> list[str] | None:
    """The run's card filter: manifest ``card_filter``, older ``cards``, else the summary's."""
    if "card_filter" in manifest:
        value = manifest["card_filter"]
    elif "cards" in manifest:
        value = manifest["cards"]
    else:
        value = summary.get("card_filter")
    if value is None:
        return None
    if not isinstance(value, list):
        raise LegacyRunUnparseable(f"card filter is not a list: {value!r}")
    return [str(v) for v in value]


def build_legacy_record(legacy: LegacyRun, *, config_loader: ConfigLoader) -> RunRecord:
    """Build the :class:`RunRecord` for one legacy run, or raise :class:`LegacyRunUnparseable`."""
    missing = [name for name in REQUIRED_FILES if not (legacy.run_dir / name).is_file()]
    if missing:
        present = sorted(p.name for p in legacy.run_dir.iterdir())
        raise LegacyRunUnparseable(
            f"missing {', '.join(missing)} (present: {', '.join(present) or 'nothing'})"
        )
    manifest = _load_json_object(legacy.run_dir / "run_manifest.json", "run_manifest.json")
    summary = _load_json_object(legacy.run_dir / "run_summary.json", "run_summary.json")
    eval_result = _load_json_object(legacy.run_dir / "eval_result.json", "eval_result.json")

    benchmark = manifest.get("benchmark_set") or DEFAULT_BENCHMARK
    if not isinstance(benchmark, str):
        raise LegacyRunUnparseable(f"benchmark_set is not a string: {benchmark!r}")
    try:
        config = config_loader(benchmark)
    except ResultsRepoError as exc:
        raise LegacyRunUnparseable(str(exc)) from exc

    card_filter = _legacy_card_filter(manifest, summary)
    resumed_from = manifest.get("resumed_from") or summary.get("resumed_from") or None
    if resumed_from is not None and not isinstance(resumed_from, str):
        raise LegacyRunUnparseable(f"resumed_from is not a string: {resumed_from!r}")

    sos_results = eval_result.get("sos_results")
    if not isinstance(sos_results, dict):
        raise LegacyRunUnparseable("eval_result.json has no sos_results object")
    scored_cards = sorted(sos_results)

    scores: dict[str, Any] = {}
    for source_key, neutral_key in RUN_SUMMARY_SCORE_KEYS.items():
        block = summary.get(source_key)
        if not isinstance(block, dict):
            raise LegacyRunUnparseable(f"run_summary.json lacks the {source_key} block")
        scores[neutral_key] = block

    meta = summary.get("run_metadata")
    meta = meta if isinstance(meta, dict) else {}

    budget = manifest.get("timeout_seconds")
    budget_source = "run_manifest"
    if isinstance(budget, bool) or not isinstance(budget, int):
        budget = meta.get("timeout_seconds")
        budget_source = "run_summary"
    if isinstance(budget, bool) or not isinstance(budget, int):
        raise LegacyRunUnparseable(
            "no integer timeout_seconds in run_manifest.json or run_summary.json"
        )

    reasons = leaderboard_validity_reasons(config, card_filter, resumed_from, scored_cards)

    run_metadata: dict[str, Any] = {
        "run_date": meta.get("timestamp"),
        "docker_image": (
            manifest.get("docker_image") or summary.get("docker_image") or meta.get("image") or ""
        ),
        "image_dir": legacy.image,
        "harness_version": meta.get("harness_version"),
        "run_status": summary.get("run_status"),
        "wall_clock_seconds": summary.get("wall_clock_seconds"),
        "card_count": meta.get("card_count"),
        "card_filter": card_filter,
        "scored_card_count": len(scored_cards),
        "budget_seconds_source": budget_source,
        "migrated_from": legacy.location,
    }
    if "resumed_image_changed" in summary:
        run_metadata["resumed_image_changed"] = summary["resumed_image_changed"]
    if reasons:
        run_metadata["validity_note"] = "; ".join(reasons)

    return RunRecord(
        run_id=legacy.run,
        candidate=CandidateIdentity.legacy(legacy.image),
        mode=LEGACY_MODE,
        benchmark=benchmark,
        budget_seconds=budget,
        leaderboard_valid=not reasons,
        resumed_from=resumed_from,
        run_metadata=run_metadata,
        proposal_status=None,
        scores=scores,
        artifact_pointers=[{"kind": LEGACY_TREE_KIND, "location": legacy.location}],
    )


# ---------------------------------------------------------------------------
# Plan / apply
# ---------------------------------------------------------------------------


def _config_loader_for(repo_root: Path) -> ConfigLoader:
    cache: dict[str, Mapping[str, Any]] = {}

    def load(benchmark_id: str) -> Mapping[str, Any]:
        if benchmark_id not in cache:
            cache[benchmark_id] = load_benchmark_config(repo_root, benchmark_id)
        return cache[benchmark_id]

    return load


def _existing_record_conflict(existing_dir: Path, record: RunRecord) -> str | None:
    """``None`` iff *existing_dir* holds exactly *record*; else the conflict reason.

    "Exactly" is byte-level: the existing files must equal the canonical texts
    the writer would emit for *record*, so a reformatted, extended, tampered,
    incomplete, or simply different record is a conflict, never a skip.
    """
    try:
        read_run_record(existing_dir)
    except ResultsRepoError as exc:
        return f"existing record is unreadable: {exc}"
    manifest_text, scores_text = record_file_texts(record)
    try:
        existing_manifest = (existing_dir / MANIFEST_FILENAME).read_text(encoding="utf-8")
        existing_scores = (existing_dir / SCORES_FILENAME).read_text(encoding="utf-8")
    except OSError as exc:
        return f"existing record is unreadable: {exc}"
    if existing_manifest != manifest_text or existing_scores != scores_text:
        return "existing record differs from the record this run would write"
    return None


def plan_migration(repo_root: Path, results_repo: Path) -> MigrationPlan:
    """Build every record without writing; verify runs already in *results_repo*.

    A destination that already exists is re-read and byte-compared against the
    record this run would write: an exact match is "present, skip"; anything
    else is a :class:`MigrationConflict` that blocks the whole apply.
    """
    plan = MigrationPlan()
    config_loader = _config_loader_for(repo_root)
    results_dir = Path(results_repo) / RESULTS_DIRNAME
    for legacy in discover_legacy_runs(repo_root):
        try:
            record = build_legacy_record(legacy, config_loader=config_loader)
        except LegacyRunUnparseable as exc:
            plan.skipped.append(SkippedRun(legacy=legacy, reason=str(exc)))
            continue
        existing_dir = results_dir / candidate_hash(record.candidate) / record.run_id
        present = existing_dir.exists()
        if present:
            reason = _existing_record_conflict(existing_dir, record)
            if reason is not None:
                plan.conflicts.append(MigrationConflict(legacy=legacy, reason=reason))
                continue
        plan.planned.append(PlannedRecord(legacy=legacy, record=record, already_present=present))
    return plan


def apply_migration(plan: MigrationPlan, results_repo: Path) -> list[Path]:
    """Write every not-yet-present record, rebuild the index, return the dirs written.

    Refuses a plan with conflicts outright: nothing is written and the index
    is left alone until the operator resolves the conflicting records.
    """
    if plan.conflicts:
        raise ResultsRepoError(
            f"refusing to write: {len(plan.conflicts)} migration conflict(s) — "
            "records are immutable, resolve the existing records first"
        )
    written: list[Path] = []
    for planned in plan.to_write:
        written.append(write_run_record(results_repo, planned.record))
    rebuild_index(results_repo)
    return written


def format_plan(plan: MigrationPlan, *, dry_run: bool) -> str:
    lines: list[str] = []
    verb = "would write" if dry_run else "writing"
    for planned in plan.planned:
        record = planned.record
        state = "present, skip" if planned.already_present else verb
        validity = "valid" if record.leaderboard_valid else "INVALID"
        note = record.run_metadata.get("validity_note")
        suffix = f" — {note}" if note else ""
        lines.append(
            f"  [{state}] {planned.legacy.image}/{record.run_id}: benchmark={record.benchmark} "
            f"mode={record.mode} leaderboard={validity}{suffix}"
        )
    lines.append("")
    valid = sum(1 for p in plan.planned if p.record.leaderboard_valid)
    lines.append(
        f"Planned {len(plan.planned)} record(s): {len(plan.to_write)} to write, "
        f"{len(plan.already_present)} already present; "
        f"{valid} leaderboard_valid, {len(plan.planned) - valid} not."
    )
    if plan.skipped:
        lines.append("")
        lines.append(f"SKIPPED — {len(plan.skipped)} unparseable run(s), not migrated:")
        for skipped in plan.skipped:
            lines.append(f"  {skipped.legacy.image}/{skipped.legacy.run}: {skipped.reason}")
    if plan.conflicts:
        lines.append("")
        lines.append(
            f"CONFLICTS — {len(plan.conflicts)} existing record(s) disagree with the plan; "
            "nothing will be written until they are resolved:"
        )
        for conflict in plan.conflicts:
            lines.append(f"  {conflict.legacy.image}/{conflict.legacy.run}: {conflict.reason}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--results-repo",
        default=None,
        type=Path,
        help=f"Local clone of the private results repo (default: ${RESULTS_REPO_ENV}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print the full migration plan without writing anything.",
    )
    return parser


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = REPO_ROOT if repo_root is None else repo_root
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

    plan = plan_migration(repo_root, results_repo)
    print(format_plan(plan, dry_run=args.dry_run))
    if plan.skipped:
        # Loud on stderr too, so the list survives a piped stdout.
        print(f"warning: {len(plan.skipped)} unparseable run(s) skipped", file=sys.stderr)
    if plan.conflicts:
        print(
            f"error: {len(plan.conflicts)} migration conflict(s); nothing written — "
            "records are immutable, resolve the existing records first",
            file=sys.stderr,
        )
        return 1
    if args.dry_run:
        print("\nDry run: nothing written.")
        return 0
    written = apply_migration(plan, results_repo)
    print(f"\nWrote {len(written)} record(s) to {results_repo / RESULTS_DIRNAME}; index rebuilt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
