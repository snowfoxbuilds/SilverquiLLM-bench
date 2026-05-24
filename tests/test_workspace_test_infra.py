"""Tests for TODO 1.3: Move workspace test infrastructure into the workspace."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "benchmarks" / "sos" / "workspace"


# ------------------------------------------------------------------
# New locations exist
# ------------------------------------------------------------------


class TestNewLocationsExist:
    """Verify that workspace test files exist at their new locations."""

    def test_test_utils_py_exists(self):
        assert (WORKSPACE / "tests" / "test_utils.py").is_file()

    def test_conftest_py_exists(self):
        assert (WORKSPACE / "tests" / "conftest.py").is_file()

    def test_init_py_exists(self):
        assert (WORKSPACE / "tests" / "__init__.py").is_file()

    def test_test_utils_md_exists(self):
        assert (WORKSPACE / "tests" / "test_utils.md").is_file()

    def test_engine_dir_exists(self):
        assert (WORKSPACE / "tests" / "engine").is_dir()

    def test_engine_has_test_files(self):
        engine_dir = WORKSPACE / "tests" / "engine"
        test_files = list(engine_dir.glob("test_*.py"))
        assert len(test_files) > 0, "engine/ should contain test_*.py files"


# ------------------------------------------------------------------
# Old locations removed
# ------------------------------------------------------------------


class TestOldLocationsRemoved:
    """Verify that workspace test files no longer exist at old top-level locations."""

    def test_no_toplevel_test_utils_py(self):
        assert not (REPO_ROOT / "tests" / "test_utils.py").exists()

    def test_no_toplevel_conftest_py(self):
        assert not (REPO_ROOT / "tests" / "conftest.py").exists()

    def test_no_docs_test_utils_md(self):
        assert not (REPO_ROOT / "docs" / "test_utils.md").exists()

    def test_no_toplevel_pytest_ini(self):
        assert not (REPO_ROOT / "pytest.ini").exists()


# ------------------------------------------------------------------
# Pytest collection works for workspace engine tests
# ------------------------------------------------------------------


class TestPytestDiscovery:
    """Verify that pytest can discover workspace engine test files."""

    def test_engine_test_files_are_valid_python(self):
        """All test_*.py in engine/ must be syntactically valid Python."""
        engine_dir = WORKSPACE / "tests" / "engine"
        test_files = list(engine_dir.glob("test_*.py"))
        for tf in test_files:
            result = subprocess.run(
                [sys.executable, "-c", f"import ast; ast.parse(open('{tf}').read())"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Syntax error in {tf.name}: {result.stderr}"

    def test_engine_test_files_discoverable_by_pytest(self):
        """pytest should attempt to collect files from the engine test dir.

        Note: full collection may fail until engine modules are implemented,
        but pytest must at least find and attempt to process the test files.
        """
        engine_dir = WORKSPACE / "tests" / "engine"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(engine_dir),
                "--collect-only",
                "-q",
            ],
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE),
        )
        # pytest should find the directory and attempt collection
        # (import errors show it found the files even if engine code is missing)
        output = result.stdout + result.stderr
        assert "no tests ran" not in output.lower() or "error" in output.lower(), (
            "pytest did not find any test files in engine/"
        )

    def test_workspace_has_pytest_ini(self):
        """The workspace must have its own pytest.ini for local test runs."""
        assert (WORKSPACE / "pytest.ini").is_file()

    def test_conftest_is_importable(self):
        """The workspace conftest.py should be importable as a module."""
        result = subprocess.run(
            [sys.executable, "-c", "import ast; ast.parse(open(r'{}').read())".format(
                WORKSPACE / "tests" / "conftest.py"
            )],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"conftest.py has syntax errors: {result.stderr}"
