"""Fetch and cache Secrets of Strixhaven card data.

Usage::

    python -m benchmarks.sos.fetch_data

Downloads SOS card data from Scryfall, normalizes field names to match
the project's CardMetadata convention (``mana_cost_str`` instead of
Scryfall's ``mana_cost``), and writes ``benchmarks/sos/data/sos.json``.

Logs stats: total count, type breakdown, rarity distribution, and cards
using new SOS mechanics.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Allow running as script from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from cards.scryfall import fetch_set, fetch_scryfall_query  # noqa: E402

logger = logging.getLogger(__name__)

#: Output path for normalized SOS card data.
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "sos.json"

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

#: New SOS mechanics to search for in oracle text.
NEW_MECHANICS = ["Prepared", "Converge", "Miracle", "Opus"]


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
    # Ensure set_code is always present at top level for multi-set pools
    normalized["set_code"] = card_json.get("set", card_json.get("set_code", ""))
    return normalized


def _log_stats(cards: list[dict[str, Any]]) -> None:
    """Log summary statistics for the fetched card data."""
    logger.info("=== SOS Fetch Stats ===")
    logger.info("Total cards: %d", len(cards))

    # Set breakdown (SOS vs SOA)
    set_counts: Counter[str] = Counter()
    for card in cards:
        set_counts[card.get("set_code", card.get("set", "unknown"))] += 1
    if len(set_counts) > 1:
        logger.info("Set breakdown:")
        for sc, count in set_counts.most_common():
            logger.info("  %s: %d", sc.upper(), count)

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


def fetch_sos_data(*, force: bool = False) -> list[dict[str, Any]]:
    """Fetch SOS data, normalize, cache to ``benchmarks/sos/data/sos.json``.

    Args:
        force: If True, skip cache and re-fetch from Scryfall.

    Returns:
        List of normalized card JSON dicts.
    """
    # If already cached locally and not forcing, check whether the cache
    # includes SOA cards.  Old caches only contain SOS cards and must be
    # rebuilt so the merged pool is complete.
    if not force and OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            cached = json.load(f)
        soa_count = sum(
            1 for c in cached if c.get("set_code", c.get("set", "")) == "soa"
        )
        spg_rows = [
            c for c in cached
            if c.get("set_code", c.get("set", "")) == "spg"
        ]
        spg_cns = [int(c.get("collector_number", 0)) for c in spg_rows]
        if (
            soa_count >= 65
            and len(spg_rows) == 10
            and sorted(spg_cns) == list(range(149, 159))
        ):
            return cached
        # Stale cache — fall through to rebuild

    # Use the existing scryfall fetch (which has its own cache layer).
    # When forcing, delete the raw cache first so fetch_set re-fetches from
    # Scryfall, but still pass use_cache=True so it writes the result back.
    raw_cache = _REPO_ROOT / "data" / "sets" / "sos.json"
    if force and raw_cache.exists():
        raw_cache.unlink()
    _ = fetch_set("sos", use_cache=True)

    # Read the raw Scryfall cache to get raw JSON (not CardMetadata)
    with open(raw_cache, encoding="utf-8") as f:
        raw_cards: list[dict[str, Any]] = json.load(f)

    # Fetch Mystical Archive cards from SOA set (collector numbers 1–65).
    # These are part of the SOS Draft Set but live in a separate Scryfall set.
    # Use a query-specific cache file so we never collide with a full-set
    # ``data/sets/soa.json`` cache that other callers may create/expect.
    soa_cache = _REPO_ROOT / "data" / "sets" / "soa_cn1-65.json"
    if force and soa_cache.exists():
        soa_cache.unlink()
    if soa_cache.exists() and not force:
        with open(soa_cache, encoding="utf-8") as f:
            soa_raw: list[dict[str, Any]] = json.load(f)
        # Always enforce the collector-number range even on cached data,
        # guarding against a manually edited or corrupted cache file.
        soa_raw = [
            c for c in soa_raw
            if 1 <= int(c.get("collector_number", 0)) <= 65
        ]
    else:
        soa_query = "e%3Asoa+cn%3E%3D1+cn%3C%3D65"
        soa_raw, _ = fetch_scryfall_query(soa_query, set_code="soa")
        # Cache the SOA subset for future runs
        soa_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(soa_cache, "w", encoding="utf-8") as f:
            json.dump(soa_raw, f, indent=2)

    # Fetch Special Guest cards from SPG set (collector numbers 149–158).
    # These are part of the SOS Draft Set but live in the SPG Scryfall set.
    # Distinct from FDN Special Guests (SPG 074–083) added in Phase 5.
    spg_cache = _REPO_ROOT / "data" / "sets" / "spg_cn149-158.json"
    if force and spg_cache.exists():
        spg_cache.unlink()
    if spg_cache.exists() and not force:
        with open(spg_cache, encoding="utf-8") as f:
            spg_raw: list[dict[str, Any]] = json.load(f)
        # Validate collector-number range and de-duplicate cached data
        seen_cns: dict[int, dict[str, Any]] = {}
        for c in spg_raw:
            cn = int(c.get("collector_number", 0))
            if 149 <= cn <= 158 and cn not in seen_cns:
                seen_cns[cn] = c
        spg_raw = list(seen_cns.values())
        # Verify completeness — exactly one card for each cn 149-158
        if set(seen_cns.keys()) != set(range(149, 159)):
            # Incomplete cache — refetch
            spg_query = "e%3Aspg+cn%3E%3D149+cn%3C%3D158"
            spg_raw, _ = fetch_scryfall_query(spg_query, set_code="spg")
            spg_raw = [
                c for c in spg_raw
                if 149 <= int(c.get("collector_number", 0)) <= 158
            ]
            with open(spg_cache, "w", encoding="utf-8") as f:
                json.dump(spg_raw, f, indent=2)
    else:
        spg_query = "e%3Aspg+cn%3E%3D149+cn%3C%3D158"
        spg_raw, _ = fetch_scryfall_query(spg_query, set_code="spg")
        # Filter to ensure only cn 149–158 (defensive, mirrors cache validation)
        spg_raw = [
            c for c in spg_raw
            if 149 <= int(c.get("collector_number", 0)) <= 158
        ]
        # Cache the SPG subset for future runs
        spg_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(spg_cache, "w", encoding="utf-8") as f:
            json.dump(spg_raw, f, indent=2)

    # Merge SOS + SOA + SPG cards
    raw_cards.extend(soa_raw)
    raw_cards.extend(spg_raw)

    # Normalize
    normalized = [_normalize_card(c) for c in raw_cards]

    # Write to benchmarks/sos/data/
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)

    _log_stats(normalized)
    return normalized


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    force = "--force" in sys.argv
    cards = fetch_sos_data(force=force)
    if not logger.handlers or logger.level > logging.INFO:
        # If stats weren't logged (cached path), log them now
        _log_stats(cards)
    logger.info("Wrote %d cards to %s", len(cards), OUTPUT_PATH)


if __name__ == "__main__":
    main()
