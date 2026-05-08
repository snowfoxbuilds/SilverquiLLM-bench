"""Tests for TODO item 15: Prototype card selection + engine gap analysis.

Tests verify:
- select_prototype_cards returns exactly 5 cards (one per tier).
- Each returned card has the correct tier assignment from TIERS.
- Tier preference logic (vanilla creature for trivial, keyword for simple, etc.).
- analyze_engine_gaps returns a list of gap strings.
- Gap analysis correctly identifies missing mechanics (Prepared, Converge, Miracle).
- Gap analysis recognizes existing mechanics (Opus/modal spells).
- write_prototype_artifacts produces valid JSON and MD files.
- Edge cases: missing classified file, empty tiers.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from silverquillm.prototype import (
    TIERS,
    analyze_engine_gaps,
    select_prototype_cards,
    write_prototype_artifacts,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _make_classified_and_full_data(
    tmp_path: Path,
    classified: list[dict],
    full_cards: list[dict] | None = None,
) -> str:
    """Write classified JSON (and optional sos.json) and return the path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    classified_path = data_dir / "sos_classified.json"
    classified_path.write_text(json.dumps(classified))

    if full_cards is not None:
        sos_path = data_dir / "sos.json"
        sos_path.write_text(json.dumps(full_cards))

    return str(classified_path)


def _build_card(
    name: str,
    tier: str,
    type_line: str = "",
    oracle_text: str = "",
    mana_cost: str = "",
    collector_number: str = "1",
) -> tuple[dict, dict]:
    """Return (classified_entry, full_card) pair."""
    classified = {"name": name, "tier": tier}
    full = {
        "name": name,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "mana_cost": mana_cost,
        "collector_number": collector_number,
    }
    return classified, full


# ---------------------------------------------------------------------------
# select_prototype_cards
# ---------------------------------------------------------------------------

