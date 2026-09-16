"""Standalone Karn definition admission, immutable image verification and safe vendoring."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from karn.definition import MAX_DEFINITION_BYTES, Definition, DefinitionError, decode

from silverquillm.results_repo import (
    CandidateIdentity,
    candidate_copy_dir,
    candidate_hash,
    candidate_hash8,
)

MANIFEST_NAME = "definition.json"
BUNDLE_SUBDIR = "bundle"
_CANDIDATE_DIRNAME_RE = re.compile(r"(?P<slug>[A-Za-z0-9][A-Za-z0-9._-]*?)--(?P<hash8>[0-9a-f]{8})")

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
    (
        "JSON Web Token",
        re.compile(rb"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ),
    ("bearer credential", re.compile(rb"(?i)\bbearer\s+[A-Za-z0-9_\-.=]{20,}")),
)
# A declared secret slot used as an assignment KEY, in any of the forms a
# config or a log can take: the key optionally quoted (JSON, TOML, YAML and a
# shell all do), ``=`` or ``:`` as the operator, and the value whatever
# follows on the same line — a quoted string up to its closing quote, or a
# bare scalar up to the end of the line (a bare value has no delimiter, so
# nothing after it on the line is trusted).  Inside a quoted string a
# backslash escapes the next character, so an escaped quote (``\"``) or an
# escaped backslash (``\\``) belongs to the value and the string closes only
# at an unescaped quote — the way JSON and every serializer that emits it
# write a value that happens to contain a quote; a quote that never closes
# falls through to the bare form.  No length and no character-class rule: a
# two-character value is as much a secret as a forty-character one.  The
# pattern admits an EMPTY value on purpose, so that emptiness is decided in
# exactly one place, :func:`_assigned_value`.
_SLOT_ASSIGNMENT_TEMPLATE = (
    rb"(?<![A-Za-z0-9_])(?P<q>[\"']?)%s(?P=q)[ \t]*[=:][ \t]*"
    rb"(?:\"(?P<dq>(?:[^\"\\\r\n]|\\[^\r\n])*)\"(?![\"'])"
    rb"|'(?P<sq>(?:[^'\\\r\n]|\\[^\r\n])*)'(?![\"'])"
    rb"|(?P<bare>[^\r\n]*))"
)


def _assigned_value(match: re.Match[bytes]) -> bytes:
    """The scalar a slot-assignment match assigns, stripped of surrounding
    whitespace: empty for ``SLOT=``, ``SLOT = ""`` and ``"SLOT": ''`` — the
    forms a worker-type definition's ``[secrets]`` table and a config
    template use to *declare* a slot, which leak nothing."""
    for group in ("dq", "sq", "bare"):
        value = match.group(group)
        if value is not None:
            return value.strip()
    return b""


def _any_match(match: re.Match[bytes]) -> bool:
    return True


def _non_empty_assignment(match: re.Match[bytes]) -> bool:
    return bool(_assigned_value(match))


@dataclass(frozen=True)
class _Shape:
    """One credential shape: a bytes pattern and the predicate a match must
    also satisfy.  :func:`scan_tree_for_credentials` and
    :func:`redact_credentials` share these, so what one refuses the other
    blanks — and neither ever surfaces the matched bytes."""

    label: str
    pattern: re.Pattern[bytes]
    accept: Callable[[re.Match[bytes]], bool] = _any_match

    def found(self, data: bytes) -> bool:
        return any(self.accept(match) for match in self.pattern.finditer(data))

    def redact(self, data: bytes) -> bytes:
        placeholder = f"[redacted: {self.label}]".encode()
        return self.pattern.sub(
            lambda match: placeholder if self.accept(match) else match.group(0), data
        )


_CREDENTIAL_SHAPES: tuple[_Shape, ...] = tuple(
    _Shape(label, pattern) for label, pattern in _CREDENTIAL_PATTERNS
)


def _slot_shapes(secret_slots: Iterable[str]) -> list[_Shape]:
    return [
        _Shape(
            f"a value assigned to secret slot {slot}",
            re.compile(_SLOT_ASSIGNMENT_TEMPLATE % re.escape(slot.encode("ascii"))),
            _non_empty_assignment,
        )
        for slot in secret_slots
        if isinstance(slot, str) and _SLOT_NAME_RE.fullmatch(slot)
    ]


def credential_shapes() -> tuple[str, ...]:
    """The names of every credential shape the detector recognizes (the
    declared-slot assignment shape is per slot and reads ``a value assigned
    to secret slot <NAME>``)."""
    return tuple(shape.label for shape in _CREDENTIAL_SHAPES) + (
        "a value assigned to a declared secret slot",
    )


@dataclass(frozen=True)
class CredentialFinding:
    """One file that carries a credential shape: *where* (relative to the
    scanned root) and *what shape* — never the bytes."""

    path: Path
    shape: str

    def __str__(self) -> str:
        return f"{self.path}: {self.shape}"


def scan_tree_for_credentials(
    root: Path, *, secret_slots: Iterable[str] = (), what: str = "entry"
) -> list[CredentialFinding]:
    """Scan every regular file under *root* for a credential shape — the
    complete pattern set (API keys, GitHub / AWS / Slack tokens, private-key
    blocks, JWTs, bearer credentials) plus any of *secret_slots* used as an
    assignment key with a non-empty value, whatever that value's length or
    characters — and return one finding per hit, by path and shape only.

    Strict on the tree: symlinks (to files or directories) and special files
    are a :class:`CandidateRefusedError`, never followed; an unreadable file
    is a refusal naming the file.  Bytes are matched as bytes, so a binary
    file is scanned like any other and nothing is ever decoded or echoed.
    """
    root = Path(root)
    shapes = (*_CREDENTIAL_SHAPES, *_slot_shapes(secret_slots))
    findings: list[CredentialFinding] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = Path(dirpath).relative_to(root)
        for name in sorted(dirnames):
            entry = Path(dirpath) / name
            if os.path.islink(entry) or not stat.S_ISDIR(os.lstat(entry).st_mode):
                raise CandidateRefusedError(
                    f"{what} {rel_dir / name} is not a regular directory — symlinks and"
                    " special files are refused"
                )
        for name in sorted(filenames):
            file = Path(dirpath) / name
            rel = rel_dir / name
            try:
                mode = os.lstat(file).st_mode
            except OSError as exc:
                raise CandidateRefusedError(f"cannot inspect {what} {rel}: {exc}") from exc
            if os.path.islink(file) or not stat.S_ISREG(mode):
                raise CandidateRefusedError(
                    f"{what} {rel} is not a regular file — symlinks and special files are refused"
                )
            try:
                data = file.read_bytes()
            except OSError as exc:
                raise CandidateRefusedError(
                    f"cannot read {what} {rel} ({exc.strerror or type(exc).__name__}) — an"
                    " unreadable file cannot be cleared of secret values"
                ) from exc
            for shape in shapes:
                if shape.found(data):
                    findings.append(CredentialFinding(path=rel, shape=shape.label))
                    break
    return findings


def redact_credentials(text: str, *, secret_slots: Iterable[str] = ()) -> str:
    """*text* with every credential shape replaced by ``[redacted: <shape>]``
    — for log lines, state files and error summaries that must never carry
    a value even when an exception message does.  The same shapes as
    :func:`scan_tree_for_credentials`: a declared slot assigned a value of
    any length or character set is blanked whole (key, operator and value;
    a bare value to the end of its line, a quoted one to its closing quote
    with every escaped quote or backslash inside it — no fragment of the
    value survives), an empty assignment is left as it is."""
    data = text.encode("utf-8", errors="surrogateescape")
    for shape in (*_CREDENTIAL_SHAPES, *_slot_shapes(secret_slots)):
        data = shape.redact(data)
    return data.decode("utf-8", errors="replace")


class CandidateRefusedError(Exception):
    """The path is not an admissible Candidate Bundle — a hard refusal."""


class CandidateVendorError(Exception):
    """The vendored candidate copy in the results repo could not be written or
    no longer recomputes to its directory."""


class ImageBuildError(Exception):
    """The verified standalone build failed, or the built image is not the
    candidate's."""


