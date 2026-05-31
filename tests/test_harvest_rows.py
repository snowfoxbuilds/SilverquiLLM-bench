"""Tests for item 4: JSONL row emission in harvest_validated_results.py.

Validates that ``harvest()`` and ``build_rows_for_run()`` emit one fully
denormalized JSONL row per ``(image, run, card, test_node)`` with correct
field values, rollup counts, complexity_tier, and deterministic timestamps.
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


def _write_card_spec(card_dir: Path, spec: dict) -> None:
    """Write a card_spec.json into the given card directory."""
    card_dir.mkdir(parents=True, exist_ok=True)
    (card_dir / "card_spec.json").write_text(json.dumps(spec), encoding="utf-8")


def _card_dir(root: Path, image: str, run: str, card: str) -> Path:
    return root / "docker" / image / "validated_results" / run / "cards" / card


def _build_two_card_fixture(root: Path) -> None:
    """Build a fixture with one image, one run, two cards with mixed results.

    Card sos_1: 1 pass + 1 fail node  (tests_passed=1, tests_failed=1, total=2)
    Card sos_2: 2 pass nodes           (tests_passed=2, tests_failed=0, total=2)
    """
    # Card sos_1: mixed pass/fail
    cd1 = _card_dir(root, "img-alpha", "run-2026", "sos_1")
    _write_result_json(cd1, {
        "tests_passed": 1,
        "tests_failed": 1,
        "tests_total": 2,
        "tests_hash": "abc123",
        "test_nodes": [
            {"test_node": "tests.py::test_add", "outcome": "pass"},
            {"test_node": "tests.py::test_sub", "outcome": "fail"},
        ],
    })

    # Card sos_2: all pass
    cd2 = _card_dir(root, "img-alpha", "run-2026", "sos_2")
    _write_result_json(cd2, {
        "tests_passed": 2,
        "tests_failed": 0,
        "tests_total": 2,
        "tests_hash": "def456",
        "test_nodes": [
            {"test_node": "tests.py::test_mul", "outcome": "pass"},
            {"test_node": "tests.py::test_div", "outcome": "pass"},
        ],
    })


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
# 1. Integration test: exact rows emitted for two-card mixed fixture
# ---------------------------------------------------------------------------


class TestIntegrationTwoCards:
    """Integration test: two cards (mixed pass/fail) emit exact rows."""

    @pytest.fixture()
    def harvest_rows(self, tmp_path: Path) -> list[dict]:
        _build_two_card_fixture(tmp_path)
        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        return _read_jsonl(out)

    def test_total_row_count(self, harvest_rows: list[dict]) -> None:
        assert len(harvest_rows) == 4

    def test_each_row_has_all_required_keys(self, harvest_rows: list[dict]) -> None:
        expected_keys = {
            "image", "run", "card", "test_node", "outcome",
            "tests_hash", "passed", "failed", "total",
            "complexity_tier", "harvested_at",
        }
        for row in harvest_rows:
            assert set(row.keys()) == expected_keys

    def test_card_sos_1_pass_node(self, harvest_rows: list[dict]) -> None:
        matches = [
            r for r in harvest_rows
            if r["card"] == "sos_1" and r["test_node"] == "tests.py::test_add"
        ]
        assert len(matches) == 1
        row = matches[0]
        assert row["image"] == "img-alpha"
        assert row["run"] == "run-2026"
        assert row["outcome"] == "pass"
        assert row["tests_hash"] == "abc123"
        assert row["passed"] == 1
        assert row["failed"] == 1
        assert row["total"] == 2

    def test_card_sos_1_fail_node(self, harvest_rows: list[dict]) -> None:
        matches = [
            r for r in harvest_rows
            if r["card"] == "sos_1" and r["test_node"] == "tests.py::test_sub"
        ]
        assert len(matches) == 1
        row = matches[0]
        assert row["outcome"] == "fail"
        assert row["tests_hash"] == "abc123"
        assert row["passed"] == 1
        assert row["failed"] == 1
        assert row["total"] == 2

    def test_card_sos_2_nodes(self, harvest_rows: list[dict]) -> None:
        card2_rows = [r for r in harvest_rows if r["card"] == "sos_2"]
        assert len(card2_rows) == 2
        for row in card2_rows:
            assert row["outcome"] == "pass"
            assert row["tests_hash"] == "def456"
            assert row["passed"] == 2
            assert row["failed"] == 0
            assert row["total"] == 2


# ---------------------------------------------------------------------------
# 2. Return value equals total node count
# ---------------------------------------------------------------------------


class TestReturnValue:
    """harvest() return value equals the number of emitted rows."""

    def test_return_value_matches_row_count(self, tmp_path: Path) -> None:
        _build_two_card_fixture(tmp_path)
        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        assert count == 4
        assert count == len(rows)


# ---------------------------------------------------------------------------
# 3. harvested_at is identical on every row and matches injected value
# ---------------------------------------------------------------------------


class TestHarvestedAt:
    """harvested_at is identical on every row and matches the injected value."""

    def test_all_rows_share_injected_timestamp(self, tmp_path: Path) -> None:
        _build_two_card_fixture(tmp_path)
        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        for row in rows:
            assert row["harvested_at"] == FIXED_TS


# ---------------------------------------------------------------------------
# 4. complexity_tier: present vs absent
# ---------------------------------------------------------------------------


class TestComplexityTier:
    """complexity_tier from card_spec.json when present; null when absent."""

    def test_complexity_tier_present(self, tmp_path: Path) -> None:
        cd = _card_dir(tmp_path, "imgX", "runX", "sos_10")
        _write_result_json(cd, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "h1",
            "test_nodes": [{"test_node": "tests.py::test_a", "outcome": "pass"}],
        })
        _write_card_spec(cd, {"complexity_tier": "medium"})

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        assert len(rows) == 1
        assert rows[0]["complexity_tier"] == "medium"

    def test_complexity_tier_absent(self, tmp_path: Path) -> None:
        cd = _card_dir(tmp_path, "imgX", "runX", "sos_11")
        _write_result_json(cd, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "h2",
            "test_nodes": [{"test_node": "tests.py::test_b", "outcome": "pass"}],
        })
        # No card_spec.json written

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        assert len(rows) == 1
        assert rows[0]["complexity_tier"] is None

    def test_complexity_tier_both_in_one_harvest(self, tmp_path: Path) -> None:
        """One card has complexity_tier, another does not, in the same run."""
        cd_with = _card_dir(tmp_path, "imgY", "runY", "sos_20")
        _write_result_json(cd_with, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "h3",
            "test_nodes": [{"test_node": "tests.py::test_c", "outcome": "pass"}],
        })
        _write_card_spec(cd_with, {"complexity_tier": "hard"})

        cd_without = _card_dir(tmp_path, "imgY", "runY", "sos_21")
        _write_result_json(cd_without, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "h4",
            "test_nodes": [{"test_node": "tests.py::test_d", "outcome": "pass"}],
        })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        by_card = {r["card"]: r for r in rows}
        assert by_card["sos_20"]["complexity_tier"] == "hard"
        assert by_card["sos_21"]["complexity_tier"] is None


# ---------------------------------------------------------------------------
# 5. Denormalization: rollup counts + tests_hash on every node row
# ---------------------------------------------------------------------------


class TestDenormalization:
    """Rollup counts and tests_hash are copied onto every node row for a card."""

    def test_rollup_copied_to_all_node_rows(self, tmp_path: Path) -> None:
        cd = _card_dir(tmp_path, "imgD", "runD", "sos_30")
        _write_result_json(cd, {
            "tests_passed": 2,
            "tests_failed": 1,
            "tests_total": 3,
            "tests_hash": "rollup_hash",
            "test_nodes": [
                {"test_node": "tests.py::test_x", "outcome": "pass"},
                {"test_node": "tests.py::test_y", "outcome": "pass"},
                {"test_node": "tests.py::test_z", "outcome": "fail"},
            ],
        })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        assert len(rows) == 3
        for row in rows:
            assert row["passed"] == 2
            assert row["failed"] == 1
            assert row["total"] == 3
            assert row["tests_hash"] == "rollup_hash"


# ---------------------------------------------------------------------------
# 6. Idempotency: running harvest twice produces identical file
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Running harvest twice to the same output yields the same file contents."""

    def test_idempotent_output(self, tmp_path: Path) -> None:
        _build_two_card_fixture(tmp_path)
        out = tmp_path / "out.jsonl"

        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        first_content = out.read_text(encoding="utf-8")

        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        second_content = out.read_text(encoding="utf-8")

        assert first_content == second_content

    def test_no_duplicate_rows_after_second_run(self, tmp_path: Path) -> None:
        _build_two_card_fixture(tmp_path)
        out = tmp_path / "out.jsonl"

        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        assert len(rows) == 4  # not 8


