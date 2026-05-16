"""Tests verifying pytest infrastructure: integration marker, timeout, addopts."""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class TestPyprojectInfrastructure:
    """Verify pyproject.toml has correct pytest infrastructure settings."""

    @pytest.fixture(autouse=True)
    def _load_pyproject(self) -> None:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        self.pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    def test_pytest_timeout_in_dev_deps(self) -> None:
        """pytest-timeout must be listed in [project.optional-dependencies] dev."""
        dev_deps = self.pyproject["project"]["optional-dependencies"]["dev"]
        assert any("pytest-timeout" in d for d in dev_deps), (
            "pytest-timeout not found in dev dependencies"
        )

    def test_integration_marker_defined(self) -> None:
        """The 'integration' marker must be registered to avoid warnings."""
        markers = self.pyproject["tool"]["pytest"]["ini_options"]["markers"]
        # markers can be a list or a single string
        if isinstance(markers, list):
            found = any("integration" in m for m in markers)
        else:
            found = "integration" in markers
        assert found, "integration marker not defined in pyproject.toml"

    def test_default_timeout_300(self) -> None:
        """Default timeout must be 300 seconds."""
        timeout = self.pyproject["tool"]["pytest"]["ini_options"]["timeout"]
        assert timeout == 300

    def test_addopts_skips_integration_by_default(self) -> None:
        """addopts must include '-m "not integration"' so integration tests are skipped."""
        addopts = self.pyproject["tool"]["pytest"]["ini_options"]["addopts"]
        assert "not integration" in addopts


class TestSmokeLifecycleFileExists:
    """Verify the integration test file exists and is properly marked."""

    def test_smoke_lifecycle_file_exists(self) -> None:
        """tests/test_smoke_lifecycle.py must exist."""
        assert (ROOT / "tests" / "test_smoke_lifecycle.py").is_file()

    def test_smoke_lifecycle_has_integration_marker(self) -> None:
        """The smoke lifecycle test must use @pytest.mark.integration."""
        source = (ROOT / "tests" / "test_smoke_lifecycle.py").read_text()
        assert "@pytest.mark.integration" in source


class TestIntegrationTestsSkippedByDefault:
    """Verify integration-marked tests are actually skipped in default runs."""

    def test_smoke_lifecycle_not_collected(self) -> None:
        """Running pytest without -m integration should NOT collect smoke tests."""
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/test_smoke_lifecycle.py",
                "--collect-only", "-q",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=30,
        )
        # With '-m "not integration"' in addopts, the test should be deselected
        assert "no tests ran" in result.stdout or "deselected" in result.stdout or \
               "0 selected" in result.stdout, (
            f"Integration test was not skipped. stdout: {result.stdout}"
        )

    def test_integration_tests_collected_with_marker_flag(self) -> None:
        """Running pytest -m integration should collect the smoke test."""
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/test_smoke_lifecycle.py",
                "--collect-only", "-q",
                "-m", "integration",
                "--override-ini=addopts=--import-mode=importlib",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=30,
        )
        assert "test_smoke_container_lifecycle" in result.stdout, (
            f"Integration test not collected with -m integration. stdout: {result.stdout}"
        )
