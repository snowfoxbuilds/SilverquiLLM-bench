"""Fetch the full HOB (The Hobbit) Draft Set to the shared raw-data cache.

Usage::

    python3 scripts/fetch_hob_set.py [--force]

Fetches every HOB print from the Scryfall search API (paginated), keeps the
raw Scryfall card JSON **unmodified**, sorts deterministically by collector
number, and writes the array to ``data/sets/hob.json``.

Unlike the per-benchmark fetchers, this writes the shared, benchmark-neutral
raw set data (``data/sets/hob.json``, committed and pinned): each HOB benchmark
derives its own pool from it. No normalization, no dedup, no field renaming —
the file is the contamination-fresh source of truth and must be reproducible
from a pinned fetch.

Safety: a non-200 response or a truncated pagination (``has_more`` with no
``next_page``, or a final count that disagrees with Scryfall's ``total_cards``)
aborts loudly **without writing**. The write itself is atomic (temp file +
rename) so a committed ``hob.json`` is never left half-written.

Logs totals plus a type and rarity breakdown.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

#: Bench repo root; the shared raw-data cache lives under it.
_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Scryfall set code for The Hobbit.
SET_CODE = "hob"

#: Output path for the raw, benchmark-neutral HOB set data.
OUTPUT_PATH = _REPO_ROOT / "data" / "sets" / f"{SET_CODE}.json"

#: Scryfall search API.
SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"

#: Minimum delay between Scryfall API requests (seconds), per their policy.
REQUEST_DELAY: float = 0.1

#: User-Agent Scryfall's request policy asks callers to send.
_HEADERS = {
    "User-Agent": "SilverquiLLM-bench/0.1.0",
    "Accept": "application/json",
}

#: Card types to track in the breakdown.
TRACKED_TYPES = [
    "creature",
    "instant",
    "sorcery",
    "enchantment",
    "artifact",
    "planeswalker",
    "land",
    "battle",
]


class FetchError(RuntimeError):
    """A fetch failed in a way that must abort before writing anything."""


def _cn_int(card_json: dict[str, Any]) -> int:
    """Return a card's collector number as an int (``-1`` if non-numeric)."""
    try:
        return int(card_json.get("collector_number", ""))
    except (ValueError, TypeError):
        return -1


def _fetch_page(url: str) -> dict[str, Any]:
    """Fetch one Scryfall page. Any non-200 status aborts loudly."""
    request = Request(url, headers=_HEADERS)
    with urlopen(request, timeout=30) as response:
        status = response.getcode()
        if status != 200:
            raise FetchError(f"Scryfall returned HTTP {status} for {url}")
        return json.loads(response.read().decode("utf-8"))


def _fetch_all_prints(set_code: str) -> list[dict[str, Any]]:
    """Fetch every print in *set_code* from Scryfall (paginated, raw JSON).

    Aborts (``FetchError``) on a non-200 page, a truncated pagination
    (``has_more`` with no ``next_page``), or a final count that disagrees with
    the ``total_cards`` Scryfall reports — so a partial fetch never reaches the
    committed file.
    """
    cards: list[dict[str, Any]] = []
    url: str | None = (
        f"{SCRYFALL_SEARCH_URL}?order=set&q=e%3A{set_code}&unique=prints"
    )
    expected_total: int | None = None
    while url is not None:
        data = _fetch_page(url)
        if expected_total is None:
            expected_total = data.get("total_cards")
        cards.extend(data.get("data", []))
        if data.get("has_more", False):
            next_page = data.get("next_page")
            if not next_page:
                raise FetchError(
                    "Scryfall reported has_more but returned no next_page "
                    f"(got {len(cards)} cards so far) — pagination truncated"
                )
            url = next_page
            time.sleep(REQUEST_DELAY)
        else:
            url = None

    if expected_total is not None and len(cards) != expected_total:
        raise FetchError(
            f"Fetched {len(cards)} cards but Scryfall reported "
            f"total_cards={expected_total} — pagination incomplete"
        )
    if not cards:
        raise FetchError(f"Scryfall returned no cards for set {set_code!r}")
    return cards


def _atomic_write(path: Path, text: str) -> None:
    """Write *text* to *path* via a temp file + rename, so it is all-or-nothing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _log_stats(cards: list[dict[str, Any]]) -> None:
    """Log summary statistics for the fetched card data."""
    logger.info("=== HOB Fetch Stats ===")
    logger.info("Total cards: %d", len(cards))

    cns = sorted(_cn_int(c) for c in cards)
    logger.info("Collector numbers: %d-%d (%d unique)", cns[0], cns[-1], len(set(cns)))

    type_counts: Counter[str] = Counter()
    for card in cards:
        tl = card.get("type_line", "").lower()
        for ctype in TRACKED_TYPES:
            if ctype in tl:
                type_counts[ctype] += 1
    logger.info("Type breakdown:")
    for ctype in TRACKED_TYPES:
        logger.info("  %s: %d", ctype.capitalize(), type_counts[ctype])

    rarity_counts: Counter[str] = Counter()
    for card in cards:
        rarity_counts[card.get("rarity", "unknown")] += 1
    logger.info("Rarity distribution:")
    for rarity, count in rarity_counts.most_common():
        logger.info("  %s: %d", rarity, count)


def fetch_hob_set(*, force: bool = False) -> list[dict[str, Any]]:
    """Fetch the HOB set, sort by collector number, write ``data/sets/hob.json``.

    Without ``--force`` an existing file is reused as-is (it is pinned and
    committed). ``--force`` re-fetches from Scryfall and rewrites atomically;
    the raw JSON is preserved unmodified so the result is reproducible.
    """
    if not force and OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            return json.load(f)

    cards = _fetch_all_prints(SET_CODE)
    # Deterministic order: sort by collector number (unique across HOB); the
    # secondary key on Scryfall id keeps the sort total even if a print ever
    # repeats a collector number.
    cards.sort(key=lambda c: (_cn_int(c), str(c.get("id", ""))))

    _atomic_write(OUTPUT_PATH, json.dumps(cards, indent=2, ensure_ascii=False) + "\n")
    _log_stats(cards)
    return cards


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch from Scryfall even if data/sets/hob.json already exists.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        cards = fetch_hob_set(force=args.force)
    except FetchError as exc:
        logger.error("Fetch aborted: %s", exc)
        return 1
    if not args.force:
        _log_stats(cards)
    logger.info("Wrote %d cards to %s", len(cards), OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
