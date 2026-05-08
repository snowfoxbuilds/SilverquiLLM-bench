"""Tests for TODO item 13: setup_questions.json question bank content.

Tests verify:
- The file is valid JSON and loadable by load_setup_questions().
- Each question has required fields (question, expected_keywords).
- There are at least 5 questions.
- Questions cover three areas: engine API, test conventions, workspace layout.
- Keywords are reasonable (non-empty strings).
- Questions are non-empty strings.
- If answer_pattern is present, it's a valid regex.
- Round-trip: load + validate with a mock adapter returning correct answers passes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from silverquillm.adapters.base import AgentAdapter
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.setup_questions import (
    _check_answer,
    load_setup_questions,
    validate_setup,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "setup_questions.json"


def _make_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        name="test",
        set_code="SOS",
        model_name="m",
        model_provider="p",
        agent=AgentConfig(adapter="dummy", timeout_per_card=60),
    )


@pytest.fixture(scope="module")
def questions() -> list[dict]:
    """Load questions once for all tests in this module."""
    return load_setup_questions(_QUESTIONS_PATH)


# ---------------------------------------------------------------------------
# File validity
# ---------------------------------------------------------------------------


class TestFileValidity:
    """The setup_questions.json file must be valid JSON loadable by the API."""

    def test_file_exists(self):
        assert _QUESTIONS_PATH.exists(), f"{_QUESTIONS_PATH} does not exist"

    def test_is_valid_json(self):
        with open(_QUESTIONS_PATH) as fh:
            data = json.load(fh)
        assert isinstance(data, list)

    def test_loadable_by_load_setup_questions(self):
        result = load_setup_questions(_QUESTIONS_PATH)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


class TestRequiredFields:
    """Every question must have 'question' and 'expected_keywords' fields."""

    def test_each_question_has_question_field(self, questions):
        for idx, q in enumerate(questions):
            assert "question" in q, f"Question at index {idx} missing 'question'"

    def test_each_question_has_expected_keywords_field(self, questions):
        for idx, q in enumerate(questions):
            assert "expected_keywords" in q, (
                f"Question at index {idx} missing 'expected_keywords'"
            )


# ---------------------------------------------------------------------------
# Minimum count
# ---------------------------------------------------------------------------


class TestMinimumCount:
    """There must be at least 5 questions in the bank."""

    def test_at_least_five_questions(self, questions):
        assert len(questions) >= 5, (
            f"Expected at least 5 questions, got {len(questions)}"
        )


# ---------------------------------------------------------------------------
# Topic coverage
# ---------------------------------------------------------------------------


class TestTopicCoverage:
    """Questions must cover engine API, test conventions, and workspace layout."""

    # Keywords/phrases that signal each topic area.
    _ENGINE_API_SIGNALS = {"cardimpl", "agentadapter", "engine", "create_game", "base class"}
    _TEST_CONVENTION_SIGNALS = {"pytest", "test", "test framework", "test files"}
    _WORKSPACE_LAYOUT_SIGNALS = {"engine/", "cards/", "tests/", "silverquillm", "directory", "located", "stored"}

    @staticmethod
    def _any_match(question_text: str, keywords: list[str], signals: set[str]) -> bool:
        combined = (question_text + " " + " ".join(keywords)).lower()
        return any(s in combined for s in signals)

    def test_covers_engine_api(self, questions):
        matched = any(
            self._any_match(q["question"], q["expected_keywords"], self._ENGINE_API_SIGNALS)
            for q in questions
        )
        assert matched, "No question covers engine API"

    def test_covers_test_conventions(self, questions):
        matched = any(
            self._any_match(q["question"], q["expected_keywords"], self._TEST_CONVENTION_SIGNALS)
            for q in questions
        )
        assert matched, "No question covers test conventions"

    def test_covers_workspace_layout(self, questions):
        matched = any(
            self._any_match(q["question"], q["expected_keywords"], self._WORKSPACE_LAYOUT_SIGNALS)
            for q in questions
        )
        assert matched, "No question covers workspace layout"


# ---------------------------------------------------------------------------
# Field quality
# ---------------------------------------------------------------------------


class TestFieldQuality:
    """Keywords and questions must be non-empty strings."""

    def test_questions_are_nonempty_strings(self, questions):
        for idx, q in enumerate(questions):
            assert isinstance(q["question"], str), (
                f"Question at index {idx} is not a string"
            )
            assert q["question"].strip(), (
                f"Question at index {idx} is empty or whitespace-only"
            )

    def test_expected_keywords_are_nonempty_strings(self, questions):
        for idx, q in enumerate(questions):
            kws = q["expected_keywords"]
            assert isinstance(kws, list), (
                f"expected_keywords at index {idx} is not a list"
            )
            assert len(kws) > 0, (
                f"expected_keywords at index {idx} is empty"
            )
            for kw_idx, kw in enumerate(kws):
                assert isinstance(kw, str), (
                    f"Keyword {kw_idx} in question {idx} is not a string"
                )
                assert kw.strip(), (
                    f"Keyword {kw_idx} in question {idx} is empty or whitespace-only"
                )


# ---------------------------------------------------------------------------
# answer_pattern validity
# ---------------------------------------------------------------------------


class TestAnswerPatternValidity:
    """If answer_pattern is present, it must be a valid regex."""

    def test_answer_patterns_are_valid_regexes(self, questions):
        for idx, q in enumerate(questions):
            pattern = q.get("answer_pattern")
            if pattern is not None:
                assert isinstance(pattern, str), (
                    f"answer_pattern at index {idx} is not a string"
                )
                try:
                    re.compile(pattern)
                except re.error as exc:
                    pytest.fail(
                        f"answer_pattern at index {idx} ({pattern!r}) is not a valid regex: {exc}"
                    )


# ---------------------------------------------------------------------------
# Round-trip validation
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Load the real question bank and validate with a mock adapter that gives correct answers."""

    def test_validate_setup_passes_with_correct_answers(self, questions, tmp_path):
        """A mock adapter returning all expected keywords/patterns should pass."""

        class CorrectAnswerAdapter(AgentAdapter):
            """Returns an answer containing all expected keywords for each question."""

            def __init__(self, qmap: dict[str, dict]):
                super().__init__(_make_config())
                self._qmap = qmap

            def setup(self) -> None:
                pass

            def run(self, prompt: str, workspace: Path) -> str:
                q = self._qmap.get(prompt, {})
                # Build an answer that contains every keyword
                parts = list(q.get("expected_keywords", []))
                pattern = q.get("answer_pattern")
                if pattern is not None:
                    # Include a string matching the pattern literally
                    # (patterns in the bank are simple literal substrings)
                    parts.append(pattern)
                return " ".join(parts) if parts else "unknown"

            def teardown(self) -> None:
                pass

        qmap = {q["question"]: q for q in questions}
        adapter = CorrectAnswerAdapter(qmap)
        result = validate_setup(adapter, _QUESTIONS_PATH, tmp_path)
        assert result is True, "validate_setup should pass when adapter gives correct answers"

    def test_validate_setup_fails_with_wrong_answers(self, tmp_path):
        """A mock adapter returning nonsense should fail validation."""

        class WrongAnswerAdapter(AgentAdapter):
            def __init__(self):
                super().__init__(_make_config())

            def setup(self) -> None:
                pass

            def run(self, prompt: str, workspace: Path) -> str:
                return "completely irrelevant gibberish xyzzy"

            def teardown(self) -> None:
                pass

        adapter = WrongAnswerAdapter()
        result = validate_setup(adapter, _QUESTIONS_PATH, tmp_path)
        assert result is False, "validate_setup should fail when adapter gives wrong answers"
