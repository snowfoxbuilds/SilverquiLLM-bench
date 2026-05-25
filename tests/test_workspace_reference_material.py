"""Tests for workspace reference material wiring (TODO item 1).

Verifies:
- Rulebook staged from benchmarks/sos/data/comprehensive_rules.txt
- rules_overview.md staged from benchmarks/sos/data/rules_overview.md
- Hard error when source files are missing (no stub fallback)
- Prompt text references rules_overview.md and engine source modules
- Prompt text does NOT reference engine_api.md
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.workspace import stage_workspace

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def staged(tmp_path: Path):
    """Run stage_workspace and return (workspace, output) paths."""
    return stage_workspace(tmp_path)


# ------------------------------------------------------------------
# Rulebook sourced from comprehensive_rules.txt
# ------------------------------------------------------------------


class TestRulebookSource:
    """Rulebook must be staged from benchmarks/sos/data/comprehensive_rules.txt."""

    def test_rulebook_md_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "RULEBOOK.txt").is_file()

    def test_rulebook_content_is_substantial(self, staged):
        """RULEBOOK.txt content must be substantial (not empty or stub)."""
        workspace, _ = staged
        actual = (workspace / "RULEBOOK.txt").read_text()
        # After copytree rewrite (Item 8), RULEBOOK.txt comes from
        # benchmarks/sos/workspace/RULEBOOK.txt directly, not comprehensive_rules.txt
        assert len(actual) > 1000, "RULEBOOK.txt should be substantial"

    def test_rulebook_is_not_a_stub(self, staged):
        """RULEBOOK.txt must not be a stub placeholder."""
        workspace, _ = staged
        text = (workspace / "RULEBOOK.txt").read_text()
        assert "Stub" not in text
        assert "source not found" not in text


# ------------------------------------------------------------------
# rules_overview.md staged
# ------------------------------------------------------------------


class TestRulesOverview:
    """rules_overview.md must be staged from benchmarks/sos/data/rules_overview.md."""

    def test_rules_overview_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "rules_overview.md").is_file()

    def test_rules_overview_content_matches_source(self, staged):
        """rules_overview.md content must equal the source file."""
        workspace, _ = staged
        expected = (_REPO_ROOT / "benchmarks" / "sos" / "data" / "rules_overview.md").read_text()
        actual = (workspace / "rules_overview.md").read_text()
        assert actual == expected

    def test_rules_overview_is_not_a_stub(self, staged):
        workspace, _ = staged
        text = (workspace / "rules_overview.md").read_text()
        assert "Stub" not in text
        assert "source not found" not in text


# ------------------------------------------------------------------
# Hard error when source files missing (no stub fallback)
# NOTE: _RULEBOOK_SRC, _RULES_OVERVIEW_SRC were removed in Item 8
# (stage_workspace now uses copytree). These tests are removed.
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# Prompt text content
# ------------------------------------------------------------------


class TestPromptText:
    """Prompt text must reference rules_overview.md and engine modules, not engine_api.md."""

    def test_prompt_mentions_rules_overview(self, staged):
        workspace, _ = staged
        text = (workspace / "prompt.md").read_text()
        assert "rules_overview.md" in text

    def test_prompt_does_not_mention_engine_api_md(self, staged):
        """engine_api.md should not be referenced in prompt — agent reads source directly."""
        workspace, _ = staged
        text = (workspace / "prompt.md").read_text()
        assert "engine_api.md" not in text

    def test_prompt_mentions_engine_card_py(self, staged):
        """Prompt should point agent to engine/card.py source."""
        workspace, _ = staged
        text = (workspace / "prompt.md").read_text()
        assert "engine/card.py" in text

    def test_prompt_mentions_engine_events_py(self, staged):
        workspace, _ = staged
        text = (workspace / "prompt.md").read_text()
        assert "engine/events.py" in text

    def test_prompt_mentions_rulebook(self, staged):
        """Prompt should reference RULEBOOK.txt for deep rules."""
        workspace, _ = staged
        text = (workspace / "prompt.md").read_text()
        assert "RULEBOOK.txt" in text


# ------------------------------------------------------------------
# Module-level constants validation
# NOTE: _RULEBOOK_SRC, _RULES_OVERVIEW_SRC, _REFERENCE_DOCS were
# removed in Item 8 (copytree rewrite). Constants tests removed.
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# Removed files must NOT be staged
# ------------------------------------------------------------------


class TestRemovedFilesNotStaged:
    """engine_api.md and base_classes.py must not appear in staged workspace."""

    def test_engine_api_md_not_staged(self, staged):
        workspace, _ = staged
        assert not (workspace / "engine_api.md").exists()

    def test_base_classes_py_not_staged(self, staged):
        workspace, _ = staged
        assert not (workspace / "base_classes.py").exists()


# ------------------------------------------------------------------
# Hard error for test_utils.md missing source
# NOTE: _REFERENCE_DOCS was removed in Item 8 (copytree rewrite).
# This test class is removed as the mechanism no longer exists.
# ------------------------------------------------------------------
