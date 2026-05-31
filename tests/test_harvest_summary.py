"""Tests for item 6: Cross-impl breadth summary view (--summary).

Validates ``summarize_breadth()``, ``load_rows()``, ``write_summary()``,
and the ``--summary`` CLI mode in ``scripts/harvest_validated_results.py``.

Breadth = count of distinct ``image`` values with ``outcome == "fail"``
per ``(card, test_node, tests_hash)`` group.  Ranking is descending by
breadth, ties broken ascending by ``(card, test_node, tests_hash)`` with
``None`` sorting after all strings.
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
# 1. Breadth counts distinct failing images; pass does not contribute;
#    duplicate failing image counted once
# ---------------------------------------------------------------------------


class TestBreadthBasic:
    """A group with 3 distinct failing images (one duplicate) and 1 pass
    image has breadth == 3, and failing_images is the sorted list of the
    3 distinct images."""

    def test_breadth_equals_distinct_failing_images(self) -> None:
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "alpha", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "beta", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "gamma", "outcome": "fail"},
            # duplicate failing image -- must count once
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "alpha", "outcome": "fail"},
            # pass does NOT contribute
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "delta", "outcome": "pass"},
        ]
        summary = summarize_breadth(rows)
        assert len(summary) == 1
        entry = summary[0]
        assert entry["breadth"] == 3
        assert entry["failing_images"] == ["alpha", "beta", "gamma"]

    def test_pass_image_not_in_failing_images(self) -> None:
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "alpha", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "delta", "outcome": "pass"},
        ]
        summary = summarize_breadth(rows)
        assert "delta" not in summary[0]["failing_images"]


# ---------------------------------------------------------------------------
# 2. Same (card, test_node) under different tests_hash = separate groups
# ---------------------------------------------------------------------------


class TestDifferentTestsHash:
    """The same (card, test_node) under different tests_hash values produces
    two distinct groups with independent breadths."""

    def test_different_hash_separate_groups(self) -> None:
        rows = [
            # hash "h1" group -- 2 failing images
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgA", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgB", "outcome": "fail"},
            # hash "h2" group -- 1 failing image
            {"card": "c1", "test_node": "t1", "tests_hash": "h2",
             "image": "imgC", "outcome": "fail"},
        ]
        summary = summarize_breadth(rows)
        assert len(summary) == 2
        by_hash = {e["tests_hash"]: e for e in summary}
        assert by_hash["h1"]["breadth"] == 2
        assert by_hash["h2"]["breadth"] == 1


# ---------------------------------------------------------------------------
# 3. tests_hash=None (legacy) vs real hash = separate groups
# ---------------------------------------------------------------------------


class TestNoneTestsHash:
    """tests_hash=None is its own distinct group, separate from any real
    hash for the same (card, test_node)."""

    def test_none_vs_real_hash_separate(self) -> None:
        rows = [
            # None group
            {"card": "c1", "test_node": "t1", "tests_hash": None,
             "image": "imgA", "outcome": "fail"},
            # "abc" group
            {"card": "c1", "test_node": "t1", "tests_hash": "abc",
             "image": "imgA", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "abc",
             "image": "imgB", "outcome": "fail"},
        ]
        summary = summarize_breadth(rows)
        assert len(summary) == 2
        by_hash = {e["tests_hash"]: e for e in summary}
        assert by_hash[None]["breadth"] == 1
        assert by_hash["abc"]["breadth"] == 2


# ---------------------------------------------------------------------------
# 4. Ranking: descending by breadth; tie-break determinism
# ---------------------------------------------------------------------------


class TestRanking:
    """Results are ranked descending by breadth.  Ties are broken by
    ascending (card, test_node, tests_hash), with None sorting last."""

    def test_descending_breadth(self) -> None:
        rows = [
            # Group A: breadth 3
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "i1", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "i2", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "i3", "outcome": "fail"},
            # Group B: breadth 1
            {"card": "c2", "test_node": "t2", "tests_hash": "h2",
             "image": "i1", "outcome": "fail"},
            # Group C: breadth 2
            {"card": "c3", "test_node": "t3", "tests_hash": "h3",
             "image": "i1", "outcome": "fail"},
            {"card": "c3", "test_node": "t3", "tests_hash": "h3",
             "image": "i2", "outcome": "fail"},
        ]
        summary = summarize_breadth(rows)
        breadths = [e["breadth"] for e in summary]
        assert breadths == sorted(breadths, reverse=True)
        # Specific ordering: 3, 2, 1
        assert breadths == [3, 2, 1]

    def test_known_higher_breadth_precedes_lower(self) -> None:
        rows = [
            {"card": "lo", "test_node": "t1", "tests_hash": "h1",
             "image": "i1", "outcome": "fail"},
            {"card": "hi", "test_node": "t2", "tests_hash": "h2",
             "image": "i1", "outcome": "fail"},
            {"card": "hi", "test_node": "t2", "tests_hash": "h2",
             "image": "i2", "outcome": "fail"},
        ]
        summary = summarize_breadth(rows)
        assert summary[0]["card"] == "hi"
        assert summary[0]["breadth"] == 2
        assert summary[1]["card"] == "lo"
        assert summary[1]["breadth"] == 1

    def test_tiebreak_ascending_card_test_hash(self) -> None:
        """Two groups with equal breadth appear in ascending
        (card, test_node, tests_hash) order."""
        rows = [
            # Group B: breadth 1
            {"card": "c2", "test_node": "t1", "tests_hash": "h1",
             "image": "i1", "outcome": "fail"},
            # Group A: breadth 1 -- should sort first (c1 < c2)
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "i1", "outcome": "fail"},
        ]
        summary = summarize_breadth(rows)
        assert summary[0]["card"] == "c1"
        assert summary[1]["card"] == "c2"

    def test_tiebreak_test_node(self) -> None:
        """With same card and same tests_hash, tie-break by test_node."""
        rows = [
            {"card": "c1", "test_node": "t2", "tests_hash": "h1",
             "image": "i1", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "i1", "outcome": "fail"},
        ]
        summary = summarize_breadth(rows)
        assert summary[0]["test_node"] == "t1"
        assert summary[1]["test_node"] == "t2"

    def test_tiebreak_none_tests_hash_sorts_after_strings(self) -> None:
        """With equal breadth, the group with tests_hash=None sorts after
        the group with a string tests_hash."""
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": None,
             "image": "i1", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "aaa",
             "image": "i1", "outcome": "fail"},
        ]
        summary = summarize_breadth(rows)
        assert len(summary) == 2
        assert summary[0]["tests_hash"] == "aaa"
        assert summary[1]["tests_hash"] is None


# ---------------------------------------------------------------------------
# 5. outcome="rollup" does not contribute to breadth
# ---------------------------------------------------------------------------


class TestRollupDoesNotCount:
    """Rows with outcome='rollup' (or 'pass') do not contribute to breadth.
    A group with only rollup + pass rows has breadth 0."""

    def test_rollup_only_group_breadth_zero(self) -> None:
        rows = [
            {"card": "c1", "test_node": "__rollup__", "tests_hash": None,
             "image": "imgA", "outcome": "rollup"},
            {"card": "c1", "test_node": "__rollup__", "tests_hash": None,
             "image": "imgB", "outcome": "rollup"},
        ]
        summary = summarize_breadth(rows)
        assert len(summary) == 1
        assert summary[0]["breadth"] == 0
        assert summary[0]["failing_images"] == []

    def test_rollup_plus_pass_breadth_zero(self) -> None:
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgA", "outcome": "rollup"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgB", "outcome": "pass"},
        ]
        summary = summarize_breadth(rows)
        assert len(summary) == 1
        assert summary[0]["breadth"] == 0


# ---------------------------------------------------------------------------
# 6. Pass-only group has breadth 0 and IS included in output
# ---------------------------------------------------------------------------


class TestPassOnlyGroupIncluded:
    """A group with only pass rows has breadth 0, and is still included in
    the summary (ranked last)."""

    def test_pass_only_breadth_zero_included(self) -> None:
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgA", "outcome": "pass"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgB", "outcome": "pass"},
        ]
        summary = summarize_breadth(rows)
        assert len(summary) == 1
        assert summary[0]["breadth"] == 0
        assert summary[0]["failing_images"] == []

    def test_pass_only_ranked_last(self) -> None:
        """A pass-only group (breadth 0) ranks after a failing group."""
        rows = [
            # Group with failures
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgA", "outcome": "fail"},
            # Pass-only group
            {"card": "c2", "test_node": "t2", "tests_hash": "h2",
             "image": "imgA", "outcome": "pass"},
        ]
        summary = summarize_breadth(rows)
        assert len(summary) == 2
        assert summary[0]["breadth"] == 1
        assert summary[0]["card"] == "c1"
        assert summary[1]["breadth"] == 0
        assert summary[1]["card"] == "c2"


# ---------------------------------------------------------------------------
# 7. load_rows: round-trip JSONL with blank lines
# ---------------------------------------------------------------------------


class TestLoadRows:
    """load_rows round-trips a JSONL file and tolerates blank lines."""

    def test_round_trip(self, tmp_path: Path) -> None:
        rows_in = [
            {"card": "c1", "test_node": "t1", "outcome": "fail"},
            {"card": "c2", "test_node": "t2", "outcome": "pass"},
        ]
        jsonl = tmp_path / "data.jsonl"
        jsonl.write_text(
            "\n".join(json.dumps(r) for r in rows_in) + "\n",
            encoding="utf-8",
        )
        rows_out = load_rows(jsonl)
        assert rows_out == rows_in

    def test_tolerates_blank_lines(self, tmp_path: Path) -> None:
        content = (
            '{"card": "c1", "test_node": "t1", "outcome": "fail"}\n'
            "\n"
            '{"card": "c2", "test_node": "t2", "outcome": "pass"}\n'
            "\n"
            "\n"
        )
        jsonl = tmp_path / "blank.jsonl"
        jsonl.write_text(content, encoding="utf-8")
        rows = load_rows(jsonl)
        assert len(rows) == 2
        assert rows[0]["card"] == "c1"
        assert rows[1]["card"] == "c2"

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "empty.jsonl"
        jsonl.write_text("", encoding="utf-8")
        rows = load_rows(jsonl)
        assert rows == []


# ---------------------------------------------------------------------------
# 8. CLI --summary integration: write summary JSON and print report
# ---------------------------------------------------------------------------


class TestSummaryCLI:
    """--summary mode loads JSONL, writes harvested_summary.json sibling,
    and prints a ranked report to stdout."""

    def _write_fixture_jsonl(self, analysis_dir: Path) -> Path:
        """Write a small fixture JSONL and return the path."""
        analysis_dir.mkdir(parents=True, exist_ok=True)
        jsonl = analysis_dir / "harvested_results.jsonl"
        rows = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgA", "outcome": "fail"},
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "image": "imgB", "outcome": "fail"},
            {"card": "c2", "test_node": "t2", "tests_hash": "h2",
             "image": "imgA", "outcome": "pass"},
        ]
        jsonl.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n",
            encoding="utf-8",
        )
        return jsonl

    def test_summary_json_created(self, tmp_path: Path, capsys) -> None:
        analysis_dir = tmp_path / "benchmarks" / "sos" / "analysis"
        jsonl = self._write_fixture_jsonl(analysis_dir)
        summary_path = analysis_dir / "harvested_summary.json"

        with mock.patch(
            "sys.argv",
            ["harvest_validated_results.py", "--summary", "--output", str(jsonl)],
        ):
            main(repo_root=tmp_path)

        assert summary_path.is_file()
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 2  # two groups: c1/t1/h1 and c2/t2/h2

    def test_summary_json_content_ranked(self, tmp_path: Path, capsys) -> None:
        analysis_dir = tmp_path / "benchmarks" / "sos" / "analysis"
        jsonl = self._write_fixture_jsonl(analysis_dir)
        summary_path = analysis_dir / "harvested_summary.json"

        with mock.patch(
            "sys.argv",
            ["harvest_validated_results.py", "--summary", "--output", str(jsonl)],
        ):
            main(repo_root=tmp_path)

        data = json.loads(summary_path.read_text(encoding="utf-8"))
        # Highest breadth first
        assert data[0]["breadth"] == 2
        assert data[0]["card"] == "c1"
        assert data[0]["failing_images"] == ["imgA", "imgB"]
        # Second group: pass-only breadth 0
        assert data[1]["breadth"] == 0
        assert data[1]["card"] == "c2"

    def test_report_printed_to_stdout(self, tmp_path: Path, capsys) -> None:
        analysis_dir = tmp_path / "benchmarks" / "sos" / "analysis"
        jsonl = self._write_fixture_jsonl(analysis_dir)

        with mock.patch(
            "sys.argv",
            ["harvest_validated_results.py", "--summary", "--output", str(jsonl)],
        ):
            main(repo_root=tmp_path)

        captured = capsys.readouterr().out
        # Should contain breadth report header and group entries
        assert "breadth" in captured.lower() or "Breadth" in captured
        # Should mention the cards
        assert "c1" in captured
        assert "c2" in captured


# ---------------------------------------------------------------------------
# 9. CLI --summary with missing JSONL -> non-zero exit + stderr message
# ---------------------------------------------------------------------------


class TestSummaryMissingJSONL:
    """When --summary is invoked and the JSONL file does not exist, the
    script exits with non-zero status and prints a message to stderr."""

    def test_missing_jsonl_exits_nonzero(self, tmp_path: Path, capsys) -> None:
        nonexistent = tmp_path / "benchmarks" / "sos" / "analysis" / "harvested_results.jsonl"
        assert not nonexistent.exists()

        with pytest.raises(SystemExit) as exc_info:
            with mock.patch(
                "sys.argv",
                ["harvest_validated_results.py", "--summary", "--output", str(nonexistent)],
            ):
                main(repo_root=tmp_path)

        assert exc_info.value.code != 0

    def test_missing_jsonl_stderr_message(self, tmp_path: Path, capsys) -> None:
        nonexistent = tmp_path / "benchmarks" / "sos" / "analysis" / "harvested_results.jsonl"

        with pytest.raises(SystemExit):
            with mock.patch(
                "sys.argv",
                ["harvest_validated_results.py", "--summary", "--output", str(nonexistent)],
            ):
                main(repo_root=tmp_path)

        captured = capsys.readouterr().err
        assert "does not exist" in captured or str(nonexistent) in captured


# ---------------------------------------------------------------------------
# 10. write_summary produces valid JSON with expected shape
# ---------------------------------------------------------------------------


class TestWriteSummary:
    """write_summary writes pretty-printed JSON that round-trips cleanly."""

    def test_write_summary_round_trip(self, tmp_path: Path) -> None:
        summary = [
            {"card": "c1", "test_node": "t1", "tests_hash": "h1",
             "breadth": 3, "failing_images": ["a", "b", "c"]},
        ]
        out = tmp_path / "summary.json"
        write_summary(summary, out)
        assert out.is_file()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded == summary

    def test_write_summary_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "dir" / "summary.json"
        assert not out.parent.exists()
        write_summary([], out)
        assert out.is_file()
