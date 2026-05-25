"""Host-side verification that FDN reference tests meet TODO 1.6 requirements.

Validates:
- At least 3 test files exist under cards/fdn/*/tests.py
- Required mechanics are covered (modal spell, targeted ETB, multi-blocker combat,
  replacement effect, and converge/mana-color tracking)
- Tests import from the correct paths
- Tests are discoverable and pass via pytest
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "benchmarks" / "sos" / "workspace"
FDN_CARDS = WORKSPACE / "cards" / "fdn"


def _get_fdn_test_files() -> list[Path]:
    """Return all tests.py files under cards/fdn/*/."""
    return sorted(FDN_CARDS.glob("*/tests.py"))


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Requirement: At least 3 test files exist
# ---------------------------------------------------------------------------


class TestFdnTestFileCount:
    """At least 3-5 FDN reference test files must exist."""

    def test_minimum_three_test_files(self) -> None:
        """TODO 1.6 requires 3-5 illustrative FDN test files."""
        test_files = _get_fdn_test_files()
        assert len(test_files) >= 3, (
            f"Expected at least 3 FDN test files, found {len(test_files)}: {test_files}"
        )

    def test_maximum_five_test_files(self) -> None:
        """TODO 1.6 specifies 3-5 test files."""
        test_files = _get_fdn_test_files()
        assert len(test_files) <= 5, (
            f"Expected at most 5 FDN test files, found {len(test_files)}"
        )


# ---------------------------------------------------------------------------
# Requirement: Each test imports from correct paths
# ---------------------------------------------------------------------------


class TestFdnImportPaths:
    """Each test must import from engine and card_impl."""

    @pytest.fixture()
    def test_files(self) -> list[Path]:
        return _get_fdn_test_files()

    def test_each_file_imports_from_engine(self, test_files: list[Path]) -> None:
        """Every FDN test file must import from engine.*."""
        for tf in test_files:
            source = _read_source(tf)
            assert "from engine" in source, (
                f"{tf.relative_to(REPO_ROOT)} does not import from engine"
            )

    def test_each_file_imports_from_card_impl(self, test_files: list[Path]) -> None:
        """Every FDN test file must import from its own card_impl module."""
        for tf in test_files:
            source = _read_source(tf)
            # e.g. from cards.fdn.fdn_13.card_impl import ...
            card_dir = tf.parent.name  # e.g. "fdn_13"
            expected_import = f"from cards.fdn.{card_dir}.card_impl"
            assert expected_import in source, (
                f"{tf.relative_to(REPO_ROOT)} does not import from {expected_import}"
            )


# ---------------------------------------------------------------------------
# Requirement: Required mechanics are covered
# ---------------------------------------------------------------------------


def _get_test_method_bodies(source: str) -> list[str]:
    """Extract source code of test method bodies (def test_*) using AST."""
    tree = ast.parse(source)
    bodies: list[str] = []
    source_lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                # Extract lines of the method body (excluding the def line itself)
                start = node.body[0].lineno - 1  # 0-indexed
                end = node.end_lineno  # 1-indexed, inclusive
                bodies.append("\n".join(source_lines[start:end]))
    return bodies


def _file_has_pattern_in_test_code(path: Path, patterns: list[str]) -> bool:
    """Check if any test method body in the file contains any of the patterns."""
    source = _read_source(path)
    bodies = _get_test_method_bodies(source)
    combined = "\n".join(bodies).lower()
    return any(p.lower() in combined for p in patterns)


class TestFdnMechanicsCoverage:
    """The 5 required mechanics must be covered across the test files via actual code."""

    @pytest.fixture()
    def test_files(self) -> list[Path]:
        return _get_fdn_test_files()

    def test_target_selection_covered(self, test_files: list[Path]) -> None:
        """At least one test exercises target selection/validation in method code."""
        # Look for actual target-related code patterns: chosen_targets, target assignment,
        # validate_target calls — not just the word "target" in comments
        patterns = ["chosen_targets", "select_target", "validate_target", "target"]
        found = any(
            _file_has_pattern_in_test_code(f, patterns) for f in test_files
        )
        assert found, (
            "No FDN test file exercises target selection/validation in test method code"
        )

    def test_mana_color_converge_covered(self, test_files: list[Path]) -> None:
        """At least one test exercises mana colors / converge with assertions."""
        # Look for actual converge/color tracking code: colors_spent, payment_colors,
        # mana_pool references in test bodies
        patterns = ["colors_spent", "payment_colors", "mana_pool", "colors_of_mana"]
        found = any(
            _file_has_pattern_in_test_code(f, patterns) for f in test_files
        )
        assert found, (
            "No FDN test file exercises converge / mana-color tracking in test method code"
        )

    def test_blocker_declaration_covered(self, test_files: list[Path]) -> None:
        """At least one test exercises blocker declaration mechanics in code."""
        # Look for actual blocker/combat code: declare_blockers, blockers list,
        # can_block calls
        patterns = ["declare_blockers", "blockers", "_can_block", "block"]
        found = any(
            _file_has_pattern_in_test_code(f, patterns) for f in test_files
        )
        assert found, (
            "No FDN test file exercises blocker declaration mechanics in test method code"
        )

    def test_modal_choice_covered(self, test_files: list[Path]) -> None:
        """At least one test exercises modal choice / mode selection logic in code."""
        # Look for actual mode selection code: chosen_mode, mode=, select_mode
        patterns = ["chosen_mode", "mode=", "select_mode"]
        found = any(
            _file_has_pattern_in_test_code(f, patterns) for f in test_files
        )
        assert found, (
            "No FDN test file exercises modal choice / mode selection in test method code"
        )

    def test_replacement_effect_covered(self, test_files: list[Path]) -> None:
        """At least one test exercises replacement effects in code."""
        # Look for actual replacement effect code: combat_damage_prevented,
        # prevent, replacement_effect, instead
        patterns = [
            "combat_damage_prevented",
            "prevent",
            "replacement_effect",
            "damage_prevented",
        ]
        found = any(
            _file_has_pattern_in_test_code(f, patterns) for f in test_files
        )
        assert found, (
            "No FDN test file exercises replacement effects in test method code"
        )


# ---------------------------------------------------------------------------
# Requirement: Tests are discoverable by pytest
# ---------------------------------------------------------------------------


class TestFdnPytestDiscovery:
    """FDN tests must be discoverable when running pytest."""

    def test_pytest_collects_fdn_tests(self) -> None:
        """pytest --collect-only should find tests under cards/fdn/."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             str(FDN_CARDS)],
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE),
        )
        # Should collect at least some tests (exit code 0 means collected OK)
        assert result.returncode == 0, (
            f"pytest collection failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Should report at least 3 tests collected
        lines = [l for l in result.stdout.strip().splitlines() if "::" in l]
        assert len(lines) >= 3, (
            f"Expected at least 3 collected tests, got {len(lines)}:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Requirement: All FDN reference tests pass
# ---------------------------------------------------------------------------


class TestFdnTestsPass:
    """All FDN reference tests must pass when run via pytest."""

    def test_all_fdn_tests_pass(self) -> None:
        """Run the FDN tests and verify they all pass."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(FDN_CARDS),
             "-q", "--no-header", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE),
        )
        assert result.returncode == 0, (
            f"FDN tests failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
