"""Candidate Bundle ingestion: the trust boundary for every published result.

A Benchmark Candidate enters the bench as a **Candidate Bundle** — the
self-contained export TheOzolith's ``theozolith candidate export`` writes
(``candidate.json`` + the generated ``Dockerfile`` + the compiled knowledge
tree + the baked policy tree; ``docs/specs/BENCH-CONTRACT.md``, ADR-0054) —
and nothing else (CONTEXT.md → Candidate Bundle).  This module is the only
path from a path on disk to a :class:`~silverquillm.results_repo.CandidateIdentity`
the bench will attribute results to, and it never trusts a recorded value:

1. **Load** — resolve the path (a bundle directory, or a checked-in candidate
   directory ``<slug>--<hash8>/`` wrapping one under ``bundle/``), parse
   ``candidate.json`` strictly (a JSON object, duplicate keys refused).
2. **Refuse secret values** — the bundle carries secret slot *names* only.  A
   slot entry that is not an environment-variable name, a manifest field
   shaped like a credential carrier, or any bundle byte that looks like a
   credential (API-key, token, private-key shapes; a declared slot assigned
   a credential-shaped value) is a hard refusal that names the file and the
   shape, never the value.
3. **Verify** — delegate to TheOzolith's published verifier
   (``theozolith_control.candidate.verify_bundle``, ``bundle_format_version``
   / ``identity_spec_version`` surface): strict manifest parse, knowledge and
   policy pins recomputed from bundle bytes, the materialized setup and the
   instruction hash recomputed through the production formula (the published
   golden vectors pin it), the Dockerfile byte-matched against the production
   codegen, the layout allowlisted.  The bench does not reimplement the hash
   — a hand-rolled copy would drift silently (BENCH-CONTRACT.md).
4. **Compare** — the recomputed identity triple must equal every identity the
   bundle records (``candidate.json``'s ``base_digest``, ``instruction_hash``
   and ``adapter``) and, when the candidate directory is named
   ``<slug>--<hash8>``, the recomputed :func:`~silverquillm.results_repo.candidate_hash`
   must carry that suffix — a mismatch is a hard refusal printing both values.

The adapter is an opaque field throughout: nothing here (or anywhere in the
bench) allowlists adapter names — claude and codex today, Pi later; which
adapters a bundle *can* name is TheOzolith's parse gate, consumed through the
verifier, never restated.

Two more responsibilities live here because they are the same trust boundary:

- :func:`vendor_candidate` writes the vendored copy a results repo keeps at
  ``results/<candidate-hash>/candidate/`` — write-once, verified at write time
  (the copy must recompute to the directory's hash; fail loud), immutable; a
  second run of the same candidate skips the write, and a pre-existing copy
  that no longer recomputes to its directory is refused, never repaired.
- :func:`build_candidate_image` runs TheOzolith's *verified* standalone build
  (private snapshot → full verification → ``docker build`` → deterministic
  tag) and resolves the tag to the image ID the driver then launches by, after
  checking the image's identity labels against the bundle — a stale or
  re-pointed local tag can never substitute another image.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from theozolith_control import candidate as ozcandidate
from theozolith_nodedaemon.builds import LABEL_BASE_DIGEST, LABEL_INSTRUCTION_HASH

from silverquillm.results_repo import (
    CandidateIdentity,
    candidate_copy_dir,
    candidate_hash,
    candidate_hash8,
)

__all__ = [
    "BUNDLE_SUBDIR",
    "MANIFEST_NAME",
    "BuiltImage",
    "CandidateBundle",
    "CandidateRefusedError",
    "CandidateVendorError",
    "ImageBuildError",
    "VendoredCandidate",
    "build_candidate_image",
    "load_candidate_bundle",
    "resolve_candidate_path",
    "vendor_candidate",
]

#: The bundle's machine manifest — TheOzolith's name, never restated.
MANIFEST_NAME = ozcandidate.MANIFEST_NAME
#: Where a checked-in candidate directory (``candidates/<slug>--<hash8>/``)
#: keeps the bundle proper; the bundle's layout allowlist leaves no room for a
#: README or the exported source beside ``candidate.json``, so those sit one
#: level up.
BUNDLE_SUBDIR = "bundle"

# <slug>--<hash8>: the checked-in candidate directory name (issue #39 §4).
_CANDIDATE_DIRNAME_RE = re.compile(r"(?P<slug>[A-Za-z0-9][A-Za-z0-9._-]*?)--(?P<hash8>[0-9a-f]{8})")
# A secret SLOT is an environment-variable name; anything else in the slot
# list is something a value could hide in.
_SLOT_NAME_RE = re.compile(r"[A-Z][A-Z0-9_]*")
# Manifest fields whose name says "I carry a credential value" — refused with
# the secret-values message before the verifier's generic unknown-field
# refusal, so the operator learns what actually went wrong.
_VALUE_CARRIER_KEYWORDS = ("secret", "credential", "token", "password", "api_key", "apikey", "env")
# Credential shapes.  A hit names the file and the shape — never the bytes.
_CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("Anthropic API key", re.compile(rb"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI API key", re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}")),
    ("GitHub token", re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("GitHub fine-grained token", re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("AWS access key id", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(rb"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("private key block", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("JSON Web Token", re.compile(rb"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("bearer credential", re.compile(rb"(?i)\bbearer\s+[A-Za-z0-9_\-.=]{20,}")),
)
_SLOT_ASSIGNMENT_VALUE = rb"\s*[=:]\s*[\"']?[A-Za-z0-9_\-.]{20,}"


class CandidateRefusedError(Exception):
    """The path is not an admissible Candidate Bundle — a hard refusal."""


class CandidateVendorError(Exception):
    """The vendored candidate copy in the results repo could not be written or
    no longer recomputes to its directory."""


class ImageBuildError(Exception):
    """The verified standalone build failed, or the built image is not the
    candidate's."""


