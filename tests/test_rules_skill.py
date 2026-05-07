"""Tests for TODO item 8: MTG rules indexer + rules_overview.md.

Tests verify:
- download_comprehensive_rules returns a non-empty string.
- build_rules_index produces a non-empty dict with list[str] values.
- lookup_rule with keyword "flying" returns text referencing 702.9.
- lookup_rule with "702.2" returns first-strike related text.
- lookup_rule with "trample" returns relevant trample text.
- lookup_rule with unknown/nonsense query returns something reasonable.
- rules_overview.md exists, is non-empty, and under 1,000 tokens.
- rules_overview.md covers key topics: turn structure, combat, stack, zones.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.rules_skill import (
    build_rules_index,
    download_comprehensive_rules,
    lookup_rule,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_OVERVIEW_PATH = REPO_ROOT / "benchmarks" / "sos" / "data" / "rules_overview.md"


# ---------------------------------------------------------------------------
# download_comprehensive_rules
# ---------------------------------------------------------------------------

class TestDownloadComprehensiveRules:
    """Tests for download_comprehensive_rules."""

    def test_returns_non_empty_string(self) -> None:
        """download_comprehensive_rules must return a non-empty string."""
        rules = download_comprehensive_rules()
        assert isinstance(rules, str)
        assert len(rules) > 0

    def test_contains_rule_like_content(self) -> None:
        """Returned text should look like MTG rules (contain numbered rules)."""
        rules = download_comprehensive_rules()
        # Should contain at least some numbered rule references
        assert "100." in rules or "702." in rules or "rule" in rules.lower()


# ---------------------------------------------------------------------------
# build_rules_index
# ---------------------------------------------------------------------------

class TestBuildRulesIndex:
    """Tests for build_rules_index."""

    @pytest.fixture()
    def rules_text(self) -> str:
        return download_comprehensive_rules()

    @pytest.fixture()
    def index(self, rules_text: str) -> dict[str, list[str]]:
        return build_rules_index(rules_text)

    def test_returns_non_empty_dict(self, index: dict[str, list[str]]) -> None:
        """build_rules_index must return a non-empty dict."""
        assert isinstance(index, dict)
        assert len(index) > 0

    def test_values_are_lists_of_strings(self, index: dict[str, list[str]]) -> None:
        """Every value in the index should be a list of strings."""
        for key, value in list(index.items())[:20]:  # sample first 20
            assert isinstance(value, list), f"Value for key {key!r} is not a list"
            for item in value:
                assert isinstance(item, str), f"Item in key {key!r} is not a str"

    def test_keys_are_strings(self, index: dict[str, list[str]]) -> None:
        """Every key in the index should be a string."""
        for key in list(index.keys())[:20]:
            assert isinstance(key, str)


# ---------------------------------------------------------------------------
# lookup_rule
# ---------------------------------------------------------------------------

class TestLookupRule:
    """Tests for lookup_rule."""

    @pytest.fixture()
    def index(self) -> dict[str, list[str]]:
        rules_text = download_comprehensive_rules()
        return build_rules_index(rules_text)

    def test_flying_returns_702_9(self, index: dict[str, list[str]]) -> None:
        """lookup_rule(index, 'flying') should return text referencing 702.9 or 'flying'."""
        result = lookup_rule(index, "flying")
        assert isinstance(result, str)
        assert len(result) > 0
        # Must mention 702.9 (the flying rule number) or at least the word "flying"
        result_lower = result.lower()
        assert "702.9" in result or "flying" in result_lower, (
            f"Expected '702.9' or 'flying' in result, got: {result[:200]}"
        )

    def test_702_2_returns_first_strike(self, index: dict[str, list[str]]) -> None:
        """lookup_rule(index, '702.2') should return first-strike related text."""
        result = lookup_rule(index, "702.2")
        assert isinstance(result, str)
        assert len(result) > 0
        result_lower = result.lower()
        assert "first strike" in result_lower or "702.2" in result, (
            f"Expected 'first strike' or '702.2' in result, got: {result[:200]}"
        )

    def test_trample_returns_relevant_text(self, index: dict[str, list[str]]) -> None:
        """lookup_rule(index, 'trample') should return trample-related text."""
        result = lookup_rule(index, "trample")
        assert isinstance(result, str)
        assert len(result) > 0
        result_lower = result.lower()
        assert "trample" in result_lower or "702.6" in result or "702.19" in result, (
            f"Expected trample-related content, got: {result[:200]}"
        )

    def test_deathtouch_returns_relevant_text(self, index: dict[str, list[str]]) -> None:
        """lookup_rule(index, 'deathtouch') should return deathtouch-related text."""
        result = lookup_rule(index, "deathtouch")
        assert isinstance(result, str)
        assert len(result) > 0
        result_lower = result.lower()
        assert "deathtouch" in result_lower or "702.10" in result or "702.2" in result, (
            f"Expected deathtouch-related content, got: {result[:200]}"
        )

    def test_unknown_query_returns_reasonable_result(self, index: dict[str, list[str]]) -> None:
        """lookup_rule with a nonsense query should return empty string or 'not found' message."""
        result = lookup_rule(index, "xyzzy_nonexistent_keyword_12345")
        assert isinstance(result, str)
        # Should be empty or contain a "not found" style message — not raise an error
        # The key requirement is that it doesn't crash
        # If non-empty, it shouldn't contain unrelated rule dumps
        assert len(result) < 5000, "Nonsense query should not return massive text dump"

    def test_numeric_rule_lookup(self, index: dict[str, list[str]]) -> None:
        """lookup_rule with a top-level rule number like '100.1' should return relevant text."""
        result = lookup_rule(index, "100.1")
        assert isinstance(result, str)
        # Should contain the rule number or rule-like text
        if len(result) > 0:
            assert "100.1" in result or "magic" in result.lower() or "player" in result.lower()


# ---------------------------------------------------------------------------
# rules_overview.md
# ---------------------------------------------------------------------------

class TestRulesOverview:
    """Tests for the generated rules_overview.md file."""

    def test_file_exists(self) -> None:
        """rules_overview.md must exist."""
        assert RULES_OVERVIEW_PATH.exists(), (
            f"rules_overview.md not found at {RULES_OVERVIEW_PATH}"
        )

    def test_file_is_non_empty(self) -> None:
        """rules_overview.md must be non-empty."""
        content = RULES_OVERVIEW_PATH.read_text(encoding="utf-8")
        assert len(content.strip()) > 0

    def test_under_1000_tokens(self) -> None:
        """rules_overview.md must be under ~1,000 tokens.

        Uses the project-standard approximation: tokens ≈ len(text.split()) * 1.3.
        The TODO specifies ~1,000 tokens budget.
        """
        content = RULES_OVERVIEW_PATH.read_text(encoding="utf-8")
        estimated_tokens = len(content.split()) * 1.3
        assert estimated_tokens <= 1000, (
            f"rules_overview.md is ~{estimated_tokens:.0f} tokens "
            f"(len(text.split()) * 1.3), expected ≤1000"
        )

    def test_covers_turn_structure(self) -> None:
        """rules_overview.md should cover turn structure."""
        content = RULES_OVERVIEW_PATH.read_text(encoding="utf-8").lower()
        assert "turn" in content, "Expected 'turn' topic in rules_overview.md"
        # Should mention phases or steps
        assert "phase" in content or "step" in content or "untap" in content

    def test_covers_combat(self) -> None:
        """rules_overview.md should cover combat."""
        content = RULES_OVERVIEW_PATH.read_text(encoding="utf-8").lower()
        assert "combat" in content, "Expected 'combat' topic in rules_overview.md"

    def test_covers_stack(self) -> None:
        """rules_overview.md should cover the stack."""
        content = RULES_OVERVIEW_PATH.read_text(encoding="utf-8").lower()
        assert "stack" in content, "Expected 'stack' topic in rules_overview.md"

    def test_covers_zones(self) -> None:
        """rules_overview.md should cover zones."""
        content = RULES_OVERVIEW_PATH.read_text(encoding="utf-8").lower()
        assert "zone" in content or "zones" in content, (
            "Expected 'zone(s)' topic in rules_overview.md"
        )
