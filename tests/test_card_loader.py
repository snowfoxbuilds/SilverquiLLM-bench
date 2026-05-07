"""Tests for benchmark.card_loader — card spec loading and filtering utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.card_loader import (
    filter_by_collectors,
    filter_by_prototype,
    load_card_specs,
    load_prototype_cards,
)


def _make_card_spec(tmp_path: Path, subdir: str, spec: dict) -> None:
    """Helper: create a card_spec.json in a named subdirectory."""
    d = tmp_path / subdir
    d.mkdir(parents=True, exist_ok=True)
    (d / "card_spec.json").write_text(json.dumps(spec), encoding="utf-8")


class TestLoadCardSpecs:
    """Tests for load_card_specs."""

    def test_finds_specs_in_subdirectories(self, tmp_path: Path) -> None:
        """Should find card_spec.json in each subdirectory."""
        _make_card_spec(tmp_path, "card_a", {"collector_number": "10", "name": "A"})
        _make_card_spec(tmp_path, "card_b", {"collector_number": "5", "name": "B"})

        result = load_card_specs(str(tmp_path))
        assert len(result) == 2

    def test_returns_sorted_by_collector_number_numerically(self, tmp_path: Path) -> None:
        """Should sort numerically: 5 before 10."""
        _make_card_spec(tmp_path, "card_a", {"collector_number": "10", "name": "A"})
        _make_card_spec(tmp_path, "card_b", {"collector_number": "5", "name": "B"})
        _make_card_spec(tmp_path, "card_c", {"collector_number": "2", "name": "C"})

        result = load_card_specs(str(tmp_path))
        numbers = [s["collector_number"] for s in result]
        assert numbers == ["2", "5", "10"]

    def test_skips_directories_without_card_spec(self, tmp_path: Path) -> None:
        """Subdirectories without card_spec.json should be ignored."""
        _make_card_spec(tmp_path, "valid", {"collector_number": "1", "name": "V"})
        (tmp_path / "no_spec_dir").mkdir()
        (tmp_path / "no_spec_dir" / "other.txt").write_text("nope")

        result = load_card_specs(str(tmp_path))
        assert len(result) == 1
        assert result[0]["name"] == "V"

    def test_returns_empty_list_for_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory should return empty list."""
        result = load_card_specs(str(tmp_path))
        assert result == []

    def test_skips_files_at_top_level(self, tmp_path: Path) -> None:
        """Files (not dirs) at top level should be ignored."""
        (tmp_path / "card_spec.json").write_text(json.dumps({"collector_number": "1"}))
        _make_card_spec(tmp_path, "real", {"collector_number": "3", "name": "R"})

        result = load_card_specs(str(tmp_path))
        assert len(result) == 1

    def test_lexicographic_sort_for_non_numeric(self, tmp_path: Path) -> None:
        """Non-numeric collector numbers should sort lexicographically after numeric ones."""
        _make_card_spec(tmp_path, "a", {"collector_number": "2", "name": "Num"})
        _make_card_spec(tmp_path, "b", {"collector_number": "abc", "name": "Alpha"})

        result = load_card_specs(str(tmp_path))
        assert result[0]["collector_number"] == "2"
        assert result[1]["collector_number"] == "abc"


class TestLoadPrototypeCards:
    """Tests for load_prototype_cards."""

    def test_returns_collector_number_strings(self, tmp_path: Path) -> None:
        """Should extract collector numbers and return them as list[str]."""
        data = [
            {"collector_number": "10", "name": "Card A"},
            {"collector_number": "20", "name": "Card B"},
        ]
        proto_file = tmp_path / "prototype_cards.json"
        proto_file.write_text(json.dumps(data), encoding="utf-8")

        result = load_prototype_cards(str(proto_file))
        assert result == ["10", "20"]

    def test_returns_empty_list_for_empty_json(self, tmp_path: Path) -> None:
        """Should return an empty list when the JSON array is empty."""
        proto_file = tmp_path / "prototype_cards.json"
        proto_file.write_text(json.dumps([]), encoding="utf-8")

        result = load_prototype_cards(str(proto_file))
        assert result == []

    def test_preserves_order_from_file(self, tmp_path: Path) -> None:
        """Should preserve the order of collector numbers as they appear in the file."""
        data = [
            {"collector_number": "99"},
            {"collector_number": "3"},
            {"collector_number": "42"},
        ]
        proto_file = tmp_path / "prototype_cards.json"
        proto_file.write_text(json.dumps(data), encoding="utf-8")

        result = load_prototype_cards(str(proto_file))
        assert result == ["99", "3", "42"]


class TestFilterByCollectors:
    """Tests for filter_by_collectors."""

    def test_filters_to_matching_specs(self) -> None:
        """Should return only specs matching requested collector numbers."""
        specs = [
            {"collector_number": "1", "name": "A"},
            {"collector_number": "2", "name": "B"},
            {"collector_number": "3", "name": "C"},
        ]
        result = filter_by_collectors(specs, ["2"])
        assert len(result) == 1
        assert result[0]["name"] == "B"

    def test_preserves_original_order(self) -> None:
        """Filtered results should preserve the order of specs, not collector_numbers."""
        specs = [
            {"collector_number": "3", "name": "C"},
            {"collector_number": "1", "name": "A"},
            {"collector_number": "2", "name": "B"},
        ]
        result = filter_by_collectors(specs, ["2", "3"])
        assert [s["name"] for s in result] == ["C", "B"]

    def test_raises_valueerror_for_unknown_collector(self) -> None:
        """Should raise ValueError when a requested number doesn't exist."""
        specs = [{"collector_number": "1", "name": "A"}]
        with pytest.raises(ValueError, match="not found"):
            filter_by_collectors(specs, ["999"])

    def test_empty_collector_numbers_returns_empty(self) -> None:
        """Empty filter list should return empty results."""
        specs = [{"collector_number": "1", "name": "A"}]
        result = filter_by_collectors(specs, [])
        assert result == []

    def test_multiple_matches(self) -> None:
        """Should return multiple matching specs."""
        specs = [
            {"collector_number": "1", "name": "A"},
            {"collector_number": "2", "name": "B"},
            {"collector_number": "3", "name": "C"},
        ]
        result = filter_by_collectors(specs, ["1", "3"])
        assert len(result) == 2
        assert result[0]["name"] == "A"
        assert result[1]["name"] == "C"


class TestFilterByPrototype:
    """Tests for filter_by_prototype."""

    def test_filters_specs_using_prototype_file(self, tmp_path: Path) -> None:
        """Should load prototype and filter specs to matching collector numbers."""
        proto = [{"collector_number": "2"}, {"collector_number": "3"}]
        proto_file = tmp_path / "prototype_cards.json"
        proto_file.write_text(json.dumps(proto), encoding="utf-8")

        specs = [
            {"collector_number": "1", "name": "A"},
            {"collector_number": "2", "name": "B"},
            {"collector_number": "3", "name": "C"},
        ]
        result = filter_by_prototype(specs, str(proto_file))
        assert len(result) == 2
        assert [s["name"] for s in result] == ["B", "C"]

    def test_raises_valueerror_for_missing_prototype_collector(self, tmp_path: Path) -> None:
        """Should raise ValueError if prototype references a missing collector number."""
        proto = [{"collector_number": "999"}]
        proto_file = tmp_path / "prototype_cards.json"
        proto_file.write_text(json.dumps(proto), encoding="utf-8")

        specs = [{"collector_number": "1", "name": "A"}]
        with pytest.raises(ValueError):
            filter_by_prototype(specs, str(proto_file))
