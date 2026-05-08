"""Tests for TODO item 10: Prompt templates module.

Tests verify:
- blind_implementation_prompt produces a string with no {placeholder} remaining.
- Blind prompt contains card name, mana cost, type line, oracle text.
- Blind prompt does NOT mention "test_utils" or "card_impl".
- test_informed_prompt mentions test_utils constraints (max 30, card_impl, test_utils).
- test_informed_prompt with prev_test_results includes the test output.
- test_informed_prompt without prev_test_results works (round 1).
- iteration_feedback_prompt includes test output, round number, max rounds.
- No {placeholder} patterns remain in any output.
- Edge cases: card with no oracle text, planeswalker spec, etc.
"""

from __future__ import annotations

import re

import pytest

from silverquillm.prompts import (
    blind_implementation_prompt,
    iteration_feedback_prompt,
    test_informed_prompt,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SAMPLE_CARD_SPEC: dict = {
    "name": "Lightning Bolt",
    "mana_cost": "{R}",
    "type_line": "Instant",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
}

_PLANESWALKER_SPEC: dict = {
    "name": "Jace, the Mind Sculptor",
    "mana_cost": "{2}{U}{U}",
    "type_line": "Legendary Planeswalker — Jace",
    "oracle_text": (
        "+2: Look at the top card of target player's library.\n"
        "0: Draw three cards, then put two cards from your hand on top.\n"
        "-1: Return target creature to its owner's hand.\n"
        "-12: Exile all cards from target player's library."
    ),
}

_NO_ORACLE_SPEC: dict = {
    "name": "Memnite",
    "mana_cost": "{0}",
    "type_line": "Artifact Creature — Construct",
    "oracle_text": "",
}

# Regex that finds any remaining {placeholder} tokens (but ignores MTG mana
# symbols like {R}, {2}, {U} which are valid content).
_UNFILLED_PLACEHOLDER_RE = re.compile(r"\{[a-z_]{2,}\}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_unfilled_placeholder(text: str) -> bool:
    """Return True if *text* contains a ``{placeholder}``-style token."""
    return bool(_UNFILLED_PLACEHOLDER_RE.search(text))


# ---------------------------------------------------------------------------
# blind_implementation_prompt
# ---------------------------------------------------------------------------

class TestBlindImplementationPrompt:
    """Tests for blind_implementation_prompt()."""

    def test_returns_string(self) -> None:
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert isinstance(result, str)

    def test_no_unfilled_placeholders(self) -> None:
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert not _has_unfilled_placeholder(result), (
            f"Found unfilled placeholder in blind prompt: {result!r}"
        )

    def test_contains_card_name(self) -> None:
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert "Lightning Bolt" in result

    def test_contains_mana_cost(self) -> None:
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert "{R}" in result

    def test_contains_type_line(self) -> None:
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert "Instant" in result

    def test_contains_oracle_text(self) -> None:
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert "deals 3 damage" in result

    def test_does_not_mention_test_utils(self) -> None:
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert "test_utils" not in result.lower()

    def test_does_not_mention_card_impl(self) -> None:
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert "card_impl" not in result.lower()

    def test_empty_oracle_text(self) -> None:
        result = blind_implementation_prompt(_NO_ORACLE_SPEC)
        assert not _has_unfilled_placeholder(result)
        assert "Memnite" in result

    def test_planeswalker_spec(self) -> None:
        result = blind_implementation_prompt(_PLANESWALKER_SPEC)
        assert not _has_unfilled_placeholder(result)
        assert "Jace, the Mind Sculptor" in result
        assert "Legendary Planeswalker" in result


# ---------------------------------------------------------------------------
# test_informed_prompt
# ---------------------------------------------------------------------------

class TestTestInformedPrompt:
    """Tests for test_informed_prompt()."""

    def test_returns_string(self) -> None:
        result = test_informed_prompt(_SAMPLE_CARD_SPEC, round_num=1)
        assert isinstance(result, str)

    def test_no_unfilled_placeholders(self) -> None:
        result = test_informed_prompt(_SAMPLE_CARD_SPEC, round_num=1)
        assert not _has_unfilled_placeholder(result)

    def test_mentions_test_utils(self) -> None:
        result = test_informed_prompt(_SAMPLE_CARD_SPEC, round_num=1)
        assert "test_utils" in result

    def test_mentions_card_impl(self) -> None:
        result = test_informed_prompt(_SAMPLE_CARD_SPEC, round_num=1)
        assert "card_impl" in result

    def test_mentions_max_30(self) -> None:
        result = test_informed_prompt(_SAMPLE_CARD_SPEC, round_num=1)
        assert "30" in result

    def test_contains_card_name(self) -> None:
        result = test_informed_prompt(_SAMPLE_CARD_SPEC, round_num=1)
        assert "Lightning Bolt" in result

    def test_round_1_no_prev_results(self) -> None:
        """Round 1 should work without prev_test_results."""
        result = test_informed_prompt(
            _SAMPLE_CARD_SPEC, round_num=1, prev_test_results=None
        )
        assert isinstance(result, str)
        assert not _has_unfilled_placeholder(result)

    def test_includes_prev_test_results_when_provided(self) -> None:
        fake_output = "FAILED test_damage — AssertionError: expected 3, got 0"
        result = test_informed_prompt(
            _SAMPLE_CARD_SPEC,
            round_num=2,
            prev_test_results=fake_output,
        )
        assert fake_output in result

    def test_no_prev_results_does_not_contain_feedback_section(self) -> None:
        result = test_informed_prompt(
            _SAMPLE_CARD_SPEC, round_num=1, prev_test_results=None
        )
        assert "Previous test results" not in result or "previous" not in result.lower()

    def test_planeswalker_spec_no_placeholders(self) -> None:
        result = test_informed_prompt(_PLANESWALKER_SPEC, round_num=1)
        assert not _has_unfilled_placeholder(result)
        assert "Jace" in result


# ---------------------------------------------------------------------------
# iteration_feedback_prompt
# ---------------------------------------------------------------------------

class TestIterationFeedbackPrompt:
    """Tests for iteration_feedback_prompt()."""

    def test_returns_string(self) -> None:
        result = iteration_feedback_prompt("all passed", round_num=1, max_rounds=3)
        assert isinstance(result, str)

    def test_no_unfilled_placeholders(self) -> None:
        result = iteration_feedback_prompt("all passed", round_num=2, max_rounds=5)
        assert not _has_unfilled_placeholder(result)

    def test_includes_test_output(self) -> None:
        output = "FAILED test_foo — IndexError"
        result = iteration_feedback_prompt(output, round_num=1, max_rounds=3)
        assert output in result

    def test_includes_round_number(self) -> None:
        result = iteration_feedback_prompt("ok", round_num=2, max_rounds=5)
        assert "2" in result

    def test_includes_max_rounds(self) -> None:
        result = iteration_feedback_prompt("ok", round_num=2, max_rounds=5)
        assert "5" in result

    def test_round_and_max_in_context(self) -> None:
        """Round N of M should appear together."""
        result = iteration_feedback_prompt("ok", round_num=3, max_rounds=7)
        # At minimum both numbers must be present
        assert "3" in result
        assert "7" in result

    def test_multiline_test_output(self) -> None:
        output = "line1\nline2\nFAILED test_bar\nline4"
        result = iteration_feedback_prompt(output, round_num=1, max_rounds=3)
        assert "FAILED test_bar" in result
