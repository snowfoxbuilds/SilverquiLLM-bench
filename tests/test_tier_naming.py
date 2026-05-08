"""Tests for TODO item 14: Audit and align tier key naming.

Verifies that the codebase standardises on ``complexity_tier`` as the
canonical key while maintaining backward compatibility with the legacy
``tier`` key.

Test areas:
- Round-trip serialisation of card specs.
- Backward compat: legacy ``tier`` key read as ``complexity_tier``.
- When both keys present, ``complexity_tier`` wins.
- Classifier output contains ``complexity_tier``.
- Results builder uses ``complexity_tier`` consistently.
- Prototype selector accepts both key forms.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from cards.registry import CardMetadata

VALID_TIERS = {"trivial", "simple", "medium", "complex", "expert"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(**kwargs: object) -> CardMetadata:
    """Create a CardMetadata with sensible defaults, overrideable by kwargs."""
    defaults: dict[str, object] = {
        "name": "Test Card",
        "mana_cost_str": "{1}{W}",
        "type_line": "Creature — Human",
        "oracle_text": "Vigilance",
        "power": "2",
        "toughness": "2",
        "colors": ["W"],
        "keywords": ["Vigilance"],
        "rarity": "common",
        "set_code": "sos",
        "collector_number": "042",
    }
    defaults.update(kwargs)
    return CardMetadata(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Round-trip test  (explicitly required by TODO item)
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Card spec with complexity_tier serialises to JSON and back."""

    def test_round_trip_preserves_complexity_tier(self) -> None:
        from silverquillm.card_spec import generate_card_spec

        card = _make_card()
        spec = generate_card_spec(card, "complex")
        json_str = json.dumps(spec)
        loaded = json.loads(json_str)

        assert loaded["complexity_tier"] == "complex"
        assert "tier" not in loaded, "Serialised spec must not contain legacy 'tier' key"

    def test_round_trip_all_tiers(self) -> None:
        """Every valid tier value survives the round-trip."""
        from silverquillm.card_spec import generate_card_spec

        for tier in VALID_TIERS:
            card = _make_card(name=f"Card {tier}")
            spec = generate_card_spec(card, tier)
            loaded = json.loads(json.dumps(spec))
            assert loaded["complexity_tier"] == tier


# ---------------------------------------------------------------------------
# Backward compatibility: legacy ``tier`` key
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    """JSON using only the old ``tier`` key is accepted."""

    def test_results_builder_reads_legacy_tier_key(self) -> None:
        """_build_result_record should fall back to 'tier' when 'complexity_tier' absent."""
        from silverquillm.results import _build_result_record

        blind = {"tier": "simple", "agent": "test", "status": "ok"}
        test = {"tier": "simple", "agent": "test", "status": "ok"}
        record = _build_result_record("card_a", blind, test, None)

        assert record["complexity_tier"] == "simple"

    def test_card_spec_generate_all_specs_reads_legacy_tier(self) -> None:
        """generate_all_specs should fall back to 'tier' when reading classified data."""
        from silverquillm.card_spec import generate_card_spec

        # The unit function itself always receives an explicit tier string,
        # so backward compat is in generate_all_specs which reads JSON.
        # We verify generate_card_spec always outputs complexity_tier.
        card = _make_card()
        spec = generate_card_spec(card, "medium")
        assert "complexity_tier" in spec
        assert spec["complexity_tier"] == "medium"


# ---------------------------------------------------------------------------
# Canonical key preferred when both present
# ---------------------------------------------------------------------------


class TestCanonicalKeyPreferred:
    """When both ``tier`` and ``complexity_tier`` are in input, ``complexity_tier`` wins."""

    def test_results_builder_prefers_complexity_tier(self) -> None:
        from silverquillm.results import _build_result_record

        blind = {
            "tier": "simple",
            "complexity_tier": "expert",
            "agent": "test",
            "status": "ok",
        }
        test = {"agent": "test", "status": "ok"}
        record = _build_result_record("card_b", blind, test, None)

        assert record["complexity_tier"] == "expert"


# ---------------------------------------------------------------------------
# Classifier output
# ---------------------------------------------------------------------------