class Verifier(Protocol):
    """The shape of TheOzolith's ``verify_bundle``: a bundle directory in, the
    recomputed identity summary out (``base_digest``, ``instruction_hash``,
    ``adapter``, ``tag``, ``worker_type``), or ``CandidateError``."""

    def __call__(self, bundle: Path) -> Any: ...


@dataclass(frozen=True)
class CandidateBundle:
    """A verified Candidate Bundle and the identity recomputed from it."""

    path: Path
    """The directory the operator named (the bundle, or the wrapping candidate dir)."""
    bundle_path: Path
    """The bundle directory TheOzolith's verifier authenticated."""
    manifest: Mapping[str, Any]
    identity: CandidateIdentity
    candidate_hash: str
    hash8: str
    worker_type: str
    adapter: str
    base: str
    base_digest: str
    instruction_hash: str
    tag: str
    driver: str
    model: str
    effort: str
    setup: tuple[str, ...]
    knowledge: str
    knowledge_pin: str
    knowledge_target: str
    policy: str
    policy_pin: str
    secret_slots: tuple[str, ...]
    product_version: str
    exported_at: str
    bundle_format_version: int | None
    identity_spec_version: int | None

    def summary_dict(self) -> dict[str, Any]:
        """The evidence view of the candidate (identity, provenance, slot
        *names*) — nothing here is ever a secret value."""
        return {
            "path": str(self.path),
            "bundle_path": str(self.bundle_path),
            "candidate_hash": self.candidate_hash,
            "hash8": self.hash8,
            "identity": self.identity.to_dict(),
            "worker_type": self.worker_type,
            "adapter": self.adapter,
            "base": self.base,
            "base_digest": self.base_digest,
            "instruction_hash": self.instruction_hash,
            "tag": self.tag,
            "driver": self.driver,
            "model": self.model,
            "effort": self.effort,
            "setup": list(self.setup),
            "knowledge": self.knowledge,
            "knowledge_pin": self.knowledge_pin,
            "knowledge_target": self.knowledge_target,
            "policy": self.policy,
            "policy_pin": self.policy_pin,
            "secret_slots": list(self.secret_slots),
            "product_version": self.product_version,
            "exported_at": self.exported_at,
            "bundle_format_version": self.bundle_format_version,
            "identity_spec_version": self.identity_spec_version,
        }


