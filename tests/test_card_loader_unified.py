"""Tests for unified card layout functions in silverquillm.card_loader.

Uses fixture card data under tests/fixtures/cards/ instead of live repo data.
Fixtures include:
  - fdn/ set: 001, 005, 042, 105b (collision suffix)
  - sos/ set: 1, 10, soa_6 (SOA prefix), spg_149 (SPG prefix)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.card_loader import (
    is_template,
    load_all_card_specs,
    load_card_impl,
    load_card_spec,
)

# Fixture cards root (not live repo data)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "cards"


# ---------------------------------------------------------------------------
# load_card_spec
# ---------------------------------------------------------------------------


class TestLoadCardSpec:
    """Tests for load_card_spec — loads one card spec from fixture data."""

    def test_loads_fdn_card_returns_dict_with_name(self) -> None:
        """Should load fixture FDN 001 and return dict with expected name."""
        spec = load_card_spec(FIXTURES_DIR, "fdn", "001")
        assert isinstance(spec, dict)
        assert spec["name"] == "Plains"

    def test_spec_has_all_required_fields(self) -> None:
        """Returned spec should contain all standard card spec fields."""
        spec = load_card_spec(FIXTURES_DIR, "fdn", "042")
        required = (
            "name", "mana_cost", "type_line", "oracle_text",
            "power", "toughness", "colors", "keywords", "rarity",
            "set_code", "collector_number",
        )
        for field in required:
            assert field in spec, f"Missing field: {field}"

    def test_set_code_populated_from_path(self) -> None:
        """set_code should be derived from the directory path, not JSON content."""
        spec = load_card_spec(FIXTURES_DIR, "fdn", "001")
        assert spec["set_code"] == "fdn"

    def test_collector_number_populated_from_path(self) -> None:
        """collector_number should be the directory name (path-derived)."""
        spec = load_card_spec(FIXTURES_DIR, "fdn", "001")
        assert spec["collector_number"] == "001"

    def test_loads_collision_suffix_collector_number(self) -> None:
        """Should load card with collision suffix like 105b."""
        spec = load_card_spec(FIXTURES_DIR, "fdn", "105b")
        assert spec["name"] == "Goblin Striker (Alt)"
        assert spec["collector_number"] == "105b"
        assert spec["set_code"] == "fdn"

    def test_loads_soa_prefixed_collector_number(self) -> None:
        """Should load card with soa_ prefix in SOS set."""
        spec = load_card_spec(FIXTURES_DIR, "sos", "soa_6")
        assert spec["name"] == "Akroma's Will"
        assert spec["collector_number"] == "soa_6"
        assert spec["set_code"] == "sos"

    def test_loads_spg_prefixed_collector_number(self) -> None:
        """Should load card with spg_ prefix in SOS set."""
        spec = load_card_spec(FIXTURES_DIR, "sos", "spg_149")
        assert spec["name"] == "Thought Vessel"
        assert spec["collector_number"] == "spg_149"

    def test_missing_card_raises_file_not_found(self) -> None:
        """Should raise FileNotFoundError for non-existent collector number."""
        with pytest.raises(FileNotFoundError):
            load_card_spec(FIXTURES_DIR, "fdn", "99999")

    def test_missing_set_raises_file_not_found(self) -> None:
        """Should raise FileNotFoundError for non-existent set code."""
        with pytest.raises(FileNotFoundError):
            load_card_spec(FIXTURES_DIR, "zzz_nonexistent", "001")


# ---------------------------------------------------------------------------
# load_all_card_specs
# ---------------------------------------------------------------------------


class TestLoadAllCardSpecs:
    """Tests for load_all_card_specs — loads all specs for a set, sorted."""

    def test_loads_all_fdn_fixture_cards(self) -> None:
        """Should return exactly 4 specs from fixture fdn set."""
        specs = load_all_card_specs(FIXTURES_DIR, "fdn")
        assert isinstance(specs, list)
        assert len(specs) == 4

    def test_loads_all_sos_fixture_cards(self) -> None:
        """Should return exactly 4 specs from fixture sos set."""
        specs = load_all_card_specs(FIXTURES_DIR, "sos")
        assert len(specs) == 4

    def test_fdn_sorted_by_natural_directory_name(self) -> None:
        """FDN cards should be sorted: 001, 005, 042, 105b (natural sort)."""
        specs = load_all_card_specs(FIXTURES_DIR, "fdn")
        collector_numbers = [s["collector_number"] for s in specs]
        assert collector_numbers == ["001", "005", "042", "105b"]

    def test_sos_sorted_numeric_then_prefixed(self) -> None:
        """SOS cards: numeric dirs (1, 10) sort before prefixed (soa_6, spg_149)."""
        specs = load_all_card_specs(FIXTURES_DIR, "sos")
        collector_numbers = [s["collector_number"] for s in specs]
        # Numeric first (1 < 10), then lexicographic for non-numeric
        assert collector_numbers == ["1", "10", "soa_6", "spg_149"]

    def test_each_spec_has_set_code_populated(self) -> None:
        """Every spec in the result should have set_code populated."""
        specs = load_all_card_specs(FIXTURES_DIR, "fdn")
        for spec in specs:
            assert spec["set_code"] == "fdn"

    def test_each_spec_has_collector_number_from_dirname(self) -> None:
        """collector_number should be directory name for each spec."""
        specs = load_all_card_specs(FIXTURES_DIR, "sos")
        names = {s["collector_number"] for s in specs}
        assert names == {"1", "10", "soa_6", "spg_149"}

    def test_nonexistent_set_returns_empty(self) -> None:
        """Should return empty list for a set that doesn't exist."""
        specs = load_all_card_specs(FIXTURES_DIR, "zzz_nonexistent")
        assert specs == []


