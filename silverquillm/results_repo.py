"""Private results repo: schema and run-record reader and writer.

Issue #39 §3 moves results out of ``docker/<image>/validated_results/`` into a
dedicated private results repo, git-as-truth.  This module is the bench side of
that home.  The repo is an ordinary git clone the operator owns; every function
here takes its local path (``repo_root``) and never runs git.

Layout of a results repo::

    AGENTS.md                                   schema doc (results_repo_templates/)
    results/<candidate-hash>/candidate/         the vendored Candidate Bundle (ozolith-v1 only;
                                                write-once, verified at write time — candidate.py)
    results/<candidate-hash>/<run-id>/manifest.json
    results/<candidate-hash>/<run-id>/scores.json

Rules the module enforces:

- **Records are immutable.** :func:`write_run_record` refuses an existing
  ``<run-id>`` directory with :class:`RunRecordExistsError` and writes
  atomically (temp dir + rename), so a reader never sees a half-written record.
- **Every read re-proves the record.** :func:`read_run_record` requires the
  manifest's ``run_id`` to equal the directory name, the recomputed candidate
  hash to equal both the manifest's ``candidate_hash`` and the parent
  directory name, and the recorded ``verified`` to be the literal boolean its
  scheme's provenance dictates — ``false`` for a ``legacy`` identity (a label,
  never verified), ``true`` for an ``ozolith-v1`` identity (established only
  through TheOzolith's verification path); deserialization preserves that
  value and refuses the other combination or any coercible look-alike — so
  the index and the harvester fail loudly on a tampered or misplaced record
  instead of emitting misattributed rows.
- **The manifest records ``benchmark``, never ``workload``** (the term is
  retired — CONTEXT.md).  ``mode`` and ``benchmark`` are run-spec parameters,
  orthogonal to candidate identity.
- **Scores use benchmark-neutral keys** (:data:`SCORE_DIMENSIONS`) so a migrated
  SOS record, a smoke record, and a HOB record all have the same shape.
- **Heavy artifacts never enter the tree.** ``artifact_pointers`` carry
  ``{"kind", "location"}`` references only.  A ``legacy-tree`` pointer is
  identity-bound: its location must be exactly
  :func:`legacy_tree_location` for the record's own candidate and run id, so
  a pointer can never select another candidate's artifacts.
- **Candidate identity is never trusted from a recorded value.**  A ``legacy``
  identity is a label and records ``verified: false``.  An ``ozolith-v1``
  identity was only ever produced by recomputation from a Candidate Bundle
  (the retired Candidate Bundle path, over TheOzolith's verifier; see ADR-014)
  and records ``verified: true``; any other combination is malformed and
  refused on write and on read.
- **Candidate keys are injective.** A legacy image dir must already be one
  safe path segment (the same rule run ids obey) and is used unchanged as the
  ``results/<candidate-hash>/`` key — nothing is sanitized, so two distinct
  images can never collide into one directory.  An ``ozolith-v1`` key is the
  SHA-256 of the canonical JSON of the whole identity triple (base digest,
  instruction hash, adapter) — see :func:`candidate_hash` — so two candidates
  differing in any component of the triple never share a directory.

Public API
----------
``CandidateIdentity``, ``RunRecord``, ``candidate_hash``, ``candidate_hash8``,
``candidate_dirname``, ``candidate_copy_dir``, ``legacy_image_dir``,
``legacy_tree_location``, ``write_run_record``, ``read_run_record``,
``record_file_texts``, ``iter_run_dirs``, ``iter_run_records``,
``init_results_repo``, ``resolve_results_repo``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "CANDIDATE_DIRNAME",
    "CANDIDATE_HASH8_LEN",
    "LEGACY_SCHEME",
    "LEGACY_TREE_KIND",
    "MANIFEST_FILENAME",
    "OZOLITH_SCHEME",
    "RESULTS_DIRNAME",
    "RESULTS_REPO_ENV",
    "SCHEMA_VERSION",
    "SCORES_FILENAME",
    "SCORE_DIMENSIONS",
    "TEMPLATE_DIR",
    "CandidateIdentity",
    "InvalidRunRecordError",
    "ResultsRepoError",
    "RunRecord",
    "RunRecordExistsError",
    "candidate_copy_dir",
    "candidate_dirname",
    "candidate_hash",
    "candidate_hash8",
    "init_results_repo",
    "iter_run_dirs",
    "iter_run_records",
    "legacy_image_dir",
    "legacy_tree_location",
    "read_run_record",
    "record_file_texts",
    "resolve_results_repo",
    "write_run_record",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

#: Environment variable naming the results repo clone; an explicit flag wins.
RESULTS_REPO_ENV = "SILVERQUILLM_RESULTS_REPO"

RESULTS_DIRNAME = "results"
MANIFEST_FILENAME = "manifest.json"
SCORES_FILENAME = "scores.json"
AGENTS_FILENAME = "AGENTS.md"

#: Identity scheme of runs migrated from the legacy image lineage
#: (``docker/<image>/``).  The image dir name is the whole identity.
LEGACY_SCHEME = "legacy"
#: Identity scheme of runs driven from a verified Candidate Bundle: the triple
#: (base image digest, instruction hash, adapter name) TheOzolith's identity
#: spec defines, recomputed by its verifier and never trusted from a record.
OZOLITH_SCHEME = "ozolith-v1"
#: Identity schemes of Karn runs, one per Construct Definition version; mirrors
#: ``silverquillm.karn.definition.SCHEMES``, whose package imports this module.
KARN_SCHEMES = frozenset({"karn-v4", "karn-v5"})

#: The reserved entry under ``results/<candidate-hash>/`` holding the vendored
#: Candidate Bundle of an ``ozolith-v1`` candidate (never a run id).
CANDIDATE_DIRNAME = "candidate"
#: The length of the short identity-hash suffix in ``<slug>--<hash8>`` names.
CANDIDATE_HASH8_LEN = 8

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")
# The SHAPE of an adapter name (one safe token) — deliberately not a set of
# adapters: the bench never allowlists adapters (BENCH-CONTRACT.md).
_ADAPTER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

#: The three audited dimensions under benchmark-neutral keys.  ``scores.json``
#: carries exactly these keys, each holding the matching ``run_summary.json``
#: sub-object unchanged.
SCORE_DIMENSIONS: tuple[str, ...] = ("card_correctness", "fdn_regression", "engine_regression")

#: ``artifact_pointers[].kind`` for a migrated run whose heavy artifacts stay
#: in place under the bench repo's ``docker/<image>/validated_results/<run>/``.
LEGACY_TREE_KIND = "legacy-tree"

TEMPLATE_DIR = Path(__file__).resolve().parent / "results_repo_templates"

_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]")

#: Every field a schema-v1 ``manifest.json`` carries.  All are required on
#: read; nothing is defaulted from an absent key.
_MANIFEST_FIELDS: tuple[str, ...] = (
    "schema_version",
    "run_id",
    "candidate",
    "candidate_hash",
    "mode",
    "benchmark",
    "budget_seconds",
    "leaderboard_valid",
    "resumed_from",
    "proposal_status",
    "run_metadata",
    "artifact_pointers",
)


def _is_safe_segment(value: str) -> bool:
    """One safe path segment: no separators, no whitespace, no leading dot."""
    return (
        bool(value)
        and value not in {".", ".."}
        and not value.startswith(".")
        and (_SAFE_SEGMENT_RE.search(value) is None)
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ResultsRepoError(Exception):
    """Base class for results-repo failures."""


class RunRecordExistsError(ResultsRepoError):
    """A record for this run-id already exists — records are immutable."""


class InvalidRunRecordError(ResultsRepoError):
    """A :class:`RunRecord` violates the schema."""


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateIdentity:
    """Who ran: (base image digest, instruction hash, adapter identity) + scheme.

    Under :data:`OZOLITH_SCHEME` the three fields are TheOzolith's identity
    triple exactly as its verifier recomputed them from a Candidate Bundle
    (:meth:`recomputed`), and ``verified`` is ``True`` — that is the only way
    such an identity comes to exist; a recorded value is re-validated for
    shape on read but is never what makes it verified.

    Under :data:`LEGACY_SCHEME` the three hash fields all carry
    ``legacy:<image-dir>``: in the legacy lineage the Docker image *was* the
    whole agent configuration, so the tuple does not decompose — and
    ``verified`` is ``False``, always.
    """

    base_image_digest: str
    instruction_hash: str
    adapter_identity: str
    scheme: str
    verified: bool = False

    @classmethod
    def recomputed(
        cls, base_image_digest: str, instruction_hash: str, adapter_identity: str
    ) -> CandidateIdentity:
        """The ``ozolith-v1`` identity of a Candidate Bundle *as recomputed by
        TheOzolith's verifier*.  The retired Candidate Bundle path was the one
        caller (ADR-014); historical records keep this identity.  Never build
        one from a recorded manifest value."""
        identity = cls(
            base_image_digest=base_image_digest,
            instruction_hash=instruction_hash,
            adapter_identity=adapter_identity,
            scheme=OZOLITH_SCHEME,
            verified=True,
        )
        identity.validate()
        return identity

    @classmethod
    def legacy(cls, image_dir: str) -> CandidateIdentity:
        """Identity of a run from the legacy ``docker/<image_dir>/`` lineage.

        *image_dir* must already be one safe path segment (the rule run ids
        obey): the name becomes the ``results/<candidate-hash>/`` key
        unchanged, never sanitized, so distinct images can never collide.
        """
        if not isinstance(image_dir, str) or not _is_safe_segment(image_dir):
            raise InvalidRunRecordError(
                f"invalid legacy image dir: {image_dir!r}; must be one safe path "
                "segment ([A-Za-z0-9._-], no leading dot) — legacy names are used "
                "unchanged as the candidate directory key, never sanitized"
            )
        token = f"{LEGACY_SCHEME}:{image_dir}"
        return cls(
            base_image_digest=token,
            instruction_hash=token,
            adapter_identity=token,
            scheme=LEGACY_SCHEME,
            verified=False,
        )

    def validate(self) -> None:
        """Raise :class:`InvalidRunRecordError` unless the identity is well-formed.

        The one identity rule, shared by every path an identity travels:
        construction (:meth:`legacy`), persistence (``RunRecord.validate()``
        runs before every write) and deserialization (:meth:`from_dict`) — so
        the writer can never produce an identity the reader rejects.
        """
        for key in ("scheme", "base_image_digest", "instruction_hash", "adapter_identity"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value:
                raise InvalidRunRecordError(
                    f"candidate identity {key} must be a non-empty string, got {value!r}"
                )
        if not isinstance(self.verified, bool):
            raise InvalidRunRecordError(
                f"candidate identity verified must be a JSON boolean, got {self.verified!r}"
            )
        if self.scheme == LEGACY_SCHEME:
            if self.verified is not False:
                raise InvalidRunRecordError(
                    "a legacy identity is a label, never verified; only an ozolith-v1 "
                    "identity recomputed from a Candidate Bundle carries verified: true"
                )
            token = self.base_image_digest
            prefix = f"{LEGACY_SCHEME}:"
            image_dir = token[len(prefix) :] if token.startswith(prefix) else ""
            if not token.startswith(prefix) or not _is_safe_segment(image_dir):
                raise InvalidRunRecordError(
                    "legacy identity fields must carry 'legacy:<image-dir>' with a "
                    f"safe image dir (one path segment, no leading dot), got {token!r}"
                )
            if not (self.instruction_hash == self.adapter_identity == token):
                raise InvalidRunRecordError(
                    "legacy identity fields disagree; all three must carry the same "
                    f"'legacy:<image-dir>' token, got {token!r}, "
                    f"{self.instruction_hash!r}, {self.adapter_identity!r}"
                )
        elif self.scheme == OZOLITH_SCHEME:
            if not _DIGEST_RE.fullmatch(self.base_image_digest):
                raise InvalidRunRecordError(
                    "an ozolith-v1 base_image_digest must be 'sha256:<64 hex>', got "
                    f"{self.base_image_digest!r}"
                )
            if not _HEX64_RE.fullmatch(self.instruction_hash):
                raise InvalidRunRecordError(
                    "an ozolith-v1 instruction_hash must be 64 hex chars, got "
                    f"{self.instruction_hash!r}"
                )
            if not _ADAPTER_RE.fullmatch(self.adapter_identity):
                raise InvalidRunRecordError(
                    "an ozolith-v1 adapter_identity must be one safe token "
                    f"([A-Za-z0-9._-], no leading dot), got {self.adapter_identity!r}"
                )
            if self.verified is not True:
                raise InvalidRunRecordError(
                    "an ozolith-v1 identity exists only by recomputation from a "
                    "Candidate Bundle and records verified: true; an unverified "
                    "ozolith-v1 identity is malformed"
                )
        else:
            raise InvalidRunRecordError(f"unknown candidate identity scheme: {self.scheme!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme,
            "base_image_digest": self.base_image_digest,
            "instruction_hash": self.instruction_hash,
            "adapter_identity": self.adapter_identity,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CandidateIdentity:
        """Deserialize a recorded identity, strictly.

        A recorded value is a label, never evidence: the payload must be a
        JSON object and every field must already have the exact type and
        shape the writer emits — nothing is coerced — with ``verified`` the
        literal JSON ``false``.  Recomputation from a Candidate Bundle (#65)
        is the only path to a verified identity.  The rules are
        :meth:`validate`, the same ones the writer enforces.
        """
        if not isinstance(data, Mapping):
            raise InvalidRunRecordError(f"candidate identity must be a JSON object, got {data!r}")
        identity = cls(
            base_image_digest=data.get("base_image_digest"),
            instruction_hash=data.get("instruction_hash"),
            adapter_identity=data.get("adapter_identity"),
            scheme=data.get("scheme"),
            verified=data.get("verified"),
        )
        identity.validate()
        return identity


def legacy_image_dir(identity: CandidateIdentity) -> str | None:
    """Return the ``docker/<image-dir>`` name a legacy identity encodes, else ``None``."""
    if identity.scheme != LEGACY_SCHEME:
        return None
    prefix = f"{LEGACY_SCHEME}:"
    if not identity.base_image_digest.startswith(prefix):
        return None
    return identity.base_image_digest[len(prefix) :] or None


def candidate_hash(identity: CandidateIdentity) -> str:
    """The ``results/<candidate-hash>/`` directory key for *identity*.

    Instruction-independent: derived from the identity, not the run, and
    defined only for a valid identity (*identity* is validated first).

    For the legacy scheme it is the image dir name **unchanged** — legacy
    names are already safe path segments, so the mapping is injective and two
    distinct images can never share a directory.

    For ``ozolith-v1`` it is the SHA-256 hex digest of the compact canonical
    JSON (sorted keys, ``,``/``:`` separators) of the whole identity triple::

        {"adapter": <adapter name>, "base_digest": <sha256:…>, "instruction_hash": <64 hex>}

    The instruction hash alone would not do: TheOzolith's canonical identity
    does not contain the adapter name (BENCH-CONTRACT.md, identity spec), so
    two candidates on the same base with the same materialized setup and
    different adapters share an instruction hash — hashing the triple keeps
    the key injective over the identity.  The first :data:`CANDIDATE_HASH8_LEN`
    characters are the ``<slug>--<hash8>`` suffix of a checked-in candidate
    directory (:func:`candidate_dirname`).
    """
    identity.validate()
    if identity.scheme in KARN_SCHEMES:
        return identity.hash
    if identity.scheme == LEGACY_SCHEME:
        return identity.base_image_digest[len(f"{LEGACY_SCHEME}:") :]
    canonical = json.dumps(
        {
            "adapter": identity.adapter_identity,
            "base_digest": identity.base_image_digest,
            "instruction_hash": identity.instruction_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def candidate_hash8(identity: CandidateIdentity) -> str:
    """The short suffix of :func:`candidate_hash` used in candidate directory names."""
    return candidate_hash(identity)[:CANDIDATE_HASH8_LEN]


def candidate_dirname(slug: str, identity: CandidateIdentity) -> str:
    """The ``<slug>--<hash8>`` name a checked-in candidate directory carries
    (``candidates/`` in the bench repo, issue #39 §4: identity-hash suffix,
    flat, deduplicating)."""
    if not _is_safe_segment(slug) or "--" in slug:
        raise InvalidRunRecordError(
            f"invalid candidate slug {slug!r}: one safe path segment without '--'"
        )
    return f"{slug}--{candidate_hash8(identity)}"


def candidate_copy_dir(repo_root: Path, identity: CandidateIdentity) -> Path:
    """Where the vendored Candidate Bundle of *identity* lives in a results repo:
    ``results/<candidate-hash>/candidate/`` (``ozolith-v1`` only)."""
    if identity.scheme != OZOLITH_SCHEME:
        raise ResultsRepoError(
            f"only an {OZOLITH_SCHEME!r} candidate is vendored; {identity.scheme!r} has no bundle"
        )
    return Path(repo_root) / RESULTS_DIRNAME / candidate_hash(identity) / CANDIDATE_DIRNAME


def legacy_tree_location(image_dir: str, run_id: str) -> str:
    """The canonical bench-repo-relative ``legacy-tree`` pointer location.

    Exactly ``docker/<image-dir>/validated_results/<run-id>/``.  Both parts
    must be safe path segments, so the location can never be absolute, escape
    the bench root, or name another candidate's artifacts.  A record's
    ``legacy-tree`` pointer must equal this string for the record's own
    candidate and run id — validated on write, on read, and again by the
    harvester before the pointer is followed.
    """
    if not isinstance(image_dir, str) or not _is_safe_segment(image_dir):
        raise InvalidRunRecordError(f"invalid legacy image dir: {image_dir!r}")
    if not isinstance(run_id, str) or not _is_safe_segment(run_id):
        raise InvalidRunRecordError(f"invalid run id: {run_id!r}")
    return f"docker/{image_dir}/validated_results/{run_id}/"


# ---------------------------------------------------------------------------
# Run record
# ---------------------------------------------------------------------------


@dataclass
class RunRecord:
    """One Benchmark Run's record: ``manifest.json`` + ``scores.json``.

    ``run_metadata`` is metadata only (adapter/product versions, run date,
    notes) — never identity-bearing.  ``proposal_status`` is what the #64
    driver records about ``output/proposal.json`` (``"applied"``,
    ``"missing"``, ``"invalid"``); ``None`` for legacy runs, which had no
    proposal.
    """

    run_id: str
    candidate: CandidateIdentity
    mode: str
    benchmark: str
    budget_seconds: int
    leaderboard_valid: bool
    resumed_from: str | None
    run_metadata: dict[str, Any]
    proposal_status: str | None
    scores: dict[str, Any]
    artifact_pointers: list[dict[str, str]] = field(default_factory=list)

    # -- validation ---------------------------------------------------------

    def validate(self) -> None:
        """Raise :class:`InvalidRunRecordError` unless the record is well-formed."""
        if not isinstance(self.run_id, str) or not _is_safe_segment(self.run_id):
            raise InvalidRunRecordError(
                f"run_id must be a single safe path segment, got {self.run_id!r}"
            )
        if not isinstance(self.candidate, CandidateIdentity):
            raise InvalidRunRecordError("candidate must be a CandidateIdentity")
        self.candidate.validate()
        for name in ("mode", "benchmark"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise InvalidRunRecordError(f"{name} must be a non-empty string")
        if isinstance(self.budget_seconds, bool) or not isinstance(self.budget_seconds, int):
            raise InvalidRunRecordError("budget_seconds must be an int")
        if self.budget_seconds < 0:
            raise InvalidRunRecordError("budget_seconds must be >= 0")
        if not isinstance(self.leaderboard_valid, bool):
            raise InvalidRunRecordError("leaderboard_valid must be a bool")
        if self.resumed_from is not None and (
            not isinstance(self.resumed_from, str) or not self.resumed_from
        ):
            raise InvalidRunRecordError("resumed_from must be None or a non-empty string")
        if self.proposal_status is not None and not isinstance(self.proposal_status, str):
            raise InvalidRunRecordError("proposal_status must be None or a string")
        if not isinstance(self.run_metadata, dict):
            raise InvalidRunRecordError("run_metadata must be a dict")
        if "workload" in self.run_metadata:
            raise InvalidRunRecordError(
                "'workload' is retired vocabulary; the manifest records 'benchmark'"
            )
        if not isinstance(self.scores, dict) or set(self.scores) != set(SCORE_DIMENSIONS):
            raise InvalidRunRecordError(
                f"scores must have exactly the keys {list(SCORE_DIMENSIONS)}, "
                f"got {sorted(self.scores) if isinstance(self.scores, dict) else self.scores!r}"
            )
        for key in SCORE_DIMENSIONS:
            if not isinstance(self.scores[key], dict):
                raise InvalidRunRecordError(f"scores[{key!r}] must be a dict")
        if not isinstance(self.artifact_pointers, list):
            raise InvalidRunRecordError("artifact_pointers must be a list")
        for pointer in self.artifact_pointers:
            if not isinstance(pointer, dict):
                raise InvalidRunRecordError("each artifact pointer must be a dict")
            for key in ("kind", "location"):
                if not isinstance(pointer.get(key), str) or not pointer[key]:
                    raise InvalidRunRecordError(
                        f"artifact pointer lacks a non-empty {key!r}: {pointer!r}"
                    )
        legacy_pointers = [p for p in self.artifact_pointers if p["kind"] == LEGACY_TREE_KIND]
        if legacy_pointers:
            image_dir = legacy_image_dir(self.candidate)
            if image_dir is None:
                raise InvalidRunRecordError(
                    "a legacy-tree pointer requires a legacy candidate identity"
                )
            expected = legacy_tree_location(image_dir, self.run_id)
            if len(legacy_pointers) > 1:
                raise InvalidRunRecordError(
                    f"duplicate legacy-tree pointers; a record carries at most one, "
                    f"at exactly {expected!r}"
                )
            location = legacy_pointers[0]["location"]
            if location != expected:
                raise InvalidRunRecordError(
                    f"legacy-tree location must be exactly the canonical identity-bound "
                    f"path {expected!r}, got {location!r}"
                )

    # -- serialization ------------------------------------------------------

    def manifest_dict(self) -> dict[str, Any]:
        """The ``manifest.json`` payload (everything but the scores)."""
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "candidate": self.candidate.to_dict(),
            "candidate_hash": candidate_hash(self.candidate),
            "mode": self.mode,
            "benchmark": self.benchmark,
            "budget_seconds": self.budget_seconds,
            "leaderboard_valid": self.leaderboard_valid,
            "resumed_from": self.resumed_from,
            "proposal_status": self.proposal_status,
            "run_metadata": self.run_metadata,
            "artifact_pointers": self.artifact_pointers,
        }

    def scores_dict(self) -> dict[str, Any]:
        """The ``scores.json`` payload: exactly the neutral dimension keys."""
        return {key: self.scores[key] for key in SCORE_DIMENSIONS}

    @classmethod
    def from_dicts(cls, manifest: Mapping[str, Any], scores: Mapping[str, Any]) -> RunRecord:
        """Deserialize a persisted record, strictly.

        Every schema-v1 manifest field must be present with the exact JSON
        type the writer emits — no default fills in for an absent key, and
        no malformed value is normalized with ``str()``, ``dict()``,
        ``list()`` or truthiness.  Any violation is
        :class:`InvalidRunRecordError`; malformed persisted data never
        surfaces as ``AttributeError``, ``TypeError`` or a raw ``KeyError``.
        """
        if not isinstance(manifest, Mapping):
            raise InvalidRunRecordError(f"manifest must be a JSON object, got {manifest!r}")
        if not isinstance(scores, Mapping):
            raise InvalidRunRecordError(f"scores must be a JSON object, got {scores!r}")
        missing = [key for key in _MANIFEST_FIELDS if key not in manifest]
        if missing:
            raise InvalidRunRecordError(f"manifest lacks {', '.join(missing)}")
        version = manifest["schema_version"]
        if isinstance(version, bool) or not isinstance(version, int) or version != SCHEMA_VERSION:
            raise InvalidRunRecordError(
                f"schema_version must be the integer {SCHEMA_VERSION}, got {version!r}"
            )
        if "workload" in manifest:
            raise InvalidRunRecordError("manifest carries the retired 'workload' field")
        candidate_data = manifest["candidate"]
        if not isinstance(candidate_data, Mapping):
            raise InvalidRunRecordError(
                f"manifest candidate must be a JSON object, got {candidate_data!r}"
            )
        run_metadata = manifest["run_metadata"]
        if not isinstance(run_metadata, dict):
            raise InvalidRunRecordError(f"run_metadata must be a JSON object, got {run_metadata!r}")
        artifact_pointers = manifest["artifact_pointers"]
        if not isinstance(artifact_pointers, list):
            raise InvalidRunRecordError(
                f"artifact_pointers must be a JSON array, got {artifact_pointers!r}"
            )
        record = cls(
            run_id=manifest["run_id"],
            candidate=CandidateIdentity.from_dict(candidate_data),
            mode=manifest["mode"],
            benchmark=manifest["benchmark"],
            budget_seconds=manifest["budget_seconds"],
            leaderboard_valid=manifest["leaderboard_valid"],
            resumed_from=manifest["resumed_from"],
            run_metadata=run_metadata,
            proposal_status=manifest["proposal_status"],
            scores=dict(scores),
            artifact_pointers=artifact_pointers,
        )
        record.validate()
        recorded_hash = manifest["candidate_hash"]
        if not isinstance(recorded_hash, str) or not recorded_hash:
            raise InvalidRunRecordError(
                f"manifest candidate_hash must be a non-empty string, got {recorded_hash!r}"
            )
        expected_hash = candidate_hash(record.candidate)
        if recorded_hash != expected_hash:
            raise InvalidRunRecordError(
                f"manifest candidate_hash {recorded_hash!r} does not match "
                f"the recorded candidate ({expected_hash!r})"
            )
        return record


# ---------------------------------------------------------------------------
# Writer / reader
# ---------------------------------------------------------------------------


def _dumps(payload: Any) -> str:
    """Deterministic JSON: sorted keys, two-space indent, trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResultsRepoError(f"cannot read {path}: {exc}") from exc


def record_file_texts(record: RunRecord) -> tuple[str, str]:
    """The canonical ``(manifest.json, scores.json)`` texts the writer emits.

    Deterministic (sorted keys, fixed indent), so two records are exactly
    equivalent iff these texts are byte-identical — the migrator uses this to
    tell an already-migrated record from a conflicting one.
    """
    return _dumps(record.manifest_dict()), _dumps(record.scores_dict())


def write_run_record(repo_root: Path, record: RunRecord) -> Path:
    """Write ``results/<candidate-hash>/<run-id>/{manifest,scores}.json``.

    Immutable: raises :class:`RunRecordExistsError` if the run-id directory
    already exists.  Atomic: both files are written into a temporary sibling
    directory that is renamed into place, so readers never observe a partial
    record and a failed write leaves nothing behind.  Returns the record dir.
    """
    record.validate()
    # Serialization errors surface before any I/O.
    manifest_text, scores_text = record_file_texts(record)

    candidate_dir = Path(repo_root) / RESULTS_DIRNAME / candidate_hash(record.candidate)
    final_dir = candidate_dir / record.run_id
    if final_dir.exists():
        raise RunRecordExistsError(f"run record already exists: {final_dir}")

    candidate_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=f".tmp-{record.run_id}-", dir=candidate_dir))
    try:
        (tmp_dir / MANIFEST_FILENAME).write_text(manifest_text, encoding="utf-8")
        (tmp_dir / SCORES_FILENAME).write_text(scores_text, encoding="utf-8")
        try:
            tmp_dir.rename(final_dir)
        except OSError as exc:  # lost a race: final_dir appeared after the check
            raise RunRecordExistsError(f"run record already exists: {final_dir}") from exc
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return final_dir