@dataclass(frozen=True)
class CandidateBundle:
    path: Path
    bundle_path: Path
    definition: Definition
    identity: CandidateIdentity

    @property
    def manifest(self):
        return self.definition.document

    @property
    def candidate_hash(self):
        return candidate_hash(self.identity)

    @property
    def hash8(self):
        return candidate_hash8(self.identity)

    @property
    def worker_type(self):
        return self.manifest["name"]

    @property
    def secret_slots(self):
        return tuple(
            sorted(
                {
                    row["source"]["secret"].upper().replace("-", "_").replace(".", "_")
                    for row in self.manifest["runtime"]["credentials"]
                    if row["source"]["type"] == "raw"
                }
            )
        )

    def summary_dict(self):
        return {
            "path": str(self.path),
            "definition": self.manifest,
            "candidate_hash": self.candidate_hash,
            "hash8": self.hash8,
            "identity": self.identity.to_dict(),
            "definition_version": self.manifest["definition_version"],
            "image": self.manifest["image"],
            "secret_slots": list(self.secret_slots),
        }


@dataclass(frozen=True)
class VendoredCandidate:
    path: Path
    written: bool

    def to_dict(self):
        return {"path": str(self.path), "written": self.written}


@dataclass(frozen=True)
class BuiltImage:
    tag: str
    image_id: str

    def to_dict(self):
        return {"reference": self.tag, "id": self.image_id}


