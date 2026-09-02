"""Platform test for the pinned HOB Draft Set data (``data/sets/hob.json``).

The file is the committed, contamination-fresh source every HOB benchmark
derives its pool from (fetched by ``scripts/fetch_hob_set.py``). These tests
pin its shape so a bad re-fetch or hand-edit is caught in CI:

- it exists and is valid JSON,
- every entry is a HOB card (``set == "hob"``),
- it covers exactly the 321 collector numbers 1-321, each unique,
- every card carries ``name`` and ``type_line`` plus either ``oracle_text`` or
  ``card_faces`` (a vanilla card legitimately has an empty ``oracle_text``),
- and the raw set data lives only in the shared cache, never copied into a
  benchmark's own ``data/`` as a pool file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HOB_SET_PATH = _REPO_ROOT / "data" / "sets" / "hob.json"

EXPECTED_COUNT = 321


@pytest.fixture(scope="module")
def hob_cards() -> list[dict]:
    assert _HOB_SET_PATH.exists(), f"missing pinned set data at {_HOB_SET_PATH}"
    with open(_HOB_SET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list), "hob.json must be a JSON array of cards"
    return data


def test_file_is_valid_json_array(hob_cards: list[dict]) -> None:
    assert len(hob_cards) == EXPECTED_COUNT
    assert all(isinstance(c, dict) for c in hob_cards)


def test_every_entry_is_a_hob_card(hob_cards: list[dict]) -> None:
    off_set = sorted({c.get("set") for c in hob_cards} - {"hob"})
    assert not off_set, f"non-HOB set codes present: {off_set}"


def test_collector_numbers_cover_1_to_321_uniquely(hob_cards: list[dict]) -> None:
    cns = [int(c["collector_number"]) for c in hob_cards]
    assert len(cns) == len(set(cns)) == EXPECTED_COUNT, "duplicate collector numbers"
    assert sorted(cns) == list(range(1, EXPECTED_COUNT + 1))


def test_every_card_has_required_fields(hob_cards: list[dict]) -> None:
    # Key presence, not truthiness: a vanilla creature (e.g. Ordinary Bear,
    # cn 133) has an empty-string oracle_text, which is still a real field.
    missing: list[str] = []
    for c in hob_cards:
        cn = c.get("collector_number", "?")
        if "name" not in c:
            missing.append(f"{cn}: name")
        if "type_line" not in c:
            missing.append(f"{cn}: type_line")
        if "oracle_text" not in c and "card_faces" not in c:
            missing.append(f"{cn}: oracle_text/card_faces")
    assert not missing, f"cards missing required fields: {missing}"


def test_raw_set_data_is_not_copied_into_a_benchmark_pool() -> None:
    """The raw set is benchmark-neutral; no benchmark data/ holds a HOB pool file."""
    stray = list((_REPO_ROOT / "benchmarks").glob("*/data/hob.json"))
    assert not stray, f"HOB set data leaked into benchmark data dirs: {stray}"