def read_run_record(run_dir: Path) -> RunRecord:
    """Load and validate the record stored in *run_dir*.

    Every read re-proves agreement between the path and the recorded identity:
    the manifest's ``run_id`` must equal the directory name, and the candidate
    hash recomputed from the recorded candidate must equal both the manifest's
    ``candidate_hash`` and the parent directory name.  A record that fails any
    of these is tampered or misplaced and raises :class:`InvalidRunRecordError`
    rather than being attributed to the wrong candidate.
    """
    run_dir = Path(run_dir)
    manifest = _load_json(run_dir / MANIFEST_FILENAME)
    scores = _load_json(run_dir / SCORES_FILENAME)
    if not isinstance(manifest, dict) or not isinstance(scores, dict):
        raise InvalidRunRecordError(f"{run_dir}: manifest.json and scores.json must be objects")
    if manifest.get("schema_version") == 2:
        from silverquillm.karn.records import read_record

        return read_record(run_dir)
    try:
        record = RunRecord.from_dicts(manifest, scores)
    except InvalidRunRecordError as exc:
        raise InvalidRunRecordError(f"{run_dir}: {exc}") from exc
    if record.run_id != run_dir.name:
        raise InvalidRunRecordError(
            f"{run_dir}: manifest run_id {record.run_id!r} does not match the "
            f"directory name {run_dir.name!r}"
        )
    expected_hash = candidate_hash(record.candidate)
    if run_dir.parent.name != expected_hash:
        raise InvalidRunRecordError(
            f"{run_dir}: record sits under {run_dir.parent.name!r}, not its "
            f"candidate's directory {expected_hash!r}"
        )
    return record


