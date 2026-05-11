#!/usr/bin/env python3
"""Generate minimal stub card classes for all SOS Draft Set cards.

Reads ``benchmarks/sos/data/sos.json`` and generates
``cards/stubs/sos_stubs.py`` containing one stub class per card plus a
``register_sos_stubs(registry)`` function.

Usage:
    python3 scripts/generate_audited_stubs.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import silverquillm
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from silverquillm.template_gen import card_name_to_class_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _determine_base_class(type_line: str) -> tuple[str, list[str]]:
    """Return (base_class_name, card_type_enums) for a type line."""
    # Multi-type combos
    if "Artifact Creature" in type_line:
        return "ArtifactCreature", ["CardType.ARTIFACT", "CardType.CREATURE"]
    if "Enchantment Creature" in type_line:
        return "Creature", ["CardType.CREATURE", "CardType.ENCHANTMENT"]

    # Single types (order matters — check Creature before Artifact)
    single_types = [
        ("Creature", "Creature", ["CardType.CREATURE"]),
        ("Planeswalker", "Planeswalker", ["CardType.PLANESWALKER"]),
        ("Instant", "Instant", ["CardType.INSTANT"]),
        ("Sorcery", "Sorcery", ["CardType.SORCERY"]),
        ("Enchantment", "Enchantment", ["CardType.ENCHANTMENT"]),
        ("Artifact", "Artifact", ["CardType.ARTIFACT"]),
        ("Land", "Land", ["CardType.LAND"]),
    ]

    for keyword, base_cls, card_types in single_types:
        if keyword in type_line:
            return base_cls, card_types

    return "CardImpl", []


def _parse_subtypes(type_line: str) -> list[str]:
    """Extract subtypes from a type line (text after '—').

    For split/adventure cards with '//' face separators, only considers the
    first face's subtypes to avoid treating the separator or second-face
    card types as subtypes.
    """
    # Only consider the first face for subtypes
    if "//" in type_line:
        type_line = type_line.split("//", 1)[0].strip()

    if "\u2014" in type_line:
        after_dash = type_line.split("\u2014", 1)[1].strip()
        return [s.strip() for s in after_dash.split() if s.strip()]
    if " — " in type_line:
        after_dash = type_line.split(" — ", 1)[1].strip()
        return [s.strip() for s in after_dash.split() if s.strip()]
    return []


def _parse_supertypes(type_line: str) -> list[str]:
    """Extract supertypes (Legendary, Basic, Snow) from type line."""
    supertypes = []
    before_dash = type_line.split("\u2014")[0] if "\u2014" in type_line else type_line
    if "Legendary" in before_dash:
        supertypes.append("Supertype.LEGENDARY")
    if "Basic" in before_dash:
        supertypes.append("Supertype.BASIC")
    if "Snow" in before_dash:
        supertypes.append("Supertype.SNOW")
    return supertypes


def _mana_cost_code(mana_cost_str: str) -> str:
    """Generate code to construct a ManaCost from a mana cost string.

    Uses ManaCost.parse() at runtime for non-empty cost strings, falls back
    to ManaCost() for empty/missing costs (e.g. lands).

    For split cards (containing '//') we use only the first face's cost.
    Supported hybrid symbols like {U/R}, {W/B} are preserved.
    Unsupported symbols (Phyrexian {B/P}, two-brid {2/R}) are stripped and
    the remaining supported portion is parsed, so the stub retains at least
    the basic mana value rather than collapsing to CMC 0.
    """
    if not mana_cost_str or not mana_cost_str.strip():
        return "ManaCost()"
    # Split cards: use only first face's cost
    if "//" in mana_cost_str:
        first_face = mana_cost_str.split("//")[0].strip()
        if not first_face:
            return "ManaCost()"
        mana_cost_str = first_face

    import re as _re
    # Supported colour letters for hybrid symbols
    _COLORS = {"W", "U", "B", "R", "G"}

    tokens = _re.findall(r"\{([^}]+)\}", mana_cost_str)
    supported_tokens: list[str] = []
    for tok in tokens:
        if "/" in tok:
            parts = tok.split("/")
            if len(parts) == 2 and parts[0] in _COLORS and parts[1] in _COLORS:
                # Standard hybrid — engine supports this
                supported_tokens.append(f"{{{tok}}}")
            elif len(parts) == 2:
                # Unsupported hybrid variant (two-brid {2/R}, Phyrexian {B/P}).
                # Approximate: use the numeric part if present (two-brid),
                # or the colour pip otherwise, to preserve a nonzero CMC.
                numeric_part = None
                color_part = None
                for p in parts:
                    if p.isdigit():
                        numeric_part = p
                    elif p in _COLORS:
                        color_part = p
                if numeric_part is not None:
                    supported_tokens.append(f"{{{numeric_part}}}")
                elif color_part is not None:
                    supported_tokens.append(f"{{{color_part}}}")
                # else: truly unrecognised — drop it
        else:
            supported_tokens.append(f"{{{tok}}}")

    if not supported_tokens:
        return "ManaCost()"

    cost_str = "".join(supported_tokens)
    return f"ManaCost.parse({cost_str!r})"


def _parse_power_toughness(card: dict) -> tuple[int | None, int | None]:
    """Parse power/toughness, handling * and other non-numeric values."""
    power_str = card.get("power")
    toughness_str = card.get("toughness")

    def _to_int(val: str | None) -> int | None:
        if val is None:
            return None
        # Handle *, *+1, etc. — default to 0 for stubs
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    return _to_int(power_str), _to_int(toughness_str)


def generate_stubs(sos_data: list[dict]) -> str:
    """Generate the full sos_stubs.py source code."""
    lines: list[str] = []

    # Header
    lines.append('"""Auto-generated SOS Draft Set stub card classes.')
    lines.append("")
    lines.append("Generated by scripts/generate_audited_stubs.py.")
    lines.append("DO NOT EDIT MANUALLY — re-run the generator instead.")
    lines.append("")
    lines.append(f"Contains {len(sos_data)} stub classes for all SOS Draft Set cards.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from typing import TYPE_CHECKING")
    lines.append("")
    lines.append("from engine.card import (")
    lines.append("    Artifact,")
    lines.append("    ArtifactCreature,")
    lines.append("    CardImpl,")
    lines.append("    Creature,")
    lines.append("    Enchantment,")
    lines.append("    Instant,")
    lines.append("    Land,")
    lines.append("    Planeswalker,")
    lines.append("    Sorcery,")
    lines.append(")")
    lines.append("from engine.types import CardType, ManaCost, Supertype")
    lines.append("")
    lines.append("if TYPE_CHECKING:")
    lines.append("    from cards.registry import CardRegistry")
    lines.append("")
    lines.append("")

    # Track class names to handle duplicates
    class_name_counts: dict[str, int] = {}
    # Store card info for registration
    card_entries: list[dict] = []

    for card in sos_data:
        name = card["name"]
        class_name = card_name_to_class_name(name)

        # Handle duplicate class names
        if class_name in class_name_counts:
            class_name_counts[class_name] += 1
            class_name = f"{class_name}_{class_name_counts[class_name]}"
        else:
            class_name_counts[class_name] = 1

        type_line = card.get("type_line", "")
        base_class, card_type_enums = _determine_base_class(type_line)
        subtypes = _parse_subtypes(type_line)
        supertypes = _parse_supertypes(type_line)
        mana_cost_str = card.get("mana_cost", "")
        mana_cost_code = _mana_cost_code(mana_cost_str)
        power, toughness = _parse_power_toughness(card)
        loyalty = card.get("loyalty")
        if loyalty is not None:
            try:
                loyalty = int(loyalty)
            except (ValueError, TypeError):
                loyalty = 0
        colors = card.get("colors", [])
        set_code = card.get("set", "sos")
        collector_number = card.get("collector_number", "")

        # Generate class
        lines.append(f"class {class_name}({base_class}):")
        lines.append(f'    """Stub for {name}."""')
        lines.append("")
        lines.append(f"    def __init__(self, **kwargs):")

        # Build kwargs for super().__init__
        init_parts = []
        init_parts.append(f'        kwargs.setdefault("name", {name!r})')
        init_parts.append(f'        kwargs.setdefault("mana_cost", {mana_cost_code})')

        if card_type_enums:
            types_set = "{" + ", ".join(card_type_enums) + "}"
            init_parts.append(f'        kwargs.setdefault("card_types", {types_set})')

        if subtypes:
            subtypes_set = "{" + ", ".join(repr(s) for s in subtypes) + "}"
            init_parts.append(f'        kwargs.setdefault("subtypes", {subtypes_set})')

        if supertypes:
            supertypes_set = "{" + ", ".join(supertypes) + "}"
            init_parts.append(f'        kwargs.setdefault("supertypes", {supertypes_set})')

        if base_class in ("Creature", "ArtifactCreature"):
            init_parts.append(f'        kwargs.setdefault("base_power", {power or 0})')
            init_parts.append(f'        kwargs.setdefault("base_toughness", {toughness or 0})')

        if base_class == "Planeswalker" and loyalty is not None:
            init_parts.append(f'        kwargs.setdefault("starting_loyalty", {loyalty})')

        # Track whether we need to set P/T as instance attrs after super().__init__
        needs_post_init_pt = (
            power is not None and toughness is not None
            and base_class not in ("Creature", "ArtifactCreature")
        )

        lines.extend(init_parts)
        lines.append("        super().__init__(**kwargs)")

        if needs_post_init_pt:
            lines.append(f"        self.base_power = {power or 0}")
            lines.append(f"        self.base_toughness = {toughness or 0}")

        if colors:
            colors_list = repr(colors)
            lines.append(f"        self.colors = {colors_list}")
        lines.append("")
        lines.append("")

        card_entries.append({
            "name": name,
            "class_name": class_name,
            "mana_cost_str": mana_cost_str,
            "type_line": type_line,
            "power": card.get("power"),
            "toughness": card.get("toughness"),
            "colors": colors,
            "keywords": card.get("keywords", []),
            "rarity": card.get("rarity", ""),
            "set_code": set_code,
            "collector_number": collector_number,
        })

    # Generate the registration function
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# Registration")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.append("_STUB_CARDS: list[tuple[str, type, str, str, str | None, str | None, list[str], list[str], str, str, str]] = [")

    for entry in card_entries:
        lines.append(f"    (")
        lines.append(f"        {entry['name']!r},")
        lines.append(f"        {entry['class_name']},")
        lines.append(f"        {entry['mana_cost_str']!r},")
        lines.append(f"        {entry['type_line']!r},")
        lines.append(f"        {entry['power']!r},")
        lines.append(f"        {entry['toughness']!r},")
        lines.append(f"        {entry['colors']!r},")
        lines.append(f"        {entry['keywords']!r},")
        lines.append(f"        {entry['rarity']!r},")
        lines.append(f"        {entry['set_code']!r},")
        lines.append(f"        {entry['collector_number']!r},")
        lines.append(f"    ),")

    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append("def register_sos_stubs(registry: CardRegistry) -> None:")
    lines.append('    """Register all SOS Draft Set stub cards with *registry*."""')
    lines.append("    from cards.registry import CardMetadata")
    lines.append("")
    lines.append("    for (name, impl_class, mana_cost_str, type_line, power,")
    lines.append("         toughness, colors, keywords, rarity, set_code, collector_number) in _STUB_CARDS:")
    lines.append("        metadata = CardMetadata(")
    lines.append("            name=name,")
    lines.append("            mana_cost_str=mana_cost_str,")
    lines.append("            type_line=type_line,")
    lines.append("            oracle_text='',")
    lines.append("            power=power,")
    lines.append("            toughness=toughness,")
    lines.append("            colors=colors,")
    lines.append("            keywords=keywords,")
    lines.append("            rarity=rarity,")
    lines.append("            set_code=set_code,")
    lines.append("            collector_number=collector_number,")
    lines.append("        )")
    lines.append("        registry.register(name, impl_class, metadata)")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Main entry point."""
    sos_json_path = PROJECT_ROOT / "benchmarks" / "sos" / "data" / "sos.json"
    if not sos_json_path.exists():
        print(f"ERROR: {sos_json_path} not found. Run fetch_data.py first.", file=sys.stderr)
        sys.exit(1)

    with open(sos_json_path) as f:
        sos_data = json.load(f)

    print(f"Loaded {len(sos_data)} cards from {sos_json_path}")

    # Sort by set_code then collector_number for deterministic output
    def sort_key(card: dict) -> tuple[str, int]:
        set_code = card.get("set", "sos")
        cn = card.get("collector_number", "0")
        try:
            cn_int = int(cn)
        except ValueError:
            cn_int = 9999
        # sos first, then soa, then spg
        set_order = {"sos": 0, "soa": 1, "spg": 2}
        return (set_order.get(set_code, 3), cn_int)

    sos_data.sort(key=sort_key)

    source = generate_stubs(sos_data)

    output_path = PROJECT_ROOT / "cards" / "stubs" / "sos_stubs.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(source)
    print(f"Generated {output_path} ({len(sos_data)} stub classes)")


if __name__ == "__main__":
    main()
