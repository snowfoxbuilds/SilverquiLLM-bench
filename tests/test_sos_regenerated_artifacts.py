"""Tests for TODO item 4: Re-run classification and spec generation on updated card pool.

Tests verify:
- sos.json has exactly 346 cards with correct set breakdown (271 SOS + 65 SOA + 10 SPG).
- sos_classified.json has exactly 346 entries, one per card in sos.json.
- Every card in sos_classified.json has a corresponding spec directory under benchmarks/sos/cards/.
- Multi-set disambiguation: SOS/SOA/SPG card directories use distinct naming so they don't collide.
- No stale directories from old cards (cn > 271 SOS) remain.
- NEW_MECHANICS covers required SOS/SOA/SPG mechanics (Prepared, Converge, Miracle, Opus).
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

    def test_soa_count_is_65(self, sos_cards: list[dict]) -> None:
        """SOA Mystical Archives contributes exactly 65 cards."""
        soa_only = [c for c in sos_cards if c.get("set_code") == "soa"]
        assert len(soa_only) == 65

    def test_spg_count_is_10(self, sos_cards: list[dict]) -> None:
        """SPG Special Guests contributes exactly 10 cards."""
        spg_only = [c for c in sos_cards if c.get("set_code") == "spg"]
        assert len(spg_only) == 10

    def test_no_sos_card_above_271(self, sos_cards: list[dict]) -> None:
        """No SOS card should have collector_number > 271."""
        for card in sos_cards:
            if card.get("set_code") == "sos":
                cn = int(card["collector_number"])
                assert cn <= 271, f"SOS card cn={cn} exceeds cutoff"

    def test_spg_collector_numbers_149_to_158(self, sos_cards: list[dict]) -> None:
        """SPG cards should have collector numbers 149-158."""
        spg = [c for c in sos_cards if c.get("set_code") == "spg"]
        cns = sorted(int(c["collector_number"]) for c in spg)
        assert cns == list(range(149, 159))


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

    def test_classified_set_breakdown_matches_pool(self, classified_cards: list[dict]) -> None:
        """Classified cards must have same set breakdown as sos.json."""
        from collections import Counter
        sets = Counter(c.get("set_code") for c in classified_cards)
        assert sets["sos"] == 271
        assert sets["soa"] == 65
        assert sets["spg"] == 10

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
    """Every classified card must have a corresponding spec directory."""

    def test_spec_directory_count_is_346(self) -> None:
        """There should be exactly 346 card spec directories."""
        dirs = [d for d in _CARDS_DIR.iterdir() if d.is_dir()]
        assert len(dirs) == 346, f"Expected 346 spec dirs, found {len(dirs)}"

    def test_every_classified_card_has_spec_dir(self, classified_cards: list[dict]) -> None:
        """Each classified card must map to an existing spec directory."""
        existing_dirs = {d.name for d in _CARDS_DIR.iterdir() if d.is_dir()}
        missing = []
        for card in classified_cards:
            set_code = card.get("set_code", "sos")
            cn = card["collector_number"]
            # Multi-set disambiguation: SOA uses "soa_<cn>", SPG uses "spg_<cn>", SOS uses "sos_<cn>"
            if set_code == "soa":
                expected_dir = f"soa_{cn}"
            elif set_code == "spg":
                expected_dir = f"spg_{cn}"
            else:
                expected_dir = f"sos_{cn}"
            if expected_dir not in existing_dirs:
                missing.append(f"{card.get('name', '?')} -> {expected_dir}")
        assert not missing, f"Missing spec directories: {missing[:10]}"

    def test_each_spec_dir_has_card_spec_json(self, classified_cards: list[dict]) -> None:
        """Each spec directory must contain a card_spec.json file."""
        missing = []
        for card in classified_cards:
            set_code = card.get("set_code", "sos")
            cn = card["collector_number"]
            if set_code == "soa":
                dir_name = f"soa_{cn}"
            elif set_code == "spg":
                dir_name = f"spg_{cn}"
            else:
                dir_name = f"sos_{cn}"
            spec_file = _CARDS_DIR / dir_name / "card_spec.json"
            if not spec_file.exists():
                missing.append(dir_name)
        assert not missing, f"Directories missing card_spec.json: {missing[:10]}"

    def test_soa_dirs_use_soa_prefix(self) -> None:
        """SOA spec directories must use 'soa_' prefix for disambiguation."""
        soa_dirs = [d.name for d in _CARDS_DIR.iterdir() if d.is_dir() and d.name.startswith("soa_")]
        assert len(soa_dirs) == 65, f"Expected 65 soa_* dirs, found {len(soa_dirs)}"

    def test_spg_dirs_use_spg_prefix(self) -> None:
        """SPG spec directories must use 'spg_' prefix for disambiguation."""
        spg_dirs = [d.name for d in _CARDS_DIR.iterdir() if d.is_dir() and d.name.startswith("spg_")]
        assert len(spg_dirs) == 10, f"Expected 10 spg_* dirs, found {len(spg_dirs)}"

    def test_no_stale_sos_dirs_above_271(self) -> None:
        """No SOS spec directory for collector number > 271 should exist."""
        # SOS dirs use sos_N prefix
        for d in _CARDS_DIR.iterdir():
            if d.is_dir() and d.name.startswith("sos_") and d.name[4:].isdigit():
                cn = int(d.name[4:])
                assert cn <= 271, f"Stale SOS spec dir found: {d.name} (cn > 271)"


# ---------------------------------------------------------------------------
# SOA/SPG set identity and metadata consistency
# ---------------------------------------------------------------------------


class TestSoaSpgSetIdentity:
    """SOA/SPG cards must have real names, correct set metadata, and not be mislabeled SOS rows."""

    def test_soa_names_are_not_placeholders(self, sos_cards: list[dict]) -> None:
        """SOA card names must not be placeholder 'Mystical Archive <n>' patterns."""
        import re
        soa = [c for c in sos_cards if c.get("set_code") == "soa"]
        placeholders = [c["name"] for c in soa if re.match(r"Mystical Archive \d+", c["name"])]
        assert not placeholders, f"SOA contains placeholder names: {placeholders[:5]}"

    def test_spg_names_are_not_placeholders(self, sos_cards: list[dict]) -> None:
        """SPG card names must not be placeholder 'Special Guest <n>' patterns."""
        import re
        spg = [c for c in sos_cards if c.get("set_code") == "spg"]
        placeholders = [c["name"] for c in spg if re.match(r"Special Guest \d+", c["name"])]
        assert not placeholders, f"SPG contains placeholder names: {placeholders[:5]}"

    def test_soa_scryfall_uri_points_to_soa(self, sos_cards: list[dict]) -> None:
        """SOA cards' scryfall_uri must reference /card/soa/, not /card/sos/."""
        soa = [c for c in sos_cards if c.get("set_code") == "soa"]
        bad = [c["name"] for c in soa if "scryfall_uri" in c and "/card/sos/" in c["scryfall_uri"]]
        assert not bad, f"SOA cards with scryfall_uri pointing to SOS: {bad[:5]}"

    def test_spg_scryfall_uri_points_to_spg(self, sos_cards: list[dict]) -> None:
        """SPG cards' scryfall_uri must reference /card/spg/, not /card/sos/."""
        spg = [c for c in sos_cards if c.get("set_code") == "spg"]
        bad = [c["name"] for c in spg if "scryfall_uri" in c and "/card/sos/" in c["scryfall_uri"]]
        assert not bad, f"SPG cards with scryfall_uri pointing to SOS: {bad[:5]}"

    def test_soa_set_field_is_soa(self, sos_cards: list[dict]) -> None:
        """SOA cards' 'set' field must be 'soa', not 'sos'."""
        soa = [c for c in sos_cards if c.get("set_code") == "soa"]
        bad = [c["name"] for c in soa if c.get("set") == "sos"]
        assert not bad, f"SOA cards with set='sos': {bad[:5]}"

    def test_spg_set_field_is_spg(self, sos_cards: list[dict]) -> None:
        """SPG cards' 'set' field must be 'spg', not 'sos'."""
        spg = [c for c in sos_cards if c.get("set_code") == "spg"]
        bad = [c["name"] for c in spg if c.get("set") == "sos"]
        assert not bad, f"SPG cards with set='sos': {bad[:5]}"

    def test_soa_collector_numbers_are_1_to_65(self, sos_cards: list[dict]) -> None:
        """SOA cards should have collector numbers in range 1-65."""
        soa = [c for c in sos_cards if c.get("set_code") == "soa"]
        cns = sorted(int(c["collector_number"]) for c in soa)
        assert cns == list(range(1, 66)), f"SOA collector numbers not 1-65: {cns[:5]}...{cns[-5:]}"

    def test_classified_soa_preserves_set_code(self, classified_cards: list[dict]) -> None:
        """Classified SOA entries must retain set_code='soa'."""
        # Find cards that should be SOA by checking collector_number pattern + set_code
        soa = [c for c in classified_cards if c.get("set_code") == "soa"]
        assert len(soa) == 65
        bad = [c["name"] for c in soa if c.get("set_code") != "soa"]
        assert not bad

    def test_classified_spg_preserves_set_code(self, classified_cards: list[dict]) -> None:
        """Classified SPG entries must retain set_code='spg'."""
        spg = [c for c in classified_cards if c.get("set_code") == "spg"]
        assert len(spg) == 10
        bad = [c["name"] for c in spg if c.get("set_code") != "spg"]
        assert not bad