def iter_run_dirs(repo_root: Path) -> Iterator[Path]:
    """Yield every ``results/<candidate-hash>/<run-id>/`` holding a manifest.

    Deterministic order: sorted by ``(candidate-hash, run-id)``.  Dot-prefixed
    directories (in-flight temp dirs) and the reserved vendored-bundle entry
    (:data:`CANDIDATE_DIRNAME`) are skipped.
    """
    results_dir = Path(repo_root) / RESULTS_DIRNAME
    if not results_dir.is_dir():
        return
    for candidate_dir in sorted(p for p in results_dir.iterdir() if p.is_dir()):
        if candidate_dir.name.startswith("."):
            continue
        for run_dir in sorted(p for p in candidate_dir.iterdir() if p.is_dir()):
            if run_dir.name.startswith(".") or run_dir.name == CANDIDATE_DIRNAME:
                continue
            if (run_dir / MANIFEST_FILENAME).is_file():
                yield run_dir


def iter_run_records(repo_root: Path) -> Iterator[tuple[Path, RunRecord]]:
    """Yield ``(run_dir, record)`` for every record, in :func:`iter_run_dirs` order."""
    for run_dir in iter_run_dirs(repo_root):
        yield run_dir, read_run_record(run_dir)


# ---------------------------------------------------------------------------
# Repo init / configuration
# ---------------------------------------------------------------------------


