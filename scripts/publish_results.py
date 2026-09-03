#!/usr/bin/env python3
"""Stage run records from the private Results Repo into the bench repo's
public ``published/`` tree (issue #39 §4, #66 Part A).

The publish script is a **porter with two checks, never a librarian**: it
copies ``manifest.json`` + ``scores.json`` of explicitly named runs into a
destination the operator chooses, and it never commits — the operator reviews
the staged diff and commits, and that commit is the approval stamp.

The two checks, per run:

- **Traceability — a hard refusal.**  The run's candidate identity must exist
  under ``candidates/`` (``candidates/<slug>--<hash8>/``) and verify by
  recomputation: the checked-in bundle is ingested through the bench's own
  path (TheOzolith's verifier, identity recomputed from bundle bytes) and its
  candidate hash and identity triple must equal the record's.  An absent
  candidate, a mismatch, a bundle that fails verification, or a ``legacy``
  identity (which has no bundle) refuses the whole publication.  When the
  Results Repo holds the vendored copy at ``results/<hash>/candidate/`` it is
  re-verified too.
- **Validity — a warning.**  ``leaderboard_valid: false`` (a Resume Leg, a
  gate-failed or unevaluated run, an ineligible benchmark) is reported and
  refuses unless ``--allow-invalid`` is passed: publishable at the operator's
  discretion, and never able to enter a leaderboard because tooling filters
  on the flag mechanically.

Idempotent and side-effect-free on refusal: every run is checked before the
first file is staged; an already-staged byte-identical record is skipped;
a differing record under the same destination is a conflict that refuses
the publication.  Discovery of published results
(:func:`iter_published_records`) goes through manifests only — never a path
convention — so the operator organizes ``published/`` freely.

Usage::

    python scripts/publish_results.py --results-repo <clone> --dest published/<subdir> RUN_ID...
        [--candidates-dir candidates] [--allow-invalid] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from theozolith_control import candidate as ozcandidate

from silverquillm.candidate import CandidateRefusedError, load_candidate_bundle
from silverquillm.results_repo import (
    MANIFEST_FILENAME,
    OZOLITH_SCHEME,
    RESULTS_REPO_ENV,
    SCORES_FILENAME,
    CandidateIdentity,
    ResultsRepoError,
    RunRecord,
    candidate_copy_dir,
    candidate_hash,
    candidate_hash8,
    iter_run_dirs,
    read_run_record,
    resolve_results_repo,
)

DEFAULT_CANDIDATES_DIR = REPO_ROOT / "candidates"
DEFAULT_PUBLISHED_DIR = REPO_ROOT / "published"
RECORD_FILES = (MANIFEST_FILENAME, SCORES_FILENAME)


class PublicationRefused(Exception):
    """The publication cannot proceed; nothing was staged."""


@dataclass(frozen=True)
class Traceability:
    """Where the run's candidate identity is checked in, verified."""

    candidate_dir: Path
    candidate_hash: str
    vendored_copy_verified: bool


@dataclass
class PlannedRun:
    run_id: str
    source_dir: Path
    record: RunRecord
    dest_dir: Path
    traceability: Traceability | None = None
    refusals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    already_staged: bool = False


@dataclass
class PublicationPlan:
    dest: Path
    runs: list[PlannedRun]

    @property
    def refusals(self) -> list[str]:
        return [f"{run.run_id}: {reason}" for run in self.runs for reason in run.refusals]

    @property
    def warnings(self) -> list[str]:
        return [f"{run.run_id}: {reason}" for run in self.runs for reason in run.warnings]

    @property
    def to_stage(self) -> list[PlannedRun]:
        return [run for run in self.runs if not run.already_staged]


# ---------------------------------------------------------------------------
# Locating records
# ---------------------------------------------------------------------------


def find_run_record(results_repo: Path, run_id: str) -> tuple[Path, RunRecord]:
    """The one ``results/<hash>/<run-id>/`` record named *run_id*, re-proven
    on read.  Zero or several matches refuse."""
    matches = [run_dir for run_dir in iter_run_dirs(results_repo) if run_dir.name == run_id]
    if not matches:
        raise PublicationRefused(f"no run record named {run_id!r} in {results_repo}")
    if len(matches) > 1:
        raise PublicationRefused(
            f"run id {run_id!r} is ambiguous in {results_repo}: "
            + ", ".join(str(m) for m in matches)
        )
    try:
        return matches[0], read_run_record(matches[0])
    except ResultsRepoError as exc:
        raise PublicationRefused(f"{run_id}: the record does not re-prove on read: {exc}") from exc


# ---------------------------------------------------------------------------
# The two checks
# ---------------------------------------------------------------------------


def _candidate_dirs_with_hash8(candidates_dir: Path, hash8: str) -> list[Path]:
    if not candidates_dir.is_dir():
        return []
    suffix = f"--{hash8}"
    return sorted(
        p for p in candidates_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name.endswith(suffix)
    )


