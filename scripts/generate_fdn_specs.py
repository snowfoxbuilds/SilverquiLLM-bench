#!/usr/bin/env python3
"""Generate FDN card specs and empty implementation templates.

Fetches authoritative card data from Scryfall for the FDN Draft Set:
  - FDN base set: collector numbers 1–281
  - FDN Special Guests (SPG): collector numbers 74–83

For each card, creates:
  benchmarks/sos/workspace/cards/fdn/{dir_key}/card_spec.json   — oracle data + complexity tier
  benchmarks/sos/workspace/cards/fdn/{dir_key}/card_impl.py     — empty class skeleton (template)

Directory key rules (per KEY_DECISIONS.md):
  - FDN cards:  {collector_number}
  - SPG cards:  spg_{collector_number}

Usage:
    python3 scripts/generate_fdn_specs.py [--dry-run] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from silverquillm.card_spec import card_name_to_class_name

OUTPUT_DIR = PROJECT_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "fdn"
CACHE_DIR = PROJECT_ROOT / "data" / "sets"

# FDN Draft Set collector-number ranges
FDN_CN_MIN = 1
FDN_CN_MAX = 281

FDN_SPG_CN_MIN = 74
FDN_SPG_CN_MAX = 83

SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"
REQUEST_DELAY = 0.1  # seconds, per Scryfall rate-limit policy

# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

_CARD_IMPL_TEMPLATE = '''\
"""Card implementation for {name}."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class {class_name}(CardImpl):
    """TODO: Implement {name}."""

    pass
