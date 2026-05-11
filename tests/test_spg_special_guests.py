"""Tests for TODO item 2: Include Special Guests (SPG set, cn 149–158).

Tests verify:
- _normalize_card preserves set_code="spg" for SPG cards.
- fetch_sos_data issues SPG query, merges into SOS pool, uses query-specific cache.
- Exactly 10 SPG cards with collector numbers 149–158 in output.
- Stale cache (missing SPG) triggers rebuild.
- Cache filtering enforces collector-number range 149–158.
- SPG 149–158 are distinct from FDN SPG 074–083.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest


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
        "rarity": "rare",
    }
    card.update(extra)
    return card


def _sos_raw_cards(count: int = 3) -> list[dict[str, Any]]:
    return [
        _make_raw_scryfall_card(
            name=f"SOS Card {i}", set_code="sos", collector_number=str(i),
        )
        for i in range(1, count + 1)
    ]


def _soa_raw_cards(count: int = 65) -> list[dict[str, Any]]:
    return [
        _make_raw_scryfall_card(
            name=f"SOA Card {i}", set_code="soa", collector_number=str(i),
        )
        for i in range(1, count + 1)
    ]


def _spg_raw_cards(start: int = 149, end: int = 158) -> list[dict[str, Any]]:
    """Build SPG Special Guest cards for cn range [start, end]."""
    return [
        _make_raw_scryfall_card(
            name=f"SPG Guest {i}", set_code="spg", collector_number=str(i),
        )
        for i in range(start, end + 1)
    ]


def _run_fetch(
    tmp_path: Path,
    sos_count: int = 3,
    soa_count: int = 65,
    spg_cards: list[dict[str, Any]] | None = None,
    *,
    force: bool = False,
    pre_cached_output: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Call fetch_sos_data with all filesystem paths redirected to tmp_path."""
    import benchmarks.sos.fetch_data as mod

    sos_raw = _sos_raw_cards(sos_count)
    soa_raw = _soa_raw_cards(soa_count)
    if spg_cards is None:
        spg_cards = _spg_raw_cards()

    output_path = tmp_path / "sos.json"
    raw_cache = tmp_path / "data" / "sets" / "sos.json"

    # Write the SOS raw cache (simulates what fetch_set writes)
    raw_cache.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_cache, "w") as f:
        json.dump(sos_raw, f)

    # If there's a pre-cached output, write it
    if pre_cached_output is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(pre_cached_output, f)

    # fetch_scryfall_query is called twice: once for SOA, once for SPG.
    def _mock_fetch_query(query: str, set_code: str = "", **kw: Any):
        if "soa" in query or set_code == "soa":
            return (soa_raw, [])
        elif "spg" in query or set_code == "spg":
            return (spg_cards, [])
        return ([], [])

    # fetch_set is called for side-effect of populating raw cache.
    # When force=True, the code deletes raw_cache first, so we must re-write it.
    def _fake_fetch_set(code: str, **kw: Any) -> list[Any]:
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_cache, "w") as fh:
            json.dump(sos_raw, fh)
        return []

    with (
        patch.object(mod, "OUTPUT_PATH", output_path),
        patch.object(mod, "_REPO_ROOT", tmp_path),
        patch.object(mod, "fetch_set", side_effect=_fake_fetch_set),
        patch.object(mod, "fetch_scryfall_query", side_effect=_mock_fetch_query),
    ):
        return mod.fetch_sos_data(force=force)


# ---------------------------------------------------------------------------
# _normalize_card — SPG set_code preservation
# ---------------------------------------------------------------------------


class TestNormalizeCardSPG:
    """_normalize_card must preserve set_code='spg' for Special Guest cards."""

    def test_spg_card_has_spg_set_code(self) -> None:
        from benchmarks.sos.fetch_data import _normalize_card

        raw = _make_raw_scryfall_card(set_code="spg", collector_number="149")
        result = _normalize_card(raw)
        assert result["set_code"] == "spg"

    def test_spg_card_preserves_collector_number(self) -> None:
        from benchmarks.sos.fetch_data import _normalize_card

        raw = _make_raw_scryfall_card(set_code="spg", collector_number="155")
        result = _normalize_card(raw)
        assert result["collector_number"] == "155"


