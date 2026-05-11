"""Tests for TODO item 3: Enforce SOS base set draft cutoff at collector number 271.

Tests verify:
- SOS base set cards with collector_number > 271 are excluded from the output.
- The SOS_BASE_MAX_COLLECTOR_NUMBER constant is 271.
- SOA and SPG cards are NOT affected by the SOS cutoff filter.
- Stale cache containing SOS cards > 271 triggers rebuild.
- Final total count = SOS(≤271) + SOA(65) + SPG(10) = 346 cards.
- No card with set_code="sos" and collector_number > 271 appears in output.
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
        "rarity": "common",
    }
    card.update(extra)
    return card


def _sos_raw_cards(start: int = 1, end: int = 271) -> list[dict[str, Any]]:
    """Build SOS base set cards for cn range [start, end]."""
    return [
        _make_raw_scryfall_card(
            name=f"SOS Card {i}", set_code="sos", collector_number=str(i),
        )
        for i in range(start, end + 1)
    ]


def _soa_raw_cards(count: int = 65) -> list[dict[str, Any]]:
    return [
        _make_raw_scryfall_card(
            name=f"SOA Card {i}", set_code="soa", collector_number=str(i),
        )
        for i in range(1, count + 1)
    ]


def _spg_raw_cards(start: int = 149, end: int = 158) -> list[dict[str, Any]]:
    return [
        _make_raw_scryfall_card(
            name=f"SPG Guest {i}", set_code="spg", collector_number=str(i),
        )
        for i in range(start, end + 1)
    ]


def _run_fetch(
    tmp_path: Path,
    sos_cards: list[dict[str, Any]] | None = None,
    soa_count: int = 65,
    spg_cards: list[dict[str, Any]] | None = None,
    *,
    force: bool = False,
    pre_cached_output: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Call fetch_sos_data with all filesystem paths redirected to tmp_path."""
    import benchmarks.sos.fetch_data as mod

    if sos_cards is None:
        sos_cards = _sos_raw_cards(1, 271)
    soa_raw = _soa_raw_cards(soa_count)
    if spg_cards is None:
        spg_cards = _spg_raw_cards()

    output_path = tmp_path / "sos.json"
    raw_cache = tmp_path / "data" / "sets" / "sos.json"

    # Write the SOS raw cache
    raw_cache.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_cache, "w") as f:
        json.dump(sos_cards, f)

    # If there's a pre-cached output, write it
    if pre_cached_output is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(pre_cached_output, f)

    def _mock_fetch_query(query: str, set_code: str = "", **kw: Any):
        if "soa" in query or set_code == "soa":
            return (soa_raw, [])
        elif "spg" in query or set_code == "spg":
            return (spg_cards, [])
        return ([], [])

    def _fake_fetch_set(code: str, **kw: Any) -> list[Any]:
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_cache, "w") as fh:
            json.dump(sos_cards, fh)
        return []

    with (
        patch.object(mod, "OUTPUT_PATH", output_path),
        patch.object(mod, "_REPO_ROOT", tmp_path),
        patch.object(mod, "fetch_set", side_effect=_fake_fetch_set),
        patch.object(mod, "fetch_scryfall_query", side_effect=_mock_fetch_query),
    ):
        return mod.fetch_sos_data(force=force)


# ---------------------------------------------------------------------------
# SOS_BASE_MAX_COLLECTOR_NUMBER constant
# ---------------------------------------------------------------------------


class TestSOSBaseMaxConstant:
    """The cutoff constant must be 271."""

    def test_constant_is_271(self) -> None:
        from benchmarks.sos.fetch_data import SOS_BASE_MAX_COLLECTOR_NUMBER

        assert SOS_BASE_MAX_COLLECTOR_NUMBER == 271


# ---------------------------------------------------------------------------
# SOS base set filtering — cards > 271 excluded
# ---------------------------------------------------------------------------