'''

# ---------------------------------------------------------------------------
# Scryfall fetch helpers
# ---------------------------------------------------------------------------

def _fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={
        "User-Agent": "SilverquiLLM-bench/0.1.0",
        "Accept": "application/json",
    })
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_pages(url: str) -> list[dict[str, Any]]:
    """Fetch all paginated Scryfall results starting from *url*."""
    cards: list[dict[str, Any]] = []
    while url:
        data = _fetch_json(url)
        cards.extend(data.get("data", []))
        url = data["next_page"] if data.get("has_more") else ""
        if url:
            time.sleep(REQUEST_DELAY)
    return cards


def _load_cache(path: Path) -> list[dict[str, Any]] | None:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(path: Path, cards: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2)


def _fetch_fdn_base(force: bool = False) -> list[dict[str, Any]]:
    """Fetch FDN base-set cards (CN 1–281), deduplicated by name.

    Basic lands have multiple art variants (different CNs, same card behavior).
    We keep the lowest-CN occurrence of each unique card name so that each
    unique implementation maps to exactly one directory.
    """
    cache = CACHE_DIR / f"fdn_cn{FDN_CN_MIN}-{FDN_CN_MAX}.json"
    if not force and _load_cache(cache) is not None:
        return _load_cache(cache)

    print(f"Fetching FDN CN {FDN_CN_MIN}–{FDN_CN_MAX} from Scryfall…")
    q = f"e%3Afdn+cn%3E%3D{FDN_CN_MIN}+cn%3C%3D{FDN_CN_MAX}"
    url = f"{SCRYFALL_SEARCH_URL}?order=set&q={q}&unique=prints"
    raw = _fetch_pages(url)

    # Filter to the CN range, sort by CN, deduplicate by name (keep lowest CN).
    in_range = sorted(
        (c for c in raw if FDN_CN_MIN <= _cn_int(c.get("collector_number", "")) <= FDN_CN_MAX),
        key=lambda c: _cn_int(c["collector_number"]),
    )
    seen_names: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for card in in_range:
        name = card.get("name", "")
        if name not in seen_names:
            seen_names.add(name)
            deduped.append(card)

    _save_cache(cache, deduped)
    print(f"  {len(deduped)} unique FDN cards (from {len(in_range)} total in CN {FDN_CN_MIN}–{FDN_CN_MAX})")
    return deduped


def _fetch_fdn_spg(force: bool = False) -> list[dict[str, Any]]:
    """Fetch SPG Special Guest cards for the FDN draft pool (CN 74–83)."""
    cache = CACHE_DIR / f"spg_cn{FDN_SPG_CN_MIN}-{FDN_SPG_CN_MAX}.json"
    if not force and _load_cache(cache) is not None:
        cached = _load_cache(cache)
        cached_cns = {int(c["collector_number"]) for c in cached}
        if cached_cns == set(range(FDN_SPG_CN_MIN, FDN_SPG_CN_MAX + 1)):
            return cached

    print(f"Fetching SPG CN {FDN_SPG_CN_MIN}–{FDN_SPG_CN_MAX} from Scryfall…")
    q = f"e%3Aspg+cn%3E%3D{FDN_SPG_CN_MIN}+cn%3C%3D{FDN_SPG_CN_MAX}"
    url = f"{SCRYFALL_SEARCH_URL}?order=set&q={q}&unique=prints"
    raw = _fetch_pages(url)

    filtered = [
        c for c in raw
        if FDN_SPG_CN_MIN <= _cn_int(c.get("collector_number", "")) <= FDN_SPG_CN_MAX
    ]
    _save_cache(cache, filtered)
    print(f"  {len(filtered)} SPG Special Guest cards")
    return filtered


def _cn_int(cn: str) -> int:
    try:
        return int(cn)
    except (ValueError, TypeError):
        return -1


# ---------------------------------------------------------------------------
# Complexity tier heuristic
# ---------------------------------------------------------------------------

def _infer_tier(oracle_text: str, type_line: str) -> str:
    """Infer complexity tier from oracle text and type line."""
    if "Planeswalker" in type_line:
        return "complex"
    n = len(oracle_text)
    if n == 0 or n < 60:
        return "simple"
    if n > 280:
        return "complex"
    return "medium"


# ---------------------------------------------------------------------------
# Card extraction helpers
# ---------------------------------------------------------------------------

def _extract_fields(card: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant fields from a raw Scryfall card dict."""
    faces = card.get("card_faces", [])
    front = faces[0] if faces else {}

    def _str(key: str) -> str:
        v = card.get(key)
        if v is not None and v != "":
            return v
        return front.get(key, "")

    def _opt(key: str) -> str | None:
        v = card.get(key)
        if v is not None:
            return v
        return front.get(key)

    return {
        "name": card.get("name", ""),
        "mana_cost": _str("mana_cost"),
        "type_line": card.get("type_line", ""),
        "oracle_text": _str("oracle_text"),
        "power": _opt("power"),
        "toughness": _opt("toughness"),
        "loyalty": card.get("loyalty"),
        "colors": card.get("colors", []),
        "keywords": card.get("keywords", []),
        "rarity": card.get("rarity", ""),
        "set_code": card.get("set", ""),
        "collector_number": card.get("collector_number", ""),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False, force: bool = False) -> None:
    # 1. Fetch Scryfall data
    fdn_cards = _fetch_fdn_base(force=force)
    spg_cards = _fetch_fdn_spg(force=force)

    print(f"Total: {len(fdn_cards)} FDN + {len(spg_cards)} SPG = {len(fdn_cards) + len(spg_cards)} cards")

    # 2. Build (dir_key, fields) pairs
    entries: list[tuple[str, dict[str, Any]]] = []

    for card in sorted(fdn_cards, key=lambda c: _cn_int(c.get("collector_number", ""))):
        fields = _extract_fields(card)
        cn = fields["collector_number"]
        entries.append((cn, fields))

    for card in sorted(spg_cards, key=lambda c: _cn_int(c.get("collector_number", ""))):
        fields = _extract_fields(card)
        cn = fields["collector_number"]
        entries.append((f"spg_{cn}", fields))

    # 3. Sanity-check for duplicate directory keys
    seen_keys: dict[str, str] = {}
    for key, fields in entries:
        name = fields["name"]
        if key in seen_keys:
            print(f"WARNING: directory key {key!r} used by both {seen_keys[key]!r} and {name!r}")
        seen_keys[key] = name

    # 4. Write output
    written = 0
    for key, fields in entries:
        oracle_text = fields["oracle_text"]
        type_line = fields["type_line"]
        name = fields["name"]

        spec = {
            "name": name,
            "mana_cost": fields["mana_cost"],
            "type_line": type_line,
            "oracle_text": oracle_text,
            "power": fields["power"],
            "toughness": fields["toughness"],
            "loyalty": fields["loyalty"],
            "colors": fields["colors"],
            "keywords": fields["keywords"],
            "rarity": fields["rarity"],
            "set_code": fields["set_code"],
            "collector_number": fields["collector_number"],
            "complexity_tier": _infer_tier(oracle_text, type_line),
        }

        class_name = card_name_to_class_name(name)
        impl = _CARD_IMPL_TEMPLATE.format(name=name, class_name=class_name)

        card_dir = OUTPUT_DIR / key
        spec_path = card_dir / "card_spec.json"
        impl_path = card_dir / "card_impl.py"

        if dry_run:
            print(f"  [dry-run] {key}/  ({name})")
            continue

        card_dir.mkdir(parents=True, exist_ok=True)
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
            f.write("\n")
        impl_path.write_text(impl, encoding="utf-8")
        written += 1

    if dry_run:
        print(f"Dry run: would write {len(entries)} directories under {OUTPUT_DIR}/")
    else:
        print(f"Wrote {written} card directories under {OUTPUT_DIR}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing files")
    parser.add_argument("--force", action="store_true", help="Re-fetch from Scryfall (ignore cache)")
    args = parser.parse_args()
    main(dry_run=args.dry_run, force=args.force)
