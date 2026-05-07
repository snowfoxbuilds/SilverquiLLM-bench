"""Tests for TODO item 15: Prompt templates contain explicit output filenames.

Without explicit filename instructions, agents don't know where to write files.
These tests verify each template includes the correct output filenames in an
instructional context.
"""

from __future__ import annotations

from silverquillm.prompts import (
    _BLIND_IMPLEMENTATION_TEMPLATE,
    _ITERATION_FEEDBACK_TEMPLATE,
    _TEST_INFORMED_TEMPLATE,
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


# ---------------------------------------------------------------------------
# Template-level checks (raw templates are non-empty strings)
# ---------------------------------------------------------------------------

class TestTemplatesAreNonEmpty:
    """Each raw template must be a non-empty string."""

    def test_blind_template_is_nonempty_string(self) -> None:
        assert isinstance(_BLIND_IMPLEMENTATION_TEMPLATE, str)
        assert len(_BLIND_IMPLEMENTATION_TEMPLATE.strip()) > 0

    def test_test_informed_template_is_nonempty_string(self) -> None:
        assert isinstance(_TEST_INFORMED_TEMPLATE, str)
        assert len(_TEST_INFORMED_TEMPLATE.strip()) > 0

    def test_iteration_feedback_template_is_nonempty_string(self) -> None:
        assert isinstance(_ITERATION_FEEDBACK_TEMPLATE, str)
        assert len(_ITERATION_FEEDBACK_TEMPLATE.strip()) > 0


# ---------------------------------------------------------------------------
# _BLIND_IMPLEMENTATION_TEMPLATE — must instruct writing to blind_impl.py
# ---------------------------------------------------------------------------

class TestBlindTemplateFilenames:
    """_BLIND_IMPLEMENTATION_TEMPLATE must tell the agent to write to blind_impl.py."""

    def test_contains_blind_impl_filename(self) -> None:
        assert "blind_impl.py" in _BLIND_IMPLEMENTATION_TEMPLATE

    def test_blind_impl_in_instructional_context(self) -> None:
        """The filename should appear near a 'write' instruction, not randomly."""
        lower = _BLIND_IMPLEMENTATION_TEMPLATE.lower()
        write_idx = lower.find("write")
        blind_idx = lower.find("blind_impl.py")
        assert write_idx != -1, "Template should contain a 'write' instruction"
        assert blind_idx != -1, "Template should contain 'blind_impl.py'"
        # The write instruction and filename should be within the same paragraph
        # (within 200 chars of each other)
        assert abs(write_idx - blind_idx) < 200, (
            "blind_impl.py should appear near a 'write' instruction"
        )

    def test_substituted_prompt_contains_blind_impl(self) -> None:
        """After substitution, the filename must still be present."""
        result = blind_implementation_prompt(_SAMPLE_CARD_SPEC)
        assert "blind_impl.py" in result


# ---------------------------------------------------------------------------
# _TEST_INFORMED_TEMPLATE — must instruct tested_impl.py and tests.py
# ---------------------------------------------------------------------------

class TestTestInformedTemplateFilenames:
    """_TEST_INFORMED_TEMPLATE must tell agent to write to tested_impl.py and tests.py."""

    def test_contains_tested_impl_filename(self) -> None:
        assert "tested_impl.py" in _TEST_INFORMED_TEMPLATE

    def test_contains_tests_filename(self) -> None:
        assert "tests.py" in _TEST_INFORMED_TEMPLATE

    def test_tested_impl_in_instructional_context(self) -> None:
        """tested_impl.py should appear near a 'save' or 'write' instruction."""
        lower = _TEST_INFORMED_TEMPLATE.lower()
        # Look for save/write near tested_impl.py
        tested_idx = lower.find("tested_impl.py")
        assert tested_idx != -1
        # Check surrounding context (200 chars before) for instructional word
        context_start = max(0, tested_idx - 200)
        context = lower[context_start:tested_idx + 20]
        assert any(word in context for word in ("save", "write", "update")), (
            "tested_impl.py should appear near an instructional verb (save/write/update)"
        )

    def test_tests_py_in_instructional_context(self) -> None:
        """tests.py should appear near a 'write' or 'save' instruction."""
        lower = _TEST_INFORMED_TEMPLATE.lower()
        tests_idx = lower.find("tests.py")
        assert tests_idx != -1
        context_start = max(0, tests_idx - 200)
        context = lower[context_start:tests_idx + 10]
        assert any(word in context for word in ("save", "write", "test")), (
            "tests.py should appear near an instructional verb"
        )

    def test_substituted_prompt_contains_filenames(self) -> None:
        """After substitution, both filenames must still be present."""
        result = test_informed_prompt(_SAMPLE_CARD_SPEC, round_num=1)
        assert "tested_impl.py" in result
        assert "tests.py" in result


# ---------------------------------------------------------------------------
# _ITERATION_FEEDBACK_TEMPLATE — must reference tested_impl.py and tests.py
# ---------------------------------------------------------------------------

class TestIterationFeedbackTemplateFilenames:
    """_ITERATION_FEEDBACK_TEMPLATE must reference tested_impl.py and tests.py."""

    def test_contains_tested_impl_filename(self) -> None:
        assert "tested_impl.py" in _ITERATION_FEEDBACK_TEMPLATE

    def test_contains_tests_filename(self) -> None:
        assert "tests.py" in _ITERATION_FEEDBACK_TEMPLATE

    def test_resubmit_context(self) -> None:
        """The resubmit instruction must explicitly name tested_impl.py and tests.py.

        We check that at least one sentence/line containing an instructional verb
        also contains both filenames, ensuring they are tied together in context.
        """
        verbs = ("resubmit", "write", "save", "submit", "update", "produce", "output", "provide")
        # Split template into lines and find lines that contain an instructional verb
        lines = _ITERATION_FEEDBACK_TEMPLATE.lower().splitlines()
        verb_lines = [
            line for line in lines if any(v in line for v in verbs)
        ]
        assert verb_lines, "Template should contain at least one line with an instructional verb"

        # At least one verb-containing line must reference tested_impl.py
        assert any(
            "tested_impl.py" in line for line in verb_lines
        ), "No instructional line references 'tested_impl.py'"

        # At least one verb-containing line must reference tests.py
        assert any(
            "tests.py" in line for line in verb_lines
        ), "No instructional line references 'tests.py'"

    def test_substituted_prompt_contains_filenames(self) -> None:
        """After substitution, both filenames must still be present."""
        result = iteration_feedback_prompt("test output", round_num=1, max_rounds=3)
        assert "tested_impl.py" in result
        assert "tests.py" in result
