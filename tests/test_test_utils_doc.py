"""Tests for TODO item 7: test_utils documentation for agents.

Tests verify:
- docs/test_utils.md exists and is non-empty.
- All 6 public functions are mentioned: create_game, set_board_state, cast_spell,
  advance_to_phase, declare_attackers, declare_blockers.
- Token count < 2,000 (via len(text.split()) * 1.3).
- Example code snippets are syntactically valid Python (extracted code blocks compile).
- Required test structure template is present.
- Constraints (max 30 tests, import from card_impl) are mentioned.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "benchmarks" / "sos" / "workspace" / "tests" / "test_utils.md"

PUBLIC_FUNCTIONS = [
    "create_game",
    "set_board_state",
    "cast_spell",
    "advance_to_phase",
    "declare_attackers",
    "declare_blockers",
]


@pytest.fixture(scope="module")
def doc_text() -> str:
    """Read the test_utils documentation."""
    assert DOC_PATH.exists(), f"docs/test_utils.md does not exist at {DOC_PATH}"
    text = DOC_PATH.read_text(encoding="utf-8")
    return text


# ---------------------------------------------------------------------------
# File existence and basic content
# ---------------------------------------------------------------------------


class TestDocExists:
    def test_file_exists(self) -> None:
        assert DOC_PATH.exists(), "docs/test_utils.md must exist"

    def test_file_is_nonempty(self, doc_text: str) -> None:
        assert len(doc_text.strip()) > 0, "docs/test_utils.md must not be empty"


# ---------------------------------------------------------------------------
# All public functions mentioned
# ---------------------------------------------------------------------------


class TestFunctionCoverage:
    @pytest.mark.parametrize("func_name", PUBLIC_FUNCTIONS)
    def test_function_mentioned(self, doc_text: str, func_name: str) -> None:
        assert func_name in doc_text, (
            f"Public function '{func_name}' must be documented in test_utils.md"
        )

    def test_all_six_functions_present(self, doc_text: str) -> None:
        """Redundant aggregate check ensuring no partial coverage."""
        missing = [f for f in PUBLIC_FUNCTIONS if f not in doc_text]
        assert missing == [], f"Missing functions in doc: {missing}"


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


class TestTokenBudget:
    def test_under_2000_tokens(self, doc_text: str) -> None:
        estimated_tokens = len(doc_text.split()) * 1.3
        assert estimated_tokens < 2000, (
            f"Doc exceeds 2,000 token budget: ~{estimated_tokens:.0f} tokens"
        )


# ---------------------------------------------------------------------------
# Code snippets are syntactically valid Python
# ---------------------------------------------------------------------------


class TestCodeSnippets:
    def _extract_code_blocks(self, text: str) -> list[str]:
        """Extract fenced code blocks marked as python."""
        pattern = r"```python\s*\n(.*?)```"
        return re.findall(pattern, text, re.DOTALL)

    def test_has_at_least_one_code_block(self, doc_text: str) -> None:
        blocks = self._extract_code_blocks(doc_text)
        assert len(blocks) >= 1, "Doc must contain at least one python code example"

    @pytest.mark.parametrize("func_name", PUBLIC_FUNCTIONS)
    def test_function_has_example_in_code_block(self, doc_text: str, func_name: str) -> None:
        """Each public function must appear inside a ```python code block as example usage."""
        blocks = self._extract_code_blocks(doc_text)
        assert blocks, "No python code blocks found in doc"
        found = any(func_name in block for block in blocks)
        assert found, (
            f"Function '{func_name}' must have example usage inside a "
            f"```python code block in docs/test_utils.md"
        )

    def test_all_code_blocks_compile(self, doc_text: str) -> None:
        blocks = self._extract_code_blocks(doc_text)
        for i, block in enumerate(blocks):
            try:
                compile(block, f"<code_block_{i}>", "exec")
            except SyntaxError as e:
                pytest.fail(
                    f"Code block {i} has invalid Python syntax: {e}\n\n{block}"
                )

    def test_code_blocks_parse_as_valid_ast(self, doc_text: str) -> None:
        """Ensure code blocks parse into valid AST (stricter than compile)."""
        blocks = self._extract_code_blocks(doc_text)
        for i, block in enumerate(blocks):
            try:
                ast.parse(block)
            except SyntaxError as e:
                pytest.fail(f"Code block {i} fails AST parse: {e}\n\n{block}")


# ---------------------------------------------------------------------------
# Test structure and constraints
# ---------------------------------------------------------------------------


class TestStructureAndConstraints:
    def test_mentions_max_30_tests(self, doc_text: str) -> None:
        assert "30" in doc_text, "Doc must mention the max 30 tests constraint"

    def test_mentions_card_impl_import(self, doc_text: str) -> None:
        assert "card_impl" in doc_text, (
            "Doc must mention importing from card_impl"
        )

    def test_mentions_test_structure(self, doc_text: str) -> None:
        """Doc should describe/show the required test structure."""
        # Check for indicators of test structure guidance
        has_structure = any(
            keyword in doc_text.lower()
            for keyword in ["test structure", "class test", "def test_", "pytest"]
        )
        assert has_structure, (
            "Doc must include test structure guidance (e.g., class/function pattern)"
        )


# ---------------------------------------------------------------------------
# Function signatures documented
# ---------------------------------------------------------------------------


class TestSignatures:
    @pytest.mark.parametrize("func_name", PUBLIC_FUNCTIONS)
    def test_function_has_signature_or_def(self, doc_text: str, func_name: str) -> None:
        """Each function should show its signature (def line or parameter list)."""
        # Look for either a def statement or the function name followed by (
        has_sig = (
            f"def {func_name}(" in doc_text
            or f"`{func_name}(" in doc_text
            or f"{func_name}(" in doc_text
        )
        assert has_sig, (
            f"Function '{func_name}' should have its signature documented"
        )
