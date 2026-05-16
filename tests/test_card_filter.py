"""Tests for the --cards filter feature in stage_workspace.

Verifies that:
- card_filter=None stages all SOS cards (default behaviour)
- card_filter=["1","2"] stages only matching SOS cards
- FDN cards are always staged in full regardless of filter
- Prompt text is adjusted when a filter is active
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.workspace import stage_workspace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sos_collector_numbers(workspace: Path) -> set[str]:
    """Return the set of collector numbers staged under workspace/cards/sos/."""
    result = set()
    sos = workspace / "cards" / "sos"
    if not sos.exists():
        return result
    for d in sos.iterdir():
        spec = d / "card_spec.json"
        if d.is_dir() and spec.exists():
            data = json.loads(spec.read_text(encoding="utf-8"))
            cn = str(data.get("collector_number", ""))
            result.add(cn)
    return result


def _fdn_dir_count(workspace: Path) -> int:
    """Return number of FDN card directories staged."""
    fdn = workspace / "cards" / "fdn"
    if not fdn.exists():
        return 0
    return sum(1 for d in fdn.iterdir() if d.is_dir() and (d / "card_spec.json").exists())


def _all_sos_collector_numbers() -> set[str]:
    """Return collector numbers from the source cards/sos directory."""
    repo_root = Path(__file__).resolve().parent.parent
    sos_src = repo_root / "cards" / "sos"
    result = set()
    for d in sos_src.iterdir():
        spec = d / "card_spec.json"
        if d.is_dir() and spec.exists():
            data = json.loads(spec.read_text(encoding="utf-8"))
            cn = str(data.get("collector_number", ""))
            result.add(cn)
    return result


# ---------------------------------------------------------------------------
# card_filter=None → all SOS cards staged
# ---------------------------------------------------------------------------


class TestCardFilterNone:
    """When card_filter is None (default), all SOS cards are staged."""

    def test_all_sos_cards_present(self, tmp_path):
        ws, _ = stage_workspace(tmp_path)
        staged = _sos_collector_numbers(ws)
        expected = _all_sos_collector_numbers()
        assert staged == expected

    def test_fdn_cards_present(self, tmp_path):
        ws, _ = stage_workspace(tmp_path)
        assert _fdn_dir_count(ws) > 0

    def test_prompt_says_all(self, tmp_path):
        ws, _ = stage_workspace(tmp_path)
        prompt = (ws / "prompt.md").read_text()
        assert "Implement all SOS cards" in prompt


# ---------------------------------------------------------------------------
# card_filter with specific collector numbers
# ---------------------------------------------------------------------------


class TestCardFilterSubset:
    """When card_filter is set, only matching SOS cards are staged."""

    def test_only_filtered_sos_cards_staged(self, tmp_path):
        ws, _ = stage_workspace(tmp_path, card_filter=["1", "2"])
        staged = _sos_collector_numbers(ws)
        assert staged == {"1", "2"}

    def test_single_card_filter(self, tmp_path):
        ws, _ = stage_workspace(tmp_path, card_filter=["1"])
        staged = _sos_collector_numbers(ws)
        assert staged == {"1"}

    def test_fdn_always_full_with_filter(self, tmp_path):
        """FDN dirs must always be staged in full regardless of card_filter."""
        ws_filtered, _ = stage_workspace(tmp_path / "filtered", card_filter=["1"])
        ws_unfiltered, _ = stage_workspace(tmp_path / "unfiltered")
        assert _fdn_dir_count(ws_filtered) == _fdn_dir_count(ws_unfiltered)

    def test_fdn_count_positive_with_filter(self, tmp_path):
        ws, _ = stage_workspace(tmp_path, card_filter=["1"])
        assert _fdn_dir_count(ws) > 0

    def test_prompt_mentions_filtered_cards(self, tmp_path):
        ws, _ = stage_workspace(tmp_path, card_filter=["1", "2"])
        prompt = (ws / "prompt.md").read_text()
        assert "1" in prompt
        assert "2" in prompt

    def test_prompt_does_not_say_all_when_filtered(self, tmp_path):
        ws, _ = stage_workspace(tmp_path, card_filter=["1"])
        prompt = (ws / "prompt.md").read_text()
        assert "Implement all SOS cards" not in prompt


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCardFilterEdgeCases:
    """Edge cases for the card_filter parameter."""

    def test_empty_filter_stages_no_sos(self, tmp_path):
        """An empty list means no SOS cards match."""
        ws, _ = stage_workspace(tmp_path, card_filter=[])
        staged = _sos_collector_numbers(ws)
        assert staged == set()

    def test_nonexistent_collector_number_stages_nothing(self, tmp_path):
        """A filter with no matching collector numbers produces empty SOS."""
        ws, _ = stage_workspace(tmp_path, card_filter=["99999"])
        staged = _sos_collector_numbers(ws)
        assert staged == set()

    def test_fdn_present_even_with_empty_filter(self, tmp_path):
        ws, _ = stage_workspace(tmp_path, card_filter=[])
        assert _fdn_dir_count(ws) > 0

    def test_sos_tier_dir_exists_even_when_empty(self, tmp_path):
        """The sos/ directory should exist even when filter matches nothing."""
        ws, _ = stage_workspace(tmp_path, card_filter=["99999"])
        assert (ws / "cards" / "sos").is_dir()


# ---------------------------------------------------------------------------
# Stdout output
# ---------------------------------------------------------------------------


class TestCardFilterStdout:
    """Verify card_filter info is echoed to stdout."""

    def test_prints_filter_value(self, tmp_path, capsys):
        stage_workspace(tmp_path, card_filter=["1", "2"])
        captured = capsys.readouterr().out
        assert "1" in captured
        assert "2" in captured

    def test_prints_all_when_no_filter(self, tmp_path, capsys):
        stage_workspace(tmp_path)
        captured = capsys.readouterr().out
        assert "all" in captured.lower()
