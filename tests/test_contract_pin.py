"""The Bench Contract pin: three sources, one revision, and the refusal.

``pyproject.toml`` (the install), ``docs/specs/BENCH-CONTRACT.md`` (the
vendored contract) and ``silverquillm/contract_version.py`` (what the driver
enforces) must name the same immutable the-ozolith revision, and the installed
worker must *be* that revision: its package tree must hash to the pinned
revision's tree digest, so a directory or editable install is authenticated by
its contents and a locally modified install is refused — version and schema
numbers never admit a worker on their own.  A skew in any of them is refused
by the driver's preflight before a job dir is staged.

The vendored contract does not travel alone: ``docs/specs/bench-identity-
vectors.json`` — the golden identity vectors the contract links to — is
vendored read-only from the same pinned revision, and is authenticated the
same content-addressed way (its git blob hash must equal the pinned one).  A
version bump re-syncs both artifacts together; a drifted vectors file is
refused, and both artifacts must publish the same ``identity_spec_version``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
from importlib import metadata
from pathlib import Path

import pytest
from theozolith_worker import api

from silverquillm import contract_version as cv

REPO = Path(__file__).resolve().parents[1]
CONTRACT_DOC = REPO / "docs" / "specs" / "BENCH-CONTRACT.md"
IDENTITY_VECTORS = REPO / "docs" / "specs" / "bench-identity-vectors.json"


def _pyproject_requirement(name: str = cv.WORKER_DISTRIBUTION) -> str:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    reqs = [r for r in data["project"]["dependencies"] if r.startswith(f"{name} ")]
    assert len(reqs) == 1, reqs
    return reqs[0]


class TestThreeSourcesAgree:
    def test_pyproject_pins_the_exact_immutable_revision(self) -> None:
        assert re.fullmatch(r"[0-9a-f]{40}", cv.PINNED_WORKER_REVISION)
        assert _pyproject_requirement() == cv.pinned_requirement()
        assert " @ git+" in cv.pinned_requirement()
        assert cv.pinned_requirement().endswith("#subdirectory=worker")

    def test_every_consumed_package_is_pinned_to_the_one_revision(self) -> None:
        """The verifier (control), its codegen (nodedaemon) and compiler
        (knowledge) ride the same immutable revision as the worker."""
        names = [pin.name for pin in cv.PINNED_DISTRIBUTIONS]
        assert names == [
            "theozolith-worker", "theozolith-control", "theozolith-nodedaemon", "theozolith-knowledge",
        ]
        for pin in cv.PINNED_DISTRIBUTIONS:
            assert _pyproject_requirement(pin.name) == pin.requirement == cv.pinned_requirement(pin.name)
            assert f"@{cv.PINNED_REVISION}#subdirectory={pin.subdirectory}" in pin.requirement
            assert re.fullmatch(r"[0-9a-f]{64}", pin.tree_digest)
        with pytest.raises(ValueError):
            cv.pinned_requirement("theozolith-nonesuch")

    def test_vendored_contract_is_from_the_pinned_revision(self) -> None:
        text = CONTRACT_DOC.read_text(encoding="utf-8")
        match = re.search(r"Commit:\s*([0-9a-f]{40})", text)
        assert match, "the vendored contract carries no provenance commit"
        assert match.group(1) == cv.PINNED_WORKER_REVISION

    def test_vendored_contract_publishes_the_versions_the_bench_enforces(self) -> None:
        text = CONTRACT_DOC.read_text(encoding="utf-8")
        assert re.search(
            rf"\*\*`schema_version`\*\* \(currently {cv.CONTRACT_SCHEMA_VERSION},", text
        ), "BENCH-CONTRACT.md's schema_version differs from CONTRACT_SCHEMA_VERSION"
        assert re.search(
            rf"\*\*`bundle_format_version`\*\* \(currently {cv.CONTRACT_BUNDLE_FORMAT_VERSION},", text
        )
        assert re.search(
            rf"\*\*`identity_spec_version`\*\* \(currently {cv.CONTRACT_IDENTITY_SPEC_VERSION},", text
        )
        assert api.SCHEMA_VERSION == cv.CONTRACT_SCHEMA_VERSION
        from theozolith_control import candidate as verifier

        assert verifier.BUNDLE_FORMAT_VERSION == cv.CONTRACT_BUNDLE_FORMAT_VERSION
        assert verifier.IDENTITY_SPEC_VERSION == cv.CONTRACT_IDENTITY_SPEC_VERSION

    def test_vendored_identity_vectors_are_the_pinned_spec_version(self) -> None:
        vectors = json.loads(IDENTITY_VECTORS.read_text(encoding="utf-8"))
        assert vectors["identity_spec_version"] == cv.CONTRACT_IDENTITY_SPEC_VERSION


class TestVendoredIdentityVectorsShareTheRevision:
    """The golden identity vectors are vendored from the same pinned revision
    as the contract that links to them, and cannot silently drift from it."""

    def test_the_contract_links_to_a_present_vectors_file(self) -> None:
        # The contract links to the vectors relative to itself; the target of
        # that link must exist next to it (the link must resolve, not dangle).
        text = CONTRACT_DOC.read_text(encoding="utf-8")
        assert "(bench-identity-vectors.json)" in text, (
            "BENCH-CONTRACT.md no longer links to bench-identity-vectors.json"
        )
        assert IDENTITY_VECTORS.is_file(), (
            f"{IDENTITY_VECTORS} is missing — re-sync it from the pinned revision"
        )

    def test_vectors_are_the_pinned_revisions_bytes(self) -> None:
        # Content-addressed authentication: the vendored file must be, byte for
        # byte, the blob at PINNED_REVISION.  A version bump that re-syncs the
        # contract must re-sync these vectors too, or this fails.
        blob = cv.git_blob_sha(IDENTITY_VECTORS.read_bytes())
        assert blob == cv.PINNED_IDENTITY_VECTORS_BLOB_SHA, (
            f"bench-identity-vectors.json blob {blob} != pinned "
            f"{cv.PINNED_IDENTITY_VECTORS_BLOB_SHA} — the vectors have drifted "
            f"from the-ozolith @ {cv.PINNED_REVISION}; re-sync the vectors "
            "and BENCH-CONTRACT.md together and update the pin"
        )
        assert re.fullmatch(r"[0-9a-f]{40}", cv.PINNED_IDENTITY_VECTORS_BLOB_SHA)


class TestInstalledWorkerIsThePinnedOne:
    def test_version_and_schema(self) -> None:
        worker = cv.installed_worker()
        assert worker.version == cv.PINNED_WORKER_VERSION
        assert cv.support_errors(worker) == []
        assert cv.check_contract_support() == worker

    def test_installed_tree_hashes_to_the_pinned_digest(self) -> None:
        # The suite itself refuses to pass against a worker that is not,
        # byte for byte, the pinned revision's tree.
        worker = cv.installed_worker()
        assert worker.tree_digest == cv.PINNED_WORKER_TREE_DIGEST, worker
        assert re.fullmatch(r"[0-9a-f]{64}", cv.PINNED_WORKER_TREE_DIGEST)

    def test_revision_when_the_install_records_one(self) -> None:
        worker = cv.installed_worker()
        if worker.revision is not None:
            assert worker.revision == cv.PINNED_WORKER_REVISION
        if os.environ.get("GITHUB_ACTIONS"):
            # CI installs from the pinned git reference, so the revision is
            # recorded and must be proven — never just the version.
            assert worker.revision == cv.PINNED_WORKER_REVISION, worker

    def test_every_installed_package_tree_hashes_to_its_pin(self) -> None:
        installed = cv.installed_contract()
        assert set(installed) == {pin.name for pin in cv.PINNED_DISTRIBUTIONS}
        for pin in cv.PINNED_DISTRIBUTIONS:
            dist = installed[pin.name]
            assert dist.version == cv.PINNED_VERSION, (pin.name, dist)
            assert dist.tree_digest == pin.tree_digest, (pin.name, dist)
            if dist.revision is not None or os.environ.get("GITHUB_ACTIONS"):
                assert dist.revision == cv.PINNED_REVISION, (pin.name, dist)


class TestRefusal:
    def test_a_non_worker_package_tree_mismatch_is_refused(self) -> None:
        """The verifier's own code is authenticated like the worker's: a
        control tree that does not hash to the pin is refused."""
        packages = dict(cv.installed_contract())
        packages["theozolith-control"] = cv.InstalledDistribution(
            version=cv.PINNED_VERSION, revision=None, source="file:///x", tree_digest="0" * 64
        )
        errors = cv.support_errors(packages[cv.WORKER_DISTRIBUTION], packages)
        assert any("theozolith-control" in e and "tree digest" in e for e in errors)
        assert not any("theozolith-worker" in e for e in errors)

    def test_a_missing_package_is_refused(self, monkeypatch) -> None:
        real = cv.installed_distribution

        def missing(pin):
            if pin.name == "theozolith-nodedaemon":
                raise cv.UnsupportedContractError("theozolith-nodedaemon is not installed")
            return real(pin)

        monkeypatch.setattr(cv, "installed_distribution", missing)
        errors = cv.support_errors()
        assert any("theozolith-nodedaemon is not installed" in e for e in errors)
        with pytest.raises(cv.UnsupportedContractError, match="nodedaemon"):
            cv.check_contract_support()

    @pytest.mark.parametrize("attr", ["BUNDLE_FORMAT_VERSION", "IDENTITY_SPEC_VERSION"])
    def test_verifier_version_skew_is_refused(self, monkeypatch, attr) -> None:
        from theozolith_control import candidate as verifier

        monkeypatch.setattr(verifier, attr, getattr(verifier, attr) + 1)
        errors = cv.support_errors()
        assert any(attr.lower() in e for e in errors), errors
        with pytest.raises(cv.UnsupportedContractError, match=attr.lower()):
            cv.check_contract_support()

    def test_schema_skew_is_refused(self, monkeypatch) -> None:
        monkeypatch.setattr(api, "SCHEMA_VERSION", cv.CONTRACT_SCHEMA_VERSION + 1)
        errors = cv.support_errors()
        assert any("schema_version" in e for e in errors)
        with pytest.raises(cv.UnsupportedContractError, match="schema_version"):
            cv.check_contract_support()

    def test_version_skew_is_refused(self) -> None:
        worker = cv.InstalledWorker(
            version="0.2.9", revision=cv.PINNED_WORKER_REVISION, source="x",
            tree_digest=cv.PINNED_WORKER_TREE_DIGEST,
        )
        assert any("0.2.9" in e for e in cv.support_errors(worker))

    def test_revision_skew_is_refused(self) -> None:
        worker = cv.InstalledWorker(
            version=cv.PINNED_WORKER_VERSION, revision="deadbeef" * 5, source="git+x",
            tree_digest=cv.PINNED_WORKER_TREE_DIGEST,
        )
        assert any("deadbeef" in e for e in cv.support_errors(worker))

    def test_unrecorded_revision_without_the_pinned_tree_is_refused(self, monkeypatch) -> None:
        """Fail closed: no recorded revision plus a non-pinned tree is an
        unauthenticated worker — version 0.3.0 and schema 1 do not admit it."""
        worker = cv.InstalledWorker(
            version=cv.PINNED_WORKER_VERSION, revision=None, source="file:///x",
            tree_digest="0" * 64,
        )
        errors = cv.support_errors(worker)
        assert any("tree digest" in e for e in errors)
        monkeypatch.setattr(cv, "installed_worker", lambda: worker)
        with pytest.raises(cv.UnsupportedContractError, match="tree digest"):
            cv.check_contract_support()

    def test_locally_modified_worker_is_refused(self, tmp_path: Path, monkeypatch) -> None:
        """A correct recorded revision does not excuse edited files: the live
        tree is what gets hashed, and one changed byte is a refusal."""
        source = Path(api.__file__).resolve().parent
        copy = tmp_path / "theozolith_worker"
        shutil.copytree(source, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        assert cv.worker_tree_digest(copy) == cv.PINNED_WORKER_TREE_DIGEST
        api_py = copy / "api.py"
        api_py.write_text(api_py.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
        modified_digest = cv.worker_tree_digest(copy)
        assert modified_digest != cv.PINNED_WORKER_TREE_DIGEST
        worker = cv.InstalledWorker(
            version=cv.PINNED_WORKER_VERSION, revision=cv.PINNED_WORKER_REVISION,
            source="git+x", tree_digest=modified_digest,
        )
        assert any("locally modified" in e for e in cv.support_errors(worker))
        monkeypatch.setattr(cv, "installed_worker", lambda: worker)
        with pytest.raises(cv.UnsupportedContractError, match="tree digest"):
            cv.check_contract_support()

    def test_unreadable_tree_is_refused_not_excused(self) -> None:
        worker = cv.InstalledWorker(
            version=cv.PINNED_WORKER_VERSION, revision=cv.PINNED_WORKER_REVISION,
            source="git+x", tree_digest=None,
        )
        assert any("cannot be authenticated" in e for e in cv.support_errors(worker))
        assert cv.worker_tree_digest(Path("/nonexistent/theozolith_worker")) is None

    def test_unrecorded_revision_with_the_pinned_tree_is_authenticated(self) -> None:
        """The one legitimate no-revision install: a directory/editable install
        whose tree IS the pinned revision, proven by its digest."""
        worker = cv.InstalledWorker(
            version=cv.PINNED_WORKER_VERSION, revision=None, source="file:///x",
            tree_digest=cv.PINNED_WORKER_TREE_DIGEST,
        )
        assert cv.support_errors(worker) == []

    def test_missing_distribution_is_refused(self, monkeypatch) -> None:
        def missing(name):
            raise metadata.PackageNotFoundError(name)

        monkeypatch.setattr(cv.metadata, "distribution", missing)
        with pytest.raises(cv.UnsupportedContractError, match="not installed"):
            cv.installed_worker()