# ---------------------------------------------------------------------------
# 7. Ordering: rows appear in discovery order (sorted by image, run)
# ---------------------------------------------------------------------------


class TestOrdering:
    """With multiple images/runs, rows appear sorted by (image, run), then card."""

    def test_rows_in_discovery_order(self, tmp_path: Path) -> None:
        # image "beta" run "run-b"
        cd1 = _card_dir(tmp_path, "beta", "run-b", "sos_50")
        _write_result_json(cd1, {
            "tests_passed": 1, "tests_failed": 0, "tests_total": 1,
            "tests_hash": "hb",
            "test_nodes": [{"test_node": "tests.py::test_b1", "outcome": "pass"}],
        })

        # image "alpha" run "run-a"
        cd2 = _card_dir(tmp_path, "alpha", "run-a", "sos_40")
        _write_result_json(cd2, {
            "tests_passed": 1, "tests_failed": 0, "tests_total": 1,
            "tests_hash": "ha",
            "test_nodes": [{"test_node": "tests.py::test_a1", "outcome": "pass"}],
        })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)

        assert len(rows) == 2
        # alpha should come before beta
        assert rows[0]["image"] == "alpha"
        assert rows[1]["image"] == "beta"

    def test_card_order_within_run(self, tmp_path: Path) -> None:
        """Cards within a run appear in sorted (alphabetical) order."""
        for card_name in ("sos_99", "sos_01", "sos_50"):
            cd = _card_dir(tmp_path, "imgZ", "runZ", card_name)
            _write_result_json(cd, {
                "tests_passed": 1, "tests_failed": 0, "tests_total": 1,
                "tests_hash": f"h_{card_name}",
                "test_nodes": [
                    {"test_node": f"tests.py::test_{card_name}", "outcome": "pass"},
                ],
            })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        cards = [r["card"] for r in rows]
        assert cards == ["sos_01", "sos_50", "sos_99"]


