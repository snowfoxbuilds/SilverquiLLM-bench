#!/usr/bin/env python3
"""Promote a worker-type definition from the operator's private Config Repo into
the public, curated ``candidates/`` tree (issue #39 §4, #66 Part A).

A promoted candidate is one directory, ``candidates/<slug>--<hash8>/``:

    README.md                        a stub the operator completes (what the
                                     candidate varies) before committing
    source/worker-types/<type>.toml  the definition, base pinned by digest
    source/knowledge/<name>/         the referenced knowledge SOURCE tree
    source/policy/<name>/            the referenced Agent Policy tree
    bundle/                          the Candidate Bundle exported from source/

The bundle is the export TheOzolith's own tooling writes
(``theozolith_control.candidate.export_candidate``); the identity in the
directory name is the bench's candidate hash recomputed from the exported
bytes through the same ingestion every run uses
(:func:`silverquillm.candidate.load_candidate_bundle`).  Before anything is
written the copy is proven reproducible: re-exporting the vendored
``source/`` with the recorded ``exported_at`` must reproduce ``bundle/``
byte for byte — the property ``tests/test_reference_candidates.py`` holds
every checked-in candidate to.

**Vendor-at-promote is strict** (the-ozolith ADR-0048: the promoted copy
vendors the knowledge tree; the identity carries the pin).  A knowledge tree
the definition references is vendored in full, so it must be publishable:
the tree must exist in the source and carry a ``PUBLISHABLE`` marker file at
its root (the operator's explicit declaration; TheOzolith's knowledge loader
ignores the file and the compiled tree — the pin — never contains it).  A
missing tree or a missing marker is a hard refusal: knowledge that cannot be
published means the candidate cannot be promoted and its results cannot be
published.

Idempotent and side-effect-free on refusal: every check runs against a
private staging directory beside the destination, and the candidate
directory appears through one atomic rename at the very end.  An existing
directory for the same identity is a no-op (dedup by identity); an existing
directory under this name whose bundle does not recompute to it, or the
same identity already promoted under another slug, is a refusal.  This
script never runs git: the operator reviews the new directory and commits
it — the commit is the approval stamp.

Usage::

    python scripts/promote_candidate.py <config-repo-path> <worker-type>
        [--slug NAME] [--candidates-dir candidates] [--docker-config DIR] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from theozolith_control import candidate as ozcandidate

from silverquillm.candidate import (
    BUNDLE_SUBDIR,
    CandidateBundle,
    CandidateRefusedError,
    load_candidate_bundle,
)
from silverquillm.results_repo import (
    InvalidRunRecordError,
    candidate_dirname,
)

#: The operator's explicit declaration that a knowledge tree may be published:
#: a regular file of this name at the tree's root in the Config Repo.
PUBLISHABLE_MARKER = "PUBLISHABLE"
#: The token the README stub carries until the operator completes it; the
#: platform test refuses a checked-in candidate whose README still has it.
README_TODO_MARKER = "TODO(promote)"
SOURCE_SUBDIR = "source"
WORKER_TYPES_SUBDIR = "worker-types"
KNOWLEDGE_SUBDIR = "knowledge"
POLICY_SUBDIR = "policy"
DEFAULT_CANDIDATES_DIR = REPO_ROOT / "candidates"

_TREE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_TOP_LEVEL_BASE_LINE = re.compile(r'^(?P<lead>\s*base\s*=\s*)"(?P<value>[^"\\]*)"(?P<trail>\s*(?:#.*)?)$')
_TABLE_HEADER = re.compile(r"^\s*\[")
_VENDOR_IGNORED = frozenset({".git", "__pycache__", ".DS_Store"})

DigestResolver = Callable[[str], str]
Clock = Callable[[], str]


class PromotionRefused(Exception):
    """The candidate cannot be promoted; nothing was written."""


@dataclass(frozen=True)
class PromotionResult:
    """What promotion did: the candidate directory, whether this call wrote
    it (``False`` = the identity was already promoted there), and the
    verified bundle."""

    candidate_dir: Path
    written: bool
    bundle: CandidateBundle
    base_pinned_at_promote: bool
    notes: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Source inspection and the publishability gate
# ---------------------------------------------------------------------------


def _read_definition(source: Path, worker_type: str) -> tuple[Path, str, dict[str, Any]]:
    if not source.is_dir():
        raise PromotionRefused(f"config repo {source} is not a directory")
    if not _TREE_NAME.fullmatch(worker_type):
        raise PromotionRefused(
            f"worker type name {worker_type!r} must match ^[A-Za-z0-9][A-Za-z0-9._-]*$"
        )
    type_path = source / WORKER_TYPES_SUBDIR / f"{worker_type}.toml"
    if type_path.is_symlink() or not type_path.is_file():
        raise PromotionRefused(
            f"{source} has no {WORKER_TYPES_SUBDIR}/{worker_type}.toml (a regular file)"
        )
    text = type_path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PromotionRefused(f"{type_path} does not parse as TOML: {exc}") from exc
    return type_path, text, data


def _referenced_tree(data: dict[str, Any], key: str, prefix: str) -> str:
    """The bare tree name a ``knowledge = "knowledge/<name>"`` style reference
    names (``""`` when the definition carries none)."""
    ref = data.get(key, "")
    if not isinstance(ref, str):
        raise PromotionRefused(f"worker-type field {key!r} must be a string")
    if not ref:
        return ""
    if not ref.startswith(prefix) or not _TREE_NAME.fullmatch(ref[len(prefix) :]):
        raise PromotionRefused(
            f"worker-type field {key!r} must be '{prefix}<name>' (ADR-0048), got {ref!r}"
        )
    return ref[len(prefix) :]


def check_knowledge_publishable(source: Path, tree_name: str) -> Path:
    """The vendor-at-promote gate: the referenced knowledge tree must exist in
    the Config Repo and carry its :data:`PUBLISHABLE_MARKER`.  Returns the
    tree; raises :class:`PromotionRefused` naming the rule otherwise."""
    rule = (
        "knowledge that cannot be published means the candidate cannot be promoted"
        " and its results cannot be published (vendor-at-promote is strict — #39 §4,"
        " the-ozolith ADR-0048)"
    )
    tree = source / KNOWLEDGE_SUBDIR / tree_name
    if tree.is_symlink() or not tree.is_dir():
        raise PromotionRefused(
            f"the definition references knowledge tree {KNOWLEDGE_SUBDIR}/{tree_name},"
            f" which is absent from {source} — a promoted candidate vendors the full"
            f" knowledge tree, and an absent tree cannot be vendored: {rule}"
        )
    marker = tree / PUBLISHABLE_MARKER
    if marker.is_symlink() or not marker.is_file():
        raise PromotionRefused(
            f"knowledge tree {KNOWLEDGE_SUBDIR}/{tree_name} carries no {PUBLISHABLE_MARKER}"
            f" marker — promotion vendors the whole tree into the public candidates/"
            f" directory, so the operator must declare it publishable by adding a"
            f" regular file named {PUBLISHABLE_MARKER} at the tree's root (its text is"
            f" the basis, e.g. the license): {rule}"
        )
    return tree


def _check_policy_present(source: Path, tree_name: str) -> Path:
    tree = source / POLICY_SUBDIR / tree_name
    if tree.is_symlink() or not tree.is_dir():
        raise PromotionRefused(
            f"the definition references Agent Policy tree {POLICY_SUBDIR}/{tree_name},"
            f" which is absent from {source}; the promoted copy vendors it"
        )
    return tree


# ---------------------------------------------------------------------------
# Vendoring the source
# ---------------------------------------------------------------------------


def _copy_tree_strict(src: Path, dest: Path) -> None:
    """Copy a source tree as regular files and directories only: symlinks and
    special files refuse (never followed, never copied); ``.git``,
    ``__pycache__``, ``.DS_Store`` and bytecode are left out.  Exec bits are
    preserved — the knowledge compiler carries them into the pin."""
    dest.mkdir(parents=True)
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        rel = Path(dirpath).relative_to(src)
        dirnames[:] = sorted(d for d in dirnames if d not in _VENDOR_IGNORED)
        for name in dirnames:
            entry = Path(dirpath) / name
            if os.path.islink(entry) or not stat.S_ISDIR(os.lstat(entry).st_mode):
                raise PromotionRefused(
                    f"source entry {src.name}/{rel / name} is not a regular directory —"
                    " symlinks and special files cannot be vendored"
                )
            (dest / rel / name).mkdir()
        for name in sorted(filenames):
            if name in _VENDOR_IGNORED or name.endswith(".pyc"):
                continue
            entry = Path(dirpath) / name
            mode = os.lstat(entry).st_mode
            if os.path.islink(entry) or not stat.S_ISREG(mode):
                raise PromotionRefused(
                    f"source entry {src.name}/{rel / name} is not a regular file —"
                    " symlinks and special files cannot be vendored"
                )
            target = dest / rel / name
            shutil.copyfile(entry, target)
            target.chmod(0o755 if mode & 0o111 else 0o644)


def pin_base_in_definition(text: str, data: dict[str, Any], pinned_base: str) -> tuple[str, bool]:
    """The definition text with its top-level ``base`` pinned to *pinned_base*
    (``<ref>@sha256:<digest>``), and whether a rewrite happened.

    A source that already pins the base by digest is copied verbatim (it must
    equal what the export recorded).  A tag-only base — the Config Repo
    doctrine (ADR-0048) — is rewritten on its one top-level ``base = "..."``
    line so the vendored copy re-exports with no registry access; any other
    shape is refused rather than guessed at.
    """
    current = data.get("base")
    if not isinstance(current, str) or not current:
        raise PromotionRefused("the worker-type definition carries no string 'base'")
    if "@sha256:" in current:
        if current != pinned_base:
            raise PromotionRefused(
                f"the definition pins base {current!r} but the export recorded"
                f" {pinned_base!r}"
            )
        return text, False
    lines = text.splitlines(keepends=True)
    hits: list[int] = []
    for index, line in enumerate(lines):
        if _TABLE_HEADER.match(line):
            break
        match = _TOP_LEVEL_BASE_LINE.match(line.rstrip("\r\n"))
        if match and match.group("value") == current:
            hits.append(index)
    if len(hits) != 1:
        raise PromotionRefused(
            "cannot pin the base by digest in the vendored definition: expected exactly"
            f" one top-level line of the form base = \"{current}\" before any [table]"
            f" header, found {len(hits)} — pin the base by digest in the source"
            f" ({pinned_base!r}) and promote again"
        )
    index = hits[0]
    line = lines[index]
    newline = line[len(line.rstrip("\r\n")) :]
    match = _TOP_LEVEL_BASE_LINE.match(line.rstrip("\r\n"))
    assert match is not None
    lines[index] = f'{match.group("lead")}"{pinned_base}"{match.group("trail")}{newline}'
    rewritten = "".join(lines)
    try:
        reparsed = tomllib.loads(rewritten)
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - the rewrite is one string
        raise PromotionRefused(f"pinning the base produced unparseable TOML: {exc}") from exc
    expected = dict(data, base=pinned_base)
    if reparsed != expected:
        raise PromotionRefused(
            "pinning the base changed more than the base field; pin it by digest in the"
            " source and promote again"
        )
    return rewritten, True


# ---------------------------------------------------------------------------
# README stub
# ---------------------------------------------------------------------------


def render_readme_stub(
    slug: str,
    bundle: CandidateBundle,
    *,
    source: Path,
    knowledge_tree: str,
    policy_tree: str,
    base_pinned: bool,
    promoted_at: str,
) -> str:
    knowledge = (
        f"`{bundle.knowledge}` pinned `{bundle.knowledge_pin}` — compiled tree vendored"
        f" under `bundle/knowledge/`; source under `source/knowledge/{knowledge_tree}/`,"
        f" declared publishable by its `{PUBLISHABLE_MARKER}` marker"
        if bundle.knowledge
        else "none"
    )
    policy = (
        f"`{bundle.policy}` pinned `{bundle.policy_pin}` — baked tree vendored under"
        f" `bundle/policy/`; source under `source/policy/{policy_tree}/`"
        if bundle.policy
        else "none"
    )
    slots = ", ".join(f"`{slot}`" for slot in bundle.secret_slots) or "none"
    pin_note = (
        " The source carried the base tag only; promotion pinned it to the digest the"
        " export resolved (the one edit to the definition), so re-export needs no"
        " registry access."
        if base_pinned
        else ""
    )
    effort = f"`{bundle.effort}`" if bundle.effort else "the model's default"
    return f"""# {slug}

