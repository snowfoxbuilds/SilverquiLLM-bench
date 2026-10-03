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
    sos_src = repo_root / "benchmarks" / "sos" / "workspace" / "cards" / "sos"
    result = set()
    for d in sos_src.iterdir():
        spec = d / "card_spec.json"
        if d.is_dir() and spec.exists():
            data = json.loads(spec.read_text(encoding="utf-8"))
            cn = str(data.get("collector_number", ""))
            result.add(cn)
    return result


# ---------------------------------------------------------------------------
# One staging per filter, each checked for everything that filter decides
# ---------------------------------------------------------------------------


def test_no_filter_stages_every_sos_card_and_fdn_and_says_all(staged_sos_workspace):
    ws, _ = staged_sos_workspace
    assert _sos_collector_numbers(ws) == _all_sos_collector_numbers()
    assert _fdn_dir_count(ws) > 0
    assert "Implement all SOS cards" in (ws / "prompt.md").read_text()


def test_a_subset_filter_stages_only_its_cards_names_them_and_prints_them(tmp_path, capsys):
    ws, _ = stage_workspace(tmp_path, card_filter=["1", "2"])
    captured = capsys.readouterr().out
    assert _sos_collector_numbers(ws) == {"1", "2"}
    prompt = (ws / "prompt.md").read_text()
    assert "1" in prompt
    assert "2" in prompt
    assert "1" in captured
    assert "2" in captured


def test_a_single_card_filter_keeps_fdn_in_full_and_never_says_all(
    tmp_path, staged_sos_workspace
):
    """FDN dirs must always be staged in full regardless of card_filter."""
    ws, _ = stage_workspace(tmp_path, card_filter=["1"])
    unfiltered, _ = staged_sos_workspace
    assert _sos_collector_numbers(ws) == {"1"}
    assert _fdn_dir_count(ws) > 0
    assert _fdn_dir_count(ws) == _fdn_dir_count(unfiltered)
    assert "Implement all SOS cards" not in (ws / "prompt.md").read_text()


def test_an_empty_filter_stages_no_sos_card_but_all_fdn(tmp_path):
    """An empty list means no SOS cards match."""
    ws, _ = stage_workspace(tmp_path, card_filter=[])
    assert _sos_collector_numbers(ws) == set()
    assert _fdn_dir_count(ws) > 0


def test_an_unmatched_filter_stages_nothing_but_keeps_the_sos_dir(tmp_path):
    """A filter with no matching collector numbers produces an empty, present sos/ directory."""
    ws, _ = stage_workspace(tmp_path, card_filter=["99999"])
    assert _sos_collector_numbers(ws) == set()
    assert (ws / "cards" / "sos").is_dir()


# ---------------------------------------------------------------------------
# Stdout output
# ---------------------------------------------------------------------------


class TestCardFilterStdout:
    """Verify card_filter info is echoed to stdout."""

    def test_prints_all_when_no_filter(self, tmp_path, capsys):
        stage_workspace(tmp_path)
        captured = capsys.readouterr().out
        assert "all" in captured.lower()
