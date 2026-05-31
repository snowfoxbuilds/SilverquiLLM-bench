"""Gap tests for item 6: summarize_breadth / load_rows / write_summary / --summary.

Covers gaps NOT addressed by the Tester in tests/test_harvest_summary.py:
  - Empty rows list → empty summary, no crash.
  - Row missing the ``outcome`` key is tolerated (treated as non-fail).
  - ``failing_images`` is genuinely sorted even when images arrive out of order.
  - ``write_summary`` produces newline-terminated, valid JSON (re-loads equal).
  - ``--summary`` over a JSONL of only rollup rows → every group has breadth 0.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import the script module via importlib (scripts/ is not a package)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = REPO_ROOT / "scripts" / "harvest_validated_results.py"

_spec = importlib.util.spec_from_file_location(
    "harvest_validated_results", _SCRIPT_PATH
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("harvest_validated_results", _mod)
_spec.loader.exec_module(_mod)

summarize_breadth = _mod.summarize_breadth
load_rows = _mod.load_rows
write_summary = _mod.write_summary
main = _mod.main


# ---------------------------------------------------------------------------
# 1. Empty rows list → empty summary, no crash
# ---------------------------------------------------------------------------


class TestEmptyRows:
    """summarize_breadth with an empty input must return [] without raising."""

    def test_empty_returns_empty_list(self) -> None:
        result = summarize_breadth([])
        assert result == []

    def test_empty_returns_list_type(self) -> None:
        result = summarize_breadth([])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 2. Row missing the ``outcome`` key is tolerated (no KeyError)
# ---------------------------------------------------------------------------


class TestMissingOutcomeKey:
    """A row without an ``outcome`` key must not raise KeyError.

    The impl uses row.get("outcome"), so a missing key returns None, which
    is not equal to "fail", so the row contributes 0 failing images.
    """

    def test_no_keyerror_on_missing_outcome(self) -> None:
        rows = [
            # No "outcome" key at all
            {"card": "c1", "test_node": "t1", "tests_hash": "h1", "image": "imgA"},
        ]
        # Must not raise
        result = summarize_breadth(rows)
        assert len(result) == 1
        assert result[0]["breadth"] == 0

    def test_missing_outcome_not_counted_as_fail(self) -> None:
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1", "image": "imgA"},
            # Mix: one with explicit "fail", one with no outcome key
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgB", "outcome": "fail"},
        ]
        result = summarize_breadth(rows)
        assert len(result) == 1
        # Only imgB (explicit fail) contributes; imgA (missing key) does not
        assert result[0]["breadth"] == 1
        assert result[0]["failing_images"] == ["imgB"]


# ---------------------------------------------------------------------------
# 3. failing_images is sorted alphabetically regardless of input order
# ---------------------------------------------------------------------------


class TestFailingImagesSorted:
    """failing_images must be sorted lexicographically, not in encounter order."""

    def test_failing_images_sorted_ascending(self) -> None:
        # Images arrive in reverse alphabetical order
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "zz-model", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "aa-model", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "mm-model", "outcome": "fail"},
        ]
        result = summarize_breadth(rows)
        assert len(result) == 1
        fi = result[0]["failing_images"]
        assert fi == sorted(fi), "failing_images must be sorted"
        assert fi == ["aa-model", "mm-model", "zz-model"]

    def test_single_failing_image_sorted_trivially(self) -> None:
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "only-one", "outcome": "fail"},
        ]
        result = summarize_breadth(rows)
        assert result[0]["failing_images"] == ["only-one"]


# ---------------------------------------------------------------------------
# 4. write_summary produces newline-terminated, valid JSON that round-trips
# ---------------------------------------------------------------------------


class TestWriteSummaryValidity:
    """write_summary output is syntactically valid JSON and newline-terminated."""

    def test_written_file_is_newline_terminated(self, tmp_path: Path) -> None:
        summary = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "breadth": 1, "failing_images": ["imgA"]},
        ]
        out = tmp_path / "summary.json"
        write_summary(summary, out)
        raw = out.read_bytes()
        assert raw.endswith(b"\n"), "JSON file must end with a newline"

    def test_round_trip_preserves_structure(self, tmp_path: Path) -> None:
        summary = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "breadth": 2, "failing_images": ["imgA", "imgB"]},
            {"card": "c2", "test_node": "t2", "tests_hash": None,
             "breadth": 0, "failing_images": []},
        ]
        out = tmp_path / "summary.json"
        write_summary(summary, out)
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded == summary

    def test_empty_summary_writes_valid_json(self, tmp_path: Path) -> None:
        out = tmp_path / "empty_summary.json"
        write_summary([], out)
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded == []


# ---------------------------------------------------------------------------
# 5. --summary over JSONL of only rollup rows → all groups breadth 0
# ---------------------------------------------------------------------------


class TestSummaryAllRollupRows:
    """When the JSONL contains only rollup rows (no fail/pass), every group
    in the summary must have breadth 0."""

    def _write_rollup_only_jsonl(self, analysis_dir: Path) -> Path:
        analysis_dir.mkdir(parents=True, exist_ok=True)
        jsonl = analysis_dir / "harvested_results.jsonl"
        rows = [
            {"card": "c1", "test_node": "__rollup__", "tests_hash": None,
             "image": "imgA", "outcome": "rollup"},
            {"card": "c1", "test_node": "__rollup__", "tests_hash": None,
             "image": "imgB", "outcome": "rollup"},
            {"card": "c2", "test_node": "__rollup__", "tests_hash": None,
             "image": "imgA", "outcome": "rollup"},
        ]
        jsonl.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n",
            encoding="utf-8",
        )
        return jsonl

    def test_all_rollup_breadth_zero_via_summarize_breadth(self) -> None:
        rows = [
            {"card": "c1", "test_node": "__rollup__", "tests_hash": None,
             "image": "imgA", "outcome": "rollup"},
            {"card": "c1", "test_node": "__rollup__", "tests_hash": None,
             "image": "imgB", "outcome": "rollup"},
            {"card": "c2", "test_node": "__rollup__", "tests_hash": None,
             "image": "imgA", "outcome": "rollup"},
        ]
        result = summarize_breadth(rows)
        assert all(e["breadth"] == 0 for e in result)
        assert all(e["failing_images"] == [] for e in result)

    def test_summary_cli_all_rollup_breadth_zero(
        self, tmp_path: Path, capsys
    ) -> None:
        analysis_dir = tmp_path / "benchmarks" / "sos" / "analysis"
        jsonl = self._write_rollup_only_jsonl(analysis_dir)
        summary_path = analysis_dir / "harvested_summary.json"

        with mock.patch(
            "sys.argv",
            ["harvest_validated_results.py", "--summary", "--output", str(jsonl)],
        ):
            main(repo_root=tmp_path)

        assert summary_path.is_file()
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) > 0, "Rollup-only JSONL should still produce summary entries"
        assert all(entry["breadth"] == 0 for entry in data)
        assert all(entry["failing_images"] == [] for entry in data)
