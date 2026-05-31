"""Tests for item 5: Legacy back-compat harvest for Validated Results
lacking per-node data.

Validates that ``build_rows_for_run()`` correctly handles legacy
``result.json`` files (with ``errors`` + counts but no ``test_nodes`` and
no ``tests_hash``): derives fail rows from error strings, emits a
``__rollup__`` row with ``outcome="rollup"``, sets ``tests_hash`` to null,
and never crashes on missing fields.  Also validates that ``harvest()``
prints a per-run legacy notice exactly once.
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
    """Write a result.json into the given card directory."""
    card_dir.mkdir(parents=True, exist_ok=True)
    (card_dir / "result.json").write_text(json.dumps(data), encoding="utf-8")


def _card_dir(root: Path, image: str, run: str, card: str) -> Path:
    return root / "docker" / image / "validated_results" / run / "cards" / card


def _make_legacy_vr(root: Path, image: str, run: str, card: str,
                    result_data: dict) -> ValidatedRun:
    """Create a ValidatedRun with a single legacy card and return the VR."""
    cd = _card_dir(root, image, run, card)
    _write_result_json(cd, result_data)
    return ValidatedRun(
        image=image,
        run=run,
        run_dir=cd.parent.parent,
        card_dirs=[cd],
    )


def _read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file and return a list of parsed dicts."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# 1. Core spec: legacy result.json with errors + counts, no test_nodes/tests_hash
# ---------------------------------------------------------------------------


class TestLegacyCoreSpec:
    """A legacy result.json (errors + counts, no test_nodes, no tests_hash)
    emits fail rows derived from errors and a __rollup__ row."""

    def test_fail_rows_derived_from_errors(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img1", "run1", "sos_1", {
            "tests_passed": 3,
            "tests_failed": 2,
            "tests_total": 5,
            "errors": [
                "FAILED tests.py::test_a - AssertionError",
                "ERROR tests.py::test_b",
            ],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        fail_rows = [r for r in rows if r["outcome"] == "fail"]
        fail_nodes = {r["test_node"] for r in fail_rows}
        assert len(fail_rows) == 2
        assert "tests.py::test_a" in fail_nodes
        assert "tests.py::test_b" in fail_nodes

    def test_rollup_row_emitted(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img1", "run1", "sos_1", {
            "tests_passed": 3,
            "tests_failed": 2,
            "tests_total": 5,
            "errors": [
                "FAILED tests.py::test_a - AssertionError",
                "ERROR tests.py::test_b",
            ],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        rollup_rows = [r for r in rows if r["test_node"] == "__rollup__"]
        assert len(rollup_rows) == 1
        rollup = rollup_rows[0]
        assert rollup["outcome"] == "rollup"
        assert rollup["passed"] == 3
        assert rollup["failed"] == 2
        assert rollup["total"] == 5

    def test_tests_hash_is_none_on_all_rows(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img1", "run1", "sos_1", {
            "tests_passed": 3,
            "tests_failed": 2,
            "tests_total": 5,
            "errors": [
                "FAILED tests.py::test_a - AssertionError",
                "ERROR tests.py::test_b",
            ],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        assert len(rows) == 3  # 2 fail + 1 rollup
        for row in rows:
            assert row["tests_hash"] is None

    def test_no_exception_on_legacy_card(self, tmp_path: Path) -> None:
        """Processing a legacy card must not raise any exception."""
        vr = _make_legacy_vr(tmp_path, "img1", "run1", "sos_1", {
            "tests_passed": 1,
            "tests_failed": 1,
            "tests_total": 2,
            "errors": ["FAILED tests.py::test_x - boom"],
        })
        # Should not raise
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        assert len(rows) >= 1

    def test_no_pass_node_rows_for_legacy(self, tmp_path: Path) -> None:
        """Legacy cards cannot reconstruct passed-node identities, so no
        outcome='pass' rows should be emitted."""
        vr = _make_legacy_vr(tmp_path, "img1", "run1", "sos_1", {
            "tests_passed": 5,
            "tests_failed": 1,
            "tests_total": 6,
            "errors": ["FAILED tests.py::test_x - boom"],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        pass_rows = [r for r in rows if r["outcome"] == "pass"]
        assert len(pass_rows) == 0


# ---------------------------------------------------------------------------
# 2. De-duplication: duplicate node ids in errors produce single fail row
# ---------------------------------------------------------------------------


class TestDeDuplication:
    """Duplicate node IDs in the errors list produce a single fail row."""

    def test_duplicate_node_ids_deduped(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img2", "run2", "sos_2", {
            "tests_passed": 0,
            "tests_failed": 2,
            "tests_total": 2,
            "errors": [
                "FAILED tests.py::test_dup - first",
                "FAILED tests.py::test_dup - second",
            ],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        fail_rows = [r for r in rows if r["outcome"] == "fail"]
        assert len(fail_rows) == 1
        assert fail_rows[0]["test_node"] == "tests.py::test_dup"


# ---------------------------------------------------------------------------
# 3. Unparseable error line -> synthetic collection-error node
# ---------------------------------------------------------------------------


class TestUnparseableErrors:
    """An errors entry with no parseable node id emits a synthetic
    collection-error fail row."""

    def test_bare_collection_error_string(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img3", "run3", "sos_3", {
            "tests_passed": 0,
            "tests_failed": 1,
            "tests_total": 1,
            "errors": [
                "ImportError while importing test module '/tmp/tests.py'",
            ],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        fail_rows = [r for r in rows if r["outcome"] == "fail"]
        assert len(fail_rows) == 1
        assert fail_rows[0]["test_node"] == "tests.py::<collection-error>"

    def test_failed_without_double_colon_becomes_collection_error(self, tmp_path: Path) -> None:
        """A FAILED line whose node-id has no :: separator is treated as
        a collection error."""
        vr = _make_legacy_vr(tmp_path, "img3", "run3", "sos_3b", {
            "tests_passed": 0,
            "tests_failed": 1,
            "tests_total": 1,
            "errors": [
                "FAILED tests.py - something went wrong",
            ],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        fail_rows = [r for r in rows if r["outcome"] == "fail"]
        assert len(fail_rows) == 1
        assert fail_rows[0]["test_node"] == "tests.py::<collection-error>"

    def test_no_crash_on_collection_error(self, tmp_path: Path) -> None:
        """Unparseable lines must not crash the builder."""
        vr = _make_legacy_vr(tmp_path, "img3", "run3", "sos_3c", {
            "tests_passed": 0,
            "tests_failed": 1,
            "tests_total": 1,
            "errors": ["completely unparseable garbage"],
        })
        # Should not raise
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        assert len(rows) >= 1  # at least the rollup


# ---------------------------------------------------------------------------
# 4. Missing errors field entirely -> rollup row only, no crash
# ---------------------------------------------------------------------------


class TestMissingErrors:
    """When errors field is entirely absent, the legacy card still emits
    the __rollup__ row with 0 fail rows."""

    def test_missing_errors_emits_rollup_only(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img4", "run4", "sos_4", {
            "tests_passed": 5,
            "tests_failed": 0,
            "tests_total": 5,
            # no errors field
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        fail_rows = [r for r in rows if r["outcome"] == "fail"]
        rollup_rows = [r for r in rows if r["test_node"] == "__rollup__"]
        assert len(fail_rows) == 0
        assert len(rollup_rows) == 1
        assert rollup_rows[0]["outcome"] == "rollup"

    def test_missing_errors_no_crash(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img4", "run4", "sos_4b", {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
        })
        # Should not raise
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# 5. Missing count fields -> rollup row defaults counts to 0, no crash
# ---------------------------------------------------------------------------


class TestMissingCounts:
    """When count fields (tests_passed, tests_failed, tests_total) are
    missing, the rollup row defaults them to 0."""

    def test_missing_counts_default_to_zero(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img5", "run5", "sos_5", {
            # No tests_passed, tests_failed, tests_total
            "errors": ["FAILED tests.py::test_x - boom"],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        rollup_rows = [r for r in rows if r["test_node"] == "__rollup__"]
        assert len(rollup_rows) == 1
        assert rollup_rows[0]["passed"] == 0
        assert rollup_rows[0]["failed"] == 0
        assert rollup_rows[0]["total"] == 0

    def test_missing_counts_no_crash(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img5", "run5", "sos_5b", {})
        # Should not raise
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        assert len(rows) == 1  # just the rollup


# ---------------------------------------------------------------------------
# 6. Rollup outcome is neither "pass" nor "fail"
# ---------------------------------------------------------------------------


class TestRollupOutcome:
    """The __rollup__ row's outcome is 'rollup', which is neither 'pass'
    nor 'fail', so downstream breadth metrics won't miscount it."""

    def test_rollup_outcome_is_rollup(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img6", "run6", "sos_6", {
            "tests_passed": 2,
            "tests_failed": 1,
            "tests_total": 3,
            "errors": ["FAILED tests.py::test_z - boom"],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        rollup_rows = [r for r in rows if r["test_node"] == "__rollup__"]
        assert len(rollup_rows) == 1
        assert rollup_rows[0]["outcome"] != "pass"
        assert rollup_rows[0]["outcome"] != "fail"
        assert rollup_rows[0]["outcome"] == "rollup"


# ---------------------------------------------------------------------------
# 7. Per-run legacy notice via harvest()
# ---------------------------------------------------------------------------


class TestLegacyNotice:
    """harvest() prints a per-run [legacy] notice for runs with legacy cards,
    and does NOT print it for purely modern runs."""

    def test_legacy_run_prints_notice(self, tmp_path: Path, capsys) -> None:
        cd = _card_dir(tmp_path, "legacy-img", "legacy-run", "sos_70")
        _write_result_json(cd, {
            "tests_passed": 1,
            "tests_failed": 1,
            "tests_total": 2,
            "errors": ["FAILED tests.py::test_a - boom"],
            # no test_nodes — legacy
        })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)

        captured = capsys.readouterr().out
        assert "[legacy]" in captured
        assert "legacy-img/legacy-run" in captured

    def test_legacy_notice_appears_exactly_once_per_run(self, tmp_path: Path, capsys) -> None:
        """Even with multiple legacy cards in one run, only one notice per run."""
        for card_name in ("sos_80", "sos_81"):
            cd = _card_dir(tmp_path, "multi-img", "multi-run", card_name)
            _write_result_json(cd, {
                "tests_passed": 1,
                "tests_failed": 0,
                "tests_total": 1,
            })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)

        captured = capsys.readouterr().out
        legacy_lines = [l for l in captured.splitlines() if "[legacy]" in l]
        assert len(legacy_lines) == 1
        assert "multi-img/multi-run" in legacy_lines[0]

    def test_modern_run_no_legacy_notice(self, tmp_path: Path, capsys) -> None:
        cd = _card_dir(tmp_path, "modern-img", "modern-run", "sos_90")
        _write_result_json(cd, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "abc",
            "test_nodes": [{"test_node": "tests.py::test_m", "outcome": "pass"}],
        })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)

        captured = capsys.readouterr().out
        assert "[legacy]" not in captured