# ---------------------------------------------------------------------------
# 8. Edge case: result.json without test_nodes is skipped (no crash)
# ---------------------------------------------------------------------------


class TestMissingTestNodes:
    """Cards whose result.json lacks test_nodes contribute zero rows."""

    def test_no_test_nodes_key_skipped(self, tmp_path: Path) -> None:
        cd = _card_dir(tmp_path, "imgE", "runE", "sos_60")
        _write_result_json(cd, {
            "tests_passed": 3,
            "tests_failed": 1,
            "tests_total": 4,
            "tests_hash": "legacy",
            # no test_nodes key
        })

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        assert count == 0
        assert len(rows) == 0

    def test_mixed_modern_and_legacy_cards(self, tmp_path: Path) -> None:
        """A run with one modern card and one legacy card: only modern emits rows."""
        # Modern card
        cd_modern = _card_dir(tmp_path, "imgF", "runF", "sos_70")
        _write_result_json(cd_modern, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "modern_h",
            "test_nodes": [{"test_node": "tests.py::test_m", "outcome": "pass"}],
        })

        # Legacy card (no test_nodes)
        cd_legacy = _card_dir(tmp_path, "imgF", "runF", "sos_71")
        _write_result_json(cd_legacy, {
            "tests_passed": 2,
            "tests_failed": 1,
            "tests_total": 3,
        })

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        rows = _read_jsonl(out)
        assert count == 1
        assert len(rows) == 1
        assert rows[0]["card"] == "sos_70"

    def test_unreadable_result_json_skipped(self, tmp_path: Path) -> None:
        """A card dir with no result.json at all does not crash."""
        cd = _card_dir(tmp_path, "imgG", "runG", "sos_80")
        cd.mkdir(parents=True, exist_ok=True)
        # No result.json created

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        assert count == 0