@dataclass(frozen=True)
class VendoredCandidate:
    """The vendored copy in a results repo: where it is, and whether this
    call wrote it (``False`` = it already existed and re-verified)."""

    path: Path
    written: bool

    def to_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "written": self.written}


@dataclass(frozen=True)
class BuiltImage:
    """The candidate's derived image: the deterministic tag the verified build
    applied and the image ID the driver launches by."""

    tag: str
    image_id: str

    def to_dict(self) -> dict[str, str]:
        return {"tag": self.tag, "id": self.image_id}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def resolve_candidate_path(path: Path) -> tuple[Path, Path]:
    """``(bundle_dir, candidate_dir)`` for *path*.

    *path* is either a Candidate Bundle directory (holds ``candidate.json``)
    or a checked-in candidate directory holding the bundle under
    :data:`BUNDLE_SUBDIR` beside its README; anything else is refused.
    """
    candidate_dir = Path(path)
    if not candidate_dir.is_dir():
        raise CandidateRefusedError(f"{candidate_dir} is not a directory")
    if (candidate_dir / MANIFEST_NAME).is_file():
        return candidate_dir, candidate_dir
    wrapped = candidate_dir / BUNDLE_SUBDIR
    if (wrapped / MANIFEST_NAME).is_file():
        return wrapped, candidate_dir
    raise CandidateRefusedError(
        f"{candidate_dir} is not a Candidate Bundle: neither {MANIFEST_NAME} nor"
        f" {BUNDLE_SUBDIR}/{MANIFEST_NAME} exists — `silverquillm run --candidate`"
        " accepts only a bundle exported by `theozolith candidate export`"
        " (CONTEXT.md → Candidate Bundle)"
    )


def _refuse_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CandidateRefusedError(f"{MANIFEST_NAME} carries duplicate field {key!r}")
        result[key] = value
    return result


