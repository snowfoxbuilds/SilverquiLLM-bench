"""Prototype card selection and engine gap analysis.

Selects representative cards from the SOS set (one per complexity tier)
and analyzes which engine features are missing to support them.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any

__all__ = ["select_prototype_cards", "analyze_engine_gaps"]

# Ordered tiers from simplest to most complex.
TIERS = ["trivial", "simple", "medium", "complex", "expert"]

# ---------------------------------------------------------------------------
# Scoring helpers – each tier has a score function that returns a numeric
# preference score.  Higher is better.  The selector picks the candidate with
# the highest score (ties broken by list order, i.e. first in file wins).
# ---------------------------------------------------------------------------

_SINGLE_KEYWORDS = {
    "flying", "lifelink", "reach", "deathtouch", "haste",
    "vigilance", "trample", "first strike", "menace", "hexproof",
    "flash", "double strike", "indestructible", "defender",
}


def _score_trivial(c: dict) -> int:
    """Prefer vanilla creatures – Creature type, no oracle text abilities."""
    score = 0
    if "Creature" in c.get("type_line", ""):
        score += 2
    oracle = c.get("oracle_text", "").strip()
    if not oracle:
        score += 3  # truly vanilla – best
    return score


def _score_simple(c: dict) -> int:
    """Prefer single keyword ability creature."""
    score = 0
    if "Creature" in c.get("type_line", ""):
        score += 2
    oracle = c.get("oracle_text", "").strip().lower()
    # Check if oracle is just a single keyword
    if oracle in _SINGLE_KEYWORDS:
        score += 3
    elif any(kw in oracle for kw in _SINGLE_KEYWORDS):
        score += 1
    return score


def _score_medium(c: dict) -> int:
    """Prefer targeted spell or multi-ability creature."""
    score = 0
    oracle = c.get("oracle_text", "").lower()
    if "target" in oracle:
        score += 3
    # Multi-ability bonus
    if oracle.count("\n") >= 1:
        score += 1
    return score


def _score_complex(c: dict) -> int:
    """Prefer cards mentioning Prepared, Converge, or Opus."""
    score = 0
    oracle = c.get("oracle_text", "")
    for kw in ("Prepared", "Converge", "Opus"):
        if kw in oracle:
            score += 3
    return score


def _score_expert(c: dict) -> int:
    """Prefer planeswalker or card mentioning Miracle."""
    score = 0
    if "Planeswalker" in c.get("type_line", ""):
        score += 4
    oracle = c.get("oracle_text", "")
    if "Miracle" in oracle or "miracle" in oracle:
        score += 3
    return score


# Per-tier scoring functions and human-readable descriptions.
_TIER_PREFERENCES: dict[str, dict[str, Any]] = {
    "trivial": {
        "description": "vanilla creature (no abilities)",
        "score": _score_trivial,
    },
    "simple": {
        "description": "single keyword ability",
        "score": _score_simple,
    },
    "medium": {
        "description": "targeted spell or multi-ability creature",
        "score": _score_medium,
    },
    "complex": {
        "description": "card with a new SOS mechanic (Prepared, Converge, or Opus)",
        "score": _score_complex,
    },
    "expert": {
        "description": "planeswalker or card with Miracle",
        "score": _score_expert,
    },
}


def select_prototype_cards(
    classified_path: str,
    count_per_tier: int = 1,
) -> list[dict]:
    """Pick one card from each of the 5 complexity tiers.

    Parameters
    ----------
    classified_path:
        Path to the classified JSON file (list of ``{name, tier, ...}``).
        Each entry must have at least ``name`` and ``tier``.  If entries also
        contain ``oracle_text``, ``type_line``, ``mana_cost``, and
        ``collector_number`` the function can work without a sibling
        ``sos.json``.  When ``sos.json`` is present it is used to enrich
        card data (e.g. for entries that only carry ``name`` + ``tier``).
    count_per_tier:
        How many cards to select per tier.  Default 1 → 5 total.

    Returns
    -------
    list[dict]
        Selected cards with ``name``, ``tier``, ``rationale``, and full
        Scryfall fields.

    Raises
    ------
    FileNotFoundError
        If *classified_path* does not exist.
    """
    classified_dir = Path(classified_path).parent
    full_data_path = classified_dir / "sos.json"

    with open(classified_path) as f:
        classified = json.load(f)

    # Build tier → list of card names, and index classified entries.
    tier_map: dict[str, list[str]] = {t: [] for t in TIERS}
    classified_index: dict[str, dict] = {}
    for entry in classified:
        tier = entry.get("tier", "")
        name = entry.get("name", "")
        if tier in tier_map and name:
            tier_map[tier].append(name)
            if name not in classified_index:
                classified_index[name] = entry

    # Load full card data for oracle text / type_line lookups.
    full_cards: dict[str, dict] = {}
    if full_data_path.exists():
        with open(full_data_path) as f:
            for card in json.load(f):
                # Keep first occurrence (avoid duplicates from alternate arts).
                if card["name"] not in full_cards:
                    full_cards[card["name"]] = card

    # Merge classified entries that carry card data into full_cards as
    # fallback so the function works without sos.json when the classified
    # file contains enriched entries (oracle_text, type_line, etc.).
    for name, entry in classified_index.items():
        if name not in full_cards and "oracle_text" in entry:
            full_cards[name] = entry

    selected: list[dict] = []
    seen_names: set[str] = set()

    for tier in TIERS:
        prefs = _TIER_PREFERENCES[tier]
        score_fn = prefs["score"]
        candidates = [
            full_cards[n]
            for n in tier_map[tier]
            if n in full_cards and n not in seen_names
        ]

        # Sort candidates by tier-specific score (descending).
        candidates.sort(key=score_fn, reverse=True)

        for _ in range(count_per_tier):
            if not candidates:
                break
            card = candidates[0]
            rationale = prefs["description"]
            oracle = card.get("oracle_text", "")
            if oracle:
                rationale += f" — oracle: {oracle[:120]}"
            selected.append(
                {
                    "name": card["name"],
                    "tier": tier,
                    "rationale": rationale,
                    "collector_number": card.get("collector_number", ""),
                    "type_line": card.get("type_line", ""),
                    "oracle_text": oracle,
                    "mana_cost": card.get("mana_cost", ""),
                }
            )
            seen_names.add(card["name"])
            candidates = [c for c in candidates if c["name"] not in seen_names]

    return selected


def _file_contains(path: str, token: str) -> bool:
    """Check whether *token* appears in the source file at *path*."""
    try:
        with open(path) as f:
            return token in f.read()
    except FileNotFoundError:
        return False


def _ast_has_name(path: str, name: str) -> bool:
    """Check whether a Python file defines *name* (class/function/assign)."""
    try:
        with open(path) as f:
            tree = ast.parse(f.read())
    except (FileNotFoundError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return True
    return False


def analyze_engine_gaps(
    cards: list[dict],
    engine_dir: str = "engine",
) -> list[str]:
    """Identify engine features missing for the selected prototype cards.

    Parameters
    ----------
    cards:
        List of card dicts (must have ``oracle_text``).
    engine_dir:
        Path to the engine source directory.

    Returns
    -------
    list[str]
        Human-readable gap descriptions.  Empty list means no gaps found.
    """
    gaps: list[str] = []
    types_path = os.path.join(engine_dir, "types.py")
    mana_path = os.path.join(engine_dir, "mana.py")
    triggers_path = os.path.join(engine_dir, "triggers.py")
    casting_path = os.path.join(engine_dir, "casting.py")
    card_path = os.path.join(engine_dir, "card.py")

    # Collect all oracle texts.
    all_oracle = "\n".join(c.get("oracle_text", "") for c in cards)

    # --- Prepared ---
    if "Prepared" in all_oracle:
        if not _file_contains(types_path, "PREPARED"):
            gaps.append(
                "Keyword.PREPARED missing from engine/types.py — "
                "needed for the Prepared mechanic"
            )

    # --- Converge ---
    if "Converge" in all_oracle:
        # Need color-of-mana-spent tracking in mana system.
        has_color_tracking = _file_contains(mana_path, "colors_spent") or _file_contains(
            mana_path, "color_tracking"
        )
        if not has_color_tracking:
            gaps.append(
                "Mana color-of-mana-spent tracking missing from engine/mana.py — "
                "needed for the Converge mechanic"
            )

    # --- Miracle ---
    if "Miracle" in all_oracle or "miracle" in all_oracle:
        # Need draw-event hooks that allow casting at miracle cost.
        has_draw_hook = _file_contains(triggers_path, "DRAWS_CARD") or _file_contains(
            triggers_path, "draw_event"
        )
        has_miracle_cast = _file_contains(casting_path, "miracle") or _file_contains(
            casting_path, "Miracle"
        )
        if not has_miracle_cast:
            gaps.append(
                "Miracle casting support missing from engine/casting.py — "
                "draw-event hook exists (DRAWS_CARD) but no miracle cost path"
            )

    # --- Opus ---
    if "Opus" in all_oracle:
        # Modal spell infrastructure — check get_modes() exists.
        has_modes = _file_contains(card_path, "get_modes")
        if not has_modes:
            gaps.append(
                "Modal spell infrastructure (get_modes) missing from engine/card.py — "
                "needed for the Opus mechanic"
            )

    # --- Planeswalker loyalty abilities ---
    if any("Planeswalker" in c.get("type_line", "") for c in cards):
        has_loyalty = _file_contains(card_path, "loyalty") or _file_contains(
            types_path, "PLANESWALKER"
        )
        if not has_loyalty:
            gaps.append(
                "Planeswalker loyalty system missing from engine — "
                "needed for planeswalker cards"
            )

    return gaps


def write_prototype_artifacts(
    cards: list[dict],
    gaps: list[str],
    output_dir: str = "benchmarks/sos",
) -> tuple[str, str]:
    """Write prototype_cards.json and prototype_gaps.md.

    Returns
    -------
    tuple[str, str]
        Paths to the written JSON and MD files.
    """
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "prototype_cards.json")
    md_path = os.path.join(output_dir, "prototype_gaps.md")

    with open(json_path, "w") as f:
        json.dump(cards, f, indent=2)
        f.write("\n")

    lines = ["# Prototype Engine Gap Analysis\n\n"]
    lines.append(f"**Cards selected:** {len(cards)}\n\n")

    for card in cards:
        lines.append(f"## {card['name']} ({card['tier']})\n\n")
        lines.append(f"- **Type:** {card.get('type_line', 'N/A')}\n")
        lines.append(f"- **Mana cost:** {card.get('mana_cost', 'N/A')}\n")
        oracle = card.get("oracle_text", "")
        if oracle:
            lines.append(f"- **Oracle text:** {oracle}\n")
        lines.append("\n")

    lines.append("## Engine Gaps\n\n")
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}\n")
    else:
        lines.append("none\n")

    with open(md_path, "w") as f:
        f.writelines(lines)

    return json_path, md_path


def main() -> None:
    """Run prototype selection and gap analysis end-to-end."""
    classified_path = "benchmarks/sos/data/sos_classified.json"
    cards = select_prototype_cards(classified_path)
    gaps = analyze_engine_gaps(cards)
    json_path, md_path = write_prototype_artifacts(cards, gaps)
    print(f"Selected {len(cards)} prototype cards → {json_path}")
    print(f"Gap analysis ({len(gaps)} gaps) → {md_path}")
    for gap in gaps:
        print(f"  • {gap}")


if __name__ == "__main__":
    main()