# ---------------------------------------------------------------------------
# load_card_impl
# ---------------------------------------------------------------------------


class TestLoadCardImpl:
    """Tests for load_card_impl — returns path to card_impl.py."""

    def test_returns_path_for_known_card(self) -> None:
        """Should return a Path pointing to an existing card_impl.py."""
        path = load_card_impl(FIXTURES_DIR, "fdn", "001")
        assert isinstance(path, Path)
        assert path.exists()
        assert path.name == "card_impl.py"

    def test_returns_path_for_soa_prefixed_card(self) -> None:
        """Should work with soa_ prefixed collector numbers."""
        path = load_card_impl(FIXTURES_DIR, "sos", "soa_6")
        assert path.exists()
        assert path.name == "card_impl.py"

    def test_returns_path_for_collision_suffix(self) -> None:
        """Should work with collision-suffixed collector numbers (105b)."""
        path = load_card_impl(FIXTURES_DIR, "fdn", "105b")
        assert path.exists()

    def test_missing_card_raises_file_not_found(self) -> None:
        """Should raise FileNotFoundError for non-existent card."""
        with pytest.raises(FileNotFoundError):
            load_card_impl(FIXTURES_DIR, "fdn", "99999")

    def test_missing_set_raises_file_not_found(self) -> None:
        """Should raise FileNotFoundError for non-existent set."""
        with pytest.raises(FileNotFoundError):
            load_card_impl(FIXTURES_DIR, "zzz_nonexistent", "001")


# ---------------------------------------------------------------------------
# is_template
# ---------------------------------------------------------------------------


class TestIsTemplate:
    """Tests for is_template — checks if card_impl.py is an empty template."""

    def test_real_impl_returns_false(self) -> None:
        """FDN 001 fixture has real code (not just pass/...), should return False."""
        impl_path = load_card_impl(FIXTURES_DIR, "fdn", "001")
        assert is_template(impl_path) is False

    def test_pass_only_template_returns_true(self) -> None:
        """FDN 042 fixture has pass-only body, should return True."""
        impl_path = load_card_impl(FIXTURES_DIR, "fdn", "042")
        assert is_template(impl_path) is True

    def test_ellipsis_template_returns_true(self) -> None:
        """FDN 005 fixture uses ellipsis (...) body, should return True."""
        impl_path = load_card_impl(FIXTURES_DIR, "fdn", "005")
        assert is_template(impl_path) is True

    def test_sos_template_returns_true(self) -> None:
        """SOS 1 fixture is a pass-only template."""
        impl_path = load_card_impl(FIXTURES_DIR, "sos", "1")
        assert is_template(impl_path) is True

    def test_prefixed_template_returns_true(self) -> None:
        """soa_6 fixture should be a template (pass-only)."""
        impl_path = load_card_impl(FIXTURES_DIR, "sos", "soa_6")
        assert is_template(impl_path) is True
