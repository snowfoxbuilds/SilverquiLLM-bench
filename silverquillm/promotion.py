"""Atomic promotion of explicit standalone definitions with a verified source copy."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from karn.definition import decode

from silverquillm.candidate import (
    CandidateRefusedError,
    load_candidate_bundle,
    scan_tree_for_credentials,
)
from silverquillm.created_directories import (
    CreatedDirectories,
    CreatedDirectoryError,
    rename_noreplace,
)
from silverquillm.results_repo import InvalidRunRecordError, candidate_dirname
from silverquillm.safe_files import atomic_write, read_regular


class PromotionRefused(CandidateRefusedError):
    pass


class PromotionCleanupError(PromotionRefused):
    pass


@dataclass(frozen=True)
class PromotionResult:
    candidate_dir: Path
    written: bool
    bundle: object
    notes: tuple[str, ...] = ()


def verify_source(directory, candidate=None):
    directory = Path(directory).absolute()
    candidate = candidate or load_candidate_bundle(directory)
    try:
        if directory.resolve() != directory:
            raise ValueError("symlink")
        source = directory / "source"
        if (
            source.is_symlink()
            or not source.is_dir()
            or set(os.listdir(source)) != {"definition.json"}
        ):
            raise ValueError("source layout")
        raw = read_regular(source / "definition.json")
        if decode(raw).encoded != candidate.definition.encoded:
            raise ValueError("source differs")
        inventory = json.loads(read_regular(directory / "source.json"))
        expected = {
            "source_version": 1,
            "definition_digest": candidate.definition.digest,
            "image": candidate.manifest["image"],
            "files": {"definition.json": "sha256:" + hashlib.sha256(raw).hexdigest()},
        }
        if inventory != expected:
            raise ValueError("source inventory differs")
        if scan_tree_for_credentials(directory, secret_slots=candidate.secret_slots):
            raise ValueError("credential-shaped source")
    except (OSError, ValueError, CandidateRefusedError):
        raise PromotionRefused(
            "curated candidate source is missing, unsafe or does not reproduce its definition"
        ) from None
    return candidate


def promote(source, *, candidates_dir, slug=None, dry_run=False):
    candidate = load_candidate_bundle(Path(source))
    for mount in candidate.manifest["runtime"]["mounts"]:
        if mount["source"]["kind"] == "bind":
            raise PromotionRefused(
                "a public candidate cannot require an unvendored host-local bind source"
            )
    try:
        dirname = candidate_dirname(slug or candidate.worker_type, candidate.identity)
    except InvalidRunRecordError as error:
        raise PromotionRefused(str(error)) from None
    root = Path(candidates_dir).absolute()
    if root.resolve() != root:
        raise PromotionRefused("candidate root contains a symlink")
    target = root / dirname
    if dry_run:
        if target.exists() or target.is_symlink():
            existing = verify_source(target)
            if existing.identity != candidate.identity:
                raise PromotionRefused("existing candidate identity differs")
        return PromotionResult(target, False, candidate, ("dry run: no files written",))
    created = CreatedDirectories()
    staging = None
    fd = None
    written = False
    try:
        created.make(root)
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fcntl.flock(fd, fcntl.LOCK_EX)
        if target.exists() or target.is_symlink():
            existing = verify_source(target)
            if existing.definition.encoded != candidate.definition.encoded:
                raise PromotionRefused("existing candidate definition differs")
            return PromotionResult(target, False, existing)
        suffix = "--" + candidate.hash8
        if any(p.name.endswith(suffix) for p in root.iterdir()):
            raise PromotionRefused("candidate hash already has another curated name")
        staging = Path(tempfile.mkdtemp(prefix=".promote-", dir=root))
        raw = candidate.definition.encoded + b"\n"
        atomic_write(staging / "bundle/definition.json", raw)
        atomic_write(staging / "source/definition.json", raw)
        atomic_write(
            staging / "source.json",
            json.dumps(
                {
                    "source_version": 1,
                    "definition_digest": candidate.definition.digest,
                    "image": candidate.manifest["image"],
                    "files": {"definition.json": "sha256:" + hashlib.sha256(raw).hexdigest()},
                },
                sort_keys=True,
            ),
        )
        atomic_write(
            staging / "README.md",
            f"# {candidate.worker_type}\n\nStandalone Karn Construct Definition.\n\nImage: `{candidate.manifest['image']}`\n\nDefinition: `{candidate.definition.digest}`\n\nThe source copy reproduces the selected definition; it does not attest an image build.\n",
        )
        verify_source(staging)
        staging.chmod(0o755)
        rename_noreplace(staging.name, dirname, dir_fd=fd)
        staging = None
        os.fsync(fd)
        written = True
        return PromotionResult(target, True, load_candidate_bundle(target))
    finally:
        cleanup_errors = []
        if staging is not None:
            try:
                shutil.rmtree(staging)
            except OSError:
                cleanup_errors.append(f"staging is KEPT at {staging}")
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                cleanup_errors.append("candidate directory descriptor close failed")
        try:
            if written or target.exists():
                created.keep()
            else:
                created.remove()
        except (OSError, CreatedDirectoryError):
            cleanup_errors.append(f"created directory cleanup is unconfirmed at {root}")
        if cleanup_errors:
            raise PromotionCleanupError("; ".join(cleanup_errors))
