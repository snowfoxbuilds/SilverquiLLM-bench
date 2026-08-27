"""Fetch and cache Marvel Super Heroes card data.

Usage::

    python -m benchmarks.msh.fetch_data [--force]

Downloads MSH card data from Scryfall, deduplicates to one entry per
unique card (keeping the lowest collector number and dropping the
alternate-art / showcase reprints that share a name), normalizes field
names to match the project's CardMetadata convention (``mana_cost_str``
alongside Scryfall's ``mana_cost``), and writes
``benchmarks/msh/data/msh.json``.

Logs stats: total count, type breakdown, rarity distribution, and cards
using MSH mechanics.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

#: Bench repo root; used for locating the shared raw-data cache.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: Scryfall set code for Marvel Super Heroes.
SET_CODE = "msh"

#: Output path for normalized MSH card data.
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "msh.json"

#: Raw Scryfall prints cache (shared with the other fetchers).
RAW_CACHE_PATH = _REPO_ROOT / "data" / "sets" / f"{SET_CODE}.json"

#: Scryfall search API.
SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"

#: Minimum delay between Scryfall API requests (seconds), per their policy.
REQUEST_DELAY: float = 0.1

#: Card types to track in the breakdown.
TRACKED_TYPES = [
    "creature",
    "instant",
    "sorcery",
    "enchantment",
    "artifact",
    "planeswalker",
    "land",
]

#: New MSH mechanics to search for in oracle text.
NEW_MECHANICS = ["Power-up", "Teamwork"]


def _cn_int(card_json: dict[str, Any]) -> int:
    """Return a card's collector number as an int (``-1`` if non-numeric)."""
    try:
        return int(card_json.get("collector_number", ""))
    except (ValueError, TypeError):
        return -1


def _fetch_json(url: str) -> dict[str, Any]:
    """Fetch JSON from *url* with the User-Agent header Scryfall requires."""
    request = Request(url, headers={
        "User-Agent": "SilverquiLLM-bench/0.1.0",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_all_prints(set_code: str) -> list[dict[str, Any]]:
    """Fetch every print in *set_code* from Scryfall (paginated)."""
    cards: list[dict[str, Any]] = []
    url: str | None = (
        f"{SCRYFALL_SEARCH_URL}?order=set&q=e%3A{set_code}&unique=prints"
    )
    while url is not None:
        data = _fetch_json(url)
        cards.extend(data.get("data", []))
        if data.get("has_more", False) and data.get("next_page"):
            url = data["next_page"]
            time.sleep(REQUEST_DELAY)
        else:
            url = None
    return cards


def _dedupe_by_name(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one print per unique card name — the lowest collector number.

    MSH ships each card with alternate-art / showcase reprints at higher
    collector numbers (e.g. nine prints of ``Plains``).  The benchmark wants
    exactly one stub per unique card, so we keep the lowest-numbered print of
    each name and drop the rest.  The result is sorted by collector number.
    """
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for card in sorted(cards, key=_cn_int):
        name = card.get("name", "")
        if name and name not in seen:
            seen.add(name)
            deduped.append(card)
    return deduped


def _normalize_card(card_json: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw Scryfall card JSON object.

    Ensures top-level ``name``, ``mana_cost_str``, ``type_line``, and
    ``oracle_text`` fields exist, resolving multi-face fallbacks.
    """
    faces = card_json.get("card_faces", [])
    front: dict[str, Any] = faces[0] if faces else {}

    def _str(key: str, alt_key: str | None = None) -> str:
        actual_key = alt_key or key
        val = card_json.get(actual_key)
        if val is not None and val != "":
            return val
        return front.get(actual_key, "")

    normalized = dict(card_json)  # shallow copy — keep all original fields
    # Ensure canonical fields at top level
    normalized["name"] = card_json.get("name", "")
    normalized["mana_cost_str"] = _str("mana_cost_str", "mana_cost")
    normalized["type_line"] = card_json.get("type_line", "")
    normalized["oracle_text"] = _str("oracle_text")
    # Ensure set_code is always present at top level
    normalized["set_code"] = card_json.get("set", card_json.get("set_code", ""))
    return normalized


def _log_stats(cards: list[dict[str, Any]]) -> None:
    """Log summary statistics for the fetched card data."""
    logger.info("=== MSH Fetch Stats ===")
    logger.info("Total cards: %d", len(cards))

    # Type breakdown
    type_counts: Counter[str] = Counter()
    for card in cards:
        tl = card.get("type_line", "").lower()
        for ctype in TRACKED_TYPES:
            if ctype in tl:
                type_counts[ctype] += 1
    logger.info("Type breakdown:")
    for ctype in TRACKED_TYPES:
        logger.info("  %s: %d", ctype.capitalize(), type_counts[ctype])

    # Rarity distribution
    rarity_counts: Counter[str] = Counter()
    for card in cards:
        rarity_counts[card.get("rarity", "unknown")] += 1
    logger.info("Rarity distribution:")
    for rarity, count in rarity_counts.most_common():
        logger.info("  %s: %d", rarity, count)

    # New mechanics
    logger.info("Cards with new mechanics:")
    for mechanic in NEW_MECHANICS:
        matches = [
            card["name"]
            for card in cards
            if mechanic.lower() in card.get("oracle_text", "").lower()
        ]
        logger.info("  %s (%d): %s", mechanic, len(matches), ", ".join(matches[:10]))
        if len(matches) > 10:
            logger.info("    ... and %d more", len(matches) - 10)


def _cache_is_valid(cards: list[dict[str, Any]]) -> bool:
    """Return ``True`` if a cached ``msh.json`` looks complete and deduped.

    Validates that every entry has a name, a collector number, and the MSH
    set code, and that there are no duplicate names (the dedup invariant).
    """
    if not isinstance(cards, list) or not cards:
        return False
    names: set[str] = set()
    for card in cards:
        name = card.get("name")
        if not name or not card.get("collector_number"):
            return False
        if card.get("set_code", card.get("set")) != SET_CODE:
            return False
        if name in names:
            return False
        names.add(name)
    return True


def fetch_msh_data(*, force: bool = False) -> list[dict[str, Any]]:
    """Fetch MSH data, dedup, normalize, cache to ``benchmarks/msh/data/msh.json``.

    Args:
        force: If True, skip both caches and re-fetch from Scryfall.

    Returns:
        List of normalized card JSON dicts (one per unique card).
    """
    # 1. Reuse a valid normalized cache unless forcing.
    if not force and OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            cached = json.load(f)
        if _cache_is_valid(cached):
            return cached
        # Stale / incomplete — fall through to rebuild.

    # 2. Get the raw Scryfall prints (use the shared raw cache when possible).
    if not force and RAW_CACHE_PATH.exists():
        with open(RAW_CACHE_PATH, encoding="utf-8") as f:
            raw_cards: list[dict[str, Any]] = json.load(f)
    else:
        raw_cards = _fetch_all_prints(SET_CODE)
        RAW_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RAW_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(raw_cards, f, indent=2)

    # 3. Dedup to one print per unique card, then normalize.
    deduped = _dedupe_by_name(raw_cards)
    normalized = [_normalize_card(c) for c in deduped]

    # 4. Write the normalized pool.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    _log_stats(normalized)
    return normalized


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    force = "--force" in sys.argv
    cards = fetch_msh_data(force=force)
    if not logger.handlers or logger.level > logging.INFO:
        # If stats weren't logged (cached path), log them now.
        _log_stats(cards)
    logger.info("Wrote %d cards to %s", len(cards), OUTPUT_PATH)


if __name__ == "__main__":
    main()
