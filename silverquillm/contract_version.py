"""The Bench Contract pin: the exact TheOzolith worker revision the bench consumes.

BENCH-CONTRACT.md's versioning promise is visibility, not immutability: a
consumer pins one revision and re-syncs deliberately.  Three things therefore
have to agree, and this module is where the bench states two of them:

- ``docs/specs/BENCH-CONTRACT.md`` is vendored from the-ozolith at
  :data:`PINNED_WORKER_REVISION` (its provenance banner records the commit);
- ``pyproject.toml`` pins ``theozolith-worker`` to that same immutable revision
  (a git direct reference — the package is not published on PyPI, and the
  the-ozolith repository publishes no release tags);
- :data:`CONTRACT_SCHEMA_VERSION` is the ``schema_version`` that contract
  publishes for the Run Contract.

:func:`check_contract_support` is the driver's preflight, and it fails closed:
a worker that speaks a different ``schema_version``, carries a different
distribution version, records a different git revision, or whose *installed
tree* does not hash to the pinned revision's tree is refused *before* any job
dir is staged or any container launched.  The tree digest
(:data:`PINNED_WORKER_TREE_DIGEST`, computed over the pinned commit's
``worker/src/theozolith_worker``) is the authentication that a directory or
editable install — which records no revision — really is the pinned code, and
it also refuses a git install whose files were modified after installation.
Version and schema numbers alone never admit a worker.  The bench never
replays a contract it did not pin.  ``tests/test_contract_pin.py`` proves the
three sources agree and the refusals hold.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from theozolith_worker import api

__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "PINNED_WORKER_REVISION",
    "PINNED_WORKER_TREE_DIGEST",
    "PINNED_WORKER_VERSION",
    "WORKER_DISTRIBUTION",
    "WORKER_REPOSITORY",
    "WORKER_SUBDIRECTORY",
    "InstalledWorker",
    "UnsupportedContractError",
    "check_contract_support",
    "installed_worker",
    "pinned_requirement",
    "support_errors",
    "worker_tree_digest",
]

#: The Run Contract ``schema_version`` the vendored BENCH-CONTRACT.md publishes.
CONTRACT_SCHEMA_VERSION = 1

#: The ``theozolith-worker`` distribution version at the pinned revision.
PINNED_WORKER_VERSION = "0.3.0"

#: The the-ozolith commit the contract is vendored from and the worker is
#: pinned to (``docs/specs/BENCH-CONTRACT.md`` provenance banner).
PINNED_WORKER_REVISION = "19118cae6dc4faf0543bd9bf18aa54621c971358"

#: SHA-256 tree digest of ``worker/src/theozolith_worker`` at
#: :data:`PINNED_WORKER_REVISION` (the :func:`worker_tree_digest` algorithm
#: over the pinned commit's tarball).  The installed package must hash to this
#: — it is what authenticates an install that records no git revision, and
#: what refuses one whose files were edited after installation.
PINNED_WORKER_TREE_DIGEST = "db19b4dee54da426425adb35b146d5db5b950ce019d553c2e65d39bfc6e0d6e9"

WORKER_DISTRIBUTION = "theozolith-worker"
WORKER_REPOSITORY = "https://github.com/snowfoxbuilds/the-ozolith.git"
WORKER_SUBDIRECTORY = "worker"


class UnsupportedContractError(RuntimeError):
    """The installed worker does not speak the pinned Bench Contract."""


@dataclass(frozen=True)
class InstalledWorker:
    """What is actually installed: version, git revision (when the install
    records one — a ``git+`` install does; a directory or wheel install does
    not), the install source, and the digest of the installed package tree
    (the fail-closed authentication — ``None`` when it could not be computed,
    which is itself refused)."""

    version: str
    revision: str | None
    source: str
    tree_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pinned_requirement() -> str:
    """The exact PEP 508 requirement ``pyproject.toml`` must carry."""
    return (
        f"{WORKER_DISTRIBUTION} @ git+{WORKER_REPOSITORY}@{PINNED_WORKER_REVISION}"
        f"#subdirectory={WORKER_SUBDIRECTORY}"
    )


def worker_tree_digest(root: Path | None = None) -> str | None:
    """SHA-256 digest of the ``theozolith_worker`` package tree at *root*
    (the installed package when omitted).

    Every regular file except bytecode (``__pycache__``, ``*.pyc``) enters as
    ``<posix relpath>\\0<sha256 of contents>\\n``, in sorted path order — the
    same algorithm that produced :data:`PINNED_WORKER_TREE_DIGEST` from the
    pinned commit's ``worker/src/theozolith_worker``.  Returns ``None`` when
    the tree cannot be read; the preflight refuses that.
    """
    if root is None:
        root = Path(api.__file__).resolve().parent
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    try:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\x00")
            digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
            digest.update(b"\n")
    except OSError:
        return None
    return digest.hexdigest()


def installed_worker() -> InstalledWorker:
    """Inspect the installed ``theozolith-worker`` distribution.

    The revision comes from the install's ``direct_url.json`` (PEP 610)
    ``vcs_info.commit_id`` — present for a ``git+`` install, absent otherwise.
    The tree digest is always computed from the installed package itself.
    """
    try:
        dist = metadata.distribution(WORKER_DISTRIBUTION)
    except metadata.PackageNotFoundError as exc:
        raise UnsupportedContractError(
            f"{WORKER_DISTRIBUTION} is not installed; install {pinned_requirement()!r}"
        ) from exc
    revision: str | None = None
    source = "index"
    raw = dist.read_text("direct_url.json")
    if raw:
        try:
            direct = json.loads(raw)
        except json.JSONDecodeError:
            direct = {}
        if isinstance(direct, dict):
            url = direct.get("url")
            source = url if isinstance(url, str) and url else source
            vcs = direct.get("vcs_info")
            commit = vcs.get("commit_id") if isinstance(vcs, dict) else None
            revision = commit if isinstance(commit, str) and commit else None
    return InstalledWorker(
        version=dist.version,
        revision=revision,
        source=source,
        tree_digest=worker_tree_digest(),
    )


def support_errors(worker: InstalledWorker | None = None) -> list[str]:
    """Every way the installed worker disagrees with the pinned contract.

    Fails closed: the installed tree must hash to the pinned revision's tree
    digest — a matching version and schema number never admit a worker on
    their own, and an unreadable tree is refused, not excused.
    """
    worker = installed_worker() if worker is None else worker
    errors: list[str] = []
    if api.SCHEMA_VERSION != CONTRACT_SCHEMA_VERSION:
        errors.append(
            f"the installed worker speaks Run Contract schema_version {api.SCHEMA_VERSION},"
            f" but the vendored Bench Contract is schema_version {CONTRACT_SCHEMA_VERSION}"
        )
    if worker.version != PINNED_WORKER_VERSION:
        errors.append(
            f"{WORKER_DISTRIBUTION} {worker.version} is installed, but the bench pins"
            f" {PINNED_WORKER_VERSION}"
        )
    if worker.revision is not None and worker.revision != PINNED_WORKER_REVISION:
        errors.append(
            f"{WORKER_DISTRIBUTION} is installed from revision {worker.revision}, but the"
            f" bench pins {PINNED_WORKER_REVISION}"
        )
    if worker.tree_digest is None:
        errors.append(
            f"the installed {WORKER_DISTRIBUTION} tree could not be read, so it cannot be"
            f" authenticated against the pinned revision"
        )
    elif worker.tree_digest != PINNED_WORKER_TREE_DIGEST:
        errors.append(
            f"the installed {WORKER_DISTRIBUTION} tree digest {worker.tree_digest} does not"
            f" match the pinned revision's {PINNED_WORKER_TREE_DIGEST} — the install is"
            f" locally modified or not revision {PINNED_WORKER_REVISION}"
        )
    return errors


def check_contract_support() -> InstalledWorker:
    """Refuse — :class:`UnsupportedContractError` — unless the installed worker
    is the pinned one; return what is installed otherwise."""
    worker = installed_worker()
    errors = support_errors(worker)
    if errors:
        raise UnsupportedContractError(
            "; ".join(errors) + f" (re-sync docs/specs/BENCH-CONTRACT.md and install"
            f" {pinned_requirement()!r})"
        )
    return worker
