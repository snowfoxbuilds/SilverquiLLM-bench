"""Test that key engine symbols are importable from benchmarks.sos.workspace.engine.*."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestEngineImportSurface:
    """Each critical engine symbol must be importable from the new location."""

    def test_import_card_impl(self) -> None:
        from benchmarks.sos.workspace.engine.card import CardImpl

        assert CardImpl is not None

    def test_import_cast_spell(self) -> None:
        from benchmarks.sos.workspace.engine.casting import cast_spell

        assert cast_spell is not None

    def test_import_cast_spell_free(self) -> None:
        from benchmarks.sos.workspace.engine.casting import cast_spell_free

        assert cast_spell_free is not None

    def test_import_resolve_top(self) -> None:
        from benchmarks.sos.workspace.engine.casting import resolve_top

        assert resolve_top is not None


class TestEngineRelocation:
    """Verify the structural move was completed correctly."""

    def test_old_engine_directory_does_not_exist(self) -> None:
        """The top-level engine/ directory must no longer exist."""
        old_engine = REPO_ROOT / "engine"
        assert not old_engine.exists(), (
            f"Old engine/ directory still exists at {old_engine}"
        )

    def test_no_stale_engine_imports_outside_engine_package(self) -> None:
        """No .py file outside benchmarks/sos/workspace/engine/ should use bare engine imports.

        This catches both top-level and indented imports (e.g. inside functions/classes).
        """
        result = subprocess.run(
            [
                "grep",
                "-rln",
                "--include=*.py",
                "-P",
                r"(?:from\s+engine\b|import\s+engine\b)",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        # Filter out matches inside the engine package itself and false positives
        # from string literals in test assertion messages
        engine_pkg = str(REPO_ROOT / "benchmarks" / "sos" / "workspace" / "engine")
        tests_dir = str(REPO_ROOT / "tests")
        stale_files = []
        for f in result.stdout.strip().splitlines():
            if not f or f.startswith(engine_pkg):
                continue
            # For files in tests/, verify it's an actual import not a string literal
            if f.startswith(tests_dir):
                with open(f) as fh:
                    has_real_import = any(
                        (line.lstrip().startswith("from engine")
                         or line.lstrip().startswith("import engine"))
                        for line in fh
                    )
                if not has_real_import:
                    continue
            stale_files.append(f)
        assert stale_files == [], (
            f"Stale engine imports found outside engine package:\n"
            + "\n".join(stale_files)
        )

    def test_engine_package_contains_core_modules(self) -> None:
        """The relocated engine must contain all expected core modules."""
        engine_dir = REPO_ROOT / "benchmarks" / "sos" / "workspace" / "engine"
        expected_modules = [
            "__init__.py",
            "game.py",
            "card.py",
            "casting.py",
            "mana.py",
            "player.py",
            "combat.py",
            "events.py",
            "stack.py",
            "turn.py",
        ]
        for module in expected_modules:
            assert (engine_dir / module).is_file(), (
                f"Expected module {module} not found in {engine_dir}"
            )

    def test_engine_package_is_importable_as_package(self) -> None:
        """The engine directory must be a proper Python package."""
        import benchmarks.sos.workspace.engine  # noqa: F401
