"""Test that key engine symbols are importable from engine.*."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestEngineImportSurface:
    """Each critical engine symbol must be importable from the new location."""

    def test_import_card_impl(self) -> None:
        from engine.card import CardImpl

        assert CardImpl is not None

    def test_import_cast_spell(self) -> None:
        from engine.casting import cast_spell

        assert cast_spell is not None

    def test_import_cast_spell_free(self) -> None:
        from engine.casting import cast_spell_free

        assert cast_spell_free is not None

    def test_import_resolve_top(self) -> None:
        from engine.casting import resolve_top

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
        """No .py file should use the legacy ``benchmarks.sos.workspace.engine`` prefix.

        Flat ``from engine.X import …`` is canonical after Option A. This guards
        against regressions to the long-form prefix.
        """
        result = subprocess.run(
            [
                "grep",
                "-rln",
                "--include=*.py",
                "-P",
                r"benchmarks\.sos\.workspace\.engine",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        # Historical benchmark run artifacts under docker/ and third-party
        # packages under venv/ are exempt. The self-referential mention in
        # this test file is also expected.
        docker_dir = str(REPO_ROOT / "docker")
        venv_dir = str(REPO_ROOT / "venv")
        # Guardrail tests that intentionally mention the legacy prefix in
        # assertion regexes are exempt.
        exempt = {
            str(Path(__file__).resolve()),
            str(REPO_ROOT / "tests" / "test_cards_relocation.py"),
            str(REPO_ROOT / "tests" / "test_audited_tests_relocation.py"),
        }
        stale_files = [
            f
            for f in result.stdout.strip().splitlines()
            if f and not f.startswith(docker_dir)
            and not f.startswith(venv_dir)
            and f not in exempt
        ]
        assert stale_files == [], (
            f"Legacy benchmarks.sos.workspace.engine references found:\n"
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
        import engine  # noqa: F401