class TestSOSBaseCutoffFiltering:
    """SOS cards with collector_number > 271 must be excluded from the draft set."""

    def test_sos_cards_above_271_excluded(self, tmp_path: Path) -> None:
        """Cards numbered 272+ (alternate-art reprints) must not appear in output."""
        # Include cards from 1-280 (9 above cutoff)
        sos_cards = _sos_raw_cards(1, 280)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)

        sos_only = [c for c in result if c["set_code"] == "sos"]
        over_cutoff = [c for c in sos_only if int(c["collector_number"]) > 271]
        assert over_cutoff == [], (
            f"Found {len(over_cutoff)} SOS cards above cutoff: "
            f"{[c['collector_number'] for c in over_cutoff]}"
        )

    def test_sos_cards_at_271_included(self, tmp_path: Path) -> None:
        """Card at exactly collector_number 271 should be included (boundary)."""
        sos_cards = _sos_raw_cards(270, 275)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)

        sos_only = [c for c in result if c["set_code"] == "sos"]
        cns = {int(c["collector_number"]) for c in sos_only}
        assert 271 in cns, "Card at cn=271 should be included"

    def test_sos_cards_at_272_excluded(self, tmp_path: Path) -> None:
        """Card at exactly collector_number 272 should be excluded (boundary)."""
        sos_cards = _sos_raw_cards(270, 275)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)

        sos_only = [c for c in result if c["set_code"] == "sos"]
        cns = {int(c["collector_number"]) for c in sos_only}
        assert 272 not in cns, "Card at cn=272 should be excluded"

    def test_no_sos_card_exceeds_271_in_output(self, tmp_path: Path) -> None:
        """No card with set_code='sos' should have collector_number > 271."""
        # Full SOS set: 1-368 (realistic Scryfall response)
        sos_cards = _sos_raw_cards(1, 368)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)

        for card in result:
            if card["set_code"] == "sos":
                cn = int(card["collector_number"])
                assert cn <= 271, (
                    f"SOS card '{card['name']}' with cn={cn} exceeds cutoff 271"
                )

    def test_sos_count_capped_at_271(self, tmp_path: Path) -> None:
        """When raw SOS has 368 cards, output should have exactly 271 SOS cards."""
        sos_cards = _sos_raw_cards(1, 368)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)

        sos_only = [c for c in result if c["set_code"] == "sos"]
        assert len(sos_only) == 271


# ---------------------------------------------------------------------------
# Total card count = 346
# ---------------------------------------------------------------------------


class TestTotalCardCount:
    """Final draft set pool = SOS(271) + SOA(65) + SPG(10) = 346."""

    def test_total_346_cards(self, tmp_path: Path) -> None:
        """With full SOS set (368 raw), cutoff produces exactly 346 output cards."""
        sos_cards = _sos_raw_cards(1, 368)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)
        assert len(result) == 346, (
            f"Expected 346 total cards (271+65+10), got {len(result)}"
        )

    def test_set_breakdown_271_65_10(self, tmp_path: Path) -> None:
        """Verify the exact breakdown by set."""
        sos_cards = _sos_raw_cards(1, 368)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)

        sos_count = sum(1 for c in result if c["set_code"] == "sos")
        soa_count = sum(1 for c in result if c["set_code"] == "soa")
        spg_count = sum(1 for c in result if c["set_code"] == "spg")

        assert sos_count == 271, f"Expected 271 SOS cards, got {sos_count}"
        assert soa_count == 65, f"Expected 65 SOA cards, got {soa_count}"
        assert spg_count == 10, f"Expected 10 SPG cards, got {spg_count}"


# ---------------------------------------------------------------------------
# SOA and SPG not affected by SOS cutoff
# ---------------------------------------------------------------------------


class TestCutoffDoesNotAffectOtherSets:
    """The cn>271 filter applies ONLY to set_code='sos', not SOA or SPG."""

    def test_soa_cards_unaffected_by_sos_cutoff(self, tmp_path: Path) -> None:
        """SOA cards have their own range (1-65) and shouldn't be filtered by 271."""
        sos_cards = _sos_raw_cards(1, 300)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)

        soa_only = [c for c in result if c["set_code"] == "soa"]
        assert len(soa_only) == 65, (
            f"SOA should have all 65 cards regardless of SOS cutoff, got {len(soa_only)}"
        )

    def test_spg_cards_unaffected_by_sos_cutoff(self, tmp_path: Path) -> None:
        """SPG cards (cn 149-158) shouldn't be affected by the SOS 271 cutoff."""
        sos_cards = _sos_raw_cards(1, 300)
        result = _run_fetch(tmp_path, sos_cards=sos_cards, force=True)

        spg_only = [c for c in result if c["set_code"] == "spg"]
        assert len(spg_only) == 10, (
            f"SPG should have all 10 cards regardless of SOS cutoff, got {len(spg_only)}"
        )
        spg_cns = sorted(int(c["collector_number"]) for c in spg_only)
        assert spg_cns == list(range(149, 159))