# ---------------------------------------------------------------------------
# 8. tests_hash absent in legacy card -> null, never read stray value
# ---------------------------------------------------------------------------


class TestLegacyTestsHash:
    """When test_nodes is absent (legacy), tests_hash is always null even if
    a stray tests_hash value is present in result.json."""

    def test_absent_tests_hash_yields_null(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img8", "run8", "sos_8", {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            # no tests_hash, no test_nodes
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        for row in rows:
            assert row["tests_hash"] is None

    def test_stray_tests_hash_ignored_for_legacy(self, tmp_path: Path) -> None:
        """Even if a legacy card has a tests_hash value in result.json
        (from partial tooling), it should be overridden to null because
        test_nodes is absent, making this a legacy card."""
        vr = _make_legacy_vr(tmp_path, "img8b", "run8b", "sos_8b", {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "stray_value_should_be_ignored",
            # no test_nodes — this IS a legacy card
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        for row in rows:
            assert row["tests_hash"] is None


# ---------------------------------------------------------------------------
# 9. Node-ID normalization: paths with directory prefixes
# ---------------------------------------------------------------------------


class TestNodeIdNormalization:
    """FAILED lines with directory prefixes in the node ID are normalized
    to ``filename::test_name`` form."""

    def test_full_path_stripped(self, tmp_path: Path) -> None:
        vr = _make_legacy_vr(tmp_path, "img9", "run9", "sos_9", {
            "tests_passed": 0,
            "tests_failed": 1,
            "tests_total": 1,
            "errors": [
                "FAILED /tmp/eval_sos_abc123/tests.py::test_z - reason",
            ],
        })
        rows = build_rows_for_run(vr, harvested_at=FIXED_TS)
        fail_rows = [r for r in rows if r["outcome"] == "fail"]
        assert len(fail_rows) == 1
        assert fail_rows[0]["test_node"] == "tests.py::test_z"