class TestSelectPrototypeCards:
    """Tests for select_prototype_cards function."""

    def test_returns_exactly_five_cards_one_per_tier(self, tmp_path: Path) -> None:
        """With one card in each tier, exactly 5 cards should be returned."""
        classified = []
        full_cards = []
        for i, tier in enumerate(TIERS):
            c, f = _build_card(
                f"Card {tier.title()}",
                tier,
                type_line="Creature — Human",
                oracle_text=f"ability {i}",
            )
            classified.append(c)
            full_cards.append(f)

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        assert len(result) == 5
        result_tiers = [c["tier"] for c in result]
        assert result_tiers == TIERS

    def test_each_card_has_correct_tier(self, tmp_path: Path) -> None:
        """Each returned card's tier field must match the tier it was classified in."""
        classified = []
        full_cards = []
        for tier in TIERS:
            c, f = _build_card(f"Card {tier}", tier, type_line="Creature — Elf")
            classified.append(c)
            full_cards.append(f)

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        for card in result:
            assert card["tier"] in TIERS
            assert card["name"] == f"Card {card['tier']}"

    def test_trivial_prefers_vanilla_creature(self, tmp_path: Path) -> None:
        """Trivial tier should prefer a Creature over a non-creature."""
        classified = [
            {"name": "Some Enchantment", "tier": "trivial"},
            {"name": "Vanilla Bear", "tier": "trivial"},
        ]
        full_cards = [
            {"name": "Some Enchantment", "type_line": "Enchantment", "oracle_text": ""},
            {"name": "Vanilla Bear", "type_line": "Creature — Bear", "oracle_text": ""},
        ]
        # Fill other tiers so we get 5 total
        for tier in TIERS[1:]:
            classified.append({"name": f"Filler {tier}", "tier": tier})
            full_cards.append({"name": f"Filler {tier}", "type_line": "Creature — Elf", "oracle_text": ""})

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        trivial_card = [c for c in result if c["tier"] == "trivial"][0]
        assert trivial_card["name"] == "Vanilla Bear"

    def test_medium_prefers_targeted_spell(self, tmp_path: Path) -> None:
        """Medium tier should prefer a card with 'target' in oracle text."""
        classified = [
            {"name": "No Target", "tier": "medium"},
            {"name": "Targeted Bolt", "tier": "medium"},
        ]
        full_cards = [
            {"name": "No Target", "type_line": "Sorcery", "oracle_text": "Draw a card."},
            {"name": "Targeted Bolt", "type_line": "Instant", "oracle_text": "Deal 3 damage to target creature."},
        ]
        for tier in [t for t in TIERS if t != "medium"]:
            classified.append({"name": f"Filler {tier}", "tier": tier})
            full_cards.append({"name": f"Filler {tier}", "type_line": "Creature — Elf", "oracle_text": ""})

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        medium_card = [c for c in result if c["tier"] == "medium"][0]
        assert medium_card["name"] == "Targeted Bolt"

    def test_complex_prefers_sos_mechanic(self, tmp_path: Path) -> None:
        """Complex tier should prefer a card with Prepared, Converge, or Opus."""
        classified = [
            {"name": "Boring Complex", "tier": "complex"},
            {"name": "Converge Spell", "tier": "complex"},
        ]
        full_cards = [
            {"name": "Boring Complex", "type_line": "Creature", "oracle_text": "Flying, lifelink"},
            {"name": "Converge Spell", "type_line": "Sorcery", "oracle_text": "Converge — Deal damage equal to colors spent."},
        ]
        for tier in [t for t in TIERS if t != "complex"]:
            classified.append({"name": f"Filler {tier}", "tier": tier})
            full_cards.append({"name": f"Filler {tier}", "type_line": "Creature — Elf", "oracle_text": ""})

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        complex_card = [c for c in result if c["tier"] == "complex"][0]
        assert complex_card["name"] == "Converge Spell"

    def test_expert_prefers_planeswalker_or_miracle(self, tmp_path: Path) -> None:
        """Expert tier should prefer a Planeswalker or Miracle card."""
        classified = [
            {"name": "Normal Expert", "tier": "expert"},
            {"name": "Big Walker", "tier": "expert"},
        ]
        full_cards = [
            {"name": "Normal Expert", "type_line": "Creature", "oracle_text": "Complex abilities"},
            {"name": "Big Walker", "type_line": "Legendary Planeswalker — Jace", "oracle_text": "+1: Draw a card"},
        ]
        for tier in [t for t in TIERS if t != "expert"]:
            classified.append({"name": f"Filler {tier}", "tier": tier})
            full_cards.append({"name": f"Filler {tier}", "type_line": "Creature — Elf", "oracle_text": ""})

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        expert_card = [c for c in result if c["tier"] == "expert"][0]
        assert expert_card["name"] == "Big Walker"

    def test_returns_required_fields(self, tmp_path: Path) -> None:
        """Each selected card must have name, tier, rationale, and card fields."""
        classified = []
        full_cards = []
        for tier in TIERS:
            c, f = _build_card(f"Card {tier}", tier, type_line="Creature", oracle_text="Some text")
            classified.append(c)
            full_cards.append(f)

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        required_keys = {"name", "tier", "rationale", "type_line", "oracle_text", "mana_cost"}
        for card in result:
            assert required_keys.issubset(card.keys()), f"Missing keys in {card}"

    def test_empty_tier_produces_fewer_than_five(self, tmp_path: Path) -> None:
        """If a tier has no cards, the result should have fewer than 5 cards."""
        classified = []
        full_cards = []
        # Only populate 4 tiers, skip "expert"
        for tier in TIERS[:4]:
            c, f = _build_card(f"Card {tier}", tier, type_line="Creature")
            classified.append(c)
            full_cards.append(f)

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        assert len(result) == 4
        result_tiers = {c["tier"] for c in result}
        assert "expert" not in result_tiers

    def test_missing_classified_file_raises(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for a nonexistent classified path."""
        with pytest.raises(FileNotFoundError):
            select_prototype_cards(str(tmp_path / "nonexistent.json"))

    def test_no_sos_json_with_enriched_classified_returns_five(self, tmp_path: Path) -> None:
        """Without sos.json, enriched classified entries (with oracle_text) still yield 5 cards."""
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True)
        classified_path = data_dir / "sos_classified.json"
        # Provide enriched classified entries that contain oracle_text so the
        # function can select one card per tier without needing sos.json.
        classified = [
            {"name": f"Card {t}", "tier": t, "oracle_text": "Flying", "type_line": "Creature"}
            for t in TIERS
        ]
        classified_path.write_text(json.dumps(classified))
        # No sos.json written — function should still work from classified data alone

        result = select_prototype_cards(str(classified_path))
        # Contract: exactly 5 cards, one per tier
        assert len(result) == 5
        result_tiers = [c["tier"] for c in result]
        assert set(result_tiers) == set(TIERS)

    def test_no_duplicate_names(self, tmp_path: Path) -> None:
        """Selected cards should never have duplicate names."""
        classified = []
        full_cards = []
        for tier in TIERS:
            for i in range(3):
                c, f = _build_card(f"Card {tier} {i}", tier, type_line="Creature")
                classified.append(c)
                full_cards.append(f)

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path)

        names = [c["name"] for c in result]
        assert len(names) == len(set(names))

    def test_count_per_tier_greater_than_one(self, tmp_path: Path) -> None:
        """count_per_tier=2 should select up to 2 cards per tier."""
        classified = []
        full_cards = []
        for tier in TIERS:
            for i in range(3):
                c, f = _build_card(f"Card {tier} {i}", tier, type_line="Creature")
                classified.append(c)
                full_cards.append(f)

        path = _make_classified_and_full_data(tmp_path, classified, full_cards)
        result = select_prototype_cards(path, count_per_tier=2)

        assert len(result) == 10  # 2 per tier * 5 tiers


# ---------------------------------------------------------------------------
# analyze_engine_gaps
# ---------------------------------------------------------------------------

class TestAnalyzeEngineGaps:
    """Tests for analyze_engine_gaps function."""

    def test_returns_list_of_strings(self, tmp_path: Path) -> None:
        """Return type should always be a list of strings."""
        cards = [{"oracle_text": "Some ability", "type_line": "Creature"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    def test_prepared_gap_when_missing(self, tmp_path: Path) -> None:
        """Should report gap for Prepared when engine/types.py lacks PREPARED."""
        types_py = tmp_path / "types.py"
        types_py.write_text("class Keyword:\n    FLYING = 'flying'\n")

        cards = [{"oracle_text": "Prepared — Do something", "type_line": "Creature"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert any("PREPARED" in gap and "types.py" in gap for gap in result)

    def test_prepared_no_gap_when_present(self, tmp_path: Path) -> None:
        """Should NOT report Prepared gap when PREPARED exists in types.py."""
        types_py = tmp_path / "types.py"
        types_py.write_text("class Keyword:\n    PREPARED = 'prepared'\n")

        cards = [{"oracle_text": "Prepared — Do something", "type_line": "Creature"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert not any("PREPARED" in gap for gap in result)

    def test_converge_gap_when_missing_color_tracking(self, tmp_path: Path) -> None:
        """Should report gap for Converge when mana.py lacks color tracking."""
        mana_py = tmp_path / "mana.py"
        mana_py.write_text("class ManaPool:\n    pass\n")

        cards = [{"oracle_text": "Converge — Effect based on colors", "type_line": "Sorcery"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert any("Converge" in gap and "mana" in gap.lower() for gap in result)

    def test_converge_no_gap_when_color_tracking_present(self, tmp_path: Path) -> None:
        """Should NOT report Converge gap when colors_spent exists in mana.py."""
        mana_py = tmp_path / "mana.py"
        mana_py.write_text("class ManaPool:\n    colors_spent = []\n")

        cards = [{"oracle_text": "Converge — Effect based on colors", "type_line": "Sorcery"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert not any("Converge" in gap for gap in result)

    def test_miracle_gap_when_missing(self, tmp_path: Path) -> None:
        """Should report gap for Miracle when casting.py lacks miracle support."""
        casting_py = tmp_path / "casting.py"
        casting_py.write_text("def cast_spell(): pass\n")
        triggers_py = tmp_path / "triggers.py"
        triggers_py.write_text("DRAWS_CARD = 'draws_card'\n")

        cards = [{"oracle_text": "Miracle {W}", "type_line": "Sorcery"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert any("Miracle" in gap or "miracle" in gap for gap in result)

    def test_miracle_no_gap_when_present(self, tmp_path: Path) -> None:
        """Should NOT report Miracle gap when casting.py has miracle support."""
        casting_py = tmp_path / "casting.py"
        casting_py.write_text("def cast_with_miracle(): pass\n")

        cards = [{"oracle_text": "Miracle {W}", "type_line": "Sorcery"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert not any("Miracle" in gap for gap in result)

    def test_opus_gap_when_missing_get_modes(self, tmp_path: Path) -> None:
        """Should report gap for Opus when card.py lacks get_modes."""
        card_py = tmp_path / "card.py"
        card_py.write_text("class Card:\n    pass\n")

        cards = [{"oracle_text": "Opus — Choose two", "type_line": "Sorcery"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert any("Opus" in gap and "get_modes" in gap for gap in result)

    def test_opus_no_gap_when_get_modes_present(self, tmp_path: Path) -> None:
        """Should NOT report Opus gap when card.py has get_modes."""
        card_py = tmp_path / "card.py"
        card_py.write_text("class Card:\n    def get_modes(self): pass\n")

        cards = [{"oracle_text": "Opus — Choose two", "type_line": "Sorcery"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert not any("Opus" in gap for gap in result)

    def test_no_gaps_for_vanilla_cards(self, tmp_path: Path) -> None:
        """Vanilla creatures with no special mechanics should produce no gaps."""
        cards = [{"oracle_text": "", "type_line": "Creature — Bear"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))
        assert result == []

    def test_multiple_gaps_detected(self, tmp_path: Path) -> None:
        """Multiple missing mechanics should all appear in the gap list."""
        # Create empty engine files
        (tmp_path / "types.py").write_text("")
        (tmp_path / "mana.py").write_text("")
        (tmp_path / "casting.py").write_text("")
        (tmp_path / "card.py").write_text("")

        cards = [
            {"oracle_text": "Prepared — Effect", "type_line": "Creature"},
            {"oracle_text": "Converge — Colors matter", "type_line": "Sorcery"},
            {"oracle_text": "Miracle {1}{W}", "type_line": "Instant"},
            {"oracle_text": "Opus — Choose modes", "type_line": "Sorcery"},
        ]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert len(result) >= 3  # At least Prepared, Converge, Opus/Miracle

    def test_planeswalker_gap_when_missing(self, tmp_path: Path) -> None:
        """Should report planeswalker gap when engine lacks loyalty support."""
        (tmp_path / "card.py").write_text("class Card: pass")
        (tmp_path / "types.py").write_text("class CardType: pass")

        cards = [{"oracle_text": "+1: Draw a card", "type_line": "Legendary Planeswalker — Jace"}]
        result = analyze_engine_gaps(cards, engine_dir=str(tmp_path))

        assert any("planeswalker" in gap.lower() or "loyalty" in gap.lower() for gap in result)

    def test_engine_dir_with_real_engine(self) -> None:
        """Running against the real engine directory should return a list (possibly with gaps)."""
        engine_dir = str(REPO_ROOT / "engine")
        cards = [{"oracle_text": "Flying", "type_line": "Creature — Bird"}]
        result = analyze_engine_gaps(cards, engine_dir=engine_dir)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# write_prototype_artifacts
# ---------------------------------------------------------------------------

class TestWritePrototypeArtifacts:
    """Tests for write_prototype_artifacts function."""

    def test_creates_json_and_md_files(self, tmp_path: Path) -> None:
        """Should create both prototype_cards.json and prototype_gaps.md."""
        cards = [{"name": "Test Card", "tier": "trivial", "type_line": "Creature", "mana_cost": "{1}", "oracle_text": ""}]
        gaps = ["Missing feature X"]

        json_path, md_path = write_prototype_artifacts(cards, gaps, output_dir=str(tmp_path))

        assert os.path.exists(json_path)
        assert os.path.exists(md_path)
        assert json_path.endswith("prototype_cards.json")
        assert md_path.endswith("prototype_gaps.md")

    def test_json_is_valid(self, tmp_path: Path) -> None:
        """prototype_cards.json should be valid JSON matching the input cards."""
        cards = [
            {"name": "Card A", "tier": "trivial", "type_line": "Creature", "mana_cost": "", "oracle_text": ""},
            {"name": "Card B", "tier": "simple", "type_line": "Instant", "mana_cost": "{U}", "oracle_text": "Draw"},
        ]
        json_path, _ = write_prototype_artifacts(cards, [], output_dir=str(tmp_path))

        with open(json_path) as f:
            loaded = json.load(f)

        assert len(loaded) == 2
        assert loaded[0]["name"] == "Card A"
        assert loaded[1]["name"] == "Card B"

    def test_md_contains_gaps(self, tmp_path: Path) -> None:
        """prototype_gaps.md should list each gap."""
        cards = [{"name": "Card A", "tier": "trivial", "type_line": "", "mana_cost": "", "oracle_text": ""}]
        gaps = ["Missing feature X", "Missing feature Y"]

        _, md_path = write_prototype_artifacts(cards, gaps, output_dir=str(tmp_path))

        content = Path(md_path).read_text()
        assert "Missing feature X" in content
        assert "Missing feature Y" in content

    def test_md_contains_none_when_no_gaps(self, tmp_path: Path) -> None:
        """prototype_gaps.md should say 'none' when there are no gaps."""
        cards = [{"name": "Card A", "tier": "trivial", "type_line": "", "mana_cost": "", "oracle_text": ""}]

        _, md_path = write_prototype_artifacts(cards, [], output_dir=str(tmp_path))

        content = Path(md_path).read_text()
        assert "none" in content.lower()

    def test_md_contains_card_names(self, tmp_path: Path) -> None:
        """prototype_gaps.md should list each card by name and tier."""
        cards = [
            {"name": "Vanilla Bear", "tier": "trivial", "type_line": "Creature", "mana_cost": "{1}{G}", "oracle_text": ""},
            {"name": "Expert Walker", "tier": "expert", "type_line": "Planeswalker", "mana_cost": "{3}{U}", "oracle_text": "+1: Draw"},
        ]

        _, md_path = write_prototype_artifacts(cards, [], output_dir=str(tmp_path))

        content = Path(md_path).read_text()
        assert "Vanilla Bear" in content
        assert "Expert Walker" in content
        assert "trivial" in content
        assert "expert" in content


# ---------------------------------------------------------------------------
# TIERS constant
# ---------------------------------------------------------------------------

class TestTiersConstant:
    """Verify the TIERS list is correct."""

    def test_tiers_has_five_entries(self) -> None:
        assert len(TIERS) == 5

    def test_tiers_order(self) -> None:
        assert TIERS == ["trivial", "simple", "medium", "complex", "expert"]
