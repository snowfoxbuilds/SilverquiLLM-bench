"""Tests for TODO item 1: Include Mystical Archives (SOA set, cn 1–65).

Tests verify:
- _normalize_card preserves set_code from raw Scryfall card data (SOA vs SOS).
- fetch_sos_data merges SOA cards into the SOS pool with correct set_code.
- classify_set emits set_code in JSON output records for multi-set pools.
- _load_classified uses composite set_code:collector_number keys.
- generate_all_specs resolves cards via composite keys in multi-set pools.
- SOA cards are exactly 65 with collector numbers 1–65.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from cards.registry import CardMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_scryfall_card(
    name: str = "Test Card",
    set_code: str = "sos",
    collector_number: str = "1",
    mana_cost: str = "{1}{W}",
    type_line: str = "Creature — Human",
    oracle_text: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Build a minimal raw Scryfall card dict."""
    card: dict[str, Any] = {
        "name": name,
        "set": set_code,
        "collector_number": collector_number,
        "mana_cost": mana_cost,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "colors": ["W"],
        "keywords": [],
        "rarity": "common",
    }
    card.update(extra)
    return card


def _make_card_metadata(**kwargs: Any) -> CardMetadata:
    """Shorthand to create CardMetadata with sensible defaults."""
    defaults: dict[str, Any] = {
        "name": "Test Card",
        "mana_cost_str": "{1}{W}",
        "type_line": "Creature — Human",
        "oracle_text": "",
        "power": "2",
        "toughness": "2",
        "colors": ["W"],
        "keywords": [],
        "rarity": "common",
        "set_code": "sos",
        "collector_number": "1",
    }
    defaults.update(kwargs)
    return CardMetadata(**defaults)


# ---------------------------------------------------------------------------
# _normalize_card — set_code preservation
# ---------------------------------------------------------------------------


class TestNormalizeCardSetCode:
    """_normalize_card must preserve set_code so SOA cards remain distinguishable."""

    def test_sos_card_has_sos_set_code(self) -> None:
        from benchmarks.sos.fetch_data import _normalize_card

        raw = _make_raw_scryfall_card(set_code="sos", collector_number="42")
        result = _normalize_card(raw)
        assert result["set_code"] == "sos"

    def test_soa_card_has_soa_set_code(self) -> None:
        from benchmarks.sos.fetch_data import _normalize_card

        raw = _make_raw_scryfall_card(
            name="Opt",
            set_code="soa",
            collector_number="10",
        )
        result = _normalize_card(raw)
        assert result["set_code"] == "soa"

    def test_set_code_from_set_field(self) -> None:
        """Scryfall uses 'set' not 'set_code'; _normalize_card should map it."""
        from benchmarks.sos.fetch_data import _normalize_card

        raw = {"name": "Card", "set": "soa", "collector_number": "5"}
        result = _normalize_card(raw)
        assert result["set_code"] == "soa"

    def test_mana_cost_str_normalization(self) -> None:
        """mana_cost_str should be set from Scryfall's mana_cost field."""
        from benchmarks.sos.fetch_data import _normalize_card

        raw = _make_raw_scryfall_card(mana_cost="{2}{U}")
        result = _normalize_card(raw)
        assert result["mana_cost_str"] == "{2}{U}"


# ---------------------------------------------------------------------------
# fetch_sos_data — SOA merge behavior (mocked network)
# ---------------------------------------------------------------------------