def _read_manifest(bundle_dir: Path) -> dict[str, Any]:
    path = bundle_dir / MANIFEST_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_refuse_duplicate_keys)
    except (OSError, ValueError) as exc:
        raise CandidateRefusedError(f"{path} does not parse as JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CandidateRefusedError(f"{path} must be a JSON object")
    return raw


def _refuse_secret_values(bundle_dir: Path, manifest: Mapping[str, Any]) -> None:
    """Secret slot NAMES travel; values never do.  Every finding is reported
    by file and shape only."""
    for key in manifest:
        if key == "secret_slots":
            continue
        lowered = key.lower()
        if any(word in lowered for word in _VALUE_CARRIER_KEYWORDS):
            raise CandidateRefusedError(
                f"{MANIFEST_NAME} carries field {key!r}, which is shaped like a secret-value"
                " carrier — a Candidate Bundle carries secret slot NAMES only"
                " (secret_slots); a value in a bundle is a hard refusal"
            )
    slots = manifest.get("secret_slots", [])
    if not isinstance(slots, list):
        raise CandidateRefusedError(f"{MANIFEST_NAME}: secret_slots must be a list of slot names")
    for index, slot in enumerate(slots):
        if not isinstance(slot, str) or not _SLOT_NAME_RE.fullmatch(slot):
            raise CandidateRefusedError(
                f"{MANIFEST_NAME}: secret_slots[{index}] is not an environment-variable"
                " name — a slot entry carries the NAME a consumer binds, never a value"
                " (refused without echoing the entry)"
            )
    slot_patterns = [
        (f"a value assigned to secret slot {slot}", re.compile(rb"\b" + slot.encode("ascii") + _SLOT_ASSIGNMENT_VALUE))
        for slot in slots
    ]
    for dirpath, _dirnames, filenames in os.walk(bundle_dir, followlinks=False):
        for name in sorted(filenames):
            file = Path(dirpath) / name
            try:
                mode = os.lstat(file).st_mode
            except OSError as exc:
                raise CandidateRefusedError(f"cannot inspect bundle entry {file}: {exc}") from exc
            if not stat.S_ISREG(mode):
                continue  # the verifier refuses symlinks and special files by shape
            try:
                data = file.read_bytes()
            except OSError as exc:
                raise CandidateRefusedError(f"cannot read bundle entry {file}: {exc}") from exc
            rel = file.relative_to(bundle_dir)
            for label, pattern in (*_CREDENTIAL_PATTERNS, *slot_patterns):
                if pattern.search(data):
                    raise CandidateRefusedError(
                        f"bundle entry {rel} contains what looks like {label} — a Candidate"
                        " Bundle carries secret slot NAMES only; a secret value anywhere"
                        " in the bundle is a hard refusal (the value is not echoed)"
                    )


def _string(manifest: Mapping[str, Any], key: str) -> str:
    value = manifest.get(key, "")
    return value if isinstance(value, str) else ""


def _int_or_none(manifest: Mapping[str, Any], key: str) -> int | None:
    value = manifest.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def load_candidate_bundle(path: Path, *, verifier: Verifier | None = None) -> CandidateBundle:
    """Ingest the Candidate Bundle at *path*: load, refuse secret values,
    verify through TheOzolith's verifier, and compare the recomputed identity
    against everything the bundle records.  Every failure is a
    :class:`CandidateRefusedError`; nothing about the bundle is trusted until
    this returns."""
    bundle_dir, candidate_dir = resolve_candidate_path(path)
    manifest = _read_manifest(bundle_dir)
    _refuse_secret_values(bundle_dir, manifest)

    verify = verifier if verifier is not None else ozcandidate.verify_bundle
    try:
        summary = verify(bundle_dir)
    except ozcandidate.CandidateError as exc:
        raise CandidateRefusedError(
            f"{bundle_dir} failed TheOzolith's bundle verification: {exc}"
        ) from exc

    try:
        identity = CandidateIdentity.recomputed(
            summary.base_digest, summary.instruction_hash, summary.adapter
        )
    except Exception as exc:  # a malformed verifier result is a refusal
        raise CandidateRefusedError(
            f"the verifier returned an unusable identity for {bundle_dir}: {exc}"
        ) from exc

    # The recorded identity is a convenience the verifier already checked; the
    # bench states its own trust boundary in its own words, printing both.
    for field, recorded, recomputed in (
        ("base_digest", _string(manifest, "base_digest"), identity.base_image_digest),
        ("instruction_hash", _string(manifest, "instruction_hash"), identity.instruction_hash),
        ("adapter", _string(manifest, "adapter"), identity.adapter_identity),
    ):
        if recorded != recomputed:
            raise CandidateRefusedError(
                f"{MANIFEST_NAME} records {field} {recorded!r} but the identity recomputed"
                f" from the bundle is {recomputed!r} — identity is never trusted from a"
                " recorded value (CONTEXT.md → Candidate Bundle)"
            )

    chash = candidate_hash(identity)
    hash8 = candidate_hash8(identity)
    named = _CANDIDATE_DIRNAME_RE.fullmatch(candidate_dir.name)
    if named and named.group("hash8") != hash8:
        raise CandidateRefusedError(
            f"candidate directory {candidate_dir.name!r} carries identity-hash suffix"
            f" {named.group('hash8')!r} but the bundle's recomputed identity hashes to"
            f" {hash8!r} ({chash}) — the directory name is a recorded value and is"
            " never trusted; rename it or re-export the candidate"
        )

    setup = manifest.get("setup", [])
    slots = manifest.get("secret_slots", [])
    return CandidateBundle(
        path=candidate_dir,
        bundle_path=bundle_dir,
        manifest=manifest,
        identity=identity,
        candidate_hash=chash,
        hash8=hash8,
        worker_type=str(getattr(summary, "worker_type", "") or _string(manifest, "worker_type")),
        adapter=identity.adapter_identity,
        base=_string(manifest, "base"),
        base_digest=identity.base_image_digest,
        instruction_hash=identity.instruction_hash,
        tag=str(getattr(summary, "tag", "")),
        driver=_string(manifest, "driver"),
        model=_string(manifest, "model"),
        effort=_string(manifest, "effort"),
        setup=tuple(str(item) for item in setup) if isinstance(setup, list) else (),
        knowledge=_string(manifest, "knowledge"),
        knowledge_pin=_string(manifest, "knowledge_pin"),
        knowledge_target=_string(manifest, "knowledge_target"),
        policy=_string(manifest, "policy"),
        policy_pin=_string(manifest, "policy_pin"),
        secret_slots=tuple(str(slot) for slot in slots) if isinstance(slots, list) else (),
        product_version=_string(manifest, "product_version"),
        exported_at=_string(manifest, "exported_at"),
        bundle_format_version=_int_or_none(manifest, "bundle_format_version"),
        identity_spec_version=_int_or_none(manifest, "identity_spec_version"),
    )


# ---------------------------------------------------------------------------
# The vendored copy in the results repo
# ---------------------------------------------------------------------------


def _copy_bundle_tree(source: Path, dest: Path) -> None:
    """Copy a bundle as regular files and directories only — a symlink or
    special file anywhere refuses (never followed, never copied) — with modes
    normalized to the two classes the tree hash distinguishes (755/644)."""
    dest.mkdir()
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        rel = Path(dirpath).relative_to(source)
        for name in sorted(dirnames):
            entry = Path(dirpath) / name
            if os.path.islink(entry) or not stat.S_ISDIR(os.lstat(entry).st_mode):
                raise CandidateVendorError(
                    f"bundle entry {rel / name} is not a regular directory — refused"
                )
            (dest / rel / name).mkdir()
        for name in sorted(filenames):
            entry = Path(dirpath) / name
            mode = os.lstat(entry).st_mode
            if os.path.islink(entry) or not stat.S_ISREG(mode):
                raise CandidateVendorError(
                    f"bundle entry {rel / name} is not a regular file — symlinks and"
                    " special files are refused"
                )
            target = dest / rel / name
            shutil.copyfile(entry, target)
            target.chmod(0o755 if mode & 0o111 else 0o644)


def _verify_copy(copy: Path, bundle: CandidateBundle, verify: Verifier) -> None:
    try:
        summary = verify(copy)
    except ozcandidate.CandidateError as exc:
        raise CandidateVendorError(f"vendored candidate copy {copy} fails verification: {exc}") from exc
    identity = CandidateIdentity.recomputed(
        summary.base_digest, summary.instruction_hash, summary.adapter
    )
    recomputed = candidate_hash(identity)
    if recomputed != bundle.candidate_hash:
        raise CandidateVendorError(
            f"vendored candidate copy {copy} recomputes to candidate hash {recomputed},"
            f" not the directory's {bundle.candidate_hash} — the copy is not this"
            " candidate; refusing (a vendored copy is never repaired in place)"
        )


def vendor_candidate(
    results_repo: Path,
    bundle: CandidateBundle,
    *,
    verifier: Verifier | None = None,
) -> VendoredCandidate:
    """Write ``results/<candidate-hash>/candidate/`` once, verified at write time.

    The copy is staged beside its destination, re-verified through the
    verifier (its recomputed identity must hash to the destination directory's
    name), and published with one atomic rename.  An existing copy is never
    overwritten: it is re-verified the same way and the write is skipped; a
    copy that no longer recomputes to its directory is a
    :class:`CandidateVendorError`.
    """
    verify = verifier if verifier is not None else ozcandidate.verify_bundle
    target = candidate_copy_dir(results_repo, bundle.identity)
    if target.exists():
        _verify_copy(target, bundle, verify)
        return VendoredCandidate(path=target, written=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".candidate-staging-", dir=target.parent))
    try:
        copy = staging / target.name
        _copy_bundle_tree(bundle.bundle_path, copy)
        _verify_copy(copy, bundle, verify)
        try:
            os.rename(copy, target)
        except OSError:
            if not target.is_dir():
                raise
            # Lost a race with another writer of the same candidate: the
            # copy that won must itself verify, and this one is dropped.
            _verify_copy(target, bundle, verify)
            return VendoredCandidate(path=target, written=False)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return VendoredCandidate(path=target, written=True)


