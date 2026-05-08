"""Tests for TODO item 12: Setup questions validation.

Tests verify:
- load_setup_questions() loads questions from a JSON file correctly.
- load_setup_questions() raises FileNotFoundError for missing file.
- load_setup_questions() raises ValueError for non-list JSON.
- load_setup_questions() raises ValueError for missing required fields.
- validate_setup() returns True when all answers contain expected keywords.
- validate_setup() returns False when an answer misses keywords.
- validate_setup() returns True for empty questions list.
- Regex pattern matching works via answer_pattern.
- Adapter errors during validation cause that question to fail.
- Keyword matching is case-insensitive.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

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

def _make_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        name="test",
        set_code="SOS",
        model_name="m",
        model_provider="p",
        agent=AgentConfig(adapter="dummy", timeout_per_card=60),
    )


class StubAdapter(AgentAdapter):
    """Adapter that returns canned responses keyed by prompt."""

    def __init__(self, responses: dict[str, str] | None = None):
        super().__init__(_make_config())
        self.responses = responses or {}

    def setup(self) -> None:
        pass

    def run(self, prompt: str, workspace: Path) -> str:
        if prompt in self.responses:
            return self.responses[prompt]
        return ""

    def teardown(self) -> None:
        pass


class ErrorAdapter(AgentAdapter):
    """Adapter that always raises RuntimeError."""

    def __init__(self):
        super().__init__(_make_config())

    def setup(self) -> None:
        pass

    def run(self, prompt: str, workspace: Path) -> str:
        raise RuntimeError("adapter exploded")

    def teardown(self) -> None:
        pass


def _write_questions(tmp_path: Path, questions: list) -> Path:
    path = tmp_path / "setup_questions.json"
    path.write_text(json.dumps(questions))
    return path


# ---------------------------------------------------------------------------
# load_setup_questions tests
# ---------------------------------------------------------------------------


class TestLoadSetupQuestions:
    def test_loads_valid_questions(self, tmp_path):
        questions = [
            {"question": "What is 2+2?", "expected_keywords": ["4"]},
            {"question": "Name a color", "expected_keywords": ["red"], "answer_pattern": r"\bred\b"},
        ]
        path = _write_questions(tmp_path, questions)
        result = load_setup_questions(path)
        assert result == questions
        assert len(result) == 2

    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_setup_questions(tmp_path / "nonexistent.json")

    def test_raises_value_error_for_non_list(self, tmp_path):
        path = tmp_path / "setup_questions.json"
        path.write_text(json.dumps({"question": "hi", "expected_keywords": []}))
        with pytest.raises(ValueError, match="Expected a JSON array"):
            load_setup_questions(path)

    def test_raises_value_error_missing_question_field(self, tmp_path):
        questions = [{"expected_keywords": ["foo"]}]
        path = _write_questions(tmp_path, questions)
        with pytest.raises(ValueError, match="missing required field 'question'"):
            load_setup_questions(path)

    def test_raises_value_error_missing_expected_keywords(self, tmp_path):
        questions = [{"question": "What?"}]
        path = _write_questions(tmp_path, questions)
        with pytest.raises(ValueError, match="missing required field 'expected_keywords'"):
            load_setup_questions(path)

    def test_loads_empty_list(self, tmp_path):
        path = _write_questions(tmp_path, [])
        result = load_setup_questions(path)
        assert result == []


# ---------------------------------------------------------------------------
# _check_answer tests
# ---------------------------------------------------------------------------


class TestCheckAnswer:
    def test_all_keywords_present(self):
        q = {"question": "x", "expected_keywords": ["hello", "world"]}
        assert _check_answer("Hello World!", q) is True

    def test_keyword_missing(self):
        q = {"question": "x", "expected_keywords": ["hello", "world"]}
        assert _check_answer("Hello there!", q) is False

    def test_case_insensitive_keywords(self):
        q = {"question": "x", "expected_keywords": ["Python"]}
        assert _check_answer("I love python", q) is True

    def test_regex_pattern_matches(self):
        q = {"question": "x", "expected_keywords": [], "answer_pattern": r"\d{3}-\d{4}"}
        assert _check_answer("Call 555-1234", q) is True

    def test_regex_pattern_no_match(self):
        q = {"question": "x", "expected_keywords": [], "answer_pattern": r"\d{3}-\d{4}"}
        assert _check_answer("No number here", q) is False

    def test_keywords_pass_but_regex_fails(self):
        q = {"question": "x", "expected_keywords": ["yes"], "answer_pattern": r"^no$"}
        assert _check_answer("yes", q) is False

    def test_no_pattern_field_skips_regex(self):
        q = {"question": "x", "expected_keywords": ["ok"]}
        assert _check_answer("ok", q) is True


# ---------------------------------------------------------------------------
# validate_setup tests
# ---------------------------------------------------------------------------


class TestValidateSetup:
    def test_returns_true_all_pass(self, tmp_path):
        questions = [
            {"question": "What is Python?", "expected_keywords": ["language"]},
            {"question": "What is 1+1?", "expected_keywords": ["2"]},
        ]
        path = _write_questions(tmp_path, questions)
        adapter = StubAdapter({
            "What is Python?": "Python is a programming language",
            "What is 1+1?": "The answer is 2",
        })
        assert validate_setup(adapter, path, tmp_path) is True

    def test_returns_false_when_keyword_missing(self, tmp_path):
        questions = [
            {"question": "What is Python?", "expected_keywords": ["language"]},
            {"question": "What is 1+1?", "expected_keywords": ["2"]},
        ]
        path = _write_questions(tmp_path, questions)
        adapter = StubAdapter({
            "What is Python?": "Python is a programming language",
            "What is 1+1?": "I don't know",
        })
        assert validate_setup(adapter, path, tmp_path) is False

    def test_returns_true_for_empty_questions(self, tmp_path):
        path = _write_questions(tmp_path, [])
        adapter = StubAdapter()
        assert validate_setup(adapter, path, tmp_path) is True

    def test_returns_false_on_adapter_error(self, tmp_path):
        questions = [
            {"question": "Anything?", "expected_keywords": ["yes"]},
        ]
        path = _write_questions(tmp_path, questions)
        adapter = ErrorAdapter()
        assert validate_setup(adapter, path, tmp_path) is False

    def test_raises_on_missing_file(self, tmp_path):
        adapter = StubAdapter()
        with pytest.raises(FileNotFoundError):
            validate_setup(adapter, tmp_path / "nope.json", tmp_path)

    def test_continues_after_adapter_error(self, tmp_path):
        """Even if one question errors, remaining questions are still checked."""
        questions = [
            {"question": "fail", "expected_keywords": ["x"]},
            {"question": "pass", "expected_keywords": ["ok"]},
        ]
        path = _write_questions(tmp_path, questions)

        class PartialErrorAdapter(AgentAdapter):
            def __init__(self):
                super().__init__(_make_config())

            def setup(self):
                pass

            def run(self, prompt, workspace):
                if prompt == "fail":
                    raise RuntimeError("boom")
                return "ok"

            def teardown(self):
                pass

        adapter = PartialErrorAdapter()
        # Should return False (first question errored), but still process second
        result = validate_setup(adapter, path, tmp_path)
        assert result is False

    def test_regex_validation_in_validate_setup(self, tmp_path):
        questions = [
            {"question": "Version?", "expected_keywords": [], "answer_pattern": r"v\d+\.\d+"},
        ]
        path = _write_questions(tmp_path, questions)
        adapter = StubAdapter({"Version?": "Running v3.11"})
        assert validate_setup(adapter, path, tmp_path) is True

    def test_regex_failure_in_validate_setup(self, tmp_path):
        questions = [
            {"question": "Version?", "expected_keywords": [], "answer_pattern": r"v\d+\.\d+"},
        ]
        path = _write_questions(tmp_path, questions)
        adapter = StubAdapter({"Version?": "No version info"})
        assert validate_setup(adapter, path, tmp_path) is False