# ---------------------------------------------------------------------------
# Stale cache detection — SOS cards > 271 in cache
# ---------------------------------------------------------------------------


class TestStaleCacheSOSOverCutoff:
    """A cached output containing SOS cards with cn > 271 is stale and must rebuild."""

    def test_cache_with_sos_over_271_triggers_rebuild(self, tmp_path: Path) -> None:
        """Old cache with SOS cn > 271 must not be returned as-is."""
        from benchmarks.sos.fetch_data import _normalize_card

        # Build a stale cache that has SOS cards up to 368 (pre-cutoff era)
        stale = (
            [_normalize_card(c) for c in _sos_raw_cards(1, 368)]
            + [_normalize_card(c) for c in _soa_raw_cards(65)]
            + [_normalize_card(c) for c in _spg_raw_cards()]
        )
        # This cache has SOA and SPG present but also SOS > 271
        sos_cards = _sos_raw_cards(1, 368)
        result = _run_fetch(
            tmp_path, sos_cards=sos_cards, force=False, pre_cached_output=stale,
        )

        sos_only = [c for c in result if c["set_code"] == "sos"]
        over_cutoff = [c for c in sos_only if int(c["collector_number"]) > 271]
        assert over_cutoff == [], (
            "Cache with SOS cards > 271 should have triggered rebuild; "
            f"still found {len(over_cutoff)} cards above cutoff"
        )

    def test_cache_missing_in_range_sos_card_triggers_rebuild(self, tmp_path: Path) -> None:
        """Cache with SOA+SPG present, no SOS>271, but missing SOS cn=271 is stale."""
        from benchmarks.sos.fetch_data import _normalize_card

        # Build an incomplete SOS subset: 1-270 (missing 271) — 270 SOS cards
        incomplete_sos = [_normalize_card(c) for c in _sos_raw_cards(1, 270)]
        valid_soa = [_normalize_card(c) for c in _soa_raw_cards(65)]
        valid_spg = [_normalize_card(c) for c in _spg_raw_cards()]
        stale_cache = incomplete_sos + valid_soa + valid_spg

        # Verify precondition: cache has 270+65+10=345, no SOS>271
        assert len(stale_cache) == 345
        assert all(
            int(c["collector_number"]) <= 271
            for c in stale_cache
            if c["set_code"] == "sos"
        )

        # Feed complete SOS (1-271) as raw source for rebuild
        sos_cards = _sos_raw_cards(1, 271)
        result = _run_fetch(
            tmp_path, sos_cards=sos_cards, force=False, pre_cached_output=stale_cache,
        )

        # After rebuild, the result must have all 271 SOS cards
        sos_only = [c for c in result if c["set_code"] == "sos"]
        assert len(sos_only) == 271, (
            f"Cache missing cn=271 should trigger rebuild; got {len(sos_only)} SOS cards"
        )
        sos_cns = sorted(int(c["collector_number"]) for c in sos_only)
        assert 271 in sos_cns, "Rebuilt result must include SOS cn=271"
        assert len(result) == 346, (
            f"Rebuilt pool should be 346 total, got {len(result)}"
        )

    def test_cache_with_duplicate_soa_rows_triggers_rebuild(self, tmp_path: Path) -> None:
        """Cache with exact SOS 1-271, exact SPG 149-158, but duplicate SOA rows is stale."""
        from benchmarks.sos.fetch_data import _normalize_card

        # Build cache with exact SOS and SPG, but SOA has duplicates (66 rows instead of 65)
        valid_sos = [_normalize_card(c) for c in _sos_raw_cards(1, 271)]
        valid_spg = [_normalize_card(c) for c in _spg_raw_cards()]
        # SOA with a duplicate: 1-65 plus one extra copy of card 1
        soa_cards = [_normalize_card(c) for c in _soa_raw_cards(65)]
        duplicate_soa = soa_cards + [soa_cards[0].copy()]  # duplicate row
        stale_cache = valid_sos + duplicate_soa + valid_spg

        # Precondition: cache has 271 + 66 + 10 = 347 cards (one extra SOA)
        assert len(stale_cache) == 347

        # Feed correct data for rebuild
        sos_cards = _sos_raw_cards(1, 271)
        result = _run_fetch(
            tmp_path, sos_cards=sos_cards, force=False, pre_cached_output=stale_cache,
        )

        # After rebuild, exactly 346 cards with correct SOA count
        assert len(result) == 346, (
            f"Cache with duplicate SOA should trigger rebuild; got {len(result)} total"
        )
        soa_only = [c for c in result if c["set_code"] == "soa"]
        assert len(soa_only) == 65, (
            f"Rebuilt pool should have exactly 65 SOA cards, got {len(soa_only)}"
        )

    def test_cache_with_extra_soa_rows_triggers_rebuild(self, tmp_path: Path) -> None:
        """Cache with exact SOS 1-271, exact SPG 149-158, but extra SOA (cn 66) is stale."""
        from benchmarks.sos.fetch_data import _normalize_card

        # Build cache with exact SOS and SPG, but SOA has an extra card (cn 66)
        valid_sos = [_normalize_card(c) for c in _sos_raw_cards(1, 271)]
        valid_spg = [_normalize_card(c) for c in _spg_raw_cards()]
        # SOA 1-65 plus an extra card at cn=66
        soa_cards = [_normalize_card(c) for c in _soa_raw_cards(65)]
        extra_soa_card = _normalize_card(
            _make_raw_scryfall_card(name="Extra SOA", set_code="soa", collector_number="66")
        )
        bad_soa = soa_cards + [extra_soa_card]
        stale_cache = valid_sos + bad_soa + valid_spg

        # Precondition: cache has 271 + 66 + 10 = 347 cards
        assert len(stale_cache) == 347

        # Feed correct data for rebuild
        sos_cards = _sos_raw_cards(1, 271)
        result = _run_fetch(
            tmp_path, sos_cards=sos_cards, force=False, pre_cached_output=stale_cache,
        )

        # After rebuild, exactly 346 cards
        assert len(result) == 346, (
            f"Cache with extra SOA card should trigger rebuild; got {len(result)} total"
        )
        soa_only = [c for c in result if c["set_code"] == "soa"]
        assert len(soa_only) == 65, (
            f"Rebuilt pool should have exactly 65 SOA cards, got {len(soa_only)}"
        )

    def test_clean_cache_without_sos_over_271_not_rebuilt(self, tmp_path: Path) -> None:
        """A cache with SOS ≤ 271, SOA 65, SPG 10 is fresh — no rebuild needed."""
        import benchmarks.sos.fetch_data as mod
        from benchmarks.sos.fetch_data import _normalize_card

        # Build a valid cache (all SOS ≤ 271)
        valid_cache = (
            [_normalize_card(c) for c in _sos_raw_cards(1, 271)]
            + [_normalize_card(c) for c in _soa_raw_cards(65)]
            + [_normalize_card(c) for c in _spg_raw_cards()]
        )
        output_path = tmp_path / "sos.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(valid_cache, f)

        mock_fetch_query = MagicMock()

        with (
            patch.object(mod, "OUTPUT_PATH", output_path),
            patch.object(mod, "_REPO_ROOT", tmp_path),
            patch.object(mod, "fetch_scryfall_query", mock_fetch_query),
        ):
            result = mod.fetch_sos_data(force=False)

        # Should return cached data without calling any fetch functions
        mock_fetch_query.assert_not_called()
        assert len(result) == 346


# ---------------------------------------------------------------------------
# Output JSON on disk — no SOS > 271
# ---------------------------------------------------------------------------


class TestOutputJsonNoCutoffViolation:
    """The written sos.json must never contain SOS cards above cutoff."""

    def test_persisted_json_has_no_sos_above_271(self, tmp_path: Path) -> None:
        """After fetch_sos_data writes output, verify the on-disk file is clean."""
        import benchmarks.sos.fetch_data as mod

        output_path = tmp_path / "sos.json"
        raw_cache = tmp_path / "data" / "sets" / "sos.json"
        raw_cache.parent.mkdir(parents=True, exist_ok=True)
        sos_cards = _sos_raw_cards(1, 368)
        with open(raw_cache, "w") as f:
            json.dump(sos_cards, f)

        def _fake_fetch_set(code: str, **kw: Any) -> list[Any]:
            raw_cache.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_cache, "w") as fh:
                json.dump(sos_cards, fh)
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

        for card in on_disk:
            if card.get("set_code") == "sos":
                cn = int(card["collector_number"])
                assert cn <= 271, (
                    f"On-disk sos.json contains SOS card cn={cn} above cutoff"
                )