# ---------------------------------------------------------------------------
# The derived image
# ---------------------------------------------------------------------------

Builder = Callable[[Path], str]
Inspector = Callable[[str], tuple[str, Mapping[str, str]]]


def _verified_build(bundle_dir: Path, docker_config: Path | None) -> str:
    """TheOzolith's verified standalone build (snapshot → verify → build →
    tag); returns the deterministic tag it applied."""
    try:
        return ozcandidate.build_candidate(bundle_dir, docker_config=docker_config).tag
    except ozcandidate.CandidateError as exc:
        raise ImageBuildError(str(exc)) from exc


def _inspect_image(tag: str) -> tuple[str, Mapping[str, str]]:
    """``(image id, labels)`` of the local image *tag* names."""
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{json .}}", tag],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ImageBuildError(f"cannot inspect image {tag}: {exc}") from exc
    if proc.returncode != 0:
        raise ImageBuildError(f"cannot inspect image {tag}: {(proc.stderr or '').strip()}")
    try:
        data = json.loads(proc.stdout)
    except ValueError as exc:
        raise ImageBuildError(f"docker image inspect {tag} returned malformed JSON") from exc
    if isinstance(data, list):
        data = data[0] if data else {}
    image_id = data.get("Id") if isinstance(data, dict) else None
    config = data.get("Config") if isinstance(data, dict) else None
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(image_id, str) or not image_id:
        raise ImageBuildError(f"docker image inspect {tag} reported no image id")
    return image_id, labels if isinstance(labels, dict) else {}