# ---------------------------------------------------------------------------
# Multi-set collision avoidance
# ---------------------------------------------------------------------------


class TestMultiSetDisambiguation:
    """SOS/SOA/SPG directories must not collide even if collector numbers overlap."""

    def test_no_collision_between_sos_and_soa(self) -> None:
        """SOS dirs (sos_N) don't collide with SOA dirs (soa_N)."""
        # SOS dirs: "sos_1", "sos_2", ..., "sos_271"
        # SOA dirs: "soa_1", "soa_2", ..., "soa_65"
        sos_dirs = {d.name for d in _CARDS_DIR.iterdir() if d.is_dir() and d.name.startswith("sos_")}
        soa_dirs = {d.name for d in _CARDS_DIR.iterdir() if d.is_dir() and d.name.startswith("soa_")}
        # They use different naming conventions so intersection must be empty
        assert not sos_dirs & soa_dirs

    def test_total_dirs_equals_sum_of_sets(self) -> None:
        """Total directories = SOS (sos_N) + SOA (soa_N) + SPG (spg_N) = 346."""
        all_dirs = [d for d in _CARDS_DIR.iterdir() if d.is_dir()]
        sos_dirs = [d for d in all_dirs if d.name.startswith("sos_") and d.name[4:].isdigit()]
        soa_dirs = [d for d in all_dirs if d.name.startswith("soa_")]
        spg_dirs = [d for d in all_dirs if d.name.startswith("spg_")]
        assert len(sos_dirs) + len(soa_dirs) + len(spg_dirs) == 346


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

    def test_readme_uses_346(self) -> None:
        """README.md should reference 346 cards."""
        readme = (_REPO_ROOT / "README.md").read_text()
        assert "346" in readme, "README.md should mention 346 cards"
        assert "368" not in readme, "README.md still references old 368 count"

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
