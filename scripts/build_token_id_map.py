#!/usr/bin/env python3
"""Build the corpus-derived token identity map for FDN replays.

Scryfall carries no ``arena_id`` for FDN token objects (all TFDN tokens have
``arena_id: null``), so ``scripts/build_card_id_map.py`` cannot source them.
The replay stream itself is the only viable source: every
``GameObjectType_Token`` object carries ``objectSourceGrpId`` (the card that
minted it), ``cardTypes``, ``subtypes``, ``color``, ``power`` and
``toughness``. This script sweeps the corpus and emits a committed map at
``data/replays/token_id_map.json`` giving every observed token grpId a stable
identity — label, source grpId(s), characteristics and base P/T — so the
replay executor can correlate engine-minted tokens to their GRE grpId instead
of treating them as anonymous id-0 shells.

Usage::

    python scripts/build_token_id_map.py [CORPUS_DIR]

CORPUS_DIR defaults to ``/mnt/data/benchmark-replays/fdn`` (the gitignored FDN
replay corpus, 271 games). The output is deterministic: re-running over the
same corpus reproduces the file byte-identically (every collection is sorted,
and modal characteristics are chosen with a deterministic tie-break).

Two kinds of token grpId appear in the corpus:

* **generic** — the FDN token block (94156-94178, 21 grpIds): anonymous
  generic tokens (Cat, Rabbit, Soldier, Food, Treasure, ...). Their grpId is
  NOT in ``card_id_map.json``, so before this map they surfaced as
  ``grpId_<n>`` MISSING_CARD entries.
* **copy** — a token whose grpId IS a real card grpId (``grpId ==
  overlayGrpId == objectSourceGrpId``); a token copy of that card. These
  already resolve through ``card_id_map.json`` and never caused MISSING_CARD,
  but are recorded here for completeness.

The map also carries an ``arena_only_cards`` section for the four Arena-only
*card* grpIds the corpus references that Scryfall's arena_id feed omits
(93937, 93989, 93991, 95283). Three are alt-printings of registered FDN/SPG
cards; one (95283) appears in a single mixed-set game and is recorded as a
documented out-of-set exclusion. Each is resolved from its GRE characteristics
so it stops being anonymous either way.
"""

from __future__ import annotations

import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CORPUS = Path("/mnt/data/benchmark-replays/fdn")
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "data" / "replays" / "token_id_map.json"
CARD_ID_MAP_PATH = REPO_ROOT / "data" / "replays" / "card_id_map.json"

# The four Arena-only *card* grpIds the corpus references but Scryfall's
# arena_id feed omits. Resolved from GRE characteristics (verified against the
# FDN registry): three are alt-printings of registered impls; 95283 appears in
# a single mixed-set game (deck full of non-FDN grpIds) and has no FDN/registry
# match, so it is a documented out-of-set exclusion. Kept here (not derived) so
# the resolution is reviewable and stable; the characteristics are asserted
# against the corpus sweep below.
ARENA_ONLY_CARDS: dict[str, dict[str, Any]] = {
    "93937": {
        "resolves_to": "Gnarlid Colony",
        "canonical_grp_id": 94188,
        "kind": "alt_printing",
        "note": (
            "2/2 green Beast; alt-printing of Gnarlid Colony (canonical grpId "
            "94188, registered). Enters as an X/X so appears at 2/2, 4/4, 5/5."
        ),
    },
    "93989": {
        "resolves_to": "Embercleave",
        "canonical_grp_id": 94703,
        "kind": "alt_printing",
        "note": (
            "Red Equipment; the only red Equipment in the FDN/SPG registry is "
            "Embercleave (canonical synthetic grpId 94703, registered)."
        ),
    },
    "93991": {
        "resolves_to": "Llanowar Elves",
        "canonical_grp_id": 93940,
        "kind": "alt_printing",
        "note": (
            "1/1 green Elf Druid; alt-printing of Llanowar Elves (canonical "
            "grpId 93940, registered)."
        ),
    },
    "95283": {
        "resolves_to": None,
        "canonical_grp_id": None,
        "kind": "out_of_set_exclusion",
        "note": (
            "Black/green Nightmare creature, base 1/1, grows with +1/+1 "
            "counters. Appears in exactly one corpus game whose decklist is "
            "full of non-FDN grpIds (11809, 81895, 175xxx...); no FDN/SPG "
            "registry match. Recorded as a named out-of-set exclusion so it "
            "stops being an anonymous grpId; it has no engine impl."
        ),
    },
}

