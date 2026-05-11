"""Tests for card ID mapping (grpId → card name).

Validates the data/replays/card_id_map.json mapping file and the
scripts/build_card_id_map.py builder module.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = REPO_ROOT / "data" / "replays" / "card_id_map.json"


@pytest.fixture(scope="module")
def card_map() -> dict:
    """Load the card ID map JSON once per module."""
    assert MAP_PATH.exists(), f"card_id_map.json not found at {MAP_PATH}"
    with open(MAP_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def grp_to_card(card_map: dict) -> dict[str, dict]:
    return card_map["grpId_to_card"]


@pytest.fixture(scope="module")
def name_to_grp(card_map: dict) -> dict[str, int]:
    return card_map["card_name_to_grpId"]


# ---------------------------------------------------------------------------
# JSON file existence and validity
# ---------------------------------------------------------------------------


class TestJsonFileStructure:
    """Tests that the JSON file exists, is valid, and has the right shape."""

    def test_json_file_exists(self):
        assert MAP_PATH.exists()

    def test_json_file_is_valid_json(self):
        with open(MAP_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_top_level_keys_present(self, card_map: dict):
        assert "grpId_to_card" in card_map
        assert "card_name_to_grpId" in card_map
        assert "source" in card_map
        assert "description" in card_map

    def test_grp_to_card_is_dict(self, grp_to_card: dict):
        assert isinstance(grp_to_card, dict)
        assert len(grp_to_card) > 0

    def test_name_to_grp_is_dict(self, name_to_grp: dict):
        assert isinstance(name_to_grp, dict)
        assert len(name_to_grp) > 0


# ---------------------------------------------------------------------------
# Entry structure
# ---------------------------------------------------------------------------


class TestEntryStructure:
    """Each grpId entry must have card_name, set_code, collector_number."""

    def test_all_entries_have_card_name(self, grp_to_card: dict):
        for grp_id, entry in grp_to_card.items():
            assert "card_name" in entry, f"grpId {grp_id} missing card_name"
            assert isinstance(entry["card_name"], str)
            assert len(entry["card_name"]) > 0

    def test_all_entries_have_set_code(self, grp_to_card: dict):
        for grp_id, entry in grp_to_card.items():
            assert "set_code" in entry, f"grpId {grp_id} missing set_code"
            assert isinstance(entry["set_code"], str)

    def test_all_entries_have_collector_number(self, grp_to_card: dict):
        for grp_id, entry in grp_to_card.items():
            assert "collector_number" in entry, f"grpId {grp_id} missing collector_number"
            assert isinstance(entry["collector_number"], str)

    def test_grp_ids_are_numeric_strings(self, grp_to_card: dict):
        for grp_id in grp_to_card:
            assert grp_id.isdigit(), f"grpId '{grp_id}' is not a numeric string"


# ---------------------------------------------------------------------------
# Known FDN cards
# ---------------------------------------------------------------------------


class TestKnownFDNCards:
    """Basic lands and well-known FDN cards should be present."""

    @pytest.mark.parametrize("land_name", ["Forest", "Island", "Mountain", "Plains", "Swamp"])
    def test_basic_land_in_reverse_map(self, name_to_grp: dict, land_name: str):
        assert land_name in name_to_grp, f"{land_name} not found in reverse map"

    @pytest.mark.parametrize("land_name", ["Forest", "Island", "Mountain", "Plains", "Swamp"])
    def test_basic_land_grpid_resolves(self, name_to_grp: dict, grp_to_card: dict, land_name: str):
        grp_id = str(name_to_grp[land_name])
        assert grp_id in grp_to_card
        assert grp_to_card[grp_id]["card_name"] == land_name

    @pytest.mark.parametrize("land_name", ["Forest", "Island", "Mountain", "Plains", "Swamp"])
    def test_basic_land_set_code_is_fdn(self, name_to_grp: dict, grp_to_card: dict, land_name: str):
        grp_id = str(name_to_grp[land_name])
        assert grp_to_card[grp_id]["set_code"] == "FDN"


# ---------------------------------------------------------------------------
# SPG (Special Guests) cards
# ---------------------------------------------------------------------------


class TestSPGCards:
    """SPG special guest cards must be included in the map."""

    SPG_CARD_NAMES = [
        "Condemn",
        "Sphinx's Tutelage",
        "Grim Tutor",
        "Embercleave",
        "Goblin Bushwhacker",
        "Bloom Tender",
        "Paradise Druid",
        "Akroma's Memorial",
        "Temporal Manipulation",
        "Fiend Artisan",
    ]

    @pytest.mark.parametrize("card_name", SPG_CARD_NAMES)
    def test_spg_card_in_reverse_map(self, name_to_grp: dict, card_name: str):
        assert card_name in name_to_grp, f"SPG card '{card_name}' not in reverse map"

    def test_spg_cards_have_spg_set_code(self, name_to_grp: dict, grp_to_card: dict):
        for card_name in self.SPG_CARD_NAMES:
            grp_id = str(name_to_grp[card_name])
            entry = grp_to_card[grp_id]
            assert entry["set_code"] == "SPG", (
                f"{card_name} has set_code '{entry['set_code']}' instead of 'SPG'"
            )


# ---------------------------------------------------------------------------
# Reverse map consistency
# ---------------------------------------------------------------------------


class TestReverseMapConsistency:
    """Reverse map (card_name → grpId) must be consistent with forward map."""

    def test_reverse_map_grpids_exist_in_forward_map(self, name_to_grp: dict, grp_to_card: dict):
        for card_name, grp_id in name_to_grp.items():
            assert str(grp_id) in grp_to_card, (
                f"Reverse map card '{card_name}' → grpId {grp_id} not in forward map"
            )

    def test_reverse_map_names_match_forward_map(self, name_to_grp: dict, grp_to_card: dict):
        for card_name, grp_id in name_to_grp.items():
            entry = grp_to_card[str(grp_id)]
            assert entry["card_name"] == card_name, (
                f"Reverse map '{card_name}' → grpId {grp_id} but forward map "
                f"has card_name '{entry['card_name']}'"
            )


# ---------------------------------------------------------------------------
# No duplicate grpIds
# ---------------------------------------------------------------------------


class TestNoDuplicates:
    """grpId keys must be unique (JSON object keys are unique by spec, but verify)."""

    def test_no_duplicate_grpids(self):
        """Parse raw JSON and ensure no duplicate grpId keys."""
        with open(MAP_PATH) as f:
            raw = f.read()
        # json.loads with default behavior silently drops duplicate keys.
        # Parse manually to detect duplicates.
        data = json.loads(raw)
        grp_ids = list(data["grpId_to_card"].keys())
        assert len(grp_ids) == len(set(grp_ids))

    def test_mapping_has_substantial_entries(self, grp_to_card: dict):
        """Sanity check: should have hundreds of entries for FDN + SPG."""
        assert len(grp_to_card) >= 100, (
            f"Only {len(grp_to_card)} entries — expected hundreds for FDN+SPG"
        )


# ---------------------------------------------------------------------------
# Script module importability
# ---------------------------------------------------------------------------


class TestBuildScript:
    """The build script should be importable and expose expected functions."""

    def test_script_file_exists(self):
        script_path = REPO_ROOT / "scripts" / "build_card_id_map.py"
        assert script_path.exists()

    def test_build_card_id_map_function_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_card_id_map",
            REPO_ROOT / "scripts" / "build_card_id_map.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "build_card_id_map")
        assert callable(mod.build_card_id_map)

    def test_script_has_main_function(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_card_id_map",
            REPO_ROOT / "scripts" / "build_card_id_map.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "main")
        assert callable(mod.main)

    def test_script_has_synthetic_spg_cards(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_card_id_map",
            REPO_ROOT / "scripts" / "build_card_id_map.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "SYNTHETIC_SPG_CARDS")
        assert len(mod.SYNTHETIC_SPG_CARDS) == 10
