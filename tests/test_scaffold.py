"""Tests verifying the project scaffold meets TODO item 1 requirements.

These tests confirm:
- pyproject.toml metadata (project name, license, Python version, dependencies)
- Package directory structure with __init__.py files
- Importability of engine, cards, and cards.foundations packages
- py.typed PEP 561 marker exists
- ruff.toml configuration (line-length, target-version)
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

# Repo root is two levels up from this test file (tests/test_scaffold.py -> repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPyprojectToml:
    """Verify pyproject.toml exists and has the required metadata."""

    @pytest.fixture(autouse=True)
    def _load_pyproject(self) -> None:
        """Read and parse pyproject.toml once per test."""
        assert tomllib is not None, "tomllib/tomli required to parse TOML"
        pyproject_path = REPO_ROOT / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml must exist at repo root"
        with open(pyproject_path, "rb") as f:
            self.data: dict[str, Any] = tomllib.load(f)

    def test_project_name_is_silverquillm_bench(self) -> None:
        """Project name should normalize to 'silverquillm-bench'."""
        # PEP 503: names are case-insensitive, with -, _, . equivalent
        raw_name: str = self.data["project"]["name"]
        normalized = raw_name.lower().replace("_", "-").replace(".", "-")
        assert normalized == "silverquillm-bench"

    def test_requires_python_at_least_3_10(self) -> None:
        """requires-python must specify >=3.12 as minimum."""
        requires_python: str = self.data["project"]["requires-python"]
        assert "3.12" in requires_python, (
            f"requires-python should specify >=3.12, got '{requires_python}'"
        )

    def test_license_is_gpl2(self) -> None:
        """License must be GPL-2.0 (SPDX identifier)."""
        license_value = self.data["project"].get("license", "")
        # Could be a string (SPDX expression) or a dict with "text" key
        if isinstance(license_value, dict):
            license_str = license_value.get("text", "") or license_value.get("file", "")
        else:
            license_str = str(license_value)
        assert "GPL-2.0" in license_str, (
            f"License should be GPL-2.0, got '{license_str}'"
        )

    def test_runtime_dependency_requests(self) -> None:
        """Runtime dependencies must include 'requests'."""
        deps = self.data["project"].get("dependencies", [])
        dep_names = [d.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip().lower()
                     for d in deps]
        assert "requests" in dep_names, (
            f"'requests' must be a runtime dependency, got {deps}"
        )

    def test_dev_dependencies_include_required_tools(self) -> None:
        """Dev optional-dependencies must include pytest, pytest-cov, ruff, mypy."""
        optional_deps = self.data["project"].get("optional-dependencies", {})
        dev_deps = optional_deps.get("dev", [])
        dev_dep_names = {
            d.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip().lower()
            for d in dev_deps
        }
        required = {"pytest", "pytest-cov", "ruff", "mypy"}
        missing = required - dev_dep_names
        assert not missing, f"Dev deps missing: {missing}. Found: {dev_dep_names}"


class TestDirectoryStructure:
    """Verify all required directories exist with __init__.py files."""

    @pytest.mark.parametrize(
        "package_dir",
        [
            "engine",
            "cards",
            "cards/foundations",
            "tests",
            "tests/engine",
            "tests/cards",
        ],
        ids=[
            "engine",
            "cards",
            "cards/foundations",
            "tests",
            "tests/engine",
            "tests/cards",
        ],
    )
    def test_directory_has_init_py(self, package_dir: str) -> None:
        """Each package directory must contain an __init__.py file."""
        init_path = REPO_ROOT / package_dir / "__init__.py"
        assert init_path.is_file(), (
            f"{package_dir}/__init__.py must exist"
        )


class TestPackageImportability:
    """Verify that the main packages are importable as Python modules."""

    def test_import_engine(self) -> None:
        """The 'engine' package must be importable."""
        mod = importlib.import_module("engine")
        assert mod is not None

    def test_import_cards(self) -> None:
        """The 'cards' package must be importable."""
        mod = importlib.import_module("cards")
        assert mod is not None

    def test_import_cards_foundations(self) -> None:
        """The 'cards.foundations' subpackage must be importable."""
        mod = importlib.import_module("cards.foundations")
        assert mod is not None


class TestPyTypedMarker:
    """Verify PEP 561 py.typed marker files exist in each package."""

    @pytest.mark.parametrize(
        "package_dir",
        ["engine", "cards"],
        ids=["engine", "cards"],
    )
    def test_py_typed_exists(self, package_dir: str) -> None:
        """py.typed marker must exist in each package directory for PEP 561 compliance."""
        py_typed = REPO_ROOT / package_dir / "py.typed"
        assert py_typed.is_file(), (
            f"py.typed marker file must exist at {package_dir}/py.typed"
        )


class TestRuffConfig:
    """Verify ruff.toml configuration matches requirements."""

    @pytest.fixture(autouse=True)
    def _load_ruff_toml(self) -> None:
        """Read and parse ruff.toml."""
        assert tomllib is not None, "tomllib/tomli required to parse TOML"
        ruff_path = REPO_ROOT / "ruff.toml"
        assert ruff_path.exists(), "ruff.toml must exist at repo root"
        with open(ruff_path, "rb") as f:
            self.data: dict[str, Any] = tomllib.load(f)

    def test_line_length_is_100(self) -> None:
        """Ruff line-length must be 100."""
        assert self.data.get("line-length") == 100, (
            f"line-length should be 100, got {self.data.get('line-length')}"
        )

    def test_target_version_is_py311(self) -> None:
        """Ruff target-version must be py312 (Python 3.12)."""
        assert self.data.get("target-version") == "py312", (
            f"target-version should be 'py312', got {self.data.get('target-version')}"
        )
