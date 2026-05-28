"""CI regex audit: card-specific test naming.

Confirms each tests/audited/sos/sos_{cn}/tests.py references at least TWO
distinct card-specific verbs/nouns extracted from the matching card_spec.json's
oracle_text and name fields.  Generic MTG words are excluded via the
GENERIC_MTG_WORDS constant below.

Per general-issue #9: catches templated test generation that never references
card-specific behavior.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Set, Tuple

import pytest

# ---------------------------------------------------------------------------
# Module-level allow-list of generic MTG words to EXCLUDE from card-specific
# matching.  Keep sorted for easy review/tuning.
# ---------------------------------------------------------------------------
GENERIC_MTG_WORDS: Set[str] = {
    "ability",
    "activate",
    "add",
    "artifact",
    "attack",
    "battlefield",
    "block",
    "card",
    "cast",
    "color",
    "combat",
    "controller",
    "cost",
    "counter",
    "creature",
    "damage",
    "deathtouch",
    "destroy",
    "discard",
    "double",
    "draw",
    "effect",
    "enchantment",
    "exile",
    "first",
    "flash",
    "flying",
    "forest",
    "graveyard",
    "hand",
    "haste",
    "hexproof",
    "indestructible",
    "instant",
    "island",
    "land",
    "legendary",
    "library",
    "life",
    "lifelink",
    "mana",
    "menace",
    "mountain",
    "opponent",
    "pay",
    "permanent",
    "phase",
    "plains",
    "planeswalker",
    "player",
    "power",
    "reach",
    "resolve",
    "sacrifice",
    "sorcery",
    "spell",
    "stack",
    "step",
    "strike",
    "swamp",
    "tap",
    "target",
    "token",
    "toughness",
    "trample",
    "trigger",
    "turn",
    "untap",
    "vigilance",
}

# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Possible locations for audited test files
_TEST_SEARCH_DIRS = [
    _REPO_ROOT / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "tests" / "audited" / "sos",
    _REPO_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos",
    _REPO_ROOT / "tests" / "audited" / "sos",
]

# Possible locations for card_spec.json
_CARD_SPEC_DIRS = [
    _REPO_ROOT / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "cards" / "sos",
    _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "sos",
]

_CN_PATTERN = re.compile(r"sos_(\d+)")
_WORD_SPLIT = re.compile(r"[^a-zA-Z]+")


def _discover_test_cards() -> List[Tuple[str, Path, Path]]:
    """Return list of (card_id, test_path, card_spec_path) tuples."""
    results: dict[str, Tuple[Path, Path]] = {}

    for test_dir in _TEST_SEARCH_DIRS:
        if not test_dir.is_dir():
            continue
        for entry in test_dir.iterdir():
            if not entry.is_dir():
                continue
            m = _CN_PATTERN.fullmatch(entry.name)
            if not m:
                continue
            card_id = entry.name  # e.g. sos_226
            test_file = entry / "tests.py"
            if not test_file.is_file():
                continue
            if card_id in results:
                continue
            # Find matching card_spec.json
            spec_path: Path | None = None
            for spec_dir in _CARD_SPEC_DIRS:
                candidate = spec_dir / card_id / "card_spec.json"
                if candidate.is_file():
                    spec_path = candidate
                    break
            if spec_path is None:
                continue
            results[card_id] = (test_file, spec_path)

    return [(cid, tp, sp) for cid, (tp, sp) in sorted(results.items())]


def _extract_card_words(spec_path: Path) -> Set[str]:
    """Extract card-specific words from card_spec.json, excluding generic MTG words."""
    with open(spec_path) as f:
        spec = json.load(f)

    text = " ".join(
        str(spec.get(field, "")) for field in ("name", "oracle_text")
    )

    words: Set[str] = set()
    for token in _WORD_SPLIT.split(text.lower()):
        if len(token) >= 3 and token not in GENERIC_MTG_WORDS:
            words.add(token)
    return words


def _find_matches(test_content: str, card_words: Set[str]) -> Set[str]:
    """Find which card-specific words appear in the test file content."""
    content_lower = test_content.lower()
    return {w for w in card_words if w in content_lower}


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------

_TEST_CASES = _discover_test_cards()


@pytest.mark.parametrize(
    "card_id,test_path,spec_path",
    _TEST_CASES,
    ids=[c[0] for c in _TEST_CASES],
)
def test_card_specific_naming(
    card_id: str, test_path: Path, spec_path: Path
) -> None:
    """Each audited test file must reference ≥2 distinct card-specific words."""
    card_words = _extract_card_words(spec_path)
    if len(card_words) < 2:
        pytest.skip(
            f"{card_id}: card_spec has <2 unique words after filtering "
            f"({sorted(card_words)}); cannot enforce threshold"
        )
    test_content = test_path.read_text()
    matched = _find_matches(test_content, card_words)

    assert len(matched) >= 2, (
        f"{card_id}: test file references only {len(matched)} card-specific "
        f"word(s) {sorted(matched)}. Expected ≥2 from: {sorted(card_words)}"
    )