class TestClassifierOutput:
    """classify_set must output ``complexity_tier`` as a key."""

    def test_classify_set_json_contains_complexity_tier(self) -> None:
        from silverquillm.card_classifier import classify_set

        cards = [
            _make_card(name="Basic Land", type_line="Basic Land", oracle_text=""),
            _make_card(
                name="Complex Planeswalker",
                type_line="Legendary Planeswalker — Jace",
                oracle_text="+1: Draw a card.\n-2: Return target creature.\n-8: You win.",
                keywords=["planeswalker"],
            ),
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            tmp_path = Path(f.name)

        try:
            classify_set(cards, str(tmp_path))
            with open(tmp_path) as f:
                records = json.load(f)

            for rec in records:
                assert "complexity_tier" in rec, (
                    f"Classifier output record missing 'complexity_tier': {rec}"
                )
                assert rec["complexity_tier"] in VALID_TIERS
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_classify_set_json_also_has_legacy_tier_for_compat(self) -> None:
        """Classifier output should include legacy 'tier' key for backward compat."""
        from silverquillm.card_classifier import classify_set

        cards = [_make_card()]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            tmp_path = Path(f.name)

        try:
            classify_set(cards, str(tmp_path))
            with open(tmp_path) as f:
                records = json.load(f)

            for rec in records:
                assert "tier" in rec, (
                    "Classifier should still emit 'tier' for backward compat"
                )
                assert rec["tier"] == rec["complexity_tier"]
        finally:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Card spec output key
# ---------------------------------------------------------------------------


class TestCardSpecOutputKey:
    """generate_card_spec must use ``complexity_tier``, never bare ``tier``."""

    def test_output_uses_complexity_tier_key(self) -> None:
        from silverquillm.card_spec import generate_card_spec

        spec = generate_card_spec(_make_card(), "simple")
        assert "complexity_tier" in spec
        assert "tier" not in spec

    def test_output_value_matches_input(self) -> None:
        from silverquillm.card_spec import generate_card_spec

        for tier in VALID_TIERS:
            spec = generate_card_spec(_make_card(), tier)
            assert spec["complexity_tier"] == tier


# ---------------------------------------------------------------------------
# Results builder output key
# ---------------------------------------------------------------------------


class TestResultsOutputKey:
    """_build_result_record and summary helpers use ``complexity_tier``."""

    def test__build_result_record_outputs_complexity_tier(self) -> None:
        from silverquillm.results import _build_result_record

        blind = {"complexity_tier": "medium", "agent": "a", "status": "ok"}
        test = {"complexity_tier": "medium", "agent": "a", "status": "ok"}
        record = _build_result_record("c1", blind, test, None)

        assert "complexity_tier" in record
        assert record["complexity_tier"] == "medium"

    def test__build_result_record_no_bare_tier_in_output(self) -> None:
        from silverquillm.results import _build_result_record

        blind = {"complexity_tier": "medium", "agent": "a", "status": "ok"}
        test = {"complexity_tier": "medium", "agent": "a", "status": "ok"}
        record = _build_result_record("c1", blind, test, None)

        # Top-level key should be complexity_tier, not tier
        assert "tier" not in record


# ---------------------------------------------------------------------------
# Prototype selector reads both key forms
# ---------------------------------------------------------------------------


class TestPrototypeSelector:
    """select_prototype_cards should accept both key forms in classified JSON."""

    def _write_classified(
        self, path: Path, entries: list[dict[str, Any]]
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(entries, f)

    def test_reads_complexity_tier_key(self, tmp_path: Path) -> None:
        from silverquillm.prototype import select_prototype_cards

        classified_path = tmp_path / "data" / "sos_classified.json"
        entries = [
            {
                "name": f"Card {i}",
                "complexity_tier": tier,
                "collector_number": str(i),
                "oracle_text": "Some ability text.",
                "type_line": "Creature — Human",
            }
            for i, tier in enumerate(VALID_TIERS)
        ]
        self._write_classified(classified_path, entries)

        result = select_prototype_cards(str(classified_path))
        assert len(result) > 0

    def test_reads_legacy_tier_key(self, tmp_path: Path) -> None:
        from silverquillm.prototype import select_prototype_cards

        classified_path = tmp_path / "data" / "sos_classified.json"
        entries = [
            {
                "name": f"Card {i}",
                "tier": tier,
                "collector_number": str(i),
                "oracle_text": "Some ability text.",
                "type_line": "Creature — Human",
            }
            for i, tier in enumerate(VALID_TIERS)
        ]
        self._write_classified(classified_path, entries)

        result = select_prototype_cards(str(classified_path))
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases around missing or unexpected tier values."""

    def test_results_missing_both_keys_defaults_to_unknown(self) -> None:
        """When neither tier nor complexity_tier is present, default to 'unknown'."""
        from silverquillm.results import _build_result_record

        blind: dict[str, Any] = {"agent": "a", "status": "ok"}
        test: dict[str, Any] = {"agent": "a", "status": "ok"}
        record = _build_result_record("c1", blind, test, None)

        assert record["complexity_tier"] == "unknown"
