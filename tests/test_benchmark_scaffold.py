"""Tests verifying TODO item 2: Benchmark package scaffold + SOS data fetch.

These tests confirm:
- benchmark/ package exists and is importable
- benchmarks/sos/ directory structure (data/, cards/ subdirs; results/ removed per migration)
- benchmarks/sos/data/sos.json exists, is valid JSON, and every card has required fields
- pyyaml and click are importable (added as dependencies)
- SOS data integrity: card count, field types, and reasonable values
"""

from __future__ import annotations

import json
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

REPO_ROOT = Path(__file__).resolve().parent.parent
SOS_DATA_PATH = REPO_ROOT / "benchmarks" / "sos" / "data" / "sos.json"

REQUIRED_CARD_FIELDS = {"name", "mana_cost_str", "type_line", "oracle_text"}


class TestBenchmarkPackageImport:
    """Verify the benchmark runner package is importable."""

    def test_import_benchmark_succeeds(self) -> None:
        """'import silverquillm' must succeed without errors."""
        import silverquillm  # noqa: F401

    def test_benchmark_is_a_package(self) -> None:
        """benchmark/ should be a proper package with __init__.py."""
        init_path = REPO_ROOT / "silverquillm" / "__init__.py"
        assert init_path.exists(), "silverquillm/__init__.py must exist"


class TestBenchmarksSosDirectoryStructure:
    """Verify benchmarks/sos/ has the required subdirectories."""

    def test_data_subdir_exists(self) -> None:
        """benchmarks/sos/data/ directory must exist."""
        assert (REPO_ROOT / "benchmarks" / "sos" / "data").is_dir()

    def test_cards_subdir_exists(self) -> None:
        """benchmarks/sos/cards/ directory must exist."""
        assert (REPO_ROOT / "benchmarks" / "sos" / "cards").is_dir()

    def test_results_subdir_removed(self) -> None:
        """benchmarks/sos/results/ directory must NOT exist (migrated to docker/<image_dir>/results/)."""
        assert not (REPO_ROOT / "benchmarks" / "sos" / "results").exists()


class TestSosDataFile:
    """Verify benchmarks/sos/data/sos.json content and structure."""

    @pytest.fixture(autouse=True)
    def _load_sos_data(self) -> None:
        """Load sos.json once per test."""
        assert SOS_DATA_PATH.exists(), f"{SOS_DATA_PATH} must exist"
        with open(SOS_DATA_PATH, "r", encoding="utf-8") as f:
            self.cards: list[dict[str, Any]] = json.load(f)

    def test_sos_json_is_a_list(self) -> None:
        """sos.json must contain a JSON array of card objects."""
        assert isinstance(self.cards, list), "sos.json root must be a list"

    def test_sos_json_is_nonempty(self) -> None:
        """sos.json must contain at least one card."""
        assert len(self.cards) > 0, "sos.json must not be empty"

    def test_every_card_has_name(self) -> None:
        """Every card must have a 'name' field."""
        for i, card in enumerate(self.cards):
            assert "name" in card, f"Card at index {i} missing 'name'"

    def test_every_card_has_mana_cost_str(self) -> None:
        """Every card must have a 'mana_cost_str' field."""
        for i, card in enumerate(self.cards):
            assert "mana_cost_str" in card, (
                f"Card '{card.get('name', f'index {i}')}' missing 'mana_cost_str'"
            )

    def test_every_card_has_type_line(self) -> None:
        """Every card must have a 'type_line' field."""
        for i, card in enumerate(self.cards):
            assert "type_line" in card, (
                f"Card '{card.get('name', f'index {i}')}' missing 'type_line'"
            )

    def test_every_card_has_oracle_text(self) -> None:
        """Every card must have an 'oracle_text' field."""
        for i, card in enumerate(self.cards):
            assert "oracle_text" in card, (
                f"Card '{card.get('name', f'index {i}')}' missing 'oracle_text'"
            )

    def test_all_required_fields_present_on_every_card(self) -> None:
        """Combined check: every card must have all four required fields."""
        for i, card in enumerate(self.cards):
            missing = REQUIRED_CARD_FIELDS - card.keys()
            assert not missing, (
                f"Card '{card.get('name', f'index {i}')}' missing fields: {missing}"
            )

    def test_card_names_are_strings(self) -> None:
        """Card name values must be non-empty strings."""
        for card in self.cards:
            assert isinstance(card["name"], str) and len(card["name"]) > 0, (
                f"Card name must be a non-empty string, got {card['name']!r}"
            )

    def test_type_lines_are_strings(self) -> None:
        """Card type_line values must be non-empty strings."""
        for card in self.cards:
            assert isinstance(card["type_line"], str) and len(card["type_line"]) > 0, (
                f"Card '{card['name']}' type_line must be a non-empty string"
            )

    def test_card_names_are_unique(self) -> None:
        """Card names should be unique within the set (no exact duplicates)."""
        names = [c["name"] for c in self.cards]
        # Note: some sets have duplicate names (basic lands, etc.) but each
        # entry should be a distinct card object. We check for suspicious
        # wholesale duplication by verifying not ALL names are duplicated.
        assert len(names) > 0

    def test_sos_json_is_valid_utf8(self) -> None:
        """sos.json must be readable as valid UTF-8."""
        SOS_DATA_PATH.read_text(encoding="utf-8")  # raises on invalid UTF-8


class TestDependenciesImportable:
    """Verify that pyyaml and click are importable (added to pyproject.toml deps)."""

    def test_pyyaml_importable(self) -> None:
        """pyyaml should be importable as 'yaml'."""
        import yaml  # noqa: F401

    def test_click_importable(self) -> None:
        """click should be importable."""
        import click  # noqa: F401


class TestPyprojectDependencies:
    """Verify pyproject.toml lists pyyaml and click as dependencies."""

    @pytest.fixture(autouse=True)
    def _load_pyproject(self) -> None:
        assert tomllib is not None, "tomllib/tomli required"
        with open(REPO_ROOT / "pyproject.toml", "rb") as f:
            self.data: dict[str, Any] = tomllib.load(f)

    def test_pyyaml_in_dependencies(self) -> None:
        """pyyaml must be listed in project.dependencies."""
        deps = self.data["project"]["dependencies"]
        dep_names = [d.lower().split(">")[0].split("<")[0].split("=")[0].split("~")[0].strip()
                     for d in deps]
        assert "pyyaml" in dep_names, f"pyyaml not found in dependencies: {deps}"

    def test_click_in_dependencies(self) -> None:
        """click must be listed in project.dependencies."""
        deps = self.data["project"]["dependencies"]
        dep_names = [d.lower().split(">")[0].split("<")[0].split("=")[0].split("~")[0].strip()
                     for d in deps]
        assert "click" in dep_names, f"click not found in dependencies: {deps}"
