"""Template generator for benchmark card implementations.

Generates Python skeleton files that agents start from when implementing
cards for the benchmark suite.

Public API:
- ``generate_template`` — returns Python source string for a card spec.
- ``card_name_to_class_name`` — converts card name to PascalCase class name.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["generate_template", "card_name_to_class_name"]


def card_name_to_class_name(name: str) -> str:
    """Convert a card name to a PascalCase class name.

    Strips non-alphanumeric characters (except spaces used for word
    boundaries), then converts to PascalCase.

    Examples:
        >>> card_name_to_class_name("Strixhaven Prodigy")
        'StrixhavenProdigy'
        >>> card_name_to_class_name("Ral's Reinforcements")
        'RalsReinforcements'
    """
    # Strip apostrophes (possessives don't create word boundaries),
    # then treat remaining non-alphanumeric characters as word boundaries.
    no_apostrophes = name.replace("'", "").replace("\u2019", "")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", no_apostrophes)
    parts = cleaned.split()
    return "".join(word.capitalize() for word in parts)



def _determine_base_class(type_line: str) -> tuple[str, list[str]]:
    """Return (base_class_name, card_types_list) for a given type_line.

    Only "Artifact Creature" and "Enchantment Creature" are recognised as
    special multi-type combinations.  If multiple primary types match but
    don't form a recognised combination, we fall back to ``CardImpl``.
    """
    # Check special multi-type combos first
    _MULTI_TYPE_COMBOS: list[tuple[str, str, list[str]]] = [
        ("Artifact Creature", "ArtifactCreature", ["CardType.ARTIFACT", "CardType.CREATURE"]),
        ("Enchantment Creature", "Creature", ["CardType.CREATURE", "CardType.ENCHANTMENT"]),
    ]
    for keyword, base_cls, card_types in _MULTI_TYPE_COMBOS:
        if keyword in type_line:
            return base_cls, card_types

    # Single primary types
    _SINGLE_TYPES: list[tuple[str, str, list[str]]] = [
        ("Creature", "Creature", ["CardType.CREATURE"]),
        ("Instant", "Instant", ["CardType.INSTANT"]),
        ("Sorcery", "Sorcery", ["CardType.SORCERY"]),
        ("Enchantment", "Enchantment", ["CardType.ENCHANTMENT"]),
        ("Artifact", "Artifact", ["CardType.ARTIFACT"]),
        ("Planeswalker", "Planeswalker", ["CardType.PLANESWALKER"]),
        ("Land", "Land", ["CardType.LAND"]),
    ]

    matches = [
        (base_cls, card_types)
        for keyword, base_cls, card_types in _SINGLE_TYPES
        if keyword in type_line
    ]

    if len(matches) == 1:
        return matches[0]

    # Zero matches or ambiguous (multiple primary types) → CardImpl
    return "CardImpl", []


def generate_template(card_spec: dict[str, Any]) -> str:
    """Generate a Python skeleton file from a card spec dictionary.

    Parameters
    ----------
    card_spec:
        A card spec dict with keys: ``name``, ``mana_cost``, ``type_line``,
        ``oracle_text``, ``power``, ``toughness``, ``loyalty``, etc.

    Returns
    -------
    str
        Python source code for the card skeleton.
    """
    name = card_spec["name"]
    class_name = card_name_to_class_name(name)
    type_line = card_spec.get("type_line", "")
    base_class, card_types = _determine_base_class(type_line)
    mana_cost = card_spec.get("mana_cost", "")
    oracle_text = card_spec.get("oracle_text", "")
    power = card_spec.get("power")
    toughness = card_spec.get("toughness")
    loyalty = card_spec.get("loyalty")

    is_creature = base_class in ("Creature", "ArtifactCreature")
    is_planeswalker = base_class == "Planeswalker"

    lines: list[str] = []

    # Imports
    lines.append("from engine.card import *")
    lines.append("from engine.types import *")
    lines.append("")
    lines.append("")

    # Class definition
    lines.append(f"class {class_name}({base_class}):")
    lines.append(f'    """{name}."""')
    lines.append("")

    # Constructor
    lines.append("    def __init__(self, **kwargs):")

    # Build super().__init__ kwargs
    init_kwargs: list[str] = []
    init_kwargs.append(f'name="{name}"')
    if mana_cost:
        init_kwargs.append(f'mana_cost=ManaCost.parse("{mana_cost}")')
    if card_types:
        card_types_str = ", ".join(card_types)
        init_kwargs.append(f"card_types={{{card_types_str}}}")
    init_kwargs.append(f'rules_text="""{_escape_triple_quotes(oracle_text)}"""')

    if is_creature and power is not None and toughness is not None:
        init_kwargs.append(f"base_power={int(power)}")
        init_kwargs.append(f"base_toughness={int(toughness)}")

    if is_planeswalker and loyalty is not None:
        init_kwargs.append(f"starting_loyalty={int(loyalty)}")

    # Format kwargs
    lines.append("        super().__init__(")
    for kwarg in init_kwargs:
        lines.append(f"            {kwarg},")
    lines.append("            **kwargs,")
    lines.append("        )")

    lines.append("")

    # Add trailing newline
    return "\n".join(lines) + "\n"


def _escape_triple_quotes(text: str) -> str:
    """Escape triple-double-quotes in text for safe embedding in docstrings."""
    return text.replace('"""', '\\"\\"\\"')
