"""The Bench Contract pin: three sources, one revision, and the refusal.

``pyproject.toml`` (the install), ``docs/specs/BENCH-CONTRACT.md`` (the
vendored contract) and ``silverquillm/contract_version.py`` (what the driver
enforces) must name the same immutable the-ozolith revision, and the installed
worker must be that revision.  A skew in any of them is refused by the driver's
preflight before a job dir is staged.
"""

from __future__ import annotations

import os
import re
import tomllib
from importlib import metadata
from pathlib import Path

import pytest
from theozolith_worker import api

from silverquillm import contract_version as cv

REPO = Path(__file__).resolve().parents[1]
CONTRACT_DOC = REPO / "docs" / "specs" / "BENCH-CONTRACT.md"


def _pyproject_requirement() -> str:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    reqs = [r for r in data["project"]["dependencies"] if r.startswith(cv.WORKER_DISTRIBUTION)]
    assert len(reqs) == 1, reqs
    return reqs[0]


class TestThreeSourcesAgree:
    def test_pyproject_pins_the_exact_immutable_revision(self) -> None:
        assert re.fullmatch(r"[0-9a-f]{40}", cv.PINNED_WORKER_REVISION)
        assert _pyproject_requirement() == cv.pinned_requirement()
        assert " @ git+" in cv.pinned_requirement()
        assert cv.pinned_requirement().endswith("#subdirectory=worker")

    def test_vendored_contract_is_from_the_pinned_revision(self) -> None:
        text = CONTRACT_DOC.read_text(encoding="utf-8")
        match = re.search(r"Commit:\s*([0-9a-f]{40})", text)
        assert match, "the vendored contract carries no provenance commit"
        assert match.group(1) == cv.PINNED_WORKER_REVISION

    def test_vendored_contract_publishes_the_schema_version_the_bench_enforces(self) -> None:
        text = CONTRACT_DOC.read_text(encoding="utf-8")
        assert re.search(
            rf"\*\*`schema_version`\*\* \(currently {cv.CONTRACT_SCHEMA_VERSION},", text
        ), "BENCH-CONTRACT.md's schema_version differs from CONTRACT_SCHEMA_VERSION"
        assert api.SCHEMA_VERSION == cv.CONTRACT_SCHEMA_VERSION


class TestInstalledWorkerIsThePinnedOne:
    def test_version_and_schema(self) -> None:
        worker = cv.installed_worker()
        assert worker.version == cv.PINNED_WORKER_VERSION
        assert cv.support_errors(worker) == []
        assert cv.check_contract_support() == worker

    def test_revision_when_the_install_records_one(self) -> None:
        worker = cv.installed_worker()
        if worker.revision is not None:
            assert worker.revision == cv.PINNED_WORKER_REVISION
        if os.environ.get("GITHUB_ACTIONS"):
            # CI installs from the pinned git reference, so the revision is
            # recorded and must be proven — never just the version.
            assert worker.revision == cv.PINNED_WORKER_REVISION, worker


class TestRefusal:
    def test_schema_skew_is_refused(self, monkeypatch) -> None:
        monkeypatch.setattr(api, "SCHEMA_VERSION", cv.CONTRACT_SCHEMA_VERSION + 1)
        errors = cv.support_errors()
        assert any("schema_version" in e for e in errors)
        with pytest.raises(cv.UnsupportedContractError, match="schema_version"):
            cv.check_contract_support()

    def test_version_skew_is_refused(self) -> None:
        worker = cv.InstalledWorker(version="0.2.9", revision=cv.PINNED_WORKER_REVISION, source="x")
        assert any("0.2.9" in e for e in cv.support_errors(worker))

    def test_revision_skew_is_refused(self) -> None:
        worker = cv.InstalledWorker(
            version=cv.PINNED_WORKER_VERSION, revision="deadbeef" * 5, source="git+x"
        )
        assert any("deadbeef" in e for e in cv.support_errors(worker))

    def test_unverifiable_revision_is_allowed(self) -> None:
        worker = cv.InstalledWorker(version=cv.PINNED_WORKER_VERSION, revision=None, source="file:///x")
        assert cv.support_errors(worker) == []

    def test_missing_distribution_is_refused(self, monkeypatch) -> None:
        def missing(name):
            raise metadata.PackageNotFoundError(name)

        monkeypatch.setattr(cv.metadata, "distribution", missing)
        with pytest.raises(cv.UnsupportedContractError, match="not installed"):
            cv.installed_worker()
