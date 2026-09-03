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

:func:`check_contract_support` is the driver's preflight: a worker that speaks a
different ``schema_version``, carries a different distribution version, or —
when its install records a git revision — comes from a different commit is
refused *before* any job dir is staged or any container launched.  The bench
never replays a contract it did not pin.  A worker installed from a plain
directory (no recorded revision) is allowed but recorded as unverifiable.
``tests/test_contract_pin.py`` proves the three sources agree.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from importlib import metadata
from typing import Any

from theozolith_worker import api

__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "PINNED_WORKER_REVISION",
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
]

#: The Run Contract ``schema_version`` the vendored BENCH-CONTRACT.md publishes.
CONTRACT_SCHEMA_VERSION = 1

#: The ``theozolith-worker`` distribution version at the pinned revision.
PINNED_WORKER_VERSION = "0.3.0"

#: The the-ozolith commit the contract is vendored from and the worker is
#: pinned to (``docs/specs/BENCH-CONTRACT.md`` provenance banner).
PINNED_WORKER_REVISION = "19118cae6dc4faf0543bd9bf18aa54621c971358"

WORKER_DISTRIBUTION = "theozolith-worker"
WORKER_REPOSITORY = "https://github.com/snowfoxbuilds/the-ozolith.git"
WORKER_SUBDIRECTORY = "worker"


class UnsupportedContractError(RuntimeError):
    """The installed worker does not speak the pinned Bench Contract."""


@dataclass(frozen=True)
class InstalledWorker:
    """What is actually installed: version, git revision (when the install
    records one — a ``git+`` install does; a directory or wheel install does
    not), and the install source."""

    version: str
    revision: str | None
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pinned_requirement() -> str:
    """The exact PEP 508 requirement ``pyproject.toml`` must carry."""
    return (
        f"{WORKER_DISTRIBUTION} @ git+{WORKER_REPOSITORY}@{PINNED_WORKER_REVISION}"
        f"#subdirectory={WORKER_SUBDIRECTORY}"
    )


def installed_worker() -> InstalledWorker:
    """Inspect the installed ``theozolith-worker`` distribution.

    The revision comes from the install's ``direct_url.json`` (PEP 610)
    ``vcs_info.commit_id`` — present for a ``git+`` install, absent otherwise.
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
    return InstalledWorker(version=dist.version, revision=revision, source=source)


def support_errors(worker: InstalledWorker | None = None) -> list[str]:
    """Every way the installed worker disagrees with the pinned contract."""
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
