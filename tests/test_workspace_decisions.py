"""Tests for decisions.md workspace artifact — TODO item 9."""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.workspace import _PROMPT_TEXT, stage_workspace


class TestDecisionsFileStaging:
    """stage_workspace must create decisions.md in the workspace."""

    def test_decisions_md_exists_after_staging(self, tmp_path: Path):
        """decisions.md is created in the workspace root."""
        workspace, _ = stage_workspace(tmp_path)
        assert (workspace / "decisions.md").exists()

    def test_decisions_md_starts_with_header(self, tmp_path: Path):
        """decisions.md is seeded with a '# Decisions' header."""
        workspace, _ = stage_workspace(tmp_path)
        content = (workspace / "decisions.md").read_text(encoding="utf-8")
        assert content.startswith("# Decisions")

    def test_decisions_md_is_minimal_seed(self, tmp_path: Path):
        """The seed file contains only the header — agent fills in the rest."""
        workspace, _ = stage_workspace(tmp_path)
        content = (workspace / "decisions.md").read_text(encoding="utf-8")
        assert content.strip() == "# Decisions"

    def test_decisions_md_survives_repeated_staging(self, tmp_path: Path):
        """Re-running stage_workspace produces a fresh decisions.md (clean slate)."""
        workspace, _ = stage_workspace(tmp_path)
        # Simulate agent writing content
        (workspace / "decisions.md").write_text("# Decisions\n## SOS 053\n- foo\n")
        # Re-stage
        workspace2, _ = stage_workspace(tmp_path)
        content = (workspace2 / "decisions.md").read_text(encoding="utf-8")
        assert content.strip() == "# Decisions"

    def test_decisions_md_exists_with_card_filter(self, tmp_path: Path):
        """decisions.md is created even when card_filter is applied."""
        workspace, _ = stage_workspace(tmp_path, card_filter=["053"])
        assert (workspace / "decisions.md").exists()


class TestDecisionsPromptInstruction:
    """The prompt must instruct the agent to maintain decisions.md."""

    def test_prompt_mentions_decisions_md(self):
        """_PROMPT_TEXT references decisions.md by filename."""
        assert "decisions.md" in _PROMPT_TEXT

    def test_prompt_instructs_maintain(self):
        """Prompt uses language about maintaining decisions.md."""
        assert "Maintain" in _PROMPT_TEXT and "decisions.md" in _PROMPT_TEXT

    def test_prompt_requires_entry_per_card(self):
        """Prompt says every attempted card must have an entry."""
        assert "Every card you attempt must have an entry" in _PROMPT_TEXT

    def test_prompt_mentions_non_obvious_choices(self):
        """Prompt tells agent to document non-obvious implementation choices."""
        assert "non-obvious" in _PROMPT_TEXT.lower()

    def test_prompt_mentions_punted(self):
        """Prompt tells agent to document what it punted on."""
        assert "punted" in _PROMPT_TEXT.lower()

    def test_staged_prompt_md_mentions_decisions(self, tmp_path: Path):
        """The rendered prompt.md file in workspace mentions decisions.md."""
        workspace, _ = stage_workspace(tmp_path)
        prompt_md = (workspace / "prompt.md").read_text(encoding="utf-8")
        assert "decisions.md" in prompt_md