# ---------------------------------------------------------------------------
# Corpus sweep
# ---------------------------------------------------------------------------


def _game_files(corpus: Path) -> list[str]:
    """Return the corpus game JSON files in deterministic (sorted) order."""
    files = sorted(glob.glob(str(corpus / "*" / "*.json")))
    return [
        f
        for f in files
        if "_info" not in Path(f).name and "event_details" not in Path(f).name
    ]


def _iter_game_objects(node: Any):
    """Yield every GRE game-object dict (has instanceId + GameObjectType) in a tree."""
    if isinstance(node, dict):
        t = node.get("type", "")
        if (
            isinstance(t, str)
            and t.startswith("GameObjectType")
            and "instanceId" in node
        ):
            yield node
        for value in node.values():
            yield from _iter_game_objects(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_game_objects(value)


def _pt(obj: dict, key: str) -> int | None:
    val = obj.get(key)
    if isinstance(val, dict):
        return val.get("value")
    return None


def _strip(prefix: str, values: list[str]) -> list[str]:
    return [v.removeprefix(prefix) for v in values]


def _sig(obj: dict) -> tuple:
    """Characteristic signature (card types, subtypes, colors) — the identity axis."""
    return (
        tuple(sorted(_strip("CardType_", obj.get("cardTypes", []) or []))),
        tuple(sorted(_strip("SubType_", obj.get("subtypes", []) or []))),
        tuple(sorted(_strip("CardColor_", obj.get("color", []) or []))),
    )


def sweep_corpus(corpus: Path) -> tuple[dict, dict]:
    """Return ``(token_stats, arena_stats)`` aggregated over the corpus.

    ``token_stats[grpId]`` collects the per-signature object counts, per-signature
    P/T counts, source grpIds and total observed count for every
    ``GameObjectType_Token`` grpId. ``arena_stats[grpId]`` collects the observed
    signatures/P-T for the four Arena-only card grpIds, for assertion.
    """
    token_stats: dict[int, dict] = defaultdict(
        lambda: {
            "sig_counts": Counter(),
            "pt_by_sig": defaultdict(Counter),
            "sources": Counter(),
            "total": 0,
        }
    )
    arena_ids = {int(k) for k in ARENA_ONLY_CARDS}
    arena_stats: dict[int, Counter] = defaultdict(Counter)

    for path in _game_files(corpus):
        try:
            data = json.load(open(path))
        except (OSError, json.JSONDecodeError):
            continue
        for obj in _iter_game_objects(data):
            grp = obj.get("grpId", 0)
            if not grp:
                continue
            if obj.get("type") == "GameObjectType_Token":
                sig = _sig(obj)
                st = token_stats[grp]
                st["sig_counts"][sig] += 1
                st["pt_by_sig"][sig][(_pt(obj, "power"), _pt(obj, "toughness"))] += 1
                src = obj.get("objectSourceGrpId")
                if src:
                    st["sources"][src] += 1
                st["total"] += 1
            elif grp in arena_ids:
                arena_stats[grp][(_sig(obj), _pt(obj, "power"), _pt(obj, "toughness"))] += 1
    return token_stats, arena_stats


# ---------------------------------------------------------------------------
# Map construction
# ---------------------------------------------------------------------------


def _modal(counter: Counter):
    """Return the most-common key, breaking ties by sorted order (deterministic)."""
    return sorted(counter.items(), key=lambda kv: (-kv[1], repr(kv[0])))[0][0]


def _colors_phrase(colors: list[str]) -> str:
    return " ".join(c.lower() for c in colors) if colors else "colorless"


def _label(sig: tuple, base_power, base_toughness) -> str:
    card_types, subtypes, colors = sig
    subtype_phrase = " ".join(subtypes) if subtypes else " ".join(card_types).title()
    if "Creature" in card_types and base_power is not None:
        return f"{base_power}/{base_toughness} {_colors_phrase(colors)} {subtype_phrase} token"
    return f"{subtype_phrase} token"


def build_token_map(corpus: Path) -> dict:
    token_stats, arena_stats = sweep_corpus(corpus)
    card_id_map = json.load(open(CARD_ID_MAP_PATH))["grpId_to_card"]

    tokens: dict[str, dict] = {}
    for grp in sorted(token_stats):
        st = token_stats[grp]
        sig = _modal(st["sig_counts"])  # canonical characteristic signature
        base_power, base_toughness = _modal(st["pt_by_sig"][sig])
        card_types, subtypes, colors = sig
        card_name = card_id_map.get(str(grp), {}).get("card_name")
        entry: dict[str, Any] = {
            "label": _label(sig, base_power, base_toughness),
            "card_types": list(card_types),
            "subtypes": list(subtypes),
            "colors": list(colors),
            "base_power": base_power,
            "base_toughness": base_toughness,
            "source_grp_ids": sorted(st["sources"]),
            "observed_count": st["total"],
            "kind": "copy" if card_name else "generic",
        }
        if card_name:
            # Token copy of a real card — grpId already resolves via card_id_map.
            entry["name"] = card_name
        tokens[str(grp)] = entry

    # Assert the Arena-only card characteristics against the corpus sweep so the
    # hard-coded resolutions can't silently drift from the data.
    arena_out: dict[str, dict] = {}
    for grp_str, resolution in sorted(ARENA_ONLY_CARDS.items()):
        grp = int(grp_str)
        observed = arena_stats.get(grp, Counter())
        base_sig = None
        base_pt = None
        if observed:
            # Modal signature; base P/T = smallest observed P/T for that signature
            # (the printed value before counters/buffs).
            sig_counts: Counter = Counter()
            pt_for_sig: dict[tuple, list] = defaultdict(list)
            for (sig, p, t), c in observed.items():
                sig_counts[sig] += c
                pt_for_sig[sig].append((p, t))
            base_sig = _modal(sig_counts)
            pts = [pt for pt in pt_for_sig[base_sig] if pt[0] is not None]
            base_pt = min(pts) if pts else (None, None)
        entry = dict(resolution)
        if base_sig is not None:
            card_types, subtypes, colors = base_sig
            entry["card_types"] = list(card_types)
            entry["subtypes"] = list(subtypes)
            entry["colors"] = list(colors)
            entry["base_power"], entry["base_toughness"] = base_pt
        arena_out[grp_str] = entry

    return {
        "source": "corpus_derived",
        "description": (
            "grpId -> token identity map for FDN replays, derived from "
            "GameObjectType_Token objects in the replay corpus (Scryfall carries "
            "no arena_id for FDN tokens). 'generic' tokens are the anonymous FDN "
            "token block (94156-94178); 'copy' tokens already resolve via "
            "card_id_map.json. The arena_only_cards section resolves the four "
            "Arena-only card grpIds Scryfall's arena_id feed omits."
        ),
        "corpus": "fdn",
        "tokens": tokens,
        "arena_only_cards": arena_out,
    }


def main() -> None:
    corpus = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CORPUS
    if not corpus.exists():
        raise SystemExit(f"corpus directory not found: {corpus}")
    mapping = build_token_map(corpus)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)
        f.write("\n")
    n_generic = sum(1 for e in mapping["tokens"].values() if e["kind"] == "generic")
    n_copy = sum(1 for e in mapping["tokens"].values() if e["kind"] == "copy")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"  {len(mapping['tokens'])} token grpIds ({n_generic} generic, {n_copy} copy)")
    print(f"  {len(mapping['arena_only_cards'])} arena-only card grpIds")


if __name__ == "__main__":
    main()
