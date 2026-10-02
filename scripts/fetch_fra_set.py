"""Fetch raw FRA print data; retain the committed cache unless --force is used."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fetch_hob_set import _atomic_write, _cn_int, _fetch_all_prints


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "data/sets/fra.json"
    if path.exists() and not args.force:
        print(f"Reusing pinned {path}")
        return
    cards = _fetch_all_prints("fra")
    cards.sort(key=lambda card: (_cn_int(card), str(card.get("id", ""))))
    _atomic_write(path, json.dumps(cards, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(cards)} raw FRA prints to {path}")


if __name__ == "__main__":
    main()