def check_traceability(
    identity: CandidateIdentity, *, candidates_dir: Path, results_repo: Path | None = None
) -> Traceability:
    """The traceability check: *identity* is checked in under *candidates_dir*
    and verifies by recomputation.  Raises :class:`PublicationRefused`."""
    if identity.scheme != OZOLITH_SCHEME:
        raise PublicationRefused(
            f"the run's candidate identity is scheme {identity.scheme!r}, which has no"
            " Candidate Bundle to trace to — only a run driven from a verified bundle"
            f" ({OZOLITH_SCHEME}) is publishable"
        )
    expected_hash = candidate_hash(identity)
    hash8 = candidate_hash8(identity)
    dirs = _candidate_dirs_with_hash8(candidates_dir, hash8)
    if not dirs:
        raise PublicationRefused(
            f"no candidate under {candidates_dir} carries identity hash {expected_hash}"
            f" (hash8 {hash8}) — promote the candidate first"
            " (scripts/promote_candidate.py); a result whose candidate is not public"
            " is untraceable and cannot be published"
        )
    if len(dirs) > 1:
        raise PublicationRefused(
            f"identity hash8 {hash8} names several candidate directories"
            f" ({', '.join(d.name for d in dirs)}); candidates/ must be flat and"
            " deduplicating"
        )
    candidate_dir = dirs[0]
    try:
        bundle = load_candidate_bundle(candidate_dir)
    except CandidateRefusedError as exc:
        raise PublicationRefused(
            f"{candidate_dir} fails verification, so the run cannot be traced to a"
            f" verified candidate: {exc}"
        ) from exc
    recomputed = bundle.identity
    if bundle.candidate_hash != expected_hash or (
        recomputed.base_image_digest,
        recomputed.instruction_hash,
        recomputed.adapter_identity,
    ) != (identity.base_image_digest, identity.instruction_hash, identity.adapter_identity):
        raise PublicationRefused(
            f"{candidate_dir} recomputes to candidate hash {bundle.candidate_hash}"
            f" {recomputed.to_dict()}, but the record carries {expected_hash}"
            f" {identity.to_dict()} — identity is never trusted from a recorded value"
        )
    vendored_verified = False
    if results_repo is not None:
        copy = candidate_copy_dir(results_repo, identity)
        if copy.exists():
            try:
                summary = ozcandidate.verify_bundle(copy)
            except ozcandidate.CandidateError as exc:
                raise PublicationRefused(
                    f"the vendored candidate copy {copy} fails verification: {exc}"
                ) from exc
            vendored = CandidateIdentity.recomputed(
                summary.base_digest, summary.instruction_hash, summary.adapter
            )
            if candidate_hash(vendored) != expected_hash:
                raise PublicationRefused(
                    f"the vendored candidate copy {copy} recomputes to"
                    f" {candidate_hash(vendored)}, not the record's {expected_hash}"
                )
            vendored_verified = True
    return Traceability(
        candidate_dir=candidate_dir,
        candidate_hash=expected_hash,
        vendored_copy_verified=vendored_verified,
    )


def validity_warnings(record: RunRecord) -> list[str]:
    """Every reason the run is not leaderboard-valid; empty means valid."""
    if record.leaderboard_valid:
        return []
    reasons = [f"leaderboard_valid is false for benchmark {record.benchmark!r}"]
    note = record.run_metadata.get("validity_note")
    if isinstance(note, str) and note:
        reasons.append(note)
    if record.resumed_from:
        reasons.append(f"Resume Leg (resumed_from={record.resumed_from})")
    if record.run_metadata.get("evaluated") is False:
        reasons.append("the run was never evaluated (scores are zeroed placeholders)")
    failure = record.run_metadata.get("failure")
    if isinstance(failure, dict) and failure.get("class"):
        reasons.append(f"classified failure {failure['class']!r} at {failure.get('phase')!r}")
    return reasons


# ---------------------------------------------------------------------------
# Planning and staging
# ---------------------------------------------------------------------------


def _same_bytes(a: Path, b: Path) -> bool:
    return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()


def plan_publication(
    run_ids: list[str],
    *,
    results_repo: Path,
    dest: Path,
    candidates_dir: Path,
    allow_invalid: bool,
) -> PublicationPlan:
    """Check every run before anything is staged.  Refusals accumulate per run
    so the operator sees them all at once; the caller stages only a plan with
    none."""
    if not run_ids:
        raise PublicationRefused("no run ids given")
    if len(set(run_ids)) != len(run_ids):
        raise PublicationRefused("run ids repeat: " + ", ".join(sorted({r for r in run_ids if run_ids.count(r) > 1})))
    plan = PublicationPlan(dest=Path(dest), runs=[])
    for run_id in run_ids:
        source_dir, record = find_run_record(results_repo, run_id)
        planned = PlannedRun(run_id=run_id, source_dir=source_dir, record=record, dest_dir=plan.dest / run_id)
        plan.runs.append(planned)
        try:
            planned.traceability = check_traceability(
                record.candidate, candidates_dir=candidates_dir, results_repo=results_repo
            )
        except PublicationRefused as exc:
            planned.refusals.append(f"untraceable: {exc}")
        warnings = validity_warnings(record)
        planned.warnings.extend(warnings)
        if warnings and not allow_invalid:
            planned.refusals.append(
                "leaderboard_valid is false; pass --allow-invalid to publish it anyway"
                " (it can never enter a leaderboard: tooling filters on the flag)"
            )
        if planned.dest_dir.exists():
            if all(_same_bytes(source_dir / name, planned.dest_dir / name) for name in RECORD_FILES):
                planned.already_staged = True
            else:
                planned.refusals.append(
                    f"{planned.dest_dir} already exists with different content — a"
                    " staged record is never overwritten; resolve by hand"
                )
    return plan


