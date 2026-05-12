"""Tests for TODO item 11: agent_thoughts.md narrative generation.

After all rounds for a card complete, ``_generate_agent_thoughts()`` reads
``<output_dir>/cards/<card>/postmortem.jsonl`` and produces a structured Markdown
narrative at ``<output_dir>/cards/<card>/agent_thoughts.md``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from silverquillm.agent_session import _generate_agent_thoughts


def _write_postmortem(output_dir: Path, card: str, entries: list[dict]) -> Path:
    """Helper: write a postmortem.jsonl file under output_dir/cards/<card>/."""
    card_dir = output_dir / "cards" / card
    card_dir.mkdir(parents=True, exist_ok=True)
    path = card_dir / "postmortem.jsonl"
    lines = [json.dumps(e) for e in entries]
    path.write_text("\n".join(lines))
    return path


def _make_entry(
    round_num: int = 1,
    status: str = "success",
    timing_ms: int = 1500,
    prompt: str = "Do something",
    response: str = "Done",
) -> dict:
    return {
        "round": round_num,
        "status": status,
        "timing_ms": timing_ms,
        "prompt": prompt,
        "response": response,
    }


class TestAgentThoughtsCreation:
    """agent_thoughts.md is created after rounds complete."""

    def test_creates_file_with_single_round(self, tmp_path):
        card = "my-card"
        _write_postmortem(tmp_path, card, [_make_entry()])
        result = _generate_agent_thoughts(tmp_path, card)
        assert result is not None
        assert result.exists()
        assert result.name == "agent_thoughts.md"
        assert result.parent == tmp_path / "cards" / card

    def test_returns_path_to_generated_file(self, tmp_path):
        card = "test-card"
        _write_postmortem(tmp_path, card, [_make_entry()])
        result = _generate_agent_thoughts(tmp_path, card)
        assert result == tmp_path / "cards" / card / "agent_thoughts.md"


class TestSummaryHeader:
    """agent_thoughts.md contains a summary header with card name."""

    def test_header_contains_card_name(self, tmp_path):
        card = "fancy-card"
        _write_postmortem(tmp_path, card, [_make_entry()])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert f"# Agent Thoughts: {card}" in content

    def test_header_contains_total_rounds(self, tmp_path):
        card = "c"
        entries = [_make_entry(round_num=i) for i in range(1, 4)]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "**Total rounds:** 3" in content

    def test_header_contains_overall_status(self, tmp_path):
        card = "c"
        _write_postmortem(tmp_path, card, [_make_entry(status="success")])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "**Overall status:**" in content


class TestPerRoundSections:
    """Each round gets its own section with status and timing."""

    def test_round_section_headers(self, tmp_path):
        card = "c"
        entries = [_make_entry(round_num=1), _make_entry(round_num=2)]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "### Round 1" in content
        assert "### Round 2" in content

    def test_round_contains_status(self, tmp_path):
        card = "c"
        _write_postmortem(tmp_path, card, [_make_entry(status="error")])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "**Status:** error" in content

    def test_round_contains_timing_in_seconds(self, tmp_path):
        card = "c"
        _write_postmortem(tmp_path, card, [_make_entry(timing_ms=2500)])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "**Timing:** 2.50s" in content

    def test_round_contains_prompt_summary(self, tmp_path):
        card = "c"
        _write_postmortem(tmp_path, card, [_make_entry(prompt="Fix the bug")])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "Fix the bug" in content

    def test_long_prompt_is_truncated(self, tmp_path):
        card = "c"
        long_prompt = "x" * 200
        _write_postmortem(tmp_path, card, [_make_entry(prompt=long_prompt)])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        # Should be truncated at 100 chars + "..."
        assert "x" * 100 + "..." in content

    def test_long_response_is_truncated(self, tmp_path):
        card = "c"
        long_response = "y" * 400
        _write_postmortem(tmp_path, card, [_make_entry(response=long_response)])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "y" * 200 + "..." in content


class TestEmptyPostmortem:
    """Handles empty postmortem.jsonl gracefully."""

    def test_empty_file_returns_none(self, tmp_path):
        card = "c"
        (tmp_path / "cards" / card).mkdir(parents=True)
        (tmp_path / "cards" / card / "postmortem.jsonl").write_text("")
        result = _generate_agent_thoughts(tmp_path, card)
        assert result is None

    def test_whitespace_only_file_returns_none(self, tmp_path):
        card = "c"
        (tmp_path / "cards" / card).mkdir(parents=True)
        (tmp_path / "cards" / card / "postmortem.jsonl").write_text("  \n  \n")
        result = _generate_agent_thoughts(tmp_path, card)
        assert result is None


class TestMissingPostmortem:
    """Handles missing postmortem.jsonl gracefully."""

    def test_missing_file_returns_none(self, tmp_path):
        card = "c"
        (tmp_path / "cards" / card).mkdir(parents=True)
        result = _generate_agent_thoughts(tmp_path, card)
        assert result is None

    def test_missing_card_dir_returns_none(self, tmp_path):
        result = _generate_agent_thoughts(tmp_path, "nonexistent-card")
        assert result is None


class TestMultipleRounds:
    """Handles JSONL with multiple lines correctly."""

    def test_three_rounds_all_present(self, tmp_path):
        card = "c"
        entries = [
            _make_entry(round_num=1, status="error", timing_ms=1000),
            _make_entry(round_num=2, status="error", timing_ms=2000),
            _make_entry(round_num=3, status="success", timing_ms=3000),
        ]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "### Round 1" in content
        assert "### Round 2" in content
        assert "### Round 3" in content
        assert "**Total rounds:** 3" in content

    def test_overall_status_all_passed(self, tmp_path):
        card = "c"
        entries = [_make_entry(status="success"), _make_entry(round_num=2, status="success")]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "all_passed" in content

    def test_overall_status_all_failed(self, tmp_path):
        card = "c"
        entries = [_make_entry(status="error"), _make_entry(round_num=2, status="error")]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "all_failed" in content

    def test_overall_status_partial(self, tmp_path):
        card = "c"
        entries = [_make_entry(status="error"), _make_entry(round_num=2, status="success")]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "partial" in content


class TestCrossRoundAnalysis:
    """Analysis section exists and contains cross-round observations."""

    def test_analysis_section_present(self, tmp_path):
        card = "c"
        _write_postmortem(tmp_path, card, [_make_entry()])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "## Analysis" in content

    def test_single_round_analysis(self, tmp_path):
        card = "c"
        _write_postmortem(tmp_path, card, [_make_entry(status="success")])
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "Single round" in content

    def test_improvement_pattern_detected(self, tmp_path):
        card = "c"
        entries = [
            _make_entry(round_num=1, status="error"),
            _make_entry(round_num=2, status="success"),
        ]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "Improvement" in content or "improvement" in content

    def test_regression_pattern_detected(self, tmp_path):
        card = "c"
        entries = [
            _make_entry(round_num=1, status="success"),
            _make_entry(round_num=2, status="error"),
        ]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "Regression" in content or "regression" in content

    def test_persistent_failures_noted(self, tmp_path):
        card = "c"
        entries = [
            _make_entry(round_num=1, status="error"),
            _make_entry(round_num=2, status="error"),
            _make_entry(round_num=3, status="error"),
        ]
        _write_postmortem(tmp_path, card, entries)
        _generate_agent_thoughts(tmp_path, card)
        content = (tmp_path / "cards" / card / "agent_thoughts.md").read_text()
        assert "persistent" in content.lower() or "Persistent" in content


class TestEdgeCases:
    """Additional edge cases."""

    def test_malformed_jsonl_lines_skipped(self, tmp_path):
        card = "c"
        (tmp_path / "cards" / card).mkdir(parents=True)
        lines = [
            json.dumps(_make_entry(round_num=1)),
            "not valid json{{{",
            json.dumps(_make_entry(round_num=2)),
        ]
        (tmp_path / "cards" / card / "postmortem.jsonl").write_text("\n".join(lines))
        result = _generate_agent_thoughts(tmp_path, card)
        assert result is not None
        content = result.read_text()
        assert "### Round 1" in content
        assert "### Round 2" in content
        assert "**Total rounds:** 2" in content

    def test_output_dir_as_string(self, tmp_path):
        card = "c"
        _write_postmortem(tmp_path, card, [_make_entry()])
        result = _generate_agent_thoughts(str(tmp_path), card)
        assert result is not None
        assert result.exists()

    def test_missing_fields_in_entry(self, tmp_path):
        """Entries with missing optional fields should not crash."""
        card = "c"
        (tmp_path / "cards" / card).mkdir(parents=True)
        minimal_entry = {"round": 1}
        (tmp_path / "cards" / card / "postmortem.jsonl").write_text(json.dumps(minimal_entry))
        result = _generate_agent_thoughts(tmp_path, card)
        assert result is not None
        content = result.read_text()
        assert "### Round 1" in content