<!-- {README_TODO_MARKER}: complete this README before committing the candidate
     (the platform test refuses a checked-in README that still carries the
     marker). Delete this comment when done. -->

## What this candidate varies

{README_TODO_MARKER}: state what this candidate varies against the vanilla
reference candidates (model, effort, setup, knowledge tree, Agent Policy) and
why it exists.

## Identity

Recomputed from `bundle/` by TheOzolith's verifier on every run and every
test run — never trusted from this file or the directory name.

| | |
| --- | --- |
| Candidate hash | `{bundle.candidate_hash}` (hash8 `{bundle.hash8}`) |
| Worker type | `{bundle.worker_type}` |
| Adapter | `{bundle.adapter}` |
| Base image | `{bundle.base}` |
| Base digest | `{bundle.base_digest}` |
| Instruction hash | `{bundle.instruction_hash}` |
| Model / effort | `{bundle.model}` / {effort} |
| Setup | {", ".join(f"`{step}`" for step in bundle.setup) or "none"} |
| Knowledge | {knowledge} |
| Agent Policy | {policy} |
| Driver | `{bundle.driver}` (not identity-bearing) |
| Deterministic image tag | `{bundle.tag}` |
| Secret slots (names only) | {slots} |
| Exported | `{bundle.exported_at}` by theozolith-control {bundle.product_version} (bundle_format_version {bundle.bundle_format_version}, identity_spec_version {bundle.identity_spec_version}) |

