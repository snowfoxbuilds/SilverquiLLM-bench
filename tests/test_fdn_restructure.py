"""Tests for TODO item 2: FDN cards restructured to per-collector-number layout.

Verifies:
- cards/fdn/ directory exists with per-card subdirectories
- Each subdirectory has card_spec.json + card_impl.py
- SPG cards use spg_ prefix
- card_spec.json files are valid JSON with required fields
- card_impl.py files are importable with CardImpl subclass
- Old monolithic files under cards/foundations/ are deleted
- Migration script exists
- Collector number collisions use 'b' suffix
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

# Root of the repo
ROOT = Path(__file__).resolve().parent.parent
CARDS_FDN = ROOT / "cards" / "fdn"
CARDS_FOUNDATIONS = ROOT / "cards" / "foundations"
SCRIPTS = ROOT / "scripts"

# Monolithic files that should be deleted after restructuring
OLD_MONOLITHIC_FILES = [
    "activated_creatures.py",
    "etb_creatures.py",
    "death_trigger_creatures.py",
    "simple_creatures.py",
    "vanilla_creatures_batch2.py",
    "enchantments.py",
    "global_enchantments.py",
    "auras_batch2.py",
    "equipment.py",
    "artifacts.py",
    "artifacts_batch2.py",
    "simple_spells.py",
    "simple_spells_batch2.py",
    "simple_spells_batch3.py",
    "complex_spells.py",
    "modal_spells.py",
    "planeswalkers.py",
    "planeswalkers_batch2.py",
    "simple_permanents.py",
    "basic_lands.py",
    "lands.py",
    "special_guests.py",
]

# A sample of known collector numbers to spot-check
SAMPLE_COLLECTOR_NUMBERS = ["12", "42", "98", "144", "200", "252"]

# SPG collector numbers (74-83)
SPG_COLLECTOR_NUMBERS = [str(n) for n in range(74, 84)]

# Known collision-suffixed directories from the impl plan
COLLISION_DIRS = ["105b", "129b", "219b", "228b", "61b", "7b"]


class TestFdnDirectoryStructure:
    """Verify the cards/fdn/ directory exists with per-card subdirectories."""

    def test_fdn_directory_exists(self) -> None:
        """cards/fdn/ directory must exist."""
        assert CARDS_FDN.is_dir(), f"Expected {CARDS_FDN} to be a directory"

    def test_fdn_has_subdirectories(self) -> None:
        """cards/fdn/ must contain multiple card subdirectories."""
        subdirs = [p for p in CARDS_FDN.iterdir() if p.is_dir() and p.name != "__pycache__"]
        assert len(subdirs) >= 50, (
            f"Expected at least 50 card subdirectories in cards/fdn/, found {len(subdirs)}"
        )

    @pytest.mark.parametrize("collector_number", SAMPLE_COLLECTOR_NUMBERS)
    def test_card_subdirectory_has_both_files(self, collector_number: str) -> None:
        """Each card subdirectory must contain card_spec.json and card_impl.py."""
        card_dir = CARDS_FDN / collector_number
        assert card_dir.is_dir(), f"Expected directory {card_dir}"
        assert (card_dir / "card_spec.json").is_file(), f"Missing card_spec.json in {card_dir}"
        assert (card_dir / "card_impl.py").is_file(), f"Missing card_impl.py in {card_dir}"


class TestSpgPrefix:
    """SPG (Special Guest) cards must live under spg_ prefixed directories."""

    @pytest.mark.parametrize("collector_number", SPG_COLLECTOR_NUMBERS)
    def test_spg_card_directory_exists(self, collector_number: str) -> None:
        """SPG cards use cards/fdn/spg_{collector_number}/ layout."""
        spg_dir = CARDS_FDN / f"spg_{collector_number}"
        assert spg_dir.is_dir(), f"Expected SPG directory {spg_dir}"

    @pytest.mark.parametrize("collector_number", SPG_COLLECTOR_NUMBERS)
    def test_spg_card_has_both_files(self, collector_number: str) -> None:
        """Each SPG subdirectory must have card_spec.json and card_impl.py."""
        spg_dir = CARDS_FDN / f"spg_{collector_number}"
        assert (spg_dir / "card_spec.json").is_file(), f"Missing card_spec.json in {spg_dir}"
        assert (spg_dir / "card_impl.py").is_file(), f"Missing card_impl.py in {spg_dir}"


class TestCardSpecJsonValidity:
    """Spot-check card_spec.json files for valid JSON with required fields."""

    REQUIRED_FIELDS = {"name", "mana_cost", "type_line", "oracle_text", "collector_number"}

    @pytest.mark.parametrize("collector_number", ["12", "42", "200", "spg_74", "spg_80"])
    def test_card_spec_is_valid_json_with_required_fields(self, collector_number: str) -> None:
        """card_spec.json must be parseable JSON containing required fields."""
        spec_path = CARDS_FDN / collector_number / "card_spec.json"
        assert spec_path.is_file(), f"Missing {spec_path}"
        with open(spec_path) as f:
            data = json.load(f)
        missing = self.REQUIRED_FIELDS - set(data.keys())
        assert not missing, f"card_spec.json in {collector_number}/ missing fields: {missing}"

    @pytest.mark.parametrize("collector_number", ["12", "98", "252"])
    def test_card_spec_name_is_nonempty_string(self, collector_number: str) -> None:
        """The 'name' field must be a non-empty string."""
        spec_path = CARDS_FDN / collector_number / "card_spec.json"
        with open(spec_path) as f:
            data = json.load(f)
        assert isinstance(data["name"], str) and len(data["name"]) > 0

    @pytest.mark.parametrize("collector_number", ["12", "42", "98", "144", "200", "252"])
    def test_card_spec_collector_number_is_nonempty_string(self, collector_number: str) -> None:
        """The 'collector_number' field must be a non-empty string."""
        spec_path = CARDS_FDN / collector_number / "card_spec.json"
        with open(spec_path) as f:
            data = json.load(f)
        cn = data["collector_number"]
        assert isinstance(cn, str) and len(cn) > 0, (
            f"collector_number must be a non-empty string, got {cn!r}"
        )

    @pytest.mark.parametrize("collector_number", ["12", "42", "98", "144", "200", "252"])
    def test_directory_name_matches_collector_number(self, collector_number: str) -> None:
        """The directory name must match the collector_number declared in card_spec.json."""
        spec_path = CARDS_FDN / collector_number / "card_spec.json"
        with open(spec_path) as f:
            data = json.load(f)
        assert data["collector_number"] == collector_number, (
            f"Directory '{collector_number}' does not match collector_number "
            f"'{data['collector_number']}' in card_spec.json"
        )

    @pytest.mark.parametrize("collector_number", SPG_COLLECTOR_NUMBERS)
    def test_spg_directory_matches_collector_number(self, collector_number: str) -> None:
        """SPG directory numeric part must match the collector_number in card_spec.json."""
        dir_name = f"spg_{collector_number}"
        spec_path = CARDS_FDN / dir_name / "card_spec.json"
        if not spec_path.is_file():
            pytest.skip(f"{spec_path} not yet created")
        with open(spec_path) as f:
            data = json.load(f)
        assert data["collector_number"] == collector_number, (
            f"SPG directory '{dir_name}' numeric part does not match "
            f"collector_number '{data['collector_number']}' in card_spec.json"
        )

    @pytest.mark.parametrize("collector_number", ["12", "42", "98", "200"])
    def test_non_land_card_has_nonempty_mana_cost(self, collector_number: str) -> None:
        """Non-land cards must have a non-empty mana_cost value."""
        spec_path = CARDS_FDN / collector_number / "card_spec.json"
        with open(spec_path) as f:
            data = json.load(f)
        # These are known non-land cards; mana_cost must be populated
        assert isinstance(data["mana_cost"], str) and len(data["mana_cost"]) > 0, (
            f"Non-land card {collector_number} ({data.get('name')}) has empty mana_cost"
        )

    @pytest.mark.parametrize("collector_number", ["262", "263", "264"])
    def test_land_card_has_empty_mana_cost(self, collector_number: str) -> None:
        """Land cards should have empty mana_cost (sanity check for test correctness)."""
        spec_path = CARDS_FDN / collector_number / "card_spec.json"
        if not spec_path.is_file():
            pytest.skip(f"{spec_path} not yet created")
        with open(spec_path) as f:
            data = json.load(f)
        assert data["mana_cost"] == "", (
            f"Land card {collector_number} ({data.get('name')}) should have empty mana_cost"
        )


class TestCardImplValidity:
    """Spot-check card_impl.py files are importable and contain CardImpl subclass."""

    @pytest.mark.parametrize("collector_number", ["12", "42", "98", "spg_74"])
    def test_card_impl_is_importable(self, collector_number: str) -> None:
        """card_impl.py must be importable as a Python module."""
        module_path = f"cards.fdn.{collector_number}.card_impl"
        try:
            mod = importlib.import_module(module_path)
        except ImportError as e:
            pytest.fail(f"Failed to import {module_path}: {e}")
        # Module should have at least one class
        classes = [
            v for k, v in vars(mod).items()
            if isinstance(v, type) and not k.startswith("_")
        ]
        assert len(classes) >= 1, f"No classes found in {module_path}"

    @pytest.mark.parametrize("collector_number", ["12", "42", "98"])
    def test_card_impl_has_cardimpl_subclass(self, collector_number: str) -> None:
        """card_impl.py must contain at least one class that is a subclass of CardImpl."""
        from engine.card import CardImpl

        module_path = f"cards.fdn.{collector_number}.card_impl"
        mod = importlib.import_module(module_path)
        subclasses = [
            v for k, v in vars(mod).items()
            if isinstance(v, type) and issubclass(v, CardImpl) and v is not CardImpl
        ]
        assert len(subclasses) >= 1, (
            f"No CardImpl subclass found in {module_path}"
        )


class TestOldMonolithicFilesDeleted:
    """Old monolithic files under cards/foundations/ must be removed."""

    @pytest.mark.parametrize("filename", OLD_MONOLITHIC_FILES)
    def test_old_monolithic_file_deleted(self, filename: str) -> None:
        """Monolithic batch files should no longer exist in cards/foundations/."""
        old_path = CARDS_FOUNDATIONS / filename
        assert not old_path.exists(), (
            f"Old monolithic file still exists: {old_path}"
        )


class TestMigrationScriptExists:
    """Migration script must exist at the expected path."""

    def test_migration_script_exists(self) -> None:
        """scripts/restructure_fdn_cards.py must exist."""
        script_path = SCRIPTS / "restructure_fdn_cards.py"
        assert script_path.is_file(), f"Missing migration script: {script_path}"

    def test_migration_script_is_python(self) -> None:
        """Migration script must be valid Python (parseable)."""
        script_path = SCRIPTS / "restructure_fdn_cards.py"
        source = script_path.read_text()
        try:
            compile(source, str(script_path), "exec")
        except SyntaxError as e:
            pytest.fail(f"Migration script has syntax error: {e}")


class TestCollisionHandling:
    """Collector number collisions must use 'b' suffix directories."""

    @pytest.mark.parametrize("suffixed_dir", COLLISION_DIRS)
    def test_collision_directory_exists(self, suffixed_dir: str) -> None:
        """Collision-suffixed directories (e.g., 105b) must exist."""
        collision_path = CARDS_FDN / suffixed_dir
        assert collision_path.is_dir(), (
            f"Expected collision directory {collision_path} to exist"
        )

    @pytest.mark.parametrize("suffixed_dir", COLLISION_DIRS)
    def test_collision_directory_has_both_files(self, suffixed_dir: str) -> None:
        """Collision directories must have card_spec.json and card_impl.py."""
        collision_path = CARDS_FDN / suffixed_dir
        assert (collision_path / "card_spec.json").is_file()
        assert (collision_path / "card_impl.py").is_file()

    def test_at_least_one_collision_suffix_exists(self) -> None:
        """At least some directories with 'b' suffix should exist in cards/fdn/."""
        if not CARDS_FDN.is_dir():
            pytest.skip("cards/fdn/ not yet created")
        b_dirs = [
            p for p in CARDS_FDN.iterdir()
            if p.is_dir() and p.name.endswith("b")
        ]
        assert len(b_dirs) >= 1, "Expected at least one collision-suffixed directory"


class TestRegistryImports:
    """Registry should still work after restructuring."""

    def test_registry_module_importable(self) -> None:
        """cards.registry must still be importable."""
        try:
            importlib.import_module("cards.registry")
        except ImportError as e:
            pytest.fail(f"Failed to import cards.registry: {e}")

    def test_registry_has_card_registry_class(self) -> None:
        """CardRegistry class must exist in cards.registry."""
        mod = importlib.import_module("cards.registry")
        assert hasattr(mod, "CardRegistry"), "CardRegistry class not found in cards.registry"