# ---------------------------------------------------------------------------
# fetch_sos_data — SPG merge behavior
# ---------------------------------------------------------------------------


class TestFetchSosDataSPGMerge:
    """fetch_sos_data must merge SPG 149–158 into the SOS pool."""

    def test_result_contains_spg_set_code(self, tmp_path: Path) -> None:
        result = _run_fetch(tmp_path, force=True)
        set_codes = {c["set_code"] for c in result}
        assert "spg" in set_codes, "SPG cards missing from merged result"

    def test_exactly_10_spg_cards(self, tmp_path: Path) -> None:
        result = _run_fetch(tmp_path, force=True)
        spg_only = [c for c in result if c["set_code"] == "spg"]
        assert len(spg_only) == 10

    def test_spg_collector_numbers_span_149_to_158(self, tmp_path: Path) -> None:
        result = _run_fetch(tmp_path, force=True)
        spg_cns = sorted(
            int(c["collector_number"])
            for c in result
            if c["set_code"] == "spg"
        )
        assert spg_cns == list(range(149, 159))

    def test_total_count_sos_plus_soa_plus_spg(self, tmp_path: Path) -> None:
        """Total card count = SOS + SOA(65) + SPG(10)."""
        result = _run_fetch(tmp_path, sos_count=5, force=True)
        assert len(result) == 5 + 65 + 10

    def test_all_three_sets_present(self, tmp_path: Path) -> None:
        result = _run_fetch(tmp_path, force=True)
        set_codes = {c["set_code"] for c in result}
        assert set_codes >= {"sos", "soa", "spg"}

    def test_output_json_contains_spg_cards(self, tmp_path: Path) -> None:
        """fetch_sos_data must persist SPG cards to OUTPUT_PATH on disk."""
        import benchmarks.sos.fetch_data as mod

        output_path = tmp_path / "sos.json"
        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        sos_raw = _sos_raw_cards(2)

        def _fake_fetch_set(code: str, **kw: Any) -> list[Any]:
            raw_cache.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_cache, "w") as fh:
                json.dump(sos_raw, fh)
            return []

        def _mock_query(query: str, set_code: str = "", **kw: Any):
            if set_code == "soa" or "soa" in query:
                return (_soa_raw_cards(65), [])
            elif set_code == "spg" or "spg" in query:
                return (_spg_raw_cards(), [])
            return ([], [])

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_set", side_effect=_fake_fetch_set),
            patch.object(mod, "fetch_scryfall_query", side_effect=_mock_query),
        ):
            mod.fetch_sos_data(force=True)

        assert output_path.exists()
        with open(output_path) as f:
            on_disk = json.load(f)
        spg_on_disk = [c for c in on_disk if c["set_code"] == "spg"]
        assert len(spg_on_disk) == 10


# ---------------------------------------------------------------------------
# Query-specific cache for SPG subset
# ---------------------------------------------------------------------------


