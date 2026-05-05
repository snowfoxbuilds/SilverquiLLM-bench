"""Tests for TODO item 6: Engine API docs auto-generation.

Tests verify:
- generate_engine_api_doc() returns a non-empty Markdown string.
- Output mentions ALL public classes discovered via AST parsing of engine/.
- Output mentions key enums (Color, ManaType, Zone, Phase, Step, CardType, Keyword).
- Output mentions key functions (cast_spell, play_land, activate_ability).
- Token count < 5,000 (via len(text.split()) * 1.3).
- docs/engine_api.md exists, is valid Markdown, and matches generator output.
- Output is grouped by module (section headers match engine module names).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def api_doc() -> str:
    """Generate the engine API doc once for all tests."""
    from benchmark.docs_gen import generate_engine_api_doc

    return generate_engine_api_doc()


# ---------------------------------------------------------------------------
# Basic return value
# ---------------------------------------------------------------------------


class TestBasicOutput:
    def test_returns_nonempty_string(self, api_doc: str) -> None:
        assert isinstance(api_doc, str)
        assert len(api_doc.strip()) > 0

    def test_starts_with_markdown_heading(self, api_doc: str) -> None:
        assert api_doc.lstrip().startswith("#")


# ---------------------------------------------------------------------------
# Helpers: discover ALL public classes from engine/ via AST
# ---------------------------------------------------------------------------

ENGINE_DIR = REPO_ROOT / "engine"


def _discover_public_classes() -> list[str]:
    """Parse every .py in engine/ and return all public class names.

    A class is 'public' if its name does not start with '_'.
    """
    classes: list[str] = []
    for py_file in sorted(ENGINE_DIR.glob("*.py")):
        source = py_file.read_text()
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                classes.append(node.name)
    return sorted(set(classes))


ALL_PUBLIC_ENGINE_CLASSES = _discover_public_classes()


# ---------------------------------------------------------------------------
# Public classes mentioned
# ---------------------------------------------------------------------------


class TestPublicClasses:
    """ALL public engine classes must appear in the generated doc."""

    @pytest.mark.parametrize("class_name", ALL_PUBLIC_ENGINE_CLASSES)
    def test_class_mentioned(self, api_doc: str, class_name: str) -> None:
        assert class_name in api_doc, (
            f"Expected public class '{class_name}' to appear in generated doc"
        )

    def test_discovered_classes_nonempty(self) -> None:
        """Sanity: AST discovery should find a reasonable number of classes."""
        assert len(ALL_PUBLIC_ENGINE_CLASSES) >= 15, (
            f"Only found {len(ALL_PUBLIC_ENGINE_CLASSES)} public classes; "
            "expected at least 15 from engine/"
        )


# ---------------------------------------------------------------------------
# Enums mentioned
# ---------------------------------------------------------------------------


class TestEnums:
    """Key enums from engine/types.py and elsewhere must appear."""

    @pytest.mark.parametrize(
        "enum_name",
        [
            "Color",
            "ManaType",
            "Zone",
            "Phase",
            "Step",
            "CardType",
            "Keyword",
        ],
    )
    def test_enum_mentioned(self, api_doc: str, enum_name: str) -> None:
        assert enum_name in api_doc, (
            f"Expected enum '{enum_name}' to appear in generated doc"
        )


# ---------------------------------------------------------------------------
# Key functions mentioned
# ---------------------------------------------------------------------------


class TestKeyFunctions:
    """Important engine functions must appear in the generated doc."""

    @pytest.mark.parametrize(
        "func_name",
        [
            "cast_spell",
            "play_land",
            "activate_ability",
        ],
    )
    def test_function_mentioned(self, api_doc: str, func_name: str) -> None:
        assert func_name in api_doc, (
            f"Expected function '{func_name}' to appear in generated doc"
        )


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


class TestTokenBudget:
    def test_under_5000_tokens(self, api_doc: str) -> None:
        token_count = len(api_doc.split()) * 1.3
        assert token_count < 5000, (
            f"Token count {token_count:.0f} exceeds budget of 5,000"
        )

    def test_nontrivial_length(self, api_doc: str) -> None:
        """Doc should have substantial content, not just a header."""
        token_count = len(api_doc.split()) * 1.3
        assert token_count > 100, (
            f"Token count {token_count:.0f} is suspiciously low"
        )


# ---------------------------------------------------------------------------
# Grouped by module
# ---------------------------------------------------------------------------


class TestModuleGrouping:
    """Output should have sections grouped by engine module name."""

    @pytest.mark.parametrize(
        "module_name",
        [
            "card",
            "casting",
            "combat",
            "game_state",
            "stack",
            "types",
            "zones",
            "mana",
            "player",
        ],
    )
    def test_module_section_present(self, api_doc: str, module_name: str) -> None:
        # Module names should appear as section headers (### module_name)
        pattern = rf"###\s+{re.escape(module_name)}\b"
        assert re.search(pattern, api_doc), (
            f"Expected module section header for '{module_name}'"
        )


# ---------------------------------------------------------------------------
# Output file written
# ---------------------------------------------------------------------------


class TestOutputFile:
    def test_engine_api_md_exists(self) -> None:
        """docs/engine_api.md should exist in the repo."""
        path = REPO_ROOT / "docs" / "engine_api.md"
        assert path.exists(), f"Expected {path} to exist"

    def test_engine_api_md_nonempty(self) -> None:
        path = REPO_ROOT / "docs" / "engine_api.md"
        if not path.exists():
            pytest.skip("docs/engine_api.md does not exist yet")
        content = path.read_text()
        assert len(content.strip()) > 0

    def test_engine_api_md_valid_markdown_headings(self) -> None:
        """Basic markdown validity: at least one heading."""
        path = REPO_ROOT / "docs" / "engine_api.md"
        if not path.exists():
            pytest.skip("docs/engine_api.md does not exist yet")
        content = path.read_text()
        assert re.search(r"^#{1,6}\s+\S", content, re.MULTILINE), (
            "docs/engine_api.md should contain at least one Markdown heading"
        )

    def test_checked_in_doc_matches_generator(self, api_doc: str) -> None:
        """The checked-in docs/engine_api.md must match generate_engine_api_doc().

        This ensures the file stays in sync with the generator and isn't
        manually edited to drift from the auto-generated output.
        """
        path = REPO_ROOT / "docs" / "engine_api.md"
        if not path.exists():
            pytest.skip("docs/engine_api.md does not exist yet")
        checked_in = path.read_text()
        assert checked_in == api_doc, (
            "docs/engine_api.md has drifted from generate_engine_api_doc() output. "
            "Re-run the generator to update the checked-in file."
        )
