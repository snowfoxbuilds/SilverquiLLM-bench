"""The Bench Contract pin: the exact TheOzolith revision the bench consumes.

BENCH-CONTRACT.md's versioning promise is visibility, not immutability: a
consumer pins one revision and re-syncs deliberately.  Several things
therefore have to agree, and this module is where the bench states them:

- ``docs/specs/BENCH-CONTRACT.md`` (and the ``bench-identity-vectors.json`` it
  links to) are vendored from the-ozolith at :data:`PINNED_REVISION` (the
  contract's provenance banner records the commit); the vectors file carries no
  provenance banner of its own, so it is content-authenticated against
  :data:`PINNED_IDENTITY_VECTORS_BLOB_SHA` (its git blob hash at that commit) —
  the contract and its vectors re-sync together or the pin fails;
- ``pyproject.toml`` pins every the-ozolith distribution the bench imports to
  that same immutable revision (git direct references — the packages are not
  published on PyPI, and the-ozolith publishes no release tags):
  ``theozolith-worker`` (the Run Contract: ``theozolith_worker.api``, and the
  in-image harness), ``theozolith-control`` (the Candidate Bundle verifier
  ``theozolith_control.candidate`` — export, ``verify_bundle``, the verified
  build), ``theozolith-nodedaemon`` (the Dockerfile codegen and tree hash the
  verifier byte-matches against) and ``theozolith-knowledge`` (the knowledge
  compiler export runs);
- :data:`CONTRACT_SCHEMA_VERSION`, :data:`CONTRACT_BUNDLE_FORMAT_VERSION` and
  :data:`CONTRACT_IDENTITY_SPEC_VERSION` are the three compatibility keys that
  contract publishes, each owning exactly one surface.

:func:`check_contract_support` is the driver's preflight, and it fails closed:
a distribution that carries a different version, records a different git
revision, or whose *installed tree* does not hash to the pinned revision's
tree is refused — and so is a worker speaking a different ``schema_version``
or a verifier stamping different bundle/identity versions — *before* any
bundle is verified, any job dir staged, or any container launched.  The tree
digests (:class:`PinnedDistribution.tree_digest`, computed over each package
directory at the pinned commit) are the authentication that a directory or
editable install — which records no revision — really is the pinned code, and
they also refuse an install whose files were modified after installation.
Version and schema numbers alone never admit a package.  The bench never
replays a contract, and never trusts a verifier, it did not pin.
``tests/test_contract_pin.py`` proves the sources agree and the refusals hold.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from importlib import import_module, metadata
from pathlib import Path
from typing import Any

from theozolith_worker import api

__all__ = [
    "CONTRACT_BUNDLE_FORMAT_VERSION",
    "CONTRACT_IDENTITY_SPEC_VERSION",
    "CONTRACT_SCHEMA_VERSION",
    "PINNED_DISTRIBUTIONS",
    "PINNED_IDENTITY_VECTORS_BLOB_SHA",
    "PINNED_REVISION",
    "PINNED_VERSION",
    "PINNED_WORKER_REVISION",
    "PINNED_WORKER_TREE_DIGEST",
    "PINNED_WORKER_VERSION",
    "WORKER_DISTRIBUTION",
    "WORKER_REPOSITORY",
    "WORKER_SUBDIRECTORY",
    "InstalledDistribution",
    "InstalledWorker",
    "PinnedDistribution",
    "UnsupportedContractError",
    "check_contract_support",
    "git_blob_sha",
    "installed_contract",
    "installed_distribution",
    "installed_worker",
    "package_tree_digest",
    "pinned_distribution",
    "pinned_requirement",
    "support_errors",
    "worker_tree_digest",
]

#: The Run Contract ``schema_version`` the vendored BENCH-CONTRACT.md publishes.
CONTRACT_SCHEMA_VERSION = 1
#: The Candidate Bundle ``bundle_format_version`` the vendored contract publishes.
CONTRACT_BUNDLE_FORMAT_VERSION = 2
#: The candidate ``identity_spec_version`` the vendored contract (and the
#: vendored ``bench-identity-vectors.json``) publish.
CONTRACT_IDENTITY_SPEC_VERSION = 2

#: The the-ozolith commit every contract surface is vendored from and every
#: the-ozolith distribution is pinned to (``docs/specs/BENCH-CONTRACT.md``
#: provenance banner).
PINNED_REVISION = "19118cae6dc4faf0543bd9bf18aa54621c971358"
#: The distribution version every the-ozolith package carries at that revision.
PINNED_VERSION = "0.3.0"

WORKER_REPOSITORY = "https://github.com/snowfoxbuilds/the-ozolith.git"


@dataclass(frozen=True)
class PinnedDistribution:
    """One the-ozolith distribution the bench consumes: its PyPI-style name,
    its import package, its subdirectory in the monorepo, and the SHA-256
    tree digest of that package directory at :data:`PINNED_REVISION`."""

    name: str
    package: str
    subdirectory: str
    tree_digest: str

    @property
    def requirement(self) -> str:
        """The exact PEP 508 requirement ``pyproject.toml`` must carry."""
        return (
            f"{self.name} @ git+{WORKER_REPOSITORY}@{PINNED_REVISION}"
            f"#subdirectory={self.subdirectory}"
        )


#: Every the-ozolith distribution the bench imports, with the tree digest of
#: its package directory at the pinned commit (the :func:`package_tree_digest`
#: algorithm over the commit's tarball).  The installed packages must hash to
#: these — it is what authenticates an install that records no git revision,
#: and what refuses one whose files were edited after installation.
PINNED_DISTRIBUTIONS: tuple[PinnedDistribution, ...] = (
    PinnedDistribution(
        name="theozolith-worker",
        package="theozolith_worker",
        subdirectory="worker",
        tree_digest="db19b4dee54da426425adb35b146d5db5b950ce019d553c2e65d39bfc6e0d6e9",
    ),
    PinnedDistribution(
        name="theozolith-control",
        package="theozolith_control",
        subdirectory="control",
        tree_digest="c92e898853eb5de1e2b067807888c6b1b8347fe49da091cac008d809183107bd",
    ),
    PinnedDistribution(
        name="theozolith-nodedaemon",
        package="theozolith_nodedaemon",
        subdirectory="nodedaemon",
        tree_digest="8cc46b19c3004526415d820006bca27cca7693768abae179a7454cf6583f6c90",
    ),
    PinnedDistribution(
        name="theozolith-knowledge",
        package="theozolith_knowledge",
        subdirectory="knowledge",
        tree_digest="4ef71f8fa4303540bf9f41c4be1c203839d14e517fd6b7819a38ae50fbc06bcd",
    ),
)

_WORKER = PINNED_DISTRIBUTIONS[0]
_CONTROL = PINNED_DISTRIBUTIONS[1]

# The worker-specific names the #64 surface exposed; still the load-bearing
# ones for the Run Contract, kept as the canonical spellings.
WORKER_DISTRIBUTION = _WORKER.name
WORKER_SUBDIRECTORY = _WORKER.subdirectory
PINNED_WORKER_REVISION = PINNED_REVISION
PINNED_WORKER_VERSION = PINNED_VERSION
PINNED_WORKER_TREE_DIGEST = _WORKER.tree_digest

#: Git blob hash of ``docs/specs/bench-identity-vectors.json`` at
#: :data:`PINNED_REVISION` — the golden identity vectors the vendored
#: BENCH-CONTRACT.md links to, vendored read-only from that same commit.  Unlike
#: the distribution trees, the vectors ship as a doc with no provenance banner,
#: so the file on disk is authenticated by content: it must hash to this
#: (:func:`git_blob_sha` over its bytes).  The contract and its vectors are one
#: surface, re-synced together on a version bump; a drifted or hand-edited
#: vectors file is refused here.
PINNED_IDENTITY_VECTORS_BLOB_SHA = "5eea426f7cd922b65f13a8db20742964628d7ed7"


class UnsupportedContractError(RuntimeError):
    """The installed the-ozolith packages do not speak the pinned Bench Contract."""


@dataclass(frozen=True)
class InstalledDistribution:
    """What is actually installed for one distribution: version, git revision
    (when the install records one — a ``git+`` install does; a directory or
    wheel install does not), the install source, and the digest of the
    installed package tree (the fail-closed authentication — ``None`` when it
    could not be computed, which is itself refused)."""

    version: str
    revision: str | None
    source: str
    tree_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: The worker's install record under its #64 name.
InstalledWorker = InstalledDistribution


def pinned_distribution(name: str) -> PinnedDistribution:
    """The pin for distribution *name* (``ValueError`` for an unknown one)."""
    for pin in PINNED_DISTRIBUTIONS:
        if pin.name == name:
            return pin
    raise ValueError(f"{name!r} is not a pinned the-ozolith distribution")


def pinned_requirement(name: str = WORKER_DISTRIBUTION) -> str:
    """The exact PEP 508 requirement ``pyproject.toml`` must carry for *name*."""
    return pinned_distribution(name).requirement


def git_blob_sha(data: bytes) -> str:
    """The git blob hash of *data* — ``sha1("blob <len>\\0" + data)``.

    This is the object id git and GitHub address a file by, so it authenticates
    a vendored artifact against the exact blob at the pinned revision without a
    network fetch: :data:`PINNED_IDENTITY_VECTORS_BLOB_SHA` is that id for
    ``bench-identity-vectors.json`` at :data:`PINNED_REVISION`.
    """
    header = f"blob {len(data)}\x00".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def package_tree_digest(root: Path) -> str | None:
    """SHA-256 digest of the package tree at *root*.

    Every regular file except bytecode (``__pycache__``, ``*.pyc``) enters as
    ``<posix relpath>\\0<sha256 of contents>\\n``, in sorted path order — the
    same algorithm that produced every :class:`PinnedDistribution.tree_digest`
    from the pinned commit's package directories.  Returns ``None`` when the
    tree cannot be read; the preflight refuses that.
    """
    root = Path(root)
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


def worker_tree_digest(root: Path | None = None) -> str | None:
    """:func:`package_tree_digest` of the installed ``theozolith_worker``
    package (or of *root*)."""
    if root is None:
        root = Path(api.__file__).resolve().parent
    return package_tree_digest(root)


def _installed_package_root(pin: PinnedDistribution) -> Path | None:
    try:
        module = import_module(pin.package)
    except Exception:  # noqa: BLE001 - an unimportable package is refused below
        return None
    file = getattr(module, "__file__", None)
    return Path(file).resolve().parent if file else None


def installed_distribution(pin: PinnedDistribution) -> InstalledDistribution:
    """Inspect one installed the-ozolith distribution.

    The revision comes from the install's ``direct_url.json`` (PEP 610)
    ``vcs_info.commit_id`` — present for a ``git+`` install, absent otherwise.
    The tree digest is always computed from the installed package itself.
    """
    try:
        dist = metadata.distribution(pin.name)
    except metadata.PackageNotFoundError as exc:
        raise UnsupportedContractError(
            f"{pin.name} is not installed; install {pin.requirement!r}"
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
    root = _installed_package_root(pin)
    return InstalledDistribution(
        version=dist.version,
        revision=revision,
        source=source,
        tree_digest=package_tree_digest(root) if root is not None else None,
    )


def installed_worker() -> InstalledWorker:
    """Inspect the installed ``theozolith-worker`` distribution."""
    return installed_distribution(_WORKER)


def installed_contract() -> dict[str, InstalledDistribution]:
    """Every pinned distribution's install record, keyed by distribution name
    (the worker's through :func:`installed_worker`, the one seam tests stand
    a synthetic install behind)."""
    return {
        pin.name: installed_worker() if pin is _WORKER else installed_distribution(pin)
        for pin in PINNED_DISTRIBUTIONS
    }


def _distribution_errors(pin: PinnedDistribution, dist: InstalledDistribution) -> list[str]:
    errors: list[str] = []
    if dist.version != PINNED_VERSION:
        errors.append(
            f"{pin.name} {dist.version} is installed, but the bench pins {PINNED_VERSION}"
        )
    if dist.revision is not None and dist.revision != PINNED_REVISION:
        errors.append(
            f"{pin.name} is installed from revision {dist.revision}, but the bench"
            f" pins {PINNED_REVISION}"
        )
    if dist.tree_digest is None:
        errors.append(
            f"the installed {pin.name} tree could not be read, so it cannot be"
            f" authenticated against the pinned revision"
        )
    elif dist.tree_digest != pin.tree_digest:
        errors.append(
            f"the installed {pin.name} tree digest {dist.tree_digest} does not match"
            f" the pinned revision's {pin.tree_digest} — the install is locally"
            f" modified or not revision {PINNED_REVISION}"
        )
    return errors


def _verifier_version_errors() -> list[str]:
    """The bundle-format and identity-spec keys the installed verifier stamps
    must be the ones the vendored contract publishes."""
    try:
        verifier = import_module(f"{_CONTROL.package}.candidate")
    except Exception as exc:  # noqa: BLE001 - reported, never excused
        return [f"the Candidate Bundle verifier ({_CONTROL.package}.candidate) cannot be imported: {exc}"]
    errors: list[str] = []
    for attr, expected, key in (
        ("BUNDLE_FORMAT_VERSION", CONTRACT_BUNDLE_FORMAT_VERSION, "bundle_format_version"),
        ("IDENTITY_SPEC_VERSION", CONTRACT_IDENTITY_SPEC_VERSION, "identity_spec_version"),
    ):
        actual = getattr(verifier, attr, None)
        if actual != expected:
            errors.append(
                f"the installed verifier stamps {key} {actual!r}, but the vendored"
                f" Bench Contract is {key} {expected}"
            )
    return errors


def support_errors(
    worker: InstalledDistribution | None = None,
    packages: Mapping[str, InstalledDistribution] | None = None,
) -> list[str]:
    """Every way the installed the-ozolith packages disagree with the pin.

    Fails closed: each installed tree must hash to the pinned revision's tree
    digest — a matching version and schema number never admit a package on
    their own, and an unreadable tree is refused, not excused.  *worker*
    stands in for the live worker record (tests), *packages* for the others.
    """
    errors: list[str] = []
    if api.SCHEMA_VERSION != CONTRACT_SCHEMA_VERSION:
        errors.append(
            f"the installed worker speaks Run Contract schema_version {api.SCHEMA_VERSION},"
            f" but the vendored Bench Contract is schema_version {CONTRACT_SCHEMA_VERSION}"
        )
    errors.extend(_verifier_version_errors())
    for pin in PINNED_DISTRIBUTIONS:
        if pin is _WORKER and worker is not None:
            dist = worker
        elif packages is not None and pin.name in packages:
            dist = packages[pin.name]
        else:
            try:
                dist = installed_distribution(pin)
            except UnsupportedContractError as exc:
                errors.append(str(exc))
                continue
        errors.extend(_distribution_errors(pin, dist))
    return errors


def check_contract_support() -> InstalledWorker:
    """Refuse — :class:`UnsupportedContractError` — unless every installed
    the-ozolith package is the pinned one; return the worker's record otherwise."""
    packages = installed_contract()
    errors = support_errors(packages[WORKER_DISTRIBUTION], packages)
    if errors:
        requirements = ", ".join(repr(pin.requirement) for pin in PINNED_DISTRIBUTIONS)
        raise UnsupportedContractError(
            "; ".join(errors)
            + f" (re-sync docs/specs/BENCH-CONTRACT.md and install {requirements})"
        )
    return packages[WORKER_DISTRIBUTION]
