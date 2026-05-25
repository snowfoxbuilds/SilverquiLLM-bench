"""Scryfall API data fetcher and parser.

Fetches card data from the `Scryfall REST API`_ and converts it into
:class:`~cards.registry.CardMetadata` objects.

.. _Scryfall REST API: https://scryfall.com/docs/api

Features:
- Paginated fetching of entire sets.
- Local file-based cache under ``data/sets/{code}.json``.
- 100 ms delay between requests per Scryfall's rate-limit policy.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError

from benchmarks.sos.workspace.cards.registry import CardMetadata

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Base URL for the Scryfall search API.
SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"

#: Minimum delay between Scryfall API requests (seconds).
REQUEST_DELAY: float = 0.1  # 100 ms per Scryfall policy

#: Cache directory (relative to the project root).
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "sets"

#: Maximum cache age in seconds (default: 7 days).
CACHE_MAX_AGE: float = 7 * 24 * 3600


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cache_path(set_code: str) -> Path:
    """Return the cache file path for a given set code."""
    return _CACHE_DIR / f"{set_code.lower()}.json"


def _is_cache_fresh(path: Path, max_age: float = CACHE_MAX_AGE) -> bool:
    """Return ``True`` if *path* exists and was modified within *max_age* seconds."""
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < max_age


def _fetch_json(url: str) -> dict[str, Any]:
    """Fetch JSON from *url* with a User-Agent header (required by Scryfall)."""
    request = Request(url, headers={
        "User-Agent": "SilverquiLLM-bench/0.1.0",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_card(card_json: dict[str, Any], set_code: str = "") -> CardMetadata:
    """Parse a single Scryfall card JSON object into a :class:`CardMetadata`.

    For multi-face cards (transform, adventure, split), Scryfall puts fields
    like ``mana_cost``, ``oracle_text``, ``colors``, ``power``, and
    ``toughness`` under the ``card_faces`` array rather than at the top level.
    When those top-level fields are missing or empty, this function falls back
    to the front face (``card_faces[0]``).
    """
    # For multi-face cards, resolve the front face as a fallback source.
    faces = card_json.get("card_faces")
    front_face: dict[str, Any] = faces[0] if faces else {}

    # Helper: prefer top-level string field; fall back to front face.
    def _str_field(key: str, default: str = "") -> str:
        value = card_json.get(key)
        if value is not None and value != "":
            return value
        return front_face.get(key, default)

    # Helper: prefer top-level list field; fall back to front face.
    def _list_field(key: str) -> list[str]:
        value = card_json.get(key)
        if value is not None and len(value) > 0:
            return value
        return front_face.get(key, [])

    # Helper: prefer top-level optional field; fall back to front face.
    def _opt_field(key: str) -> str | None:
        value = card_json.get(key)
        if value is not None:
            return value
        return front_face.get(key)

    return CardMetadata(
        name=card_json.get("name", ""),
        mana_cost_str=_str_field("mana_cost"),
        type_line=card_json.get("type_line", ""),
        oracle_text=_str_field("oracle_text"),
        power=_opt_field("power"),
        toughness=_opt_field("toughness"),
        colors=_list_field("colors"),
        keywords=card_json.get("keywords", []),
        rarity=card_json.get("rarity", ""),
        set_code=card_json.get("set", set_code),
        collector_number=card_json.get("collector_number", ""),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_scryfall_query(
    query: str,
    *,
    set_code: str = "",
) -> tuple[list[dict[str, Any]], list[CardMetadata]]:
    """Fetch cards matching a Scryfall search *query*.

    Unlike :func:`fetch_set`, this does **not** use or update the local
    cache.  It is intended for targeted queries (e.g. collector-number
    ranges within a specific set).

    Args:
        query: A URL-encoded Scryfall search query string
            (e.g. ``"e%3Asoa+cn%3E%3D1+cn%3C%3D65"``).
        set_code: Fallback set code if the card JSON lacks a ``set`` field.

    Returns:
        A tuple of ``(raw_card_dicts, parsed_card_metadata)``.
    """
    all_cards: list[dict[str, Any]] = []
    url: str | None = f"{SCRYFALL_SEARCH_URL}?order=set&q={query}&unique=prints"

    while url is not None:
        data = _fetch_json(url)
        all_cards.extend(data.get("data", []))
        if data.get("has_more", False) and data.get("next_page"):
            url = data["next_page"]
            time.sleep(REQUEST_DELAY)
        else:
            url = None

    parsed = [_parse_card(c, set_code=set_code) for c in all_cards]
    return all_cards, parsed


def fetch_set(
    set_code: str,
    *,
    use_cache: bool = True,
    cache_max_age: float = CACHE_MAX_AGE,
) -> list[CardMetadata]:
    """Fetch all cards for *set_code* from Scryfall and return as metadata.

    Results are cached to ``data/sets/{set_code}.json``.  If a fresh cache
    file exists (less than *cache_max_age* seconds old), it is used instead
    of making network requests.

    Args:
        set_code: The Scryfall set code (e.g. ``"fdn"``).
        use_cache: Whether to read/write the local cache.  Set to ``False``
            to force a fresh fetch.
        cache_max_age: Maximum cache file age in seconds.

    Returns:
        A list of :class:`CardMetadata` objects, one per card in the set.

    Raises:
        urllib.error.URLError: If the Scryfall API is unreachable.
    """
    code = set_code.lower()
    cache = _cache_path(code)

    # 1. Try cache
    if use_cache and _is_cache_fresh(cache, max_age=cache_max_age):
        with open(cache, encoding="utf-8") as f:
            raw_cards: list[dict[str, Any]] = json.load(f)
        return [_parse_card(c, set_code=code) for c in raw_cards]

    # 2. Fetch from Scryfall with pagination
    all_cards: list[dict[str, Any]] = []
    url: str | None = f"{SCRYFALL_SEARCH_URL}?order=set&q=e%3A{code}&unique=prints"

    while url is not None:
        data = _fetch_json(url)
        all_cards.extend(data.get("data", []))
        if data.get("has_more", False) and data.get("next_page"):
            url = data["next_page"]
            time.sleep(REQUEST_DELAY)  # respect rate limit
        else:
            url = None

    # 3. Write cache
    if use_cache:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(all_cards, f, indent=2)

    return [_parse_card(c, set_code=code) for c in all_cards]
