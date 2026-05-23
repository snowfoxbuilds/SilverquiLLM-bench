"""Tests verifying the project scaffold meets TODO item 1 requirements.

These tests confirm:
- pyproject.toml metadata (project name, license, Python version, dependencies)
- Package directory structure with __init__.py files
- Importability of engine, cards, and cards.fdn packages
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
            "tests",
            "tests/engine",
        ],
        ids=[
            "engine",
            "cards",
            "tests",
            "tests/engine",
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

    def test_import_cards_fdn(self) -> None:
        """The 'cards.fdn' subpackage directory must exist."""
        from pathlib import Path
        fdn_dir = REPO_ROOT / "cards" / "fdn"
        assert fdn_dir.is_dir(), "cards/fdn/ must exist"


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


# --- Tests for TODO item 2: .gitignore results path convention ---


class TestGitignoreResultsPath:
    """Verify .gitignore uses the new docker/*/results/ pattern."""

    def setup_method(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        self.gitignore_path = repo_root / ".gitignore"
        self.content = self.gitignore_path.read_text()
        self.lines = [line.strip() for line in self.content.splitlines()]

    def test_contains_new_docker_results_pattern(self) -> None:
        """`.gitignore` must contain the `docker/*/results/` pattern."""
        assert "docker/*/results/" in self.lines

    def test_does_not_contain_bare_results_line(self) -> None:
        """`.gitignore` must NOT contain a bare `results/` line (old pattern)."""
        assert "results/" not in self.lines


class TestReadmeResultsPaths:
    """Verify README.md has migrated all results path references (TODO item 3)."""

    @pytest.fixture(autouse=True)
    def _load_readme(self) -> None:
        readme_path = REPO_ROOT / "README.md"
        assert readme_path.exists(), "README.md must exist at repo root"
        self.content = readme_path.read_text(encoding="utf-8")

    def test_no_legacy_results_run_name_references(self) -> None:
        """README.md must not contain any literal 'results/{run_name}' references."""
        assert "results/{run_name}" not in self.content, (
            "Found legacy 'results/{run_name}' reference in README.md"
        )

    def test_contains_docker_path_reference(self) -> None:
        """README.md must contain at least one 'docker/' path (confirms migration)."""
        assert "docker/" in self.content, (
            "README.md should reference 'docker/' paths after migration"
        )


class TestProjectMapResultsPaths:
    """Verify PROJECT_MAP.md has migrated results path references."""

    @pytest.fixture(autouse=True)
    def _load_project_map(self) -> None:
        """Read PROJECT_MAP.md content."""
        project_map_path = REPO_ROOT / "PROJECT_MAP.md"
        assert project_map_path.exists(), "PROJECT_MAP.md must exist at repo root"
        self.content = project_map_path.read_text(encoding="utf-8")

    def test_no_old_results_run_name_pattern(self) -> None:
        """PROJECT_MAP.md must not contain literal 'results/{run_name}' (old path format)."""
        # The old pattern "results/{run_name}/" without the docker prefix must be gone.
        # We search for occurrences that are NOT preceded by docker/<image_dir>/
        lines_with_old_pattern = [
            (i + 1, line)
            for i, line in enumerate(self.content.splitlines())
            if "results/{run_name}" in line and "docker/" not in line
        ]
        assert lines_with_old_pattern == [], (
            f"PROJECT_MAP.md still contains old 'results/{{run_name}}' references "
            f"(not under docker/) at lines: {[ln for ln, _ in lines_with_old_pattern]}"
        )

    def test_contains_docker_results_path(self) -> None:
        """PROJECT_MAP.md should reference the new docker/<image_dir>/results/<run_name>/ path."""
        assert "docker/" in self.content and "results/" in self.content, (
            "PROJECT_MAP.md should contain docker/*/results/ path references"
        )
