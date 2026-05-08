"""Tests for TODO item 18: Sort cards by complexity tier for sequential processing.

Tests verify:
- Cards are sorted trivial → simple → medium → complex → expert.
- Within same tier, cards are sorted by collector number ascending.
- Unknown/missing tier sorts after expert (last).
- Empty card list handled correctly.
- Single card works.
- Mixed tiers with various collector numbers sort correctly.
- _TIER_ORDER contains all expected tiers.
- Deterministic: same input always produces same output.
"""

from __future__ import annotations

import pytest

from silverquillm.cli import _sort_cards_by_tier, _TIER_ORDER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card(tier: str, number: str) -> dict:
    """Create a minimal card spec dict."""
    return {"complexity_tier": tier, "collector_number": number}


# ---------------------------------------------------------------------------
# _TIER_ORDER mapping
# ---------------------------------------------------------------------------

class TestTierOrder:
    def test_contains_all_expected_tiers(self):
        expected = {"trivial", "simple", "medium", "complex", "expert"}
        assert set(_TIER_ORDER.keys()) == expected

    def test_trivial_is_lowest(self):
        assert _TIER_ORDER["trivial"] < _TIER_ORDER["simple"]

    def test_ordering_is_monotonically_increasing(self):
        tiers = ["trivial", "simple", "medium", "complex", "expert"]
        for a, b in zip(tiers, tiers[1:]):
            assert _TIER_ORDER[a] < _TIER_ORDER[b], f"{a} should sort before {b}"


# ---------------------------------------------------------------------------
# _sort_cards_by_tier
# ---------------------------------------------------------------------------

class TestSortCardsByTier:
    def test_empty_list(self):
        assert _sort_cards_by_tier([]) == []

    def test_single_card(self):
        cards = [_card("medium", "SQ-042")]
        result = _sort_cards_by_tier(cards)
        assert len(result) == 1
        assert result[0]["collector_number"] == "SQ-042"

    def test_sort_by_tier_trivial_to_expert(self):
        cards = [
            _card("expert", "SQ-001"),
            _card("trivial", "SQ-002"),
            _card("complex", "SQ-003"),
            _card("simple", "SQ-004"),
            _card("medium", "SQ-005"),
        ]
        result = _sort_cards_by_tier(cards)
        tiers = [c["complexity_tier"] for c in result]
        assert tiers == ["trivial", "simple", "medium", "complex", "expert"]

    def test_within_tier_sorted_by_collector_number(self):
        cards = [
            _card("medium", "SQ-030"),
            _card("medium", "SQ-010"),
            _card("medium", "SQ-020"),
        ]
        result = _sort_cards_by_tier(cards)
        numbers = [c["collector_number"] for c in result]
        assert numbers == ["SQ-010", "SQ-020", "SQ-030"]

    def test_unknown_tier_sorts_after_expert(self):
        cards = [
            _card("unknown_tier", "SQ-001"),
            _card("expert", "SQ-002"),
            _card("trivial", "SQ-003"),
        ]
        result = _sort_cards_by_tier(cards)
        tiers = [c["complexity_tier"] for c in result]
        assert tiers == ["trivial", "expert", "unknown_tier"]

    def test_missing_tier_sorts_last(self):
        cards = [
            {"collector_number": "SQ-099"},  # no complexity_tier key
            _card("trivial", "SQ-001"),
        ]
        result = _sort_cards_by_tier(cards)
        assert result[0]["complexity_tier"] == "trivial"
        assert result[1].get("complexity_tier") is None

    def test_mixed_tiers_and_collector_numbers(self):
        cards = [
            _card("complex", "SQ-020"),
            _card("trivial", "SQ-005"),
            _card("complex", "SQ-010"),
            _card("trivial", "SQ-001"),
            _card("simple", "SQ-015"),
        ]
        result = _sort_cards_by_tier(cards)
        expected = [
            ("trivial", "SQ-001"),
            ("trivial", "SQ-005"),
            ("simple", "SQ-015"),
            ("complex", "SQ-010"),
            ("complex", "SQ-020"),
        ]
        actual = [(c["complexity_tier"], c["collector_number"]) for c in result]
        assert actual == expected

    def test_deterministic_output(self):
        cards = [
            _card("medium", "SQ-002"),
            _card("trivial", "SQ-001"),
            _card("expert", "SQ-003"),
            _card("medium", "SQ-004"),
        ]
        results = [_sort_cards_by_tier(list(cards)) for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_does_not_mutate_input(self):
        cards = [
            _card("expert", "SQ-002"),
            _card("trivial", "SQ-001"),
        ]
        original = list(cards)
        _sort_cards_by_tier(cards)
        assert cards == original

    def test_multiple_unknown_tiers_sorted_by_collector(self):
        cards = [
            _card("fictional", "SQ-020"),
            _card("fictional", "SQ-010"),
            _card("also_unknown", "SQ-005"),
        ]
        result = _sort_cards_by_tier(cards)
        numbers = [c["collector_number"] for c in result]
        # All unknown tiers have the same rank, so sorted by collector number
        assert numbers == ["SQ-005", "SQ-010", "SQ-020"]
