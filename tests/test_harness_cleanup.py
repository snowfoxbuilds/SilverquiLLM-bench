"""Tests for TODO item 1: Delete remaining old harness code.

Verifies that dead-code modules from the adapter-based harness have been
removed, kept modules still exist, no dangling imports remain, and
``silverquillm/__init__.py`` is clean.
"""

from __future__ import annotations

import ast
import importlib
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules that should have been deleted
DELETED_MODULES = [
    "silverquillm/card_classifier.py",
    "silverquillm/prototype.py",
    "silverquillm/post_eval.py",
    "silverquillm/regression.py",
    "silverquillm/scorer.py",
    "silverquillm/template_gen.py",
]

# Corresponding test files that should also be deleted
DELETED_TEST_FILES = [
    "tests/test_card_classifier.py",
    "tests/test_prototype.py",
    "tests/test_post_eval.py",
    "tests/test_regression.py",
    "tests/test_regression_runner.py",
    "tests/test_scorer.py",
    "tests/test_template_gen.py",
    "tests/test_cat4_scoring.py",
]

# Bare module names for grep/import checks
DELETED_MODULE_NAMES = [
    "card_classifier",
    "prototype",
    "post_eval",
    "regression",
    "scorer",
    "template_gen",
]

# Files/dirs that must be kept
KEPT_PATHS = [
    "silverquillm/replay",
    "silverquillm/card_spec.py",
    "silverquillm/evaluator.py",
]


class TestDeletedSourceFiles:
    """Source modules from the old harness must not exist."""

    @pytest.mark.parametrize("rel_path", DELETED_MODULES)
    def test_source_file_deleted(self, rel_path: str) -> None:
        full = REPO_ROOT / rel_path
        assert not full.exists(), f"{rel_path} should have been deleted"


class TestDeletedTestFiles:
    """Test files for the old harness modules must not exist."""

    @pytest.mark.parametrize("rel_path", DELETED_TEST_FILES)
    def test_test_file_deleted(self, rel_path: str) -> None:
        full = REPO_ROOT / rel_path
        assert not full.exists(), f"{rel_path} should have been deleted"


class TestKeptFiles:
    """Files explicitly marked to keep must still exist."""

    @pytest.mark.parametrize("rel_path", KEPT_PATHS)
    def test_kept_path_exists(self, rel_path: str) -> None:
        full = REPO_ROOT / rel_path
        assert full.exists(), f"{rel_path} must be preserved"


class TestInitPyClean:
    """``silverquillm/__init__.py`` must not reference deleted modules."""

    def test_init_has_no_deleted_references(self) -> None:
        init_path = REPO_ROOT / "silverquillm" / "__init__.py"
        assert init_path.exists(), "__init__.py must exist"
        content = init_path.read_text()
        for name in DELETED_MODULE_NAMES:
            assert name not in content, (
                f"silverquillm/__init__.py still references '{name}'"
            )


class TestNoDanglingImports:
    """No remaining .py file in silverquillm/ or tests/ should import deleted modules."""

    @staticmethod
    def _collect_py_files(*dirs: str) -> list[Path]:
        files: list[Path] = []
        for d in dirs:
            root = REPO_ROOT / d
            if root.is_dir():
                for p in root.rglob("*.py"):
                    # Skip audited tests and this very test file
                    if "audited" in str(p):
                        continue
                    files.append(p)
        return files

    @pytest.mark.parametrize("module_name", DELETED_MODULE_NAMES)
    def test_no_import_of_deleted_module_in_source(self, module_name: str) -> None:
        """No .py file in silverquillm/ should import a deleted module."""
        fqn = f"silverquillm.{module_name}"
        py_files = self._collect_py_files("silverquillm")
        hits: list[str] = []
        for pf in py_files:
            try:
                tree = ast.parse(pf.read_text(), filename=str(pf))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == fqn or node.module.startswith(fqn + "."):
                        hits.append(str(pf.relative_to(REPO_ROOT)))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == fqn or alias.name.startswith(fqn + "."):
                            hits.append(str(pf.relative_to(REPO_ROOT)))
        assert not hits, (
            f"Source files still importing '{fqn}': {hits}"
        )

    @pytest.mark.parametrize("module_name", DELETED_MODULE_NAMES)
    def test_no_import_of_deleted_module_in_tests(self, module_name: str) -> None:
        """No remaining test or script file should import a deleted silverquillm module.

        Scans both scripts/ and the full tests/ directory (excluding this file
        and audited/) to verify no dangling imports of deleted modules remain.
        """
        fqn = f"silverquillm.{module_name}"
        py_files = self._collect_py_files("scripts", "tests")
        hits: list[str] = []
        for pf in py_files:
            # Exclude this very test file to avoid false positives from
            # module names used as test parametrization data.
            if pf.name == "test_harness_cleanup.py":
                continue
            try:
                tree = ast.parse(pf.read_text(), filename=str(pf))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == fqn or node.module.startswith(fqn + "."):
                        hits.append(str(pf.relative_to(REPO_ROOT)))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == fqn or alias.name.startswith(fqn + "."):
                            hits.append(str(pf.relative_to(REPO_ROOT)))
        assert not hits, (
            f"Files still importing '{fqn}': {hits}"
        )


class TestSilverquillmPackageImports:
    """The silverquillm package should import cleanly with no errors."""

    def test_import_silverquillm(self) -> None:
        mod = importlib.import_module("silverquillm")
        assert mod is not None

    def test_import_card_spec(self) -> None:
        mod = importlib.import_module("silverquillm.card_spec")
        assert mod is not None

    def test_import_evaluator(self) -> None:
        mod = importlib.import_module("silverquillm.evaluator")
        assert mod is not None

    @pytest.mark.parametrize("module_name", DELETED_MODULE_NAMES)
    def test_deleted_module_not_importable(self, module_name: str) -> None:
        # Check that the source file does not exist in this repo
        source_path = REPO_ROOT / "silverquillm" / f"{module_name}.py"
        assert not source_path.exists(), (
            f"silverquillm/{module_name}.py should be deleted but still exists"
        )
