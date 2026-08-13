#!/usr/bin/env python3
"""Build card ID mapping (grpId → card name) for FDN and SPG sets.

Downloads card data from Scryfall API (arena_id field = MTGA grpId) and
builds a JSON mapping file at ``data/replays/card_id_map.json``.

Usage::

    python scripts/build_card_id_map.py

The output JSON has the structure::

    {
        "source": "scryfall_api",
        "description": "...",
        "grpId_to_card": {
            "<grpId>": {
                "card_name": "...",
                "set_code": "FDN",
                "collector_number": "..."
            },
            ...
        },
        "card_name_to_grpId": {
            "<card_name>": <first_grpId>,
            ...
        },
        "card_name_to_grpIds": {
            "<card_name>": [
                {"grpId": <int>, "set_code": "...", "collector_number": "..."},
                ...
            ],
            ...
        }
    }

``card_name_to_grpId`` keeps a single grpId per name (first seen) for
convenience.  ``card_name_to_grpIds`` preserves **all** grpIds for that
name so that duplicate-name printings (e.g. basic lands) are not lost.

ENGINE LIMITATION: The 17lands public_datasets page provides card data
keyed by MTGA grpId, but that endpoint requires authentication / specific
download URLs that change. We use the Scryfall API ``arena_id`` field
instead, which maps to the same MTGA grpId values.

SPG cards #74-83 (FDN Special Guests: Condemn, Sphinx's Tutelage, Grim
Tutor, Embercleave, Goblin Bushwhacker, Bloom Tender, Paradise Druid,
Akroma's Memorial, Temporal Manipulation, Fiend Artisan) do not have
``arena_id`` values on Scryfall, so we assign synthetic IDs in the
94700-94709 range. These should be replaced with real Arena grpIds when
17lands data becomes available.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SETS = ["fdn", "spg"]
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "replays" / "card_id_map.json"

# SPG #74-83 don't have arena_ids on Scryfall — assign synthetic ones.
# ENGINE LIMITATION: Replace with real grpIds from 17lands when available.
SYNTHETIC_SPG_CARDS: list[tuple[int, str, str, str]] = [
    (94700, "Condemn", "SPG", "74"),
    (94701, "Sphinx's Tutelage", "SPG", "75"),
    (94702, "Grim Tutor", "SPG", "76"),
    (94703, "Embercleave", "SPG", "77"),
    (94704, "Goblin Bushwhacker", "SPG", "78"),
    (94705, "Bloom Tender", "SPG", "79"),
    (94706, "Paradise Druid", "SPG", "80"),
    (94707, "Akroma's Memorial", "SPG", "81"),
    (94708, "Temporal Manipulation", "SPG", "82"),
    (94709, "Fiend Artisan", "SPG", "83"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_scryfall_set(set_code: str) -> list[dict]:
    """Fetch all cards for *set_code* from Scryfall, returning raw card dicts.

    Raises
    ------
    RuntimeError
        If ``curl`` returns a non-zero exit code, the response is not valid
        JSON, or Scryfall returns an error object.
    """
    cards: list[dict] = []
    page = 1
    while True:
        url = (
            f"https://api.scryfall.com/cards/search"
            f"?q=set%3A{set_code}&unique=prints&page={page}"
        )
        result = subprocess.run(
            ["curl", "-s", "--fail-with-body", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"curl failed (exit {result.returncode}) fetching {url}: "
                f"{result.stderr or result.stdout}"
            )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Invalid JSON from Scryfall for {url}: {exc}"
            ) from exc
        if data.get("object") == "error":
            raise RuntimeError(
                f"Scryfall API error for {url}: "
                f"{data.get('details', data.get('code', 'unknown'))}"
            )
        if data.get("object") != "list":
            raise RuntimeError(
                f"Unexpected Scryfall response object type "
                f"'{data.get('object')}' for {url}"
            )
        if "data" not in data:
            raise RuntimeError(
                f"Scryfall response missing 'data' key for {url}"
            )
        cards.extend(data["data"])
        if not data.get("has_more"):
            break
        page += 1
        time.sleep(0.15)  # respect Scryfall rate limit
    return cards


def build_card_id_map() -> dict:
    """Build and return the card ID map dictionary."""
    grp_to_card: dict[str, dict] = {}
    name_to_grp: dict[str, int] = {}
    name_to_grps: dict[str, list[dict]] = {}

    def _add_entry(
        arena_id: int,
        card_name: str,
        set_code: str,
        collector_number: str,
        *,
        synthetic: bool = False,
    ) -> None:
        entry: dict = {
            "card_name": card_name,
            "set_code": set_code,
            "collector_number": collector_number,
        }
        if synthetic:
            entry["synthetic"] = True
        grp_to_card[str(arena_id)] = entry
        if card_name not in name_to_grp:
            name_to_grp[card_name] = arena_id
        name_to_grps.setdefault(card_name, []).append({
            "grpId": arena_id,
            "set_code": set_code,
            "collector_number": collector_number,
        })

    for set_code in SETS:
        print(f"Fetching {set_code.upper()} cards from Scryfall...")
        cards = _fetch_scryfall_set(set_code)
        count = 0
        for card in cards:
            arena_id = card.get("arena_id")
            if not arena_id:
                continue
            _add_entry(
                arena_id,
                card["name"],
                card["set"].upper(),
                card["collector_number"],
            )
            count += 1
        print(f"  → {count} cards with arena_id")

    # Add synthetic SPG entries (clearly marked)
    for grp_id, name, sc, cn in SYNTHETIC_SPG_CARDS:
        _add_entry(grp_id, name, sc, cn, synthetic=True)

    return {
        "source": "scryfall_api",
        "description": (
            "grpId (Arena card ID) to card name mapping for FDN and SPG sets"
        ),
        "grpId_to_card": grp_to_card,
        "card_name_to_grpId": name_to_grp,
        "card_name_to_grpIds": name_to_grps,
        "_synthetic_ids": {
            "description": (
                "SPG #74-83 arena_ids are synthetic (not from Scryfall). "
                "Real Arena grpIds should replace these when available "
                "from 17lands data. Entries in grpId_to_card with "
                "\"synthetic\": true are these placeholders."
            ),
            "range": "94700-94709",
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    mapping = build_card_id_map()
    with open(OUTPUT_PATH, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=False)
    n_grp = len(mapping["grpId_to_card"])
    n_rev = len(mapping["card_name_to_grpId"])
    print(f"\nWrote {OUTPUT_PATH}")
    print(f"  {n_grp} grpId → card entries")
    print(f"  {n_rev} card_name → grpId entries")


if __name__ == "__main__":
    main()
