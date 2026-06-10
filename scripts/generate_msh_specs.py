#!/usr/bin/env python3
"""Generate MSH card specs and empty implementation stubs.

Reads the normalized card pool written by ``benchmarks/msh/fetch_data.py``
(``benchmarks/msh/data/msh.json``) and, for each card, creates:

  benchmarks/msh/workspace/cards/msh/msh_{cn}/card_spec.json  — oracle data
  benchmarks/msh/workspace/cards/msh/msh_{cn}/card_impl.py     — empty stub class

This mirrors the SOS benchmark layout (``cards/sos/sos_{cn}/``).  Per-card
directories are keyed ``msh_{collector_number}``.

Unlike SOS, MSH specs intentionally omit the ``complexity_tier`` field — we
do not classify card complexity for this set.

Usage:
    python3 scripts/generate_msh_specs.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from silverquillm.card_spec import card_name_to_class_name

SET_CODE = "msh"
DATA_PATH = PROJECT_ROOT / "benchmarks" / "msh" / "data" / "msh.json"
OUTPUT_DIR = (
    PROJECT_ROOT / "benchmarks" / "msh" / "workspace" / "cards" / "msh"
)

# Exact SOS stub template (see benchmarks/sos/workspace/cards/sos/*/card_impl.py).
_CARD_IMPL_TEMPLATE = '''\
"""Card implementation for {name}."""

from __future__ import annotations

from engine.card import CardImpl

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState


class {class_name}(CardImpl):
    """TODO: Implement {name}."""

    pass
'''

_INIT_DOCSTRING = '"""MSH card implementations and specs."""\n'


def _cn_int(card: dict[str, Any]) -> int:
    try:
        return int(card.get("collector_number", ""))
    except (ValueError, TypeError):
        return -1


def _extract_fields(card: dict[str, Any]) -> dict[str, Any]:
    """Extract spec fields from a normalized card, resolving DFC front faces.

    ``fetch_data._normalize_card`` already resolves ``name``, ``type_line``,
    ``oracle_text`` and ``mana_cost_str`` at the top level; here we also fall
    back to the front face for ``power``/``toughness``/``colors`` so modal DFCs
    keep their front-face stats.
    """
    faces = card.get("card_faces", [])
    front: dict[str, Any] = faces[0] if faces else {}

    def _opt(key: str) -> Any:
        val = card.get(key)
        if val is not None:
            return val
        return front.get(key)

    def _list(key: str) -> list[str]:
        val = card.get(key)
        if val:
            return val
        return front.get(key, [])

    return {
        "name": card.get("name", ""),
        "mana_cost": card.get("mana_cost_str", card.get("mana_cost", "")),
        "type_line": card.get("type_line", ""),
        "oracle_text": card.get("oracle_text", ""),
        "power": _opt("power"),
        "toughness": _opt("toughness"),
        "loyalty": card.get("loyalty"),
        "colors": _list("colors"),
        "keywords": card.get("keywords", []),
        "rarity": card.get("rarity", ""),
        "set_code": SET_CODE,
        "collector_number": card.get("collector_number", ""),
    }


def main(dry_run: bool = False) -> None:
    if not DATA_PATH.exists():
        print(
            f"ERROR: {DATA_PATH} not found. Run "
            f"`python -m benchmarks.msh.fetch_data` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(DATA_PATH, encoding="utf-8") as f:
        cards: list[dict[str, Any]] = json.load(f)

    print(f"Loaded {len(cards)} cards from {DATA_PATH}")

    if not dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        init_path = OUTPUT_DIR / "__init__.py"
        if not init_path.exists():
            init_path.write_text(_INIT_DOCSTRING, encoding="utf-8")

    written = 0
    for card in sorted(cards, key=_cn_int):
        fields = _extract_fields(card)
        cn = fields["collector_number"]
        name = fields["name"]
        if not cn or not name:
            print(f"WARNING: skipping card with missing cn/name: {card!r}")
            continue

        spec = {
            "name": name,
            "mana_cost": fields["mana_cost"],
            "type_line": fields["type_line"],
            "oracle_text": fields["oracle_text"],
            "power": fields["power"],
            "toughness": fields["toughness"],
            "loyalty": fields["loyalty"],
            "colors": fields["colors"],
            "keywords": fields["keywords"],
            "rarity": fields["rarity"],
            "set_code": SET_CODE,
            "collector_number": cn,
        }

        class_name = card_name_to_class_name(name)
        impl = _CARD_IMPL_TEMPLATE.format(name=name, class_name=class_name)

        dir_key = f"{SET_CODE}_{cn}"
        if dry_run:
            print(f"  [dry-run] {dir_key}/  ({name})")
            continue

        card_dir = OUTPUT_DIR / dir_key
        card_dir.mkdir(parents=True, exist_ok=True)
        with open(card_dir / "card_spec.json", "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
            f.write("\n")
        (card_dir / "card_impl.py").write_text(impl, encoding="utf-8")
        written += 1

    if dry_run:
        print(f"Dry run: would write {len(cards)} card directories under {OUTPUT_DIR}/")
    else:
        print(f"Wrote {written} card directories under {OUTPUT_DIR}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print plan without writing files"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
