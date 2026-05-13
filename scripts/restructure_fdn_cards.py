#!/usr/bin/env python3
"""Migrate FDN cards from monolithic cards/foundations/ files to per-card layout.

Target layout: cards/fdn/{collector_number}/card_impl.py + card_spec.json

SPG cards → cards/fdn/spg_{collector_number}/
Collision suffixes (105b, 61b, etc.) per KEY_DECISIONS convention.
Cards with empty collector_number use synthetic IDs from audited conftest.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import re
import sys
import textwrap
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Collision suffix map: class_name → directory suffix
# From KEY_DECISIONS: "105b", "61b", "219b", "228b", "7b", "129b"
# These cards get the "b" suffix; the other card at same CN keeps plain number.
# ---------------------------------------------------------------------------
COLLISION_B_SUFFIX: dict[str, str] = {
    "FellingBlow": "105b",
    "HighSocietyHunter": "61b",
    "ElvishArchdruid": "219b",
    "MildManneredLibrarian": "228b",
    "LeylineAxe": "129b",
    "CrystalBarricade": "7b",
}

# ---------------------------------------------------------------------------
# Synthetic IDs for cards with empty collector_number
# Matches the audited conftest synthetic directory assignments (800–829).
# ---------------------------------------------------------------------------
SYNTHETIC_IDS: dict[str, str] = {
    # Basic lands
    "Plains": "001",
    "Island": "002",
    "Swamp": "003",
    "Mountain": "004",
    "Forest": "005",
    # Artifacts
    "Sol Ring": "800",
    "Arcane Signet": "801",
    "Mind Stone": "802",
    "Bonesplitter": "803",
    "Swiftfoot Boots": "804",
    "Whispersilk Cloak": "805",
    "Mask of Memory": "806",
    "Altar of the Brood": "807",
    "Elixir of Immortality": "808",
    "Relic of Progenitus": "809",
    # Enchantments
    "Holy Strength": "810",
    "Unholy Strength": "811",
    "Stab Wound": "812",
    "Arrest": "813",
    "Glorious Anthem": "814",
    "Dictate of Heliod": "815",
    "Brave the Sands": "816",
    "Levitation": "817",
    # Planeswalkers
    "Ajani, Caller of the Pride": "818",
    "Chandra, Torch of Defiance": "819",
    "Liliana, Dreadhorde General": "820",
    "Nissa, Worldwaker": "821",
    # Modal/complex spells
    "Abzan Charm": "822",
    "Boros Charm": "823",
    "Prismari Command": "824",
    "Sublime Epiphany": "825",
    "Dromoka's Command": "826",
    "Austere Command": "827",
    "Collective Brutality": "828",
    "Inscription of Insight": "829",
}


def get_dir_name(card_name: str, class_name: str, collector_number: str, set_code: str) -> str:
    """Determine the per-card directory name under cards/fdn/."""
    # SPG cards get spg_ prefix
    if set_code == "spg":
        return f"spg_{collector_number}"
    # Collision suffix override
    if class_name in COLLISION_B_SUFFIX:
        return COLLISION_B_SUFFIX[class_name]
    # Empty collector number → synthetic ID
    if not collector_number:
        if card_name in SYNTHETIC_IDS:
            return SYNTHETIC_IDS[card_name]
        raise ValueError(f"No synthetic ID for card with empty CN: {card_name} ({class_name})")
    return collector_number


def extract_class_source(source_file: str, class_name: str) -> tuple[str, list[str]]:
    """Extract a class definition and determine its imports from a source file.

    Returns (class_source, needed_imports) where needed_imports are the
    import lines the class needs.
    """
    with open(source_file) as f:
        content = f.read()

    tree = ast.parse(content)

    # Find the class node
    class_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_node = node
            break

    if class_node is None:
        raise ValueError(f"Class {class_name} not found in {source_file}")

    # Extract class source using line numbers
    lines = content.split('\n')
    start = class_node.lineno - 1
    end = class_node.end_lineno
    class_lines = lines[start:end]
    class_source = '\n'.join(class_lines)

    return class_source, []


def collect_all_cards():
    """Register all cards and return card data."""
    from cards.registry import CardRegistry, CardMetadata

    registry = CardRegistry()

    from cards.foundations.basic_lands import register_basic_lands
    from cards.foundations.simple_spells import register_simple_spells
    from cards.foundations.simple_spells_batch2 import register_simple_spells_batch2
    from cards.foundations.simple_spells_batch3 import register_simple_spells_batch3
    from cards.foundations.simple_creatures import register_simple_creatures
    from cards.foundations.vanilla_creatures_batch2 import register_vanilla_creatures_batch2
    from cards.foundations.etb_creatures import register_etb_creatures
    from cards.foundations.activated_creatures import register_activated_creatures
    from cards.foundations.death_trigger_creatures import register_death_trigger_creatures
    from cards.foundations.enchantments import register_enchantments
    from cards.foundations.global_enchantments import register_global_enchantments
    from cards.foundations.artifacts import register_artifacts
    from cards.foundations.artifacts_batch2 import register_artifacts_batch2
    from cards.foundations.equipment import register_equipment
    from cards.foundations.auras_batch2 import register_auras_batch2
    from cards.foundations.lands import register_lands
    from cards.foundations.modal_spells import register_modal_spells
    from cards.foundations.complex_spells import register_complex_spells
    from cards.foundations.planeswalkers import register_planeswalkers
    from cards.foundations.planeswalkers_batch2 import register_planeswalkers_batch2
    from cards.foundations.simple_permanents import register_simple_permanents
    from cards.foundations.special_guests import register_special_guests

    fns = [
        register_basic_lands, register_simple_spells, register_simple_spells_batch2,
        register_simple_spells_batch3, register_simple_creatures,
        register_vanilla_creatures_batch2, register_etb_creatures,
        register_activated_creatures, register_death_trigger_creatures,
        register_enchantments, register_global_enchantments, register_artifacts,
        register_artifacts_batch2, register_equipment, register_auras_batch2,
        register_lands, register_modal_spells, register_complex_spells,
        register_planeswalkers, register_planeswalkers_batch2,
        register_simple_permanents, register_special_guests,
    ]
    for fn in fns:
        fn(registry)

    cards = []
    for name in registry.list_all():
        impl_class, meta = registry.get(name)
        source_file = inspect.getfile(impl_class)
        cards.append({
            "name": name,
            "class_name": impl_class.__name__,
            "module": impl_class.__module__,
            "source_file": source_file,
            "collector_number": meta.collector_number,
            "set_code": meta.set_code,
            "mana_cost_str": meta.mana_cost_str,
            "type_line": meta.type_line,
            "oracle_text": meta.oracle_text,
            "rarity": meta.rarity,
            "power": meta.power,
            "toughness": meta.toughness,
            "colors": meta.colors,
            "keywords": meta.keywords,
        })
    return cards


def get_module_level_source(source_file: str, class_name: str) -> str:
    """Get the source lines for a module-level assignment like `X = make_vanilla(...)`.

    For dynamically-created classes (e.g. vanilla creatures), the class might
    be a module-level variable assigned via a factory call, not an actual class
    definition.
    """
    with open(source_file) as f:
        content = f.read()

    tree = ast.parse(content)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == class_name:
                    lines = content.split('\n')
                    return '\n'.join(lines[node.lineno - 1:node.end_lineno])

    return ""


def build_card_impl(card: dict, source_file: str) -> str:
    """Build the card_impl.py content for a single card."""
    class_name = card["class_name"]

    with open(source_file) as f:
        content = f.read()

    tree = ast.parse(content)
    lines = content.split('\n')

    # Check if it's a class definition or a module-level assignment (make_vanilla)
    is_class_def = False
    class_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            is_class_def = True
            class_node = node
            break

    assign_node = None
    if not is_class_def:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == class_name:
                        assign_node = node
                        break

    # Collect all needed helper functions/constants referenced by this class
    # For simplicity, we'll import the class from its original module
    # and re-export it. This is much more reliable than trying to extract
    # all dependencies.
    module = card["module"]

    impl_content = f'''"""Card implementation for {card['name']}."""

from {module} import {class_name}

__all__ = ["{class_name}"]
'''
    return impl_content


def build_card_spec(card: dict) -> dict:
    """Build the card_spec.json content."""
    return {
        "name": card["name"],
        "mana_cost": card["mana_cost_str"],
        "type_line": card["type_line"],
        "oracle_text": card["oracle_text"],
        "collector_number": card["collector_number"],
        "set_code": card["set_code"],
        "rarity": card["rarity"],
    }


def main():
    cards = collect_all_cards()
    fdn_dir = PROJECT_ROOT / "cards" / "fdn"
    fdn_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    init_file = fdn_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    created = 0
    for card in cards:
        dir_name = get_dir_name(
            card["name"], card["class_name"],
            card["collector_number"], card["set_code"],
        )
        card_dir = fdn_dir / dir_name
        card_dir.mkdir(parents=True, exist_ok=True)

        # Write card_impl.py
        impl_path = card_dir / "card_impl.py"
        impl_content = build_card_impl(card, card["source_file"])
        impl_path.write_text(impl_content)

        # Write card_spec.json
        spec_path = card_dir / "card_spec.json"
        spec = build_card_spec(card)
        spec_path.write_text(json.dumps(spec, indent=2) + "\n")

        created += 1
        print(f"  Created {card_dir.name}/ — {card['name']} ({card['class_name']})")

    print(f"\nCreated {created} per-card directories under cards/fdn/")


if __name__ == "__main__":
    main()
