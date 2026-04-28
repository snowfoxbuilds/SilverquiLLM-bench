"""Card complexity classifier for weighted benchmark scoring.

Classifies each card into a complexity tier based on heuristics
derived from oracle text, keywords, and card type. See SCORING.md
for tier definitions and weight multipliers.

Tiers and weights:
- **trivial** (1×): Basic lands, vanilla creatures, keyword-only cards
- **simple** (2×): Single keyword/straightforward ability
- **medium** (3×): Multiple abilities, targeting, conditional effects
- **complex** (4×): Multi-step abilities, replacement effects, modal,
  new SOS mechanics (Prepared, Converge, Opus)
- **expert** (5×): Planeswalkers, complex state machines, Miracle,
  unusual mechanics
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cards.registry import CardMetadata

__all__ = ["classify_card", "classify_set", "TIER_WEIGHTS"]

TIER_WEIGHTS: dict[str, int] = {
    "trivial": 1,
    "simple": 2,
    "medium": 3,
    "complex": 4,
    "expert": 5,
}

# SOS-specific mechanic keywords that bump complexity.
_SOS_MECHANICS = {"prepared", "converge", "opus"}

# Keywords that are simple evergreen abilities (just modify combat/stats).
_EVERGREEN_KEYWORDS = {
    "flying", "first strike", "double strike", "deathtouch", "haste",
    "hexproof", "indestructible", "lifelink", "menace", "reach",
    "trample", "vigilance", "ward", "flash", "defender", "prowess",
}


def _oracle_text_clean(oracle_text: str) -> str:
    """Return oracle text with reminder text (parenthetical) removed."""
    import re
    return re.sub(r"\([^)]*\)", "", oracle_text).strip()


def _count_abilities(oracle_text: str) -> int:
    """Count distinct ability paragraphs (newline-separated blocks)."""
    cleaned = _oracle_text_clean(oracle_text)
    if not cleaned:
        return 0
    return len([line for line in cleaned.split("\n") if line.strip()])


def _is_basic_land(card: CardMetadata) -> bool:
    return "Basic" in card.type_line and "Land" in card.type_line


def _is_planeswalker(card: CardMetadata) -> bool:
    return "Planeswalker" in card.type_line


def _has_sos_mechanic(card: CardMetadata) -> bool:
    """Check if card uses any SOS-specific mechanics."""
    oracle_lower = card.oracle_text.lower()
    kw_lower = {k.lower() for k in card.keywords}
    return bool(_SOS_MECHANICS & kw_lower) or any(
        m in oracle_lower for m in _SOS_MECHANICS
    )


def _has_replacement_effect(oracle_text: str) -> bool:
    """Check for replacement effect indicators."""
    lower = oracle_text.lower()
    return " instead" in lower or "if ~ would" in lower


def _is_modal(oracle_text: str) -> bool:
    """Check for modal spell indicators."""
    lower = oracle_text.lower()
    return any(phrase in lower for phrase in [
        "choose one", "choose two", "choose three",
        "choose any number",
    ])


def _has_miracle(card: CardMetadata) -> bool:
    lower_oracle = card.oracle_text.lower()
    kw_lower = {k.lower() for k in card.keywords}
    return "miracle" in kw_lower or "miracle" in lower_oracle


def _keyword_only_oracle(card: CardMetadata) -> bool:
    """Check if oracle text consists solely of keyword abilities.

    Handles comma-separated keywords (e.g. 'Reach, haste') and
    keyword-with-cost (e.g. 'Ward {2}').
    """
    cleaned = _oracle_text_clean(card.oracle_text)
    if not cleaned:
        return True
    # Split on newlines and commas
    import re
    parts = re.split(r"[,\n]", cleaned)
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
        # Strip ward/hexproof cost annotations like "{2}"
        base = re.sub(r"\{[^}]*\}", "", part).strip()
        if base not in _EVERGREEN_KEYWORDS:
            return False
    return True


def classify_card(card: CardMetadata) -> str:
    """Classify a single card into a complexity tier.

    Args:
        card: A :class:`~cards.registry.CardMetadata` instance.

    Returns:
        One of ``"trivial"``, ``"simple"``, ``"medium"``,
        ``"complex"``, or ``"expert"``.
    """
    oracle = card.oracle_text
    oracle_clean = _oracle_text_clean(oracle)
    oracle_lower = oracle.lower()
    ability_count = _count_abilities(oracle)
    has_target = "target" in oracle_lower
    keyword_count = len(card.keywords)

    # --- Expert floor ---
    if _is_planeswalker(card):
        return "expert"
    if _has_miracle(card):
        return "expert"

    # --- Trivial ---
    if _is_basic_land(card):
        return "trivial"
    # Vanilla creatures: no meaningful oracle text beyond mana abilities / reminder
    if not oracle_clean and "Creature" in card.type_line:
        return "trivial"
    # Keyword-only creatures/permanents
    if _keyword_only_oracle(card) and keyword_count <= 1:
        return "trivial"

    # --- Complex ---
    # SOS-specific mechanics always bump to at least complex
    if _has_sos_mechanic(card):
        return "complex"
    # Replacement effects
    if _has_replacement_effect(oracle):
        return "complex"
    # Modal spells
    if _is_modal(oracle):
        return "complex"
    # Multi-step abilities (3+ paragraphs)
    if ability_count >= 3:
        return "complex"
    # Very long oracle text suggests complex card
    if len(oracle) > 250:
        return "complex"

    # --- Medium ---
    # Multiple abilities (2 paragraphs) or targeting
    if ability_count >= 2 and has_target:
        return "medium"
    if ability_count >= 2 and keyword_count >= 1:
        return "medium"
    if has_target and keyword_count >= 1:
        return "medium"
    # Multiple keywords with non-trivial oracle
    if keyword_count >= 2:
        return "medium"
    # Moderate oracle length with targeting
    if has_target and len(oracle_clean) > 80:
        return "medium"
    # Two abilities even without targeting
    if ability_count >= 2:
        return "medium"

    # --- Targeting floor: any card with "target" is at least medium ---
    if has_target:
        return "medium"

    # --- Simple ---
    # Single keyword or one straightforward ability
    return "simple"


def classify_set(
    cards: list[CardMetadata],
    output_path: str | Path | None = None,
) -> dict[str, list[CardMetadata]]:
    """Group cards by complexity tier and optionally write results to JSON.

    Args:
        cards: List of :class:`~cards.registry.CardMetadata` instances.
        output_path: If provided, write classification results as JSON to
            this path. Defaults to
            ``benchmarks/sos/data/sos_classified.json``.

    Returns:
        A dict mapping tier names to lists of
        :class:`~cards.registry.CardMetadata`.
    """
    if output_path is None:
        output_path = (
            Path(__file__).resolve().parent.parent
            / "benchmarks" / "sos" / "data" / "sos_classified.json"
        )
    else:
        output_path = Path(output_path)

    result: dict[str, list[CardMetadata]] = {
        tier: [] for tier in TIER_WEIGHTS
    }

    json_records: list[dict[str, Any]] = []

    for card in cards:
        tier = classify_card(card)
        result[tier].append(card)
        json_records.append({
            "name": card.name,
            "collector_number": card.collector_number,
            "tier": tier,
            "weight": TIER_WEIGHTS[tier],
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_records, f, indent=2, ensure_ascii=False)

    return result


def load_sos_cards() -> list[CardMetadata]:
    """Load SOS card data from the cached JSON and return CardMetadata list."""
    sos_path = (
        Path(__file__).resolve().parent.parent
        / "benchmarks" / "sos" / "data" / "sos.json"
    )
    with open(sos_path, "r", encoding="utf-8") as f:
        raw_cards: list[dict[str, Any]] = json.load(f)

    result: list[CardMetadata] = []
    for raw in raw_cards:
        result.append(CardMetadata(
            name=raw.get("name", ""),
            mana_cost_str=raw.get("mana_cost_str", ""),
            type_line=raw.get("type_line", ""),
            oracle_text=raw.get("oracle_text", ""),
            power=raw.get("power"),
            toughness=raw.get("toughness"),
            colors=raw.get("colors", []),
            keywords=raw.get("keywords", []),
            rarity=raw.get("rarity", ""),
            set_code=raw.get("set_code", raw.get("set", "")),
            collector_number=raw.get("collector_number", ""),
        ))
    return result
