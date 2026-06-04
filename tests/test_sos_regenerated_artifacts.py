"""Tests for TODO item 4: Re-run classification and spec generation on updated card pool.

Tests verify:
- sos.json has exactly 346 cards (data pool retained for reference).
- sos_classified.json has exactly 346 entries, one per card in sos.json.
- Every classified SOS card has a corresponding spec directory under cards/sos/.
- No stale directories from old cards (cn > 271 SOS) remain.
- NEW_MECHANICS covers required SOS mechanics (Prepared, Converge, Miracle, Opus).
- Documentation references use 346 (not 368) for card count.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BENCHMARKS_SOS = _REPO_ROOT / "benchmarks" / "sos"
_DATA_DIR = _BENCHMARKS_SOS / "data"
_CARDS_DIR = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "sos"
_SOS_JSON = _DATA_DIR / "sos.json"
_CLASSIFIED_JSON = _DATA_DIR / "sos_classified.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sos_cards() -> list[dict]:
    """Load sos.json card pool."""
    assert _SOS_JSON.exists(), f"sos.json not found at {_SOS_JSON}"
    with open(_SOS_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def classified_cards() -> list[dict]:
    """Load sos_classified.json."""
    assert _CLASSIFIED_JSON.exists(), f"sos_classified.json not found at {_CLASSIFIED_JSON}"
    with open(_CLASSIFIED_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# sos.json integrity
# ---------------------------------------------------------------------------


class TestSosJsonIntegrity:
    """sos.json must have exactly 346 cards with correct set composition."""

    def test_total_card_count_is_346(self, sos_cards: list[dict]) -> None:
        """The merged card pool must contain exactly 346 cards."""
        assert len(sos_cards) == 346

    def test_sos_base_count_is_271(self, sos_cards: list[dict]) -> None:
        """SOS base set contributes exactly 271 cards."""
        sos_only = [c for c in sos_cards if c.get("set_code") == "sos"]
        assert len(sos_only) == 271

    def test_no_sos_card_above_271(self, sos_cards: list[dict]) -> None:
        """No SOS card should have collector_number > 271."""
        for card in sos_cards:
            if card.get("set_code") == "sos":
                cn = int(card["collector_number"])
                assert cn <= 271, f"SOS card cn={cn} exceeds cutoff"


# ---------------------------------------------------------------------------
# sos_classified.json integrity
# ---------------------------------------------------------------------------


class TestClassifiedJsonIntegrity:
    """sos_classified.json must have entries for all 346 cards."""

    def test_classified_count_is_346(self, classified_cards: list[dict]) -> None:
        """Classification must cover all 346 cards."""
        assert len(classified_cards) == 346

    def test_every_classified_card_has_complexity_tier(self, classified_cards: list[dict]) -> None:
        """Each classified entry must have a complexity_tier field."""
        for i, card in enumerate(classified_cards):
            assert "complexity_tier" in card, (
                f"Card at index {i} ({card.get('name', '?')}) missing complexity_tier"
            )

    def test_every_classified_card_has_set_code(self, classified_cards: list[dict]) -> None:
        """Each classified entry must have a set_code field."""
        for i, card in enumerate(classified_cards):
            assert "set_code" in card, (
                f"Card at index {i} ({card.get('name', '?')}) missing set_code"
            )

    def test_classified_names_match_pool(self, sos_cards: list[dict], classified_cards: list[dict]) -> None:
        """Every card name in sos.json must appear in sos_classified.json."""
        pool_names = {c["name"] for c in sos_cards}
        classified_names = {c["name"] for c in classified_cards}
        missing = pool_names - classified_names
        assert not missing, f"Cards in pool but not classified: {missing}"


# ---------------------------------------------------------------------------
# Per-card spec directories
# ---------------------------------------------------------------------------


class TestPerCardSpecDirectories:
    """Every classified SOS card must have a corresponding spec directory."""

    def test_spec_directory_count_is_271(self) -> None:
        """There should be exactly 271 card spec directories (SOS base set)."""
        dirs = [
            d for d in _CARDS_DIR.iterdir()
            if d.is_dir() and d.name != "__pycache__"
        ]
        assert len(dirs) == 271, f"Expected 271 spec dirs, found {len(dirs)}"

    def test_every_classified_sos_card_has_spec_dir(self, classified_cards: list[dict]) -> None:
        """Each classified SOS card must map to an existing spec directory."""
        existing_dirs = {d.name for d in _CARDS_DIR.iterdir() if d.is_dir()}
        missing = []
        for card in classified_cards:
            if card.get("set_code", "sos") != "sos":
                continue
            cn = card["collector_number"]
            expected_dir = f"sos_{cn}"
            if expected_dir not in existing_dirs:
                missing.append(f"{card.get('name', '?')} -> {expected_dir}")
        assert not missing, f"Missing spec directories: {missing[:10]}"

    def test_each_sos_spec_dir_has_card_spec_json(self, classified_cards: list[dict]) -> None:
        """Each SOS spec directory must contain a card_spec.json file."""
        missing = []
        for card in classified_cards:
            if card.get("set_code", "sos") != "sos":
                continue
            cn = card["collector_number"]
            dir_name = f"sos_{cn}"
            spec_file = _CARDS_DIR / dir_name / "card_spec.json"
            if not spec_file.exists():
                missing.append(dir_name)
        assert not missing, f"Directories missing card_spec.json: {missing[:10]}"

    def test_no_stale_sos_dirs_above_271(self) -> None:
        """No SOS spec directory for collector number > 271 should exist."""
        # SOS dirs use sos_N prefix
        for d in _CARDS_DIR.iterdir():
            if d.is_dir() and d.name.startswith("sos_") and d.name[4:].isdigit():
                cn = int(d.name[4:])
                assert cn <= 271, f"Stale SOS spec dir found: {d.name} (cn > 271)"


# ---------------------------------------------------------------------------
# NEW_MECHANICS coverage
# ---------------------------------------------------------------------------


class TestNewMechanicsCoverage:
    """NEW_MECHANICS list must cover SOS/SOA/SPG draft-relevant mechanics."""

    def test_new_mechanics_includes_prepared(self) -> None:
        from benchmarks.sos.fetch_data import NEW_MECHANICS
        assert "Prepared" in NEW_MECHANICS

    def test_new_mechanics_includes_converge(self) -> None:
        from benchmarks.sos.fetch_data import NEW_MECHANICS
        assert "Converge" in NEW_MECHANICS

    def test_new_mechanics_includes_miracle(self) -> None:
        from benchmarks.sos.fetch_data import NEW_MECHANICS
        assert "Miracle" in NEW_MECHANICS

    def test_new_mechanics_includes_opus(self) -> None:
        from benchmarks.sos.fetch_data import NEW_MECHANICS
        assert "Opus" in NEW_MECHANICS


# ---------------------------------------------------------------------------
# Documentation card count references
# ---------------------------------------------------------------------------


class TestDocumentationCardCounts:
    """Documentation must reference 346 cards, not the old 368."""


    def test_project_map_uses_346(self) -> None:
        """PROJECT_MAP.md should reference 346 cards."""
        pm = (_REPO_ROOT / "PROJECT_MAP.md").read_text()
        assert "346" in pm, "PROJECT_MAP.md should mention 346 cards"
        assert "368" not in pm, "PROJECT_MAP.md still references old 368 count"

    def test_directory_summary_uses_346(self) -> None:
        """benchmarks/sos/DIRECTORY_SUMMARY.md should reference 346 cards."""
        ds = (_BENCHMARKS_SOS / "DIRECTORY_SUMMARY.md").read_text()
        assert "346" in ds, "DIRECTORY_SUMMARY.md should mention 346 cards"
        assert "368" not in ds, "DIRECTORY_SUMMARY.md still references old 368 count"
