"""Tests verifying TODO item 7: cards/foundations/ deleted, FDN compat shims removed.

These tests confirm:
- cards/foundations/ directory no longer exists
- No Python files reference ``cards.foundations`` (import or otherwise)
- cards/__init__.py does not re-export from foundations
- FDN card imports via cards.fdn._legacy still work (spot-checks)
- PROJECT_MAP.md no longer lists cards/foundations/ as active
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestFoundationsDirectoryRemoved:
    """Verify the old cards/foundations/ directory is completely gone."""

    def test_cards_foundations_dir_does_not_exist(self) -> None:
        """cards/foundations/ must not exist at all."""
        foundations = REPO_ROOT / "cards" / "foundations"
        assert not foundations.exists(), (
            f"cards/foundations/ still exists at {foundations}"
        )

    def test_cards_foundations_not_a_symlink(self) -> None:
        """cards/foundations/ must not be a dangling symlink either."""
        foundations = REPO_ROOT / "cards" / "foundations"
        assert not foundations.is_symlink(), (
            "cards/foundations/ exists as a symlink — should be fully removed"
        )


class TestNoFoundationsReferences:
    """Verify no Python source files reference cards.foundations."""

    def test_grep_cards_foundations_zero_hits_in_python(self) -> None:
        """grep -rn 'cards.foundations' should find zero hits in .py files.

        Excludes test files that document the migration (e.g. this file
        and test_fdn_card_migration.py which mention 'cards.foundations'
        in docstrings/comments about the removal).
        """
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "--include=*.py",
                "cards\\.foundations",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        # Filter out hits that are only in comments/docstrings about the migration
        real_hits = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            # Allow references in test files that document the removal itself
            if "test_fdn_foundations_removal.py" in line:
                continue
            if "test_fdn_card_migration.py" in line:
                continue
            real_hits.append(line)

        assert len(real_hits) == 0, (
            f"Found {len(real_hits)} references to 'cards.foundations' in Python files:\n"
            + "\n".join(real_hits)
        )

    def test_cards_init_no_foundations_reexport(self) -> None:
        """cards/__init__.py must not import or re-export from foundations."""
        init_path = REPO_ROOT / "cards" / "__init__.py"
        if not init_path.exists():
            # Empty or missing __init__.py is fine — no re-export possible
            return
        content = init_path.read_text()
        assert "foundations" not in content, (
            "cards/__init__.py still references 'foundations'"
        )


class TestFdnLegacyImportsWork:
    """Spot-check that FDN card imports via cards.fdn._legacy still work."""

    @pytest.mark.parametrize(
        "module_name",
        [
            "cards.fdn._legacy.simple_creatures",
            "cards.fdn._legacy.simple_spells",
            "cards.fdn._legacy.basic_lands",
            "cards.fdn._legacy.artifacts",
            "cards.fdn._legacy.enchantments",
            "cards.fdn._legacy.equipment",
        ],
        ids=[
            "simple_creatures",
            "simple_spells",
            "basic_lands",
            "artifacts",
            "enchantments",
            "equipment",
        ],
    )
    def test_legacy_module_importable(self, module_name: str) -> None:
        """Each legacy FDN module must be importable from its new path."""
        mod = importlib.import_module(module_name)
        assert mod is not None

    def test_cards_fdn_package_importable(self) -> None:
        """cards.fdn must be importable as a package."""
        mod = importlib.import_module("cards.fdn")
        assert mod is not None

    def test_cards_fdn_legacy_package_importable(self) -> None:
        """cards.fdn._legacy must be importable as a package."""
        mod = importlib.import_module("cards.fdn._legacy")
        assert mod is not None


class TestProjectMapUpdated:
    """Verify PROJECT_MAP.md reflects the migration."""

    @pytest.fixture(autouse=True)
    def _load_project_map(self) -> None:
        self.project_map_path = REPO_ROOT / "PROJECT_MAP.md"
        assert self.project_map_path.exists(), "PROJECT_MAP.md must exist"
        self.content = self.project_map_path.read_text()

    def test_no_active_foundations_directory_listing(self) -> None:
        """PROJECT_MAP.md should not list cards/foundations/ as an active directory."""
        # It may mention foundations in historical/migration context, but should
        # not have a table row showing it as a live active directory.
        lines = self.content.splitlines()
        for line in lines:
            if "cards/foundations/" in line and "| Active" in line:
                pytest.fail(
                    f"PROJECT_MAP.md still lists cards/foundations/ as Active:\n{line}"
                )

    def test_references_fdn_legacy_as_replacement(self) -> None:
        """PROJECT_MAP.md should reference cards/fdn/_legacy/ as the replacement."""
        assert "cards/fdn/_legacy/" in self.content, (
            "PROJECT_MAP.md does not mention cards/fdn/_legacy/ — "
            "should document the migration target"
        )