## Provenance

- **Definition**: `source/worker-types/{bundle.worker_type}.toml`, promoted from
  the Config Repo at `{source}` by `scripts/promote_candidate.py` on
  {promoted_at}.{pin_note} Re-exporting `source/` with the recorded
  `exported_at` reproduces `bundle/` byte for byte
  (`tests/test_reference_candidates.py` proves it).
- **Base digest**: {README_TODO_MARKER}: record where the digest came from (the
  registry resolution at promote time, or the source's own pin) and how to
  re-resolve it.

## Run

```bash
silverquillm run --candidate candidates/{slug}--{bundle.hash8} --benchmark smoke --timeout 3600
```
"""


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


def _existing_identity(path: Path) -> CandidateBundle | None:
    """The verified bundle of an existing candidate directory, or ``None``
    when the directory is not one (a refusal the caller words)."""
    try:
        return load_candidate_bundle(path)
    except CandidateRefusedError:
        return None


def _check_destination(candidates_dir: Path, dirname: str, bundle: CandidateBundle) -> Path | None:
    """Dedup by identity.  Returns the existing directory when this identity
    is already promoted under *dirname*; raises on any conflict."""
    target = candidates_dir / dirname
    if target.exists():
        existing = _existing_identity(target)
        if existing is None or existing.candidate_hash != bundle.candidate_hash:
            raise PromotionRefused(
                f"{target} exists but its content is not this candidate: its bundle"
                " does not verify or recompute to this identity"
                f" ({bundle.candidate_hash}) — refusing to touch it; inspect or remove"
                " the directory by hand"
            )
        return target
    suffix = f"--{bundle.hash8}"
    for entry in sorted(candidates_dir.iterdir()) if candidates_dir.is_dir() else []:
        if not entry.is_dir() or entry.name.startswith(".") or not entry.name.endswith(suffix):
            continue
        existing = _existing_identity(entry)
        if existing is not None and existing.candidate_hash == bundle.candidate_hash:
            raise PromotionRefused(
                f"this identity ({bundle.candidate_hash}) is already promoted as"
                f" {entry} — candidates/ is flat and deduplicating (one directory per"
                " identity); promote under that slug or rename the directory by hand"
            )
    return None


def _prove_reproducible(staging: Path, bundle: CandidateBundle) -> None:
    """Re-export the vendored source with the recorded ``exported_at`` and
    require the checked-in bundle byte for byte."""
    reexport = staging / ".reexport"
    try:
        ozcandidate.export_candidate(
            staging / SOURCE_SUBDIR,
            bundle.worker_type,
            reexport,
            now=lambda: bundle.exported_at,
        )
    except ozcandidate.CandidateError as exc:
        raise PromotionRefused(
            f"the vendored source does not re-export: {exc} — the promoted copy must"
            " be self-contained"
        ) from exc
    original = staging / BUNDLE_SUBDIR
    checked = sorted(p.relative_to(original) for p in original.rglob("*") if p.is_file())
    fresh = sorted(p.relative_to(reexport) for p in reexport.rglob("*") if p.is_file())
    differing = [
        str(rel)
        for rel in sorted(set(checked) | set(fresh))
        if rel not in checked
        or rel not in fresh
        or (original / rel).read_bytes() != (reexport / rel).read_bytes()
    ]
    shutil.rmtree(reexport)
    if differing:
        raise PromotionRefused(
            "re-exporting the vendored source does not reproduce the bundle byte for"
            f" byte (differs: {', '.join(differing)}) — refusing to promote an"
            " irreproducible copy"
        )


def promote(
    source: Path,
    worker_type: str,
    *,
    candidates_dir: Path = DEFAULT_CANDIDATES_DIR,
    slug: str | None = None,
    docker_config: Path | None = None,
    resolve_digest: DigestResolver | None = None,
    now: Clock | None = None,
    dry_run: bool = False,
) -> PromotionResult:
    """Promote ``worker-types/<worker_type>.toml`` from the Config Repo at
    *source* into *candidates_dir*.  Raises :class:`PromotionRefused` (nothing
    written) on every refusal; never runs git."""
    source = Path(source).resolve()
    candidates_dir = Path(candidates_dir)
    slug = slug or worker_type
    type_path, text, data = _read_definition(source, worker_type)
    knowledge_tree = _referenced_tree(data, "knowledge", f"{KNOWLEDGE_SUBDIR}/")
    policy_tree = _referenced_tree(data, "policy", f"{POLICY_SUBDIR}/")
    knowledge_src = check_knowledge_publishable(source, knowledge_tree) if knowledge_tree else None
    policy_src = _check_policy_present(source, policy_tree) if policy_tree else None

    candidates_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".promote-{slug}-", dir=candidates_dir))
    try:
        try:
            ozcandidate.export_candidate(
                source,
                worker_type,
                staging / BUNDLE_SUBDIR,
                docker_config=docker_config,
                resolve_digest=resolve_digest,
                now=now,
            )
        except ozcandidate.CandidateError as exc:
            raise PromotionRefused(f"export failed: {exc}") from exc
        try:
            bundle = load_candidate_bundle(staging / BUNDLE_SUBDIR)
        except CandidateRefusedError as exc:
            raise PromotionRefused(f"the exported bundle is refused by the bench: {exc}") from exc
        try:
            dirname = candidate_dirname(slug, bundle.identity)
        except InvalidRunRecordError as exc:
            raise PromotionRefused(str(exc)) from exc

        existing = _check_destination(candidates_dir, dirname, bundle)
        if existing is not None:
            return PromotionResult(
                candidate_dir=existing,
                written=False,
                bundle=bundle,
                base_pinned_at_promote=False,
                notes=(f"already promoted: {existing} carries identity {bundle.candidate_hash}",),
            )

        vendored_text, base_pinned = pin_base_in_definition(text, data, bundle.base)
        source_copy = staging / SOURCE_SUBDIR
        (source_copy / WORKER_TYPES_SUBDIR).mkdir(parents=True)
        (source_copy / WORKER_TYPES_SUBDIR / type_path.name).write_text(vendored_text, encoding="utf-8")
        if knowledge_src is not None:
            _copy_tree_strict(knowledge_src, source_copy / KNOWLEDGE_SUBDIR / knowledge_tree)
        if policy_src is not None:
            _copy_tree_strict(policy_src, source_copy / POLICY_SUBDIR / policy_tree)
        _prove_reproducible(staging, bundle)

        promoted_at = time.strftime("%Y-%m-%d", time.gmtime())
        (staging / "README.md").write_text(
            render_readme_stub(
                slug,
                bundle,
                source=source,
                knowledge_tree=knowledge_tree,
                policy_tree=policy_tree,
                base_pinned=base_pinned,
                promoted_at=promoted_at,
            ),
            encoding="utf-8",
        )
        target = candidates_dir / dirname
        if dry_run:
            return PromotionResult(
                candidate_dir=target,
                written=False,
                bundle=bundle,
                base_pinned_at_promote=base_pinned,
                notes=(f"dry run: would write {target}",),
            )
        staging.chmod(0o755)
        try:
            os.rename(staging, target)
        except OSError as exc:
            raise PromotionRefused(f"cannot publish {target}: {exc}") from exc
        return PromotionResult(
            candidate_dir=target,
            written=True,
            bundle=bundle,
            base_pinned_at_promote=base_pinned,
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Promote a worker-type definition from a Config Repo into candidates/"
            " (vendor-at-promote is strict; never runs git)."
        )
    )
    parser.add_argument("config_repo", type=Path, help="local Config Repo (worker-types/ + knowledge/ + policy/)")
    parser.add_argument("worker_type", help="the worker-types/<name>.toml to promote")
    parser.add_argument("--slug", default=None, help="candidate slug (default: the worker type name)")
    parser.add_argument(
        "--candidates-dir",
        type=Path,
        default=DEFAULT_CANDIDATES_DIR,
        help="the curated candidates tree (default: candidates/ in this repo)",
    )
    parser.add_argument(
        "--docker-config",
        type=Path,
        default=None,
        help="DOCKER_CONFIG directory for resolving a private base tag (the digest never enters the bundle)",
    )
    parser.add_argument("--dry-run", action="store_true", help="run every check and write nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = promote(
            args.config_repo,
            args.worker_type,
            candidates_dir=args.candidates_dir,
            slug=args.slug,
            docker_config=args.docker_config,
            dry_run=args.dry_run,
        )
    except PromotionRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    bundle = result.bundle
    print(json.dumps(bundle.summary_dict(), indent=2, sort_keys=True))
    for note in result.notes:
        print(note)
    if result.written:
        print(f"promoted {result.candidate_dir}")
        print(
            f"next: complete {result.candidate_dir / 'README.md'} (every {README_TODO_MARKER!r}),"
            " run `pytest tests/test_reference_candidates.py -q`, review the diff, and"
            " commit — the commit is the approval stamp; this script ran no git command"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