class TestFetchSosDataWorkflow:
    """fetch_sos_data must issue the SOA query, merge SOS+SOA, cache, and return both sets."""

    @staticmethod
    def _sos_raw_cards(count: int = 3) -> list[dict[str, Any]]:
        return [
            _make_raw_scryfall_card(
                name=f"SOS Card {i}",
                set_code="sos",
                collector_number=str(i),
            )
            for i in range(1, count + 1)
        ]

    @staticmethod
    def _soa_raw_cards(count: int = 65) -> list[dict[str, Any]]:
        return [
            _make_raw_scryfall_card(
                name=f"SOA Card {i}",
                set_code="soa",
                collector_number=str(i),
                type_line="Instant",
            )
            for i in range(1, count + 1)
        ]

    def _run_fetch(self, tmp_path: Path, sos_count: int = 3, soa_count: int = 65,
                   *, force: bool = False,
                   pre_cached_output: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Call fetch_sos_data with all filesystem paths redirected to tmp_path."""
        import benchmarks.sos.fetch_data as mod

        sos_raw = self._sos_raw_cards(sos_count)
        soa_raw = self._soa_raw_cards(soa_count)

        output_path = tmp_path / "sos.json"
        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        soa_cache = tmp_path / "data" / "sets" / "soa.json"

        # Write the SOS raw cache (simulates what fetch_set writes)
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_cache, "w") as f:
            json.dump(sos_raw, f)

        # If there's a pre-cached output, write it
        if pre_cached_output is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(pre_cached_output, f)

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_set", return_value=[]),  # called for side-effect only
            patch.object(mod, "fetch_scryfall_query", return_value=(soa_raw, [])),
        ):
            return mod.fetch_sos_data(force=force)

    def test_returns_merged_cards_with_both_set_codes(self, tmp_path: Path) -> None:
        result = self._run_fetch(tmp_path, sos_count=5, soa_count=65)
        set_codes = {c["set_code"] for c in result}
        assert "sos" in set_codes, "SOS cards missing"
        assert "soa" in set_codes, "SOA cards missing"

    def test_total_count_sos_plus_soa(self, tmp_path: Path) -> None:
        result = self._run_fetch(tmp_path, sos_count=10, soa_count=65)
        assert len(result) == 75

    def test_exactly_65_soa_cards(self, tmp_path: Path) -> None:
        result = self._run_fetch(tmp_path, sos_count=10, soa_count=65)
        soa_only = [c for c in result if c["set_code"] == "soa"]
        assert len(soa_only) == 65

    def test_soa_collector_numbers_span_1_to_65(self, tmp_path: Path) -> None:
        result = self._run_fetch(tmp_path, sos_count=5, soa_count=65)
        soa_cns = sorted(
            int(c["collector_number"])
            for c in result
            if c["set_code"] == "soa"
        )
        assert soa_cns == list(range(1, 66))

    def test_output_json_written_to_disk(self, tmp_path: Path) -> None:
        """fetch_sos_data must persist merged result to OUTPUT_PATH."""
        import benchmarks.sos.fetch_data as mod

        output_path = tmp_path / "sos.json"
        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        sos_raw = self._sos_raw_cards(2)

        # fetch_set is called for its side-effect of populating the raw cache
        def _fake_fetch_set(code: str, **kw: Any) -> list[Any]:
            with open(raw_cache, "w") as fh:
                json.dump(sos_raw, fh)
            return []

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_set", side_effect=_fake_fetch_set),
            patch.object(mod, "fetch_scryfall_query", return_value=(self._soa_raw_cards(65), [])),
        ):
            mod.fetch_sos_data(force=True)

        assert output_path.exists(), "Output JSON was not written"
        with open(output_path) as f:
            on_disk = json.load(f)
        soa_on_disk = [c for c in on_disk if c["set_code"] == "soa"]
        assert len(soa_on_disk) == 65

    def test_stale_cache_without_soa_triggers_rebuild(self, tmp_path: Path) -> None:
        """An old SOS-only cache (no SOA cards) must be rebuilt, not returned as-is."""
        from benchmarks.sos.fetch_data import _normalize_card

        # Pre-cached output with only SOS cards (stale)
        stale_cache = [_normalize_card(c) for c in self._sos_raw_cards(10)]
        result = self._run_fetch(
            tmp_path, sos_count=10, soa_count=65, pre_cached_output=stale_cache
        )
        soa_only = [c for c in result if c["set_code"] == "soa"]
        assert len(soa_only) == 65, (
            "Stale SOS-only cache was returned without rebuilding; "
            "expected 65 SOA cards after rebuild"
        )

    @staticmethod
    def _spg_raw_cards() -> list[dict[str, Any]]:
        """Build 10 SPG Special Guest cards for cn 149–158."""
        return [
            _make_raw_scryfall_card(
                name=f"SPG Guest {i}",
                set_code="spg",
                collector_number=str(i),
            )
            for i in range(149, 159)
        ]

    def test_fresh_cache_with_soa_returns_cached(self, tmp_path: Path) -> None:
        """A cache that already has SOA + SPG cards should be returned without re-fetching.

        After item 2, a fresh cache must include exactly 10 SPG cards (cn 149–158)
        in addition to 65 SOA cards. A cache missing the SPG subset is stale.
        """
        import benchmarks.sos.fetch_data as mod
        from benchmarks.sos.fetch_data import _normalize_card

        # Build a complete cache with SOS, SOA, and SPG
        complete = (
            [_normalize_card(c) for c in self._sos_raw_cards(10)]
            + [_normalize_card(c) for c in self._soa_raw_cards(65)]
            + [_normalize_card(c) for c in self._spg_raw_cards()]
        )
        output_path = tmp_path / "sos.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(complete, f)

        mock_fetch_query = MagicMock()

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_scryfall_query", mock_fetch_query),
        ):
            result = mod.fetch_sos_data(force=False)

        # Should return cached data without calling fetch_scryfall_query
        mock_fetch_query.assert_not_called()
        assert len(result) == 85  # 10 SOS + 65 SOA + 10 SPG


# ---------------------------------------------------------------------------
# classify_set — set_code in output records
# ---------------------------------------------------------------------------


class TestClassifySetMultiSet:
    """classify_set must include set_code in JSON records for multi-set pools."""

    def test_classified_json_includes_set_code_field(self, tmp_path: Path) -> None:
        from silverquillm.card_classifier import classify_set

        cards = [
            _make_card_metadata(name="SOS Creature", set_code="sos", collector_number="1"),
            _make_card_metadata(name="SOA Instant", set_code="soa", collector_number="1",
                                type_line="Instant", oracle_text="Draw a card."),
        ]
        out = tmp_path / "classified.json"
        classify_set(cards, output_path=out)

        with open(out) as f:
            records = json.load(f)

        for record in records:
            assert "set_code" in record, f"set_code missing from record: {record['name']}"

    def test_classified_json_preserves_distinct_set_codes(self, tmp_path: Path) -> None:
        from silverquillm.card_classifier import classify_set

        cards = [
            _make_card_metadata(name="SOS Card", set_code="sos", collector_number="1"),
            _make_card_metadata(name="SOA Card", set_code="soa", collector_number="1",
                                type_line="Instant"),
        ]
        out = tmp_path / "classified.json"
        classify_set(cards, output_path=out)

        with open(out) as f:
            records = json.load(f)

        set_codes = {r["set_code"] for r in records}
        assert "sos" in set_codes
        assert "soa" in set_codes

    def test_classified_json_same_cn_different_sets(self, tmp_path: Path) -> None:
        """Two cards can share collector_number if they have different set_codes."""
        from silverquillm.card_classifier import classify_set

        cards = [
            _make_card_metadata(name="SOS #1", set_code="sos", collector_number="1"),
            _make_card_metadata(name="SOA #1", set_code="soa", collector_number="1"),
        ]
        out = tmp_path / "classified.json"
        classify_set(cards, output_path=out)

        with open(out) as f:
            records = json.load(f)

        assert len(records) == 2, "Both cards should appear in classified output"


# ---------------------------------------------------------------------------
# _load_classified — composite key lookup
# ---------------------------------------------------------------------------


class TestLoadClassifiedCompositeKeys:
    """_load_classified must support composite set_code:collector_number keys."""

    def test_composite_key_lookup(self, tmp_path: Path) -> None:
        from silverquillm.card_spec import _load_classified

        data = [
            {"name": "SOS Card", "set_code": "sos", "collector_number": "1",
             "complexity_tier": "simple"},
            {"name": "SOA Card", "set_code": "soa", "collector_number": "1",
             "complexity_tier": "medium"},
        ]
        path = tmp_path / "classified.json"
        path.write_text(json.dumps(data))

        result = _load_classified(path)

        assert "sos:1" in result
        assert "soa:1" in result
        assert result["sos:1"]["name"] == "SOS Card"
        assert result["soa:1"]["name"] == "SOA Card"

    def test_plain_cn_fallback_without_set_code(self, tmp_path: Path) -> None:
        """Cards without set_code should still be accessible by plain cn."""
        from silverquillm.card_spec import _load_classified

        data = [
            {"name": "Legacy Card", "collector_number": "42",
             "complexity_tier": "trivial"},
        ]
        path = tmp_path / "classified.json"
        path.write_text(json.dumps(data))

        result = _load_classified(path)
        assert "42" in result
        assert result["42"]["name"] == "Legacy Card"

    def test_composite_key_distinguishes_same_cn(self, tmp_path: Path) -> None:
        """Composite keys must differentiate same cn across sets."""
        from silverquillm.card_spec import _load_classified

        data = [
            {"name": "SOS #5", "set_code": "sos", "collector_number": "5",
             "complexity_tier": "simple"},
            {"name": "SOA #5", "set_code": "soa", "collector_number": "5",
             "complexity_tier": "complex"},
        ]
        path = tmp_path / "classified.json"
        path.write_text(json.dumps(data))

        result = _load_classified(path)
        assert result["sos:5"]["complexity_tier"] == "simple"
        assert result["soa:5"]["complexity_tier"] == "complex"


# ---------------------------------------------------------------------------
# generate_card_spec — set_code in spec output
# ---------------------------------------------------------------------------


class TestGenerateCardSpecSetCode:
    """generate_card_spec must include set_code in the output dict."""

    def test_spec_contains_set_code(self) -> None:
        from silverquillm.card_spec import generate_card_spec

        card = _make_card_metadata(set_code="soa", collector_number="10")
        spec = generate_card_spec(card, "medium")
        assert spec["set_code"] == "soa"

    def test_spec_contains_collector_number(self) -> None:
        from silverquillm.card_spec import generate_card_spec

        card = _make_card_metadata(set_code="soa", collector_number="42")
        spec = generate_card_spec(card, "simple")
        assert spec["collector_number"] == "42"


# ---------------------------------------------------------------------------
# fetch_scryfall_query — API contract
# ---------------------------------------------------------------------------


class TestFetchScryfallQueryContract:
    """fetch_scryfall_query must return (raw_list, parsed_list) tuple."""

    def test_returns_tuple_of_two_lists(self) -> None:
        from cards.scryfall import fetch_scryfall_query

        mock_response = {
            "data": [_make_raw_scryfall_card(set_code="soa", collector_number="1")],
            "has_more": False,
        }

        with patch("cards.scryfall._fetch_json", return_value=mock_response):
            raw, parsed = fetch_scryfall_query("e%3Asoa+cn%3E%3D1+cn%3C%3D65", set_code="soa")

        assert isinstance(raw, list)
        assert isinstance(parsed, list)
        assert len(raw) == 1
        assert len(parsed) == 1

    def test_parsed_cards_are_card_metadata(self) -> None:
        from cards.scryfall import fetch_scryfall_query

        mock_response = {
            "data": [_make_raw_scryfall_card(set_code="soa", collector_number="3")],
            "has_more": False,
        }

        with patch("cards.scryfall._fetch_json", return_value=mock_response):
            _, parsed = fetch_scryfall_query("e%3Asoa+cn%3E%3D1+cn%3C%3D65", set_code="soa")

        assert isinstance(parsed[0], CardMetadata)

    def test_handles_pagination(self) -> None:
        from cards.scryfall import fetch_scryfall_query

        page1 = {
            "data": [_make_raw_scryfall_card(name="Card 1", set_code="soa", collector_number="1")],
            "has_more": True,
            "next_page": "https://api.scryfall.com/cards/search?page=2",
        }
        page2 = {
            "data": [_make_raw_scryfall_card(name="Card 2", set_code="soa", collector_number="2")],
            "has_more": False,
        }

        with patch("cards.scryfall._fetch_json", side_effect=[page1, page2]):
            with patch("cards.scryfall.time.sleep"):  # skip rate limit delay
                raw, parsed = fetch_scryfall_query("e%3Asoa", set_code="soa")

        assert len(raw) == 2
        assert len(parsed) == 2


# ---------------------------------------------------------------------------
# _log_stats — multi-set breakdown
# ---------------------------------------------------------------------------


class TestLogStatsMultiSet:
    """_log_stats should handle cards from multiple sets without errors."""

    def test_log_stats_with_mixed_set_codes(self) -> None:
        from benchmarks.sos.fetch_data import _normalize_card, _log_stats

        cards = [
            _normalize_card(_make_raw_scryfall_card(set_code="sos", collector_number="1")),
            _normalize_card(_make_raw_scryfall_card(set_code="soa", collector_number="1")),
        ]
        # Should not raise
        _log_stats(cards)
