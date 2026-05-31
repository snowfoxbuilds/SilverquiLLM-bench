"""Additional tests for item 5 legacy gaps not covered by the Tester.

Covers three genuine gaps:
1. A run with BOTH modern and legacy cards prints the [legacy] notice exactly
   once via harvest() AND emits both modern per-node rows and legacy fail/rollup
   rows in the same output file.
2. A FAILED error line whose reason text itself contains '::' (e.g.
   "FAILED tests.py::test_x - assert foo::bar failed") does not produce a
   bogus extra node — the node ID is parsed correctly.
3. harvest() with the image= filter scoped to an all-legacy image produces
   only rollup/fail rows (no modern pass rows) and does not crash.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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

harvest = _mod.harvest
build_rows_for_run = _mod.build_rows_for_run
ValidatedRun = _mod.ValidatedRun

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXED_TS = "2026-05-31T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_result_json(card_dir: Path, data: dict) -> None:
    card_dir.mkdir(parents=True, exist_ok=True)
    (card_dir / "result.json").write_text(json.dumps(data), encoding="utf-8")


def _card_dir(root: Path, image: str, run: str, card: str) -> Path:
    return root / "docker" / image / "validated_results" / run / "cards" / card


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Gap 1: Mixed legacy+modern run via harvest() — notice once + correct rows
# ---------------------------------------------------------------------------


class TestMixedRunNoticeAndRows:
    """A run containing BOTH a modern card and a legacy card:
    - harvest() prints the [legacy] notice exactly once for that run
    - the output contains the modern per-node row(s) AND legacy fail+rollup rows
    """

    def test_mixed_run_prints_notice_once(self, tmp_path: Path, capsys) -> None:
        # Modern card (has test_nodes)
        cd_modern = _card_dir(tmp_path, "mix-img", "mix-run", "sos_m1")
        _write_result_json(cd_modern, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "modern_hash",
            "test_nodes": [{"test_node": "tests.py::test_modern", "outcome": "pass"}],
        })

        # Legacy card (no test_nodes)
        cd_legacy = _card_dir(tmp_path, "mix-img", "mix-run", "sos_l1")
        _write_result_json(cd_legacy, {
            "tests_passed": 0,
            "tests_failed": 1,
            "tests_total": 1,
            "errors": ["FAILED tests.py::test_legacy - boom"],
        })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)

        captured = capsys.readouterr().out
        legacy_lines = [line for line in captured.splitlines() if "[legacy]" in line]
        # Exactly one notice for the run
        assert len(legacy_lines) == 1
        assert "mix-img/mix-run" in legacy_lines[0]

    def test_mixed_run_emits_modern_and_legacy_rows(self, tmp_path: Path) -> None:
        # Modern card
        cd_modern = _card_dir(tmp_path, "mix2-img", "mix2-run", "sos_m2")
        _write_result_json(cd_modern, {
            "tests_passed": 2,
            "tests_failed": 0,
            "tests_total": 2,
            "tests_hash": "h_modern",
            "test_nodes": [
                {"test_node": "tests.py::test_a", "outcome": "pass"},
                {"test_node": "tests.py::test_b", "outcome": "pass"},
            ],
        })

        # Legacy card with one fail
        cd_legacy = _card_dir(tmp_path, "mix2-img", "mix2-run", "sos_l2")
        _write_result_json(cd_legacy, {
            "tests_passed": 1,
            "tests_failed": 1,
            "tests_total": 2,
            "errors": ["FAILED tests.py::test_fail - AssertionError"],
        })

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)

        # 2 modern node rows + 1 legacy fail row + 1 legacy rollup row = 4
        assert count == 4
        assert len(rows) == 4

        modern_rows = [r for r in rows if r["card"] == "sos_m2"]
        legacy_rows = [r for r in rows if r["card"] == "sos_l2"]

        # Modern rows: 2 pass nodes, tests_hash set
        assert len(modern_rows) == 2
        assert all(r["outcome"] == "pass" for r in modern_rows)
        assert all(r["tests_hash"] == "h_modern" for r in modern_rows)

        # Legacy rows: 1 fail + 1 rollup, tests_hash null
        assert len(legacy_rows) == 2
        fail_rows = [r for r in legacy_rows if r["outcome"] == "fail"]
        rollup_rows = [r for r in legacy_rows if r["test_node"] == "__rollup__"]
        assert len(fail_rows) == 1
        assert fail_rows[0]["test_node"] == "tests.py::test_fail"
        assert fail_rows[0]["tests_hash"] is None
        assert len(rollup_rows) == 1
        assert rollup_rows[0]["outcome"] == "rollup"
        assert rollup_rows[0]["tests_hash"] is None


# ---------------------------------------------------------------------------
# Gap 2: '::' in reason text does not produce a bogus extra node
# ---------------------------------------------------------------------------


class TestColonsInReasonText:
    """A FAILED line whose reason text contains '::' is parsed correctly:
    only one fail row is emitted, with the correct test_node."""

    def test_double_colon_in_reason_does_not_add_extra_node(
        self, tmp_path: Path
    ) -> None:
        """FAILED tests.py::test_x - assert foo::bar failed  =>  one fail row
        with test_node='tests.py::test_x'."""
        vr = ValidatedRun(
            image="img-cc", run="run-cc", run_dir=tmp_path,
            card_dirs=[],
        )
        cd = _card_dir(tmp_path, "img-cc", "run-cc", "sos_cc1")
        _write_result_json(cd, {
            "tests_passed": 0,
            "tests_failed": 1,
            "tests_total": 1,
            "errors": [
                "FAILED tests.py::test_x - assert foo::bar == baz::qux failed",
            ],
        })
        vr = ValidatedRun(
            image="img-cc", run="run-cc", run_dir=cd.parent.parent,
            card_dirs=[cd],
        )

        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        fail_rows = [r for r in rows if r["outcome"] == "fail"]

        # Must be exactly one fail row — not one per '::' segment in reason
        assert len(fail_rows) == 1
        assert fail_rows[0]["test_node"] == "tests.py::test_x"

    def test_multiple_colons_in_reason_single_fail_row(
        self, tmp_path: Path
    ) -> None:
        """Multiple '::' in reason: still one fail row, correct node."""
        cd = _card_dir(tmp_path, "img-cc2", "run-cc2", "sos_cc2")
        _write_result_json(cd, {
            "tests_passed": 0,
            "tests_failed": 1,
            "tests_total": 1,
            "errors": [
                "FAILED tests.py::test_y - E AssertionError: a::b::c != d::e",
            ],
        })
        vr = ValidatedRun(
            image="img-cc2", run="run-cc2", run_dir=cd.parent.parent,
            card_dirs=[cd],
        )

        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        fail_rows = [r for r in rows if r["outcome"] == "fail"]

        assert len(fail_rows) == 1
        assert fail_rows[0]["test_node"] == "tests.py::test_y"


# ---------------------------------------------------------------------------
# Gap 3: harvest() with image= filter on all-legacy image — no crash, only
#         rollup/fail rows, no modern pass rows
# ---------------------------------------------------------------------------


class TestHarvestImageFilterAllLegacy:
    """harvest() filtered to an all-legacy image produces only rollup/fail
    rows and does not crash.  Modern runs for other images are excluded."""

    def test_image_filter_returns_only_legacy_rows(
        self, tmp_path: Path
    ) -> None:
        # All-legacy image
        for card_name in ("sos_100", "sos_101"):
            cd = _card_dir(tmp_path, "legacy-only-img", "run-legacy", card_name)
            _write_result_json(cd, {
                "tests_passed": 2,
                "tests_failed": 1,
                "tests_total": 3,
                "errors": [f"FAILED tests.py::test_{card_name} - boom"],
            })

        # Modern image that should be excluded by the filter
        cd_modern = _card_dir(tmp_path, "modern-only-img", "run-modern", "sos_200")
        _write_result_json(cd_modern, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "mh",
            "test_nodes": [{"test_node": "tests.py::test_z", "outcome": "pass"}],
        })

        out = tmp_path / "out.jsonl"
        count = harvest(
            tmp_path,
            output=str(out),
            image="legacy-only-img",
            harvested_at=FIXED_TS,
        )
        rows = _read_jsonl(out)

        # 2 cards * (1 fail + 1 rollup) = 4 rows; no modern rows
        assert count == 4
        assert len(rows) == 4
        assert all(r["image"] == "legacy-only-img" for r in rows)

        outcomes = {r["outcome"] for r in rows}
        assert outcomes == {"fail", "rollup"}
        # No pass rows
        assert not any(r["outcome"] == "pass" for r in rows)
        # All tests_hash null
        assert all(r["tests_hash"] is None for r in rows)