def stage_publication(plan: PublicationPlan) -> list[Path]:
    """Copy the records of a refusal-free plan byte for byte; return the files
    written.  Raises :class:`PublicationRefused` (writing nothing) otherwise."""
    if plan.refusals:
        raise PublicationRefused("refusals:\n  " + "\n  ".join(plan.refusals))
    written: list[Path] = []
    for run in plan.to_stage:
        run.dest_dir.mkdir(parents=True, exist_ok=False)
        for name in RECORD_FILES:
            target = run.dest_dir / name
            shutil.copyfile(run.source_dir / name, target)
            written.append(target)
    return written


def format_plan(plan: PublicationPlan, *, dry_run: bool) -> str:
    lines = [f"destination: {plan.dest}"]
    for run in plan.runs:
        trace = run.traceability
        where = trace.candidate_dir.name if trace else "UNTRACEABLE"
        status = "already staged (identical)" if run.already_staged else ("would stage" if dry_run else "stage")
        lines.append(
            f"  {run.run_id}: candidate {where}, benchmark {run.record.benchmark}, mode"
            f" {run.record.mode}, leaderboard_valid={str(run.record.leaderboard_valid).lower()}"
            f" — {status}"
        )
        for reason in run.warnings:
            lines.append(f"    WARNING: {reason}")
        for reason in run.refusals:
            lines.append(f"    REFUSED: {reason}")
    if plan.refusals:
        lines.append("nothing staged: resolve every REFUSED line above")
    else:
        for run in plan.to_stage:
            for name in RECORD_FILES:
                lines.append(f"  {'A' if not dry_run else '+'} {run.dest_dir / name}")
        lines.append(
            "this script ran no git command: review the staged files and commit them —"
            " the commit is the approval stamp"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Discovery of published results — by manifest, never by path convention
# ---------------------------------------------------------------------------


def iter_published_records(root: Path = DEFAULT_PUBLISHED_DIR) -> Iterator[tuple[Path, RunRecord]]:
    """Every published record under *root*, wherever the operator placed it:
    a directory is a published run iff it holds ``manifest.json`` beside
    ``scores.json`` and the pair re-proves as a record whose ``run_id`` is
    the directory's name.  Malformed pairs raise; directory layout above the
    record carries no meaning."""
    root = Path(root)
    if not root.is_dir():
        return
    for manifest in sorted(root.rglob(MANIFEST_FILENAME)):
        run_dir = manifest.parent
        if any(part.startswith(".") for part in run_dir.relative_to(root).parts):
            continue
        if not (run_dir / SCORES_FILENAME).is_file():
            raise ResultsRepoError(f"{run_dir}: {MANIFEST_FILENAME} without {SCORES_FILENAME}")
        record = RunRecord.from_dicts(
            json.loads(manifest.read_text(encoding="utf-8")),
            json.loads((run_dir / SCORES_FILENAME).read_text(encoding="utf-8")),
        )
        if record.run_id != run_dir.name:
            raise ResultsRepoError(
                f"{run_dir}: manifest run_id {record.run_id!r} does not match the directory name"
            )
        yield run_dir, record


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage run records into published/ (traceability = hard refusal, validity = warning; never commits)."
    )
    parser.add_argument("run_ids", nargs="+", metavar="RUN_ID")
    parser.add_argument(
        "--results-repo", type=Path, default=None,
        help=f"the private Results Repo clone (or ${RESULTS_REPO_ENV})",
    )
    parser.add_argument("--dest", type=Path, required=True, help="destination, e.g. published/<subdir>")
    parser.add_argument("--candidates-dir", type=Path, default=DEFAULT_CANDIDATES_DIR)
    parser.add_argument("--allow-invalid", action="store_true", help="stage runs with leaderboard_valid: false")
    parser.add_argument("--dry-run", action="store_true", help="check everything, stage nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    results_repo = resolve_results_repo(args.results_repo)
    if results_repo is None:
        print(f"REFUSED: pass --results-repo or set ${RESULTS_REPO_ENV}", file=sys.stderr)
        return 1
    try:
        plan = plan_publication(
            args.run_ids,
            results_repo=results_repo,
            dest=args.dest,
            candidates_dir=args.candidates_dir,
            allow_invalid=args.allow_invalid,
        )
        print(format_plan(plan, dry_run=args.dry_run))
        if plan.refusals:
            return 1
        if not args.dry_run:
            stage_publication(plan)
    except PublicationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
