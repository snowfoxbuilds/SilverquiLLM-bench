"""Card spec generator for benchmark agent context.

Generates per-card JSON spec files that agents receive as context when
implementing cards.  Each spec contains the card's oracle data plus its
complexity tier from the classifier.

Public API:
- ``generate_card_spec`` — build a spec dict for a single card.
- ``generate_all_specs`` — write one ``card_spec.json`` per card in *output_dir*.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cards.registry import CardMetadata

__all__ = ["generate_card_spec", "generate_all_specs"]


def generate_card_spec(
    card: CardMetadata, tier: str, *, loyalty: str | None = None
) -> dict[str, Any]:
    """Return a spec dictionary for *card* at the given complexity *tier*.

    Parameters
    ----------
    card:
        The card metadata.
    tier:
        Complexity tier from the classifier.
    loyalty:
        Loyalty value for planeswalkers (from Scryfall data).
        Should be ``None`` for non-planeswalker cards.

    The returned dict matches the benchmark card-spec schema:

    .. code-block:: json

        {
          "name": "...",
          "mana_cost": "...",
          "type_line": "...",
          "oracle_text": "...",
          "power": "..." | null,
          "toughness": "..." | null,
          "loyalty": null | "...",
          "colors": [...],
          "keywords": [...],
          "rarity": "...",
          "set_code": "...",
          "collector_number": "...",
          "complexity_tier": "..."
        }
    """
    return {
        "name": card.name,
        "mana_cost": card.mana_cost_str,
        "type_line": card.type_line,
        "oracle_text": card.oracle_text,
        "power": card.power,
        "toughness": card.toughness,
        "loyalty": loyalty,
        "colors": list(card.colors),
        "keywords": list(card.keywords),
        "rarity": card.rarity,
        "set_code": card.set_code,
        "collector_number": card.collector_number,
        "complexity_tier": tier,
    }


def _load_scryfall_cards(data_path: Path) -> list[dict[str, Any]]:
    """Load the Scryfall card list from *data_path*."""
    with open(data_path, encoding="utf-8") as f:
        return json.load(f)


def _load_classified(data_path: Path) -> dict[str, dict[str, Any]]:
    """Load classified data keyed by ``set_code:collector_number``.

    Falls back to collector_number-only keys when ``set_code`` is absent
    (backward compatibility with older classified data).
    """
    with open(data_path, encoding="utf-8") as f:
        items: list[dict[str, Any]] = json.load(f)
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        cn = item["collector_number"]
        sc = item.get("set_code", "")
        # Composite key for multi-set pools
        if sc:
            result[f"{sc}:{cn}"] = item
        # Also store plain cn key for backward compat / single-set pools
        result[cn] = item
    return result


def _scryfall_to_metadata(card: dict[str, Any]) -> CardMetadata:
    """Convert a raw Scryfall card dict to a :class:`CardMetadata`."""
    return CardMetadata(
        name=card["name"],
        mana_cost_str=card.get("mana_cost", ""),
        type_line=card.get("type_line", ""),
        oracle_text=card.get("oracle_text", ""),
        power=card.get("power"),
        toughness=card.get("toughness"),
        colors=card.get("colors", []),
        keywords=card.get("keywords", []),
        rarity=card.get("rarity", ""),
        set_code=card.get("set", ""),
        collector_number=card.get("collector_number", ""),
    )


def generate_all_specs(set_code: str, output_dir: str) -> list[Path]:
    """Generate ``card_spec.json`` for every card in *set_code*.

    Reads Scryfall data from ``benchmarks/{set_code}/data/{set_code}.json``
    and classification data from
    ``benchmarks/{set_code}/data/{set_code}_classified.json``.

    Each spec is written to
    ``{output_dir}/{collector_number}/card_spec.json``.

    Raises:
        KeyError: If a card's collector number is not found in the
            classified data.

    Returns:
        A list of :class:`Path` objects for the files written.
    """
    repo_root = Path(__file__).resolve().parent.parent
    base = repo_root / "benchmarks" / set_code / "data"
    scryfall_path = base / f"{set_code}.json"
    classified_path = base / f"{set_code}_classified.json"

    scryfall_cards = _load_scryfall_cards(scryfall_path)
    classified = _load_classified(classified_path)

    out = Path(output_dir)
    written: list[Path] = []

    for raw_card in scryfall_cards:
        cn = raw_card.get("collector_number", "")
        sc = raw_card.get("set", raw_card.get("set_code", ""))
        # Try composite key first (multi-set pools), then plain cn
        composite_key = f"{sc}:{cn}" if sc else cn
        tier_info = classified.get(composite_key) or classified.get(cn)
        if tier_info is None:
            raise KeyError(
                f"Card collector_number {cn!r} ({raw_card.get('name', '?')}) "
                f"not found in {set_code}_classified.json. "
                f"Re-run the classifier to update classification data."
            )
        tier = tier_info.get("complexity_tier", tier_info.get("tier", "unknown"))

        meta = _scryfall_to_metadata(raw_card)
        loyalty = raw_card.get("loyalty")

        spec = generate_card_spec(meta, tier, loyalty=loyalty)

        # Use set_code prefix for multi-set pools to avoid collector number
        # collisions (e.g. SOS #1 vs SOA #1).  For single-set pools where
        # sc matches the top-level set_code, use plain cn for backward compat.
        dir_name = f"{sc}_{cn}" if sc and sc != set_code else cn
        card_dir = out / dir_name
        card_dir.mkdir(parents=True, exist_ok=True)
        spec_path = card_dir / "card_spec.json"
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
            f.write("\n")

        written.append(spec_path)

    return written
