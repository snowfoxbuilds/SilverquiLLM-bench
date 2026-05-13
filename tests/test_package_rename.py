"""Tests for TODO item 1: Rename benchmark/ package to silverquillm/.

Verifies that:
- The new ``silverquillm`` package is importable.
- Key submodules are accessible under the new package name.
- The old ``benchmark`` top-level package no longer exists.
- No source files contain residual ``from benchmark.`` imports.
- pyproject.toml references ``silverquillm`` in package discovery and entry points.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Key submodules that must exist under the new package name.
_EXPECTED_SUBMODULES = [
    "silverquillm.evaluator",
    "silverquillm.card_loader",
    "silverquillm.card_spec",
]


class TestNewPackageImportable:
    """The silverquillm package and its submodules are importable."""

    def test_import_silverquillm_top_level(self) -> None:
        """``import silverquillm`` succeeds."""
        mod = importlib.import_module("silverquillm")
        assert hasattr(mod, "__all__")

    @pytest.mark.parametrize("module", _EXPECTED_SUBMODULES)
    def test_import_submodule(self, module: str) -> None:
        """Each key submodule is importable under ``silverquillm.*``."""
        mod = importlib.import_module(module)
        assert mod is not None


class TestOldPackageRemoved:
    """The old ``benchmark`` top-level package directory must not exist."""

    def test_benchmark_directory_absent(self) -> None:
        """The ``benchmark/`` directory no longer exists at the repo root."""
        old_dir = REPO_ROOT / "benchmark"
        assert not old_dir.exists(), (
            f"Old benchmark/ directory still exists at {old_dir}"
        )

    def test_no_benchmark_init_in_repo(self) -> None:
        """No ``benchmark/__init__.py`` exists at the repo root.

        This is a repo-scoped check: we verify the old package directory
        (specifically its ``__init__.py``) is gone, rather than relying on
        the global interpreter state which may have an unrelated
        ``benchmark`` package installed.
        """
        old_init = REPO_ROOT / "benchmark" / "__init__.py"
        assert not old_init.exists(), (
            f"Old benchmark/__init__.py still exists at {old_init}"
        )


class TestNoResidualImports:
    """No source or test file should contain ``from benchmark.`` imports."""

    def _python_files(self) -> list[Path]:
        """Collect all .py files under silverquillm/ and tests/."""
        dirs = [REPO_ROOT / "silverquillm", REPO_ROOT / "tests"]
        files: list[Path] = []
        for d in dirs:
            if d.exists():
                files.extend(d.rglob("*.py"))
        return files

    def test_no_from_benchmark_imports_in_source(self) -> None:
        """No .py file under silverquillm/ or tests/ should have ``from benchmark.`` imports."""
        violations: list[str] = []
        for py_file in self._python_files():
            try:
                tree = ast.parse(py_file.read_text(), filename=str(py_file))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("benchmark."):
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} -> from {node.module}"
                    )
        assert violations == [], (
            f"Residual 'from benchmark.*' imports found:\n" + "\n".join(violations)
        )


class TestPyprojectToml:
    """pyproject.toml must reference silverquillm correctly."""

    @pytest.fixture()
    def pyproject_text(self) -> str:
        return (REPO_ROOT / "pyproject.toml").read_text()

    def test_package_discovery_includes_silverquillm(self, pyproject_text: str) -> None:
        """Package find include list contains 'silverquillm*'."""
        assert "silverquillm*" in pyproject_text or '"silverquillm"' in pyproject_text

    def test_package_discovery_excludes_benchmark(self, pyproject_text: str) -> None:
        """Package find include list does NOT reference the old 'benchmark*' pattern."""
        # Should not have benchmark* in the include list (but 'benchmarks*' is fine — that's a different package)
        import tomllib
        data = tomllib.loads(pyproject_text)
        include = data.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {}).get("include", [])
        # "benchmark*" would match old package; "benchmarks*" is the benchmarks sets directory — acceptable
        bad = [item for item in include if item == "benchmark" or item == "benchmark*"]
        assert bad == [], f"pyproject.toml still references old package in include: {bad}"

    def test_cli_entry_point_uses_silverquillm(self, pyproject_text: str) -> None:
        """The ``[project.scripts]`` entry point references ``silverquillm.cli``."""
        import tomllib
        data = tomllib.loads(pyproject_text)
        scripts = data.get("project", {}).get("scripts", {})
        assert len(scripts) > 0, "No CLI entry points defined"
        # At least one script should point to silverquillm.cli
        targets = list(scripts.values())
        assert any("silverquillm.cli" in t for t in targets), (
            f"No entry point references silverquillm.cli; found: {targets}"
        )