class TestSPGQuerySpecificCache:
    """SPG cards should use a query-specific cache file, not a generic spg.json."""

    def test_spg_cache_file_created(self, tmp_path: Path) -> None:
        """After fetch, a query-specific SPG cache file should exist."""
        import benchmarks.sos.fetch_data as mod

        output_path = tmp_path / "sos.json"
        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        sos_raw = _sos_raw_cards(2)
        with open(raw_cache, "w") as f:
            json.dump(sos_raw, f)

        def _fake_fetch_set(code: str, **kw: Any) -> list[Any]:
            raw_cache.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_cache, "w") as fh:
                json.dump(sos_raw, fh)
            return []

        def _mock_query(query: str, set_code: str = "", **kw: Any):
            if set_code == "soa" or "soa" in query:
                return (_soa_raw_cards(65), [])
            elif set_code == "spg" or "spg" in query:
                return (_spg_raw_cards(), [])
            return ([], [])

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_set", side_effect=_fake_fetch_set),
            patch.object(mod, "fetch_scryfall_query", side_effect=_mock_query),
        ):
            mod.fetch_sos_data(force=True)

        # Should have created a query-specific cache, not generic spg.json
        sets_dir = tmp_path / "data" / "sets"
        cache_files = list(sets_dir.glob("spg*"))
        assert len(cache_files) >= 1, "No SPG cache file created"
        # The cache name should include collector number info (not just spg.json)
        cache_names = [f.name for f in cache_files]
        assert not any(
            n == "spg.json" for n in cache_names
        ), "Should use query-specific cache, not generic spg.json"

    def test_cached_spg_data_reused_on_non_force(self, tmp_path: Path) -> None:
        """When SPG cache exists, fetch_scryfall_query should NOT be called for SPG."""
        import benchmarks.sos.fetch_data as mod

        output_path = tmp_path / "sos.json"
        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_cache, "w") as f:
            json.dump(_sos_raw_cards(2), f)

        # Pre-populate the SPG subset cache
        spg_cache = tmp_path / "data" / "sets" / "spg_cn149-158.json"
        with open(spg_cache, "w") as f:
            json.dump(_spg_raw_cards(), f)

        # Pre-populate the SOA subset cache
        soa_cache = tmp_path / "data" / "sets" / "soa_cn1-65.json"
        with open(soa_cache, "w") as f:
            json.dump(_soa_raw_cards(65), f)

        mock_query = MagicMock()

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_set", return_value=[]),
            patch.object(mod, "fetch_scryfall_query", mock_query),
        ):
            result = mod.fetch_sos_data(force=False)

        # fetch_scryfall_query should not have been called at all
        # since both SOA and SPG caches exist
        mock_query.assert_not_called()
        spg_only = [c for c in result if c["set_code"] == "spg"]
        assert len(spg_only) == 10


# ---------------------------------------------------------------------------
# Cache filtering — collector number validation
# ---------------------------------------------------------------------------


class TestSPGCacheFiltering:
    """Cached SPG data must be filtered to cn 149–158 even if cache has extra cards."""

    def test_out_of_range_cards_filtered_from_cache(self, tmp_path: Path) -> None:
        """If cache contains SPG cards outside 149–158, they must be filtered out."""
        import benchmarks.sos.fetch_data as mod

        output_path = tmp_path / "sos.json"
        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_cache, "w") as f:
            json.dump(_sos_raw_cards(2), f)

        # Cache with extra cards outside range (e.g., FDN SPG 074–083)
        polluted_cache = _spg_raw_cards(149, 158) + _spg_raw_cards(74, 83)
        spg_cache = tmp_path / "data" / "sets" / "spg_cn149-158.json"
        with open(spg_cache, "w") as f:
            json.dump(polluted_cache, f)

        # SOA cache
        soa_cache = tmp_path / "data" / "sets" / "soa_cn1-65.json"
        with open(soa_cache, "w") as f:
            json.dump(_soa_raw_cards(65), f)

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_set", return_value=[]),
            patch.object(mod, "fetch_scryfall_query", side_effect=Exception("should not be called")),
        ):
            result = mod.fetch_sos_data(force=False)

        spg_only = [c for c in result if c["set_code"] == "spg"]
        assert len(spg_only) == 10
        spg_cns = {int(c["collector_number"]) for c in spg_only}
        assert spg_cns == set(range(149, 159))


# ---------------------------------------------------------------------------
# Stale cache — missing SPG triggers rebuild
# ---------------------------------------------------------------------------


class TestStaleCacheRebuild:
    """An old cache without SPG cards must trigger a full rebuild."""

    def test_cache_with_soa_but_no_spg_triggers_rebuild(self, tmp_path: Path) -> None:
        """Cache with SOS+SOA but no SPG must rebuild to include SPG.

        The stale-cache check must verify SPG presence (>= 10 SPG cards with
        cn 149–158) in addition to SOA presence. Without this, an old cache
        from before SPG was added would be returned as-is, missing 10 cards.
        """
        import benchmarks.sos.fetch_data as mod
        from benchmarks.sos.fetch_data import _normalize_card

        # Build a cache that has SOA (65 cards) but zero SPG
        stale = (
            [_normalize_card(c) for c in _sos_raw_cards(5)]
            + [_normalize_card(c) for c in _soa_raw_cards(65)]
        )
        output_path = tmp_path / "sos.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(stale, f)

        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        sos_raw = _sos_raw_cards(5)
        with open(raw_cache, "w") as f:
            json.dump(sos_raw, f)

        def _mock_fetch_query(query: str, set_code: str = "", **kw: Any):
            if "soa" in query or set_code == "soa":
                return (_soa_raw_cards(65), [])
            elif "spg" in query or set_code == "spg":
                return (_spg_raw_cards(), [])
            return ([], [])

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_set", return_value=[]),
            patch.object(mod, "fetch_scryfall_query", side_effect=_mock_fetch_query),
        ):
            result = mod.fetch_sos_data(force=False)

        spg_only = [c for c in result if c["set_code"] == "spg"]
        assert len(spg_only) == 10, (
            "Stale cache without SPG cards should have triggered rebuild; "
            f"got {len(spg_only)} SPG cards"
        )


