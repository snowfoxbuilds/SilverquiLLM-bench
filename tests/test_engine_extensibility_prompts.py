"""Tests for TODO item 20: Engine extensibility language in prompt templates.

Verifies that all three prompt templates (_BLIND_IMPLEMENTATION_TEMPLATE,
_TEST_INFORMED_TEMPLATE, _ITERATION_FEEDBACK_TEMPLATE) inform agents about:
1. engine/ is writable and may be extended
2. previous cards' tests are re-run (regression testing)
3. engine changes must not break existing functionality
"""

from __future__ import annotations

import pytest

from silverquillm.prompts import (
    _BLIND_IMPLEMENTATION_TEMPLATE,
    _ITERATION_FEEDBACK_TEMPLATE,
    _TEST_INFORMED_TEMPLATE,
    blind_implementation_prompt,
    iteration_feedback_prompt,
    test_informed_prompt,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CARD_SPEC: dict = {
    "name": "Lightning Bolt",
    "mana_cost": "{R}",
    "type_line": "Instant",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
}


def _lower(template: str) -> str:
    """Return lowercased template for case-insensitive checks."""
    return template.lower()


# ---------------------------------------------------------------------------
# Blind implementation template
# ---------------------------------------------------------------------------


class TestBlindTemplateEngineExtensibility:
    """Verify _BLIND_IMPLEMENTATION_TEMPLATE includes engine extensibility."""

    def test_mentions_engine_writable_or_extensible(self):
        text = _lower(_BLIND_IMPLEMENTATION_TEMPLATE)
        # "engine" must co-occur with writable/extend/modify language
        assert "engine" in text, "Blind template must mention the engine"
        assert "extend" in text or "writable" in text or "modify" in text, (
            "Blind template should tell agents the engine is writable/extensible"
        )
        # Verify co-occurrence: engine AND extensibility in the same template
        # is not accidental — check they relate (engine/ + extend/modify)
        assert "engine/" in _BLIND_IMPLEMENTATION_TEMPLATE, (
            "Blind template should reference engine/ directory path"
        )

    def test_mentions_regression_testing(self):
        text = _lower(_BLIND_IMPLEMENTATION_TEMPLATE)
        # Must mention "previous" AND some form of re-running tests
        assert "previous" in text, (
            "Blind template must mention 'previous' cards/tests for regression"
        )
        assert "re-run" in text or "rerun" in text, (
            "Blind template must mention re-running tests"
        )

    def test_mentions_not_breaking_existing(self):
        text = _lower(_BLIND_IMPLEMENTATION_TEMPLATE)
        # Must convey that changes must not break existing functionality
        has_break_existing = "break" in text and "existing" in text
        has_break_compat = "break" in text and ("backward" in text or "previous" in text)
        assert has_break_existing or has_break_compat, (
            "Blind template should warn not to break existing functionality"
        )

    def test_rendered_prompt_contains_extensibility_language(self):
        rendered = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        low = rendered.lower()
        assert "engine/" in rendered, "Rendered blind prompt must reference engine/"
        assert "extend" in low or "modify" in low, (
            "Rendered blind prompt must mention extend/modify"
        )
        assert "previous" in low, (
            "Rendered blind prompt must mention previous cards"
        )
        assert "break" in low and "existing" in low, (
            "Rendered blind prompt must warn about breaking existing functionality"
        )


# ---------------------------------------------------------------------------
# Test-informed template
# ---------------------------------------------------------------------------


class TestTestInformedTemplateEngineExtensibility:
    """Verify _TEST_INFORMED_TEMPLATE includes engine extensibility."""

    def test_mentions_engine_writable_or_extensible(self):
        text = _lower(_TEST_INFORMED_TEMPLATE)
        assert "engine/" in _TEST_INFORMED_TEMPLATE, (
            "Test-informed template should reference engine/ directory"
        )
        assert "modify" in text or "extend" in text, (
            "Test-informed template should tell agents engine is modifiable"
        )

    def test_mentions_regression_testing(self):
        text = _lower(_TEST_INFORMED_TEMPLATE)
        assert "previous" in text and ("test" in text or "re-run" in text), (
            "Test-informed template should mention previous cards' tests are re-run"
        )

    def test_mentions_not_breaking_existing(self):
        text = _lower(_TEST_INFORMED_TEMPLATE)
        has_break_existing = "break" in text and "existing" in text
        has_break_compat = "break" in text and ("backward" in text or "previous" in text)
        assert has_break_existing or has_break_compat, (
            "Test-informed template should warn about not breaking existing functionality"
        )

    def test_rendered_prompt_contains_extensibility_language(self):
        rendered = test_informed_prompt(_SAMPLE_CARD_SPEC, round_num=1, max_rounds=3)
        low = rendered.lower()
        assert "engine/" in rendered, "Rendered test-informed prompt must reference engine/"
        assert "previous" in low, (
            "Rendered test-informed prompt must mention previous cards"
        )
        assert "break" in low and "existing" in low, (
            "Rendered test-informed prompt must warn about breaking existing functionality"
        )


# ---------------------------------------------------------------------------
# Iteration feedback template
# ---------------------------------------------------------------------------


class TestIterationFeedbackTemplateEngineExtensibility:
    """Verify _ITERATION_FEEDBACK_TEMPLATE includes engine extensibility."""

    def test_mentions_engine_writable_or_extensible(self):
        assert "engine/" in _ITERATION_FEEDBACK_TEMPLATE, (
            "Iteration feedback template should reference engine/ directory"
        )
        text = _lower(_ITERATION_FEEDBACK_TEMPLATE)
        assert "modify" in text or "extend" in text, (
            "Iteration feedback template should mention engine is modifiable"
        )

    def test_mentions_regression_testing(self):
        text = _lower(_ITERATION_FEEDBACK_TEMPLATE)
        assert "previous" in text and ("test" in text or "re-run" in text), (
            "Iteration feedback template should mention regression testing"
        )

    def test_mentions_not_breaking_existing(self):
        text = _lower(_ITERATION_FEEDBACK_TEMPLATE)
        has_break_existing = "break" in text and "existing" in text
        has_break_compat = "break" in text and ("backward" in text or "previous" in text)
        assert has_break_existing or has_break_compat, (
            "Iteration feedback template should warn about backward compatibility"
        )

    def test_rendered_prompt_contains_extensibility_language(self):
        rendered = iteration_feedback_prompt(
            test_output="3 passed, 1 failed", round_num=2, max_rounds=3
        )
        low = rendered.lower()
        assert "engine/" in rendered, "Rendered iteration feedback must reference engine/"
        assert "previous" in low, (
            "Rendered iteration feedback must mention previous cards"
        )
        assert "break" in low and "existing" in low, (
            "Rendered iteration feedback must warn about breaking existing functionality"
        )


# ---------------------------------------------------------------------------
# Cross-template consistency
# ---------------------------------------------------------------------------


class TestAllTemplatesHaveExtensibilityLanguage:
    """All three templates must include all three extensibility concepts."""

    @pytest.mark.parametrize(
        "template_name,template",
        [
            ("blind", _BLIND_IMPLEMENTATION_TEMPLATE),
            ("test_informed", _TEST_INFORMED_TEMPLATE),
            ("iteration_feedback", _ITERATION_FEEDBACK_TEMPLATE),
        ],
    )
    def test_all_three_concepts_present(self, template_name, template):
        text = _lower(template)
        # Concept 1: engine is writable/extensible — engine/ path + extend/modify
        assert "engine/" in template, (
            f"{template_name} must reference engine/ directory"
        )
        has_writable = "extend" in text or "modify" in text or "writable" in text
        assert has_writable, f"{template_name} missing writable/extensible concept"

        # Concept 2: regression testing — "previous" AND re-run/test
        assert "previous" in text, (
            f"{template_name} must mention 'previous' cards for regression testing"
        )
        has_rerun = "re-run" in text or "rerun" in text
        assert has_rerun, (
            f"{template_name} must mention re-running tests"
        )

        # Concept 3: backward compatibility — "break" AND "existing"
        has_break_existing = "break" in text and "existing" in text
        has_break_compat = "break" in text and ("backward" in text or "previous" in text)
        assert has_break_existing or has_break_compat, (
            f"{template_name} missing backward compat concept (need 'break' + 'existing')"
        )