def init_results_repo(path: Path) -> list[Path]:
    """Lay out an empty results repo at *path*; return the files written.

    Writes the schema ``AGENTS.md`` (from :data:`TEMPLATE_DIR`) and an empty
    ``results/`` directory (kept with ``.gitkeep``).
    The whole target is preflighted before the first write: *path* may not
    exist yet, be an empty directory, or be an empty git clone (nothing but
    ``.git`` inside).  Anything else — including a lone ``results/`` tree or
    README — is refused, and nothing is ever
    overwritten.  If a write fails partway, everything this call created is
    removed again so the operator can simply retry.
    """
    path = Path(path)
    template = TEMPLATE_DIR / AGENTS_FILENAME
    if not template.is_file():
        raise ResultsRepoError(f"missing packaged template: {template}")
    create_root = not path.exists()
    if not create_root:
        if not path.is_dir():
            raise ResultsRepoError(f"{path} is not a directory")
        entries = sorted(p.name for p in path.iterdir() if p.name != ".git")
        if AGENTS_FILENAME in entries:
            raise ResultsRepoError(f"{path} is not an empty results repo: {AGENTS_FILENAME} exists")
        if entries:
            raise ResultsRepoError(
                f"{path} is not empty; refusing to initialize over: {', '.join(entries)}"
            )
    created: list[Path] = []
    written: list[Path] = []
    try:
        if create_root:
            path.mkdir(parents=True)
            created.append(path)
        agents_md = path / AGENTS_FILENAME
        agents_md.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(agents_md)
        written.append(agents_md)
        results_dir = path / RESULTS_DIRNAME
        results_dir.mkdir()
        created.append(results_dir)
        gitkeep = results_dir / ".gitkeep"
        gitkeep.write_text("", encoding="utf-8")
        created.append(gitkeep)
        written.append(gitkeep)
    except BaseException:
        for created_path in reversed(created):
            with contextlib.suppress(OSError):
                if created_path.is_dir():
                    shutil.rmtree(created_path, ignore_errors=True)
                else:
                    created_path.unlink()
        raise
    return written


def resolve_results_repo(
    flag: Path | str | None,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Results repo path from the ``--results-repo`` flag or the env var; flag wins.

    ``None`` means the feature is off: callers leave the legacy write path
    untouched.
    """
    if flag:
        return Path(flag)
    environ = os.environ if env is None else env
    value = environ.get(RESULTS_REPO_ENV, "").strip()
    return Path(value) if value else None
