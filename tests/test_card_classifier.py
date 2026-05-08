"""Tests for TODO item 3: Card complexity classifier.

Tests verify:
- classify_card returns valid tier strings for all inputs.
- Basic lands and vanilla creatures classify as "trivial".
- Planeswalkers classify as "expert".
- classify_set groups cards correctly and writes JSON output.
- Every SOS card gets a tier.
- Distribution is non-degenerate (no single tier >60%).
- Edge cases: empty oracle text, minimal metadata, etc.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cards.registry import CardMetadata

REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_TIERS = {"trivial", "simple", "medium", "complex", "expert"}


# ---------------------------------------------------------------------------
# Helpers to build CardMetadata fixtures
# ---------------------------------------------------------------------------

def _make_card(**kwargs: object) -> CardMetadata:
    """Shorthand to create CardMetadata with sensible defaults."""
    defaults: dict[str, object] = {
        "name": "Test Card",
        "mana_cost_str": "",
        "type_line": "",
        "oracle_text": "",
        "power": None,
        "toughness": None,
        "colors": [],
        "keywords": [],
        "rarity": "common",
        "set_code": "sos",
        "collector_number": "999",
    }
    defaults.update(kwargs)
    return CardMetadata(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# classify_card — basic contract
# ---------------------------------------------------------------------------


class TestClassifyCardContract:
    """classify_card must always return a valid tier string."""

    def test_returns_string(self) -> None:
        from silverquillm.card_classifier import classify_card

        card = _make_card(type_line="Creature — Bear", power="2", toughness="2")
        result = classify_card(card)
        assert isinstance(result, str)

    def test_returns_valid_tier(self) -> None:
        from silverquillm.card_classifier import classify_card

        card = _make_card(type_line="Instant", oracle_text="Deal 3 damage to any target.")
        result = classify_card(card)
        assert result in VALID_TIERS, f"Got unexpected tier: {result!r}"


# ---------------------------------------------------------------------------
# classify_card — trivial tier
# ---------------------------------------------------------------------------


class TestClassifyTrivial:
    """Trivial tier: basic lands, vanilla creatures, keyword-only."""

    def test_basic_land_is_trivial(self) -> None:
        from silverquillm.card_classifier import classify_card

        card = _make_card(name="Plains", type_line="Basic Land — Plains", oracle_text="")
        assert classify_card(card) == "trivial"

    def test_vanilla_creature_is_trivial(self) -> None:
        """A creature with no oracle text and no keywords is trivial."""
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Grizzly Bears",
            type_line="Creature — Bear",
            oracle_text="",
            power="2",
            toughness="2",
            keywords=[],
        )
        assert classify_card(card) == "trivial"

    def test_single_evergreen_keyword_creature_is_trivial(self) -> None:
        """Creature with just one evergreen keyword and keyword-only oracle."""
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Flying Creature",
            type_line="Creature — Bird",
            oracle_text="Flying",
            power="1",
            toughness="1",
            keywords=["Flying"],
        )
        assert classify_card(card) == "trivial"


# ---------------------------------------------------------------------------
# classify_card — expert tier
# ---------------------------------------------------------------------------


class TestClassifyExpert:
    """Expert tier: planeswalkers, Miracle."""

    def test_planeswalker_is_expert(self) -> None:
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Test Planeswalker",
            type_line="Legendary Planeswalker — Test",
            oracle_text="+1: Draw a card.\n-2: Deal 3 damage.\n-8: You win the game.",
            keywords=[],
        )
        assert classify_card(card) == "expert"

    def test_miracle_card_is_expert(self) -> None:
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Miracle Spell",
            type_line="Sorcery",
            oracle_text="Miracle {W}\nDestroy all creatures.",
            keywords=["Miracle"],
        )
        assert classify_card(card) == "expert"


# ---------------------------------------------------------------------------
# classify_card — simple tier
# ---------------------------------------------------------------------------


class TestClassifySimple:
    """Simple tier: single straightforward ability."""

    def test_targeted_spell_is_medium(self) -> None:
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Simple Bolt",
            type_line="Instant",
            oracle_text="Deal 3 damage to any target.",
            keywords=[],
        )
        # Targeting is a Medium-tier signal per the TODO spec
        result = classify_card(card)
        assert result == "medium", f"Expected 'medium' for targeted spell, got {result!r}"


# ---------------------------------------------------------------------------
# classify_card — complex tier
# ---------------------------------------------------------------------------


class TestClassifyComplex:
    """Complex tier: multi-step, replacement effects, modal, SOS mechanics."""

    def test_modal_spell_is_complex(self) -> None:
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Modal Charm",
            type_line="Instant",
            oracle_text="Choose one —\n• Counter target spell.\n• Destroy target artifact.",
            keywords=[],
        )
        assert classify_card(card) == "complex"

    def test_replacement_effect_is_complex(self) -> None:
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Replacement Card",
            type_line="Enchantment",
            oracle_text="If a creature would die, exile it instead.",
            keywords=[],
        )
        assert classify_card(card) == "complex"

    def test_converge_mechanic_is_complex(self) -> None:
        """SOS-specific mechanic 'Converge' should bump to at least complex."""
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Converge Card",
            type_line="Creature — Elemental",
            oracle_text="Converge — This creature enters with a +1/+1 counter on it for each color of mana spent to cast it.",
            keywords=["Converge"],
            power="0",
            toughness="0",
        )
        result = classify_card(card)
        assert result in {"complex", "expert"}, f"Expected complex or expert, got {result!r}"


# ---------------------------------------------------------------------------
# classify_set — grouping and output
# ---------------------------------------------------------------------------


class TestClassifySet:
    """classify_set groups cards and writes JSON output."""

    def test_groups_all_cards(self) -> None:
        from silverquillm.card_classifier import classify_set

        cards = [
            _make_card(name="Plains", type_line="Basic Land — Plains"),
            _make_card(name="PW", type_line="Legendary Planeswalker — PW",
                       oracle_text="+1: Draw.\n-7: Win."),
            _make_card(name="Bolt", type_line="Instant",
                       oracle_text="Deal 3 damage to any target."),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "classified.json"
            result = classify_set(cards, output_path=out_path)

            # Every tier key exists
            for tier in VALID_TIERS:
                assert tier in result

            # Total cards across all tiers equals input
            total = sum(len(v) for v in result.values())
            assert total == len(cards)

    def test_writes_valid_json(self) -> None:
        from silverquillm.card_classifier import classify_set

        cards = [
            _make_card(name="Plains", type_line="Basic Land — Plains"),
            _make_card(name="Bolt", type_line="Instant", oracle_text="Damage."),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "classified.json"
            classify_set(cards, output_path=out_path)

            assert out_path.exists()
            data = json.loads(out_path.read_text(encoding="utf-8"))
            assert isinstance(data, list)
            assert len(data) == 2

    def test_json_records_have_required_fields(self) -> None:
        from silverquillm.card_classifier import classify_set

        cards = [_make_card(name="Test", type_line="Instant", oracle_text="Draw a card.")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "classified.json"
            classify_set(cards, output_path=out_path)

            data = json.loads(out_path.read_text(encoding="utf-8"))
            record = data[0]
            assert "name" in record
            assert "tier" in record
            assert record["tier"] in VALID_TIERS

    def test_empty_card_list(self) -> None:
        from silverquillm.card_classifier import classify_set

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "classified.json"
            result = classify_set([], output_path=out_path)

            total = sum(len(v) for v in result.values())
            assert total == 0
            data = json.loads(out_path.read_text(encoding="utf-8"))
            assert data == []


# ---------------------------------------------------------------------------
# SOS integration tests — run against real SOS data
# ---------------------------------------------------------------------------


class TestSOSClassification:
    """Integration: classify all SOS cards and validate distribution."""

    @pytest.fixture()
    def sos_cards(self) -> list[CardMetadata]:
        from silverquillm.card_classifier import load_sos_cards
        return load_sos_cards()

    def test_every_sos_card_gets_a_tier(self, sos_cards: list[CardMetadata]) -> None:
        from silverquillm.card_classifier import classify_card

        for card in sos_cards:
            tier = classify_card(card)
            assert tier in VALID_TIERS, (
                f"Card {card.name!r} got invalid tier {tier!r}"
            )

    def test_no_tier_exceeds_60_percent(self, sos_cards: list[CardMetadata]) -> None:
        """Distribution is non-degenerate: no single tier has >60% of cards."""
        from silverquillm.card_classifier import classify_set

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "classified.json"
            result = classify_set(sos_cards, output_path=out_path)

        total = len(sos_cards)
        assert total > 0, "SOS data should have cards"
        for tier, cards_in_tier in result.items():
            pct = len(cards_in_tier) / total
            assert pct <= 0.60, (
                f"Tier {tier!r} has {len(cards_in_tier)}/{total} cards "
                f"({pct:.1%}), exceeding 60% threshold"
            )

    def test_sos_basic_land_is_trivial(self, sos_cards: list[CardMetadata]) -> None:
        """A known SOS basic land (Plains) should classify as trivial."""
        from silverquillm.card_classifier import classify_card

        plains_cards = [c for c in sos_cards if c.name == "Plains" and "Basic" in c.type_line]
        assert len(plains_cards) >= 1, "SOS data should contain Plains"
        assert classify_card(plains_cards[0]) == "trivial"

    def test_sos_planeswalker_is_expert(self, sos_cards: list[CardMetadata]) -> None:
        """A known SOS planeswalker should classify as expert."""
        from silverquillm.card_classifier import classify_card

        pws = [c for c in sos_cards if "Planeswalker" in c.type_line]
        assert len(pws) >= 1, "SOS data should contain at least one planeswalker"
        for pw in pws:
            assert classify_card(pw) == "expert", (
                f"Planeswalker {pw.name!r} should be expert"
            )

    def test_sos_card_count_matches_data(self, sos_cards: list[CardMetadata]) -> None:
        """classify_set should process all SOS cards."""
        from silverquillm.card_classifier import classify_set

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "classified.json"
            result = classify_set(sos_cards, output_path=out_path)

        total_classified = sum(len(v) for v in result.values())
        assert total_classified == len(sos_cards)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestClassifyEdgeCases:
    """Edge cases: empty fields, unusual metadata."""

    def test_empty_oracle_text_creature(self) -> None:
        """Creature with completely empty oracle text should be trivial."""
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Blank Creature",
            type_line="Creature — Human",
            oracle_text="",
            power="1",
            toughness="1",
        )
        assert classify_card(card) == "trivial"

    def test_card_with_only_reminder_text(self) -> None:
        """Oracle text that's only reminder text in parens should be treated as empty."""
        from silverquillm.card_classifier import classify_card

        card = _make_card(
            name="Reminder Only",
            type_line="Creature — Wall",
            oracle_text="(This creature has no abilities.)",
            power="0",
            toughness="4",
            keywords=[],
        )
        # After stripping reminder text, oracle is empty → trivial
        result = classify_card(card)
        assert result == "trivial"

    def test_all_default_metadata_does_not_crash(self) -> None:
        """CardMetadata with all defaults should not crash classify_card."""
        from silverquillm.card_classifier import classify_card

        card = CardMetadata()
        result = classify_card(card)
        assert result in VALID_TIERS

    def test_tier_weights_has_all_tiers(self) -> None:
        """TIER_WEIGHTS should map every valid tier to a positive int."""
        from silverquillm.card_classifier import TIER_WEIGHTS

        for tier in VALID_TIERS:
            assert tier in TIER_WEIGHTS
            assert isinstance(TIER_WEIGHTS[tier], int)
            assert TIER_WEIGHTS[tier] > 0