def build_candidate_image(
    bundle: CandidateBundle,
    *,
    builder: Builder | None = None,
    inspector: Inspector | None = None,
    docker_config: Path | None = None,
) -> BuiltImage:
    """Build the candidate's derived image through the verified build and
    return the tag plus the image ID the driver launches by.

    The image the tag resolves to must carry the candidate's own identity
    labels (base digest, instruction hash) — the tag is a local, mutable
    name, and the ID is what the run records.
    """
    build = builder if builder is not None else (lambda path: _verified_build(path, docker_config))
    inspect = inspector if inspector is not None else _inspect_image
    tag = build(bundle.bundle_path)
    if bundle.tag and tag != bundle.tag:
        raise ImageBuildError(
            f"the verified build tagged {tag!r}, but the bundle's deterministic tag is"
            f" {bundle.tag!r}"
        )
    image_id, labels = inspect(tag)
    for label, expected in (
        (LABEL_INSTRUCTION_HASH, bundle.instruction_hash),
        (LABEL_BASE_DIGEST, bundle.base_digest),
    ):
        actual = labels.get(label)
        if actual != expected:
            raise ImageBuildError(
                f"image {image_id} ({tag}) carries label {label}={actual!r}, not the"
                f" candidate's {expected!r} — the local tag does not name this"
                " candidate's image; refusing to launch it"
            )
    return BuiltImage(tag=tag, image_id=image_id)
