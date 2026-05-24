"""Tests for prompt content — engine-extension permission line."""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.workspace import _PROMPT_TEXT, stage_workspace


# The exact sentence that must appear in the prompt.
_ENGINE_PERMISSION = (
    "You are expected to make changes to the engine to implement new mechanics. "
    "The existing code base may not be perfect, you are free to make changes that "
    "don't break current behavior."
)


class TestEngineExtensionPermission:
    """The prompt must contain the engine-extension permission sentence."""

    def test_prompt_template_contains_permission_sentence(self):
        """_PROMPT_TEXT base template includes the engine-extension permission."""
        assert _ENGINE_PERMISSION in _PROMPT_TEXT

    def test_unfiltered_prompt_contains_permission(self, tmp_path: Path):
        """Unfiltered run (card_filter=None) produces prompt.md with permission."""
        workspace, _ = stage_workspace(tmp_path)
        prompt_md = (workspace / "prompt.md").read_text(encoding="utf-8")
        assert _ENGINE_PERMISSION in prompt_md

    def test_filtered_prompt_contains_permission(self, tmp_path: Path):
        """Filtered run (specific cards) still includes the permission line."""
        workspace, _ = stage_workspace(tmp_path, card_filter=["001"])
        prompt_md = (workspace / "prompt.md").read_text(encoding="utf-8")
        assert _ENGINE_PERMISSION in prompt_md

    def test_permission_mentions_engine_changes(self):
        """Key phrase 'make changes to the engine' present in template."""
        assert "make changes to the engine" in _PROMPT_TEXT

    def test_permission_mentions_no_break_current_behavior(self):
        """Key phrase 'don't break current behavior' present in template."""
        assert "don't break current behavior" in _PROMPT_TEXT