# ---------------------------------------------------------------------------
# Distinction from FDN SPG 074–083
# ---------------------------------------------------------------------------


class TestSPGDistinctFromFDN:
    """SOS SPG 149–158 are distinct from FDN SPG 074–083."""

    def test_network_response_with_fdn_range_filtered_out(self, tmp_path: Path) -> None:
        """When the network returns SPG 074-083 alongside 149-158, only 149-158 survive.

        This exercises the force/network code path (no cache) with a
        polluted Scryfall response that includes FDN-era collector numbers.
        The implementation must filter them out before merging into the pool.
        """
        polluted_spg = _spg_raw_cards(149, 158) + _spg_raw_cards(74, 83)
        result = _run_fetch(tmp_path, force=True, spg_cards=polluted_spg)
        spg_only = [c for c in result if c["set_code"] == "spg"]
        spg_cns = {int(c["collector_number"]) for c in spg_only}
        fdn_range = set(range(74, 84))
        assert spg_cns.isdisjoint(fdn_range), (
            f"FDN SPG cards (074–083) leaked into SOS pool: {spg_cns & fdn_range}"
        )
        assert spg_cns == set(range(149, 159)), (
            f"Expected exactly SPG 149-158, got {sorted(spg_cns)}"
        )
        assert len(spg_only) == 10

    def test_spg_query_targets_149_158_range(self, tmp_path: Path) -> None:
        """The Scryfall query for SPG must target cn>=149 cn<=158."""
        import benchmarks.sos.fetch_data as mod

        output_path = tmp_path / "sos.json"
        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        sos_raw = _sos_raw_cards(2)
        with open(raw_cache, "w") as f:
            json.dump(sos_raw, f)

        def _fake_fetch_set(code: str, **kw: Any) -> list[Any]:
            raw_cache.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_cache, "w") as fh:
                json.dump(sos_raw, fh)
            return []

        calls: list[tuple[str, str]] = []

        def _capture_query(query: str, set_code: str = "", **kw: Any):
            calls.append((query, set_code))
            if set_code == "soa" or "soa" in query:
                return (_soa_raw_cards(65), [])
            elif set_code == "spg" or "spg" in query:
                return (_spg_raw_cards(), [])
            return ([], [])

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_set", side_effect=_fake_fetch_set),
            patch.object(mod, "fetch_scryfall_query", side_effect=_capture_query),
        ):
            mod.fetch_sos_data(force=True)

        # Find the SPG query call
        spg_calls = [(q, s) for q, s in calls if s == "spg" or "spg" in q]
        assert len(spg_calls) >= 1, "No SPG query was issued"
        spg_query = spg_calls[0][0]
        # Query should reference 149 and 158 (the range boundaries)
        assert "149" in spg_query, f"SPG query missing cn>=149: {spg_query}"
        assert "158" in spg_query, f"SPG query missing cn<=158: {spg_query}"


# ---------------------------------------------------------------------------
# _log_stats with SPG cards
# ---------------------------------------------------------------------------


class TestLogStatsWithSPG:
    """_log_stats should handle SPG cards in the multi-set breakdown."""

    def test_log_stats_with_three_sets(self) -> None:
        from benchmarks.sos.fetch_data import _normalize_card, _log_stats

        cards = [
            _normalize_card(_make_raw_scryfall_card(set_code="sos", collector_number="1")),
            _normalize_card(_make_raw_scryfall_card(set_code="soa", collector_number="1")),
            _normalize_card(_make_raw_scryfall_card(set_code="spg", collector_number="149")),
        ]
        # Should not raise
        _log_stats(cards)
