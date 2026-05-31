"""Gap tests for item 4 harvest row emission.

Covers genuine gaps NOT already tested in test_harvest_rows.py:

1. A card with test_nodes=[] (empty list) emits zero rows.
2. --image filter narrows harvest() to only the matching image.
3. --card filter narrows harvest() to only the matching card.
4. A malformed (invalid JSON) result.json is skipped without crashing.
5. JSONL output is valid one-object-per-line (each line independently json-loads).
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
if "harvest_validated_results" not in sys.modules:
    sys.modules["harvest_validated_results"] = _mod
    _spec.loader.exec_module(_mod)
else:
    _mod = sys.modules["harvest_validated_results"]

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


def _read_jsonl_lines(path: Path) -> list[str]:
    """Return non-empty lines from a JSONL file."""
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# 1. Empty test_nodes list emits zero rows
# ---------------------------------------------------------------------------


class TestEmptyTestNodesList:
    """test_nodes=[] (empty list, key present) must emit zero rows."""

    def test_empty_list_emits_zero_rows(self, tmp_path: Path) -> None:
        cd = _card_dir(tmp_path, "imgA", "runA", "sos_100")
        _write_result_json(cd, {
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_total": 0,
            "tests_hash": "empty_hash",
            "test_nodes": [],  # key present but empty
        })

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        assert count == 0
        lines = _read_jsonl_lines(out)
        assert lines == []

    def test_empty_list_card_alongside_normal_card(self, tmp_path: Path) -> None:
        """A card with empty test_nodes contributes nothing; sibling card is unaffected."""
        # Card with empty test_nodes
        cd_empty = _card_dir(tmp_path, "imgA", "runA", "sos_101")
        _write_result_json(cd_empty, {
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_total": 0,
            "tests_hash": "h_empty",
            "test_nodes": [],
        })

        # Normal card with one node
        cd_normal = _card_dir(tmp_path, "imgA", "runA", "sos_102")
        _write_result_json(cd_normal, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "h_normal",
            "test_nodes": [{"test_node": "tests.py::test_ok", "outcome": "pass"}],
        })

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        assert count == 1
        lines = _read_jsonl_lines(out)
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["card"] == "sos_102"


# ---------------------------------------------------------------------------
# 2. --image filter narrows harvest to only the matching image
# ---------------------------------------------------------------------------


class TestImageFilter:
    """harvest(image=...) emits rows only from the specified image."""

    def _build_two_image_fixture(self, root: Path) -> None:
        for img, card, node in [
            ("img-alpha", "sos_200", "tests.py::test_alpha"),
            ("img-beta", "sos_201", "tests.py::test_beta"),
        ]:
            cd = _card_dir(root, img, "run-shared", card)
            _write_result_json(cd, {
                "tests_passed": 1,
                "tests_failed": 0,
                "tests_total": 1,
                "tests_hash": f"h_{img}",
                "test_nodes": [{"test_node": node, "outcome": "pass"}],
            })

    def test_image_filter_restricts_to_one_image(self, tmp_path: Path) -> None:
        self._build_two_image_fixture(tmp_path)
        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), image="img-alpha", harvested_at=FIXED_TS)
        assert count == 1
        lines = _read_jsonl_lines(out)
        row = json.loads(lines[0])
        assert row["image"] == "img-alpha"

    def test_image_filter_excludes_other_image(self, tmp_path: Path) -> None:
        self._build_two_image_fixture(tmp_path)
        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), image="img-alpha", harvested_at=FIXED_TS)
        lines = _read_jsonl_lines(out)
        for line in lines:
            row = json.loads(line)
            assert row["image"] != "img-beta"

    def test_image_filter_no_match_emits_zero(self, tmp_path: Path) -> None:
        self._build_two_image_fixture(tmp_path)
        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), image="img-nonexistent", harvested_at=FIXED_TS)
        assert count == 0


# ---------------------------------------------------------------------------
# 3. --card filter narrows harvest to only the matching card
# ---------------------------------------------------------------------------


class TestCardFilter:
    """harvest(card=...) emits rows only from the specified card name."""

    def _build_two_card_same_run(self, root: Path) -> None:
        for card, node in [
            ("sos_300", "tests.py::test_three"),
            ("sos_301", "tests.py::test_four"),
        ]:
            cd = _card_dir(root, "img-gamma", "run-gamma", card)
            _write_result_json(cd, {
                "tests_passed": 1,
                "tests_failed": 0,
                "tests_total": 1,
                "tests_hash": f"h_{card}",
                "test_nodes": [{"test_node": node, "outcome": "pass"}],
            })

    def test_card_filter_restricts_to_named_card(self, tmp_path: Path) -> None:
        self._build_two_card_same_run(tmp_path)
        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), card="sos_300", harvested_at=FIXED_TS)
        assert count == 1
        row = json.loads(_read_jsonl_lines(out)[0])
        assert row["card"] == "sos_300"

    def test_card_filter_excludes_other_cards(self, tmp_path: Path) -> None:
        self._build_two_card_same_run(tmp_path)
        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), card="sos_300", harvested_at=FIXED_TS)
        for line in _read_jsonl_lines(out):
            row = json.loads(line)
            assert row["card"] != "sos_301"

    def test_card_filter_no_match_emits_zero(self, tmp_path: Path) -> None:
        self._build_two_card_same_run(tmp_path)
        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), card="sos_999", harvested_at=FIXED_TS)
        assert count == 0


# ---------------------------------------------------------------------------
# 4. Malformed (invalid JSON) result.json is skipped without crashing
# ---------------------------------------------------------------------------


class TestMalformedResultJson:
    """A result.json with invalid JSON bytes is skipped; harvest does not crash."""

    def test_corrupt_json_is_skipped(self, tmp_path: Path) -> None:
        cd = _card_dir(tmp_path, "imgC", "runC", "sos_400")
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "result.json").write_text("{ not valid json !!!", encoding="utf-8")

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        assert count == 0

    def test_corrupt_json_card_skipped_sibling_emits(self, tmp_path: Path) -> None:
        """A corrupt card does not prevent a sibling valid card from emitting rows."""
        # Corrupt card
        cd_bad = _card_dir(tmp_path, "imgC", "runC", "sos_401")
        cd_bad.mkdir(parents=True, exist_ok=True)
        (cd_bad / "result.json").write_text("<<<GARBAGE>>>", encoding="utf-8")

        # Valid sibling card
        cd_good = _card_dir(tmp_path, "imgC", "runC", "sos_402")
        _write_result_json(cd_good, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "h_good",
            "test_nodes": [{"test_node": "tests.py::test_ok", "outcome": "pass"}],
        })

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        assert count == 1
        row = json.loads(_read_jsonl_lines(out)[0])
        assert row["card"] == "sos_402"

    def test_truncated_json_is_skipped(self, tmp_path: Path) -> None:
        """A truncated/incomplete JSON file is treated as unreadable and skipped."""
        cd = _card_dir(tmp_path, "imgC", "runC", "sos_403")
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "result.json").write_text('{"tests_passed": 1, "test_nodes": [', encoding="utf-8")

        out = tmp_path / "out.jsonl"
        count = harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)
        assert count == 0


# ---------------------------------------------------------------------------
# 5. JSONL output: each line is independently valid JSON
# ---------------------------------------------------------------------------


class TestJsonlValidity:
    """Every non-empty output line must be independently parseable as JSON."""

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        # Build a fixture with multiple cards / nodes
        for card, node in [
            ("sos_500", "tests.py::test_e1"),
            ("sos_501", "tests.py::test_e2"),
            ("sos_502", "tests.py::test_e3"),
        ]:
            cd = _card_dir(tmp_path, "img-jsonl", "run-jsonl", card)
            _write_result_json(cd, {
                "tests_passed": 1,
                "tests_failed": 0,
                "tests_total": 1,
                "tests_hash": f"h_{card}",
                "test_nodes": [{"test_node": node, "outcome": "pass"}],
            })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)

        raw_text = out.read_text(encoding="utf-8")
        lines = raw_text.splitlines()
        non_empty_lines = [ln for ln in lines if ln.strip()]
        assert len(non_empty_lines) == 3, "Expected exactly 3 non-empty lines"

        for i, line in enumerate(non_empty_lines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                pytest.fail(f"Line {i} is not valid JSON: {exc!r}\nLine content: {line!r}")
            assert isinstance(obj, dict), f"Line {i} did not parse as a dict"

    def test_no_trailing_newline_causes_empty_last_object(self, tmp_path: Path) -> None:
        """Output must not have a blank line that would parse as empty JSON."""
        cd = _card_dir(tmp_path, "img-jsonl2", "run-jsonl2", "sos_510")
        _write_result_json(cd, {
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_total": 1,
            "tests_hash": "h_jl2",
            "test_nodes": [{"test_node": "tests.py::test_jl2", "outcome": "pass"}],
        })

        out = tmp_path / "out.jsonl"
        harvest(tmp_path, output=str(out), harvested_at=FIXED_TS)

        raw_text = out.read_text(encoding="utf-8")
        # Every non-empty line must parse as a dict
        for line in raw_text.splitlines():
            if line.strip():
                obj = json.loads(line)
                assert isinstance(obj, dict)
