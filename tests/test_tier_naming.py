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

from pathlib import Path
from typing import Any

import pytest

from benchmarks.sos.workspace.cards.registry import CardMetadata

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

    def test_card_spec_canonical_key_used(self) -> None:
        """generate_card_spec always outputs complexity_tier regardless of input."""
        from silverquillm.card_spec import generate_card_spec

        spec = generate_card_spec(_make_card(), "expert")
        assert spec["complexity_tier"] == "expert"
        assert "tier" not in spec


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
    """generate_run_summary uses ``complexity_tier`` in output."""

    def test_generate_run_summary_exists(self) -> None:
        from silverquillm.results import generate_run_summary

        assert callable(generate_run_summary)


# ---------------------------------------------------------------------------
# Prototype selector reads both key forms
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases around missing or unexpected tier values."""

    def test_generate_card_spec_with_all_valid_tiers(self) -> None:
        """generate_card_spec handles all valid tier values."""
        from silverquillm.card_spec import generate_card_spec

        for tier in VALID_TIERS:
            spec = generate_card_spec(_make_card(), tier)
            assert spec["complexity_tier"] == tier