def resolve_candidate_path(path: Path) -> tuple[Path, Path]:
    path = Path(path).absolute()
    if path.resolve() != path:
        raise CandidateRefusedError("candidate path contains a symlink")
    if path.is_file():
        return path, path.parent
    for relative in (MANIFEST_NAME, BUNDLE_SUBDIR + "/" + MANIFEST_NAME):
        manifest = path / relative
        if manifest.is_file() and not manifest.is_symlink():
            return manifest, path
    raise CandidateRefusedError(
        "candidate must contain a standalone definition.json; historical candidate.json bundles "
        "are not reinterpreted as Construct Definitions"
    )


def load_candidate_bundle(path: Path) -> CandidateBundle:
    manifest, directory = resolve_candidate_path(path)
    try:
        fd = os.open(manifest, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise CandidateRefusedError("definition must be a regular file")
            raw = stream.read(MAX_DEFINITION_BYTES + 1)
        definition = decode(raw)
    except (OSError, DefinitionError) as error:
        raise CandidateRefusedError(
            "invalid standalone definition: " + getattr(error, "code", "unreadable")
        ) from None
    variables = [
        row["delivery"]["variable"]
        for row in definition.document["runtime"]["credentials"]
        if row["delivery"]["type"] == "environment"
    ]
    if any(shape.found(raw) for shape in (*_CREDENTIAL_SHAPES, *_slot_shapes(variables))):
        raise CandidateRefusedError("definition contains credential-shaped bytes")
    image_digest = "sha256:" + definition.document["image"].rsplit("sha256:", 1)[1]
    identity = CandidateIdentity.definition(definition.digest, image_digest)
    named = _CANDIDATE_DIRNAME_RE.fullmatch(directory.name)
    if named and named["hash8"] != candidate_hash8(identity):
        raise CandidateRefusedError("candidate directory hash disagrees with its definition")
    return CandidateBundle(directory, manifest.parent, definition, identity)


def vendor_candidate(results_repo: Path, bundle: CandidateBundle) -> VendoredCandidate:
    target = candidate_copy_dir(results_repo, bundle.identity)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.resolve() != target.parent.absolute():
        raise CandidateVendorError("candidate destination contains a symlink")
    fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    staging = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if target.exists() or target.is_symlink():
            try:
                existing = load_candidate_bundle(target)
            except CandidateRefusedError:
                raise CandidateVendorError("existing candidate is unverifiable") from None
            if existing.definition.encoded != bundle.definition.encoded:
                raise CandidateVendorError("existing candidate has different definition bytes")
            return VendoredCandidate(target, False)
        staging = Path(tempfile.mkdtemp(prefix=".candidate-staging-", dir=target.parent))
        document = staging / MANIFEST_NAME
        document.write_bytes(bundle.definition.encoded + b"\n")
        with document.open("rb") as stream:
            os.fsync(stream.fileno())
        from silverquillm.created_directories import rename_noreplace

        rename_noreplace(staging.name, target.name, dir_fd=fd)
        staging = None
        os.fsync(fd)
        return VendoredCandidate(target, True)
    finally:
        if staging is not None:
            shutil.rmtree(staging)
        os.close(fd)


def _inspect_image(reference: str) -> Mapping[str, Any]:
    try:
        process = subprocess.run(
            ["docker", "image", "inspect", reference],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if process.returncode:
            raise ImageBuildError("selected immutable image is unavailable locally")
        value = json.loads(process.stdout)
        if not isinstance(value, list) or len(value) != 1:
            raise ValueError
        return value[0]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise ImageBuildError("cannot verify selected immutable image") from None


def build_candidate_image(bundle: CandidateBundle, *, inspector=None, **options) -> BuiltImage:
    """Resolve an existing image; no build, promotion receipt or reverse label is required."""
    if options:
        raise ImageBuildError(
            "build options are not accepted; build the definition with Karn first"
        )
    reference = bundle.manifest["image"]
    observed = (inspector or _inspect_image)(reference)
    identifier = observed.get("Id")
    if (
        not isinstance(identifier, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", identifier) is None
        or observed.get("Os") != "linux"
        or (reference != identifier and reference not in (observed.get("RepoDigests") or []))
    ):
        raise ImageBuildError("selected image identity or platform does not match")
    return BuiltImage(reference, identifier)
