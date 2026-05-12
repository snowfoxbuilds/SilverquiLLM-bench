"""Tests for TODO item 5: Template generator.

Tests verify:
- card_name_to_class_name converts various names correctly.
- generate_template produces valid Python that exec()s without error.
- Generated templates have correct base classes, imports, and stubs.
- Creature templates include power/toughness; planeswalkers include loyalty.
- card_types includes mandatory CardType per KEY_DECISION #6.
"""

from __future__ import annotations

import pytest

from silverquillm.template_gen import card_name_to_class_name, generate_template


# ---------------------------------------------------------------------------
# Fixtures: card spec dicts
# ---------------------------------------------------------------------------

def _creature_spec() -> dict:
    return {
        "name": "Strixhaven Prodigy",
        "mana_cost": "{1}{U}",
        "type_line": "Creature — Human Wizard",
        "oracle_text": "When Strixhaven Prodigy enters, draw a card.",
        "power": "2",
        "toughness": "3",
        "loyalty": None,
    }


def _instant_spec() -> dict:
    return {
        "name": "Lightning Bolt",
        "mana_cost": "{R}",
        "type_line": "Instant",
        "oracle_text": "Lightning Bolt deals 3 damage to any target.",
        "power": None,
        "toughness": None,
        "loyalty": None,
    }


def _sorcery_spec() -> dict:
    return {
        "name": "Lava Axe",
        "mana_cost": "{4}{R}",
        "type_line": "Sorcery",
        "oracle_text": "Lava Axe deals 5 damage to target player or planeswalker.",
        "power": None,
        "toughness": None,
        "loyalty": None,
    }


def _planeswalker_spec() -> dict:
    return {
        "name": "Jace Beleren",
        "mana_cost": "{1}{U}{U}",
        "type_line": "Legendary Planeswalker — Jace",
        "oracle_text": "+2: Each player draws a card.\n-1: Target player draws a card.\n-10: Target player mills twenty cards.",
        "power": None,
        "toughness": None,
        "loyalty": "3",
    }


def _enchantment_spec() -> dict:
    return {
        "name": "Pacifism",
        "mana_cost": "{1}{W}",
        "type_line": "Enchantment — Aura",
        "oracle_text": "Enchant creature\nEnchanted creature can't attack or block.",
        "power": None,
        "toughness": None,
        "loyalty": None,
    }


def _artifact_spec() -> dict:
    return {
        "name": "Sol Ring",
        "mana_cost": "{1}",
        "type_line": "Artifact",
        "oracle_text": "{T}: Add {C}{C}.",
        "power": None,
        "toughness": None,
        "loyalty": None,
    }


def _land_spec() -> dict:
    return {
        "name": "Forest",
        "mana_cost": "",
        "type_line": "Basic Land — Forest",
        "oracle_text": "({T}: Add {G}.)",
        "power": None,
        "toughness": None,
        "loyalty": None,
    }


def _artifact_creature_spec() -> dict:
    return {
        "name": "Bronze Sable",
        "mana_cost": "{2}",
        "type_line": "Artifact Creature — Sable",
        "oracle_text": "",
        "power": "2",
        "toughness": "1",
        "loyalty": None,
    }


# ---------------------------------------------------------------------------
# Tests: card_name_to_class_name
# ---------------------------------------------------------------------------

class TestCardNameToClassName:
    """Test card_name_to_class_name conversion."""

    def test_basic_two_words(self):
        assert card_name_to_class_name("Strixhaven Prodigy") == "StrixhavenProdigy"

    def test_single_word(self):
        assert card_name_to_class_name("Forest") == "Forest"

    def test_apostrophe_removed(self):
        result = card_name_to_class_name("Ral's Reinforcements")
        assert result == "RalsReinforcements"

    def test_hyphen_removed(self):
        result = card_name_to_class_name("Fire-Breathing")
        # Hyphen should be treated as a separator or removed; result should be PascalCase
        # Acceptable: "FireBreathing" or "Firebreathing" depending on splitting logic
        assert result[0] == "F"
        assert result.isalnum()
        # The key requirement is no hyphens and valid identifier
        assert result.isidentifier()

    def test_multiple_spaces(self):
        result = card_name_to_class_name("Jace   Beleren")
        assert result == "JaceBeleren"

    def test_special_characters_stripped(self):
        result = card_name_to_class_name("Ghitu Fire/Ice")
        assert result.isidentifier()
        assert result.isalnum()

    def test_comma_in_name(self):
        result = card_name_to_class_name("Kaalia, Zenith Seeker")
        assert result.isidentifier()
        assert "Kaalia" in result
        assert "Zenith" in result

    def test_result_is_valid_python_identifier(self):
        names = [
            "Strixhaven Prodigy",
            "Ral's Reinforcements",
            "Fire-Breathing",
            "Sol Ring",
            "Forest",
        ]
        for name in names:
            result = card_name_to_class_name(name)
            assert result.isidentifier(), f"{name!r} -> {result!r} is not a valid identifier"

    def test_empty_string(self):
        """Edge case: empty name should still produce a string (possibly empty)."""
        result = card_name_to_class_name("")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: generate_template
# ---------------------------------------------------------------------------

class TestGenerateTemplate:
    """Test generate_template output."""

    def test_creature_template_execs_without_error(self):
        """Generated creature template should be valid Python."""
        source = generate_template(_creature_spec())
        # exec in a namespace that has the engine imports available
        # We exec to verify syntax; actual engine imports may not resolve
        # but we can compile to check syntax
        compile(source, "<creature_template>", "exec")

    def test_instant_template_execs_without_error(self):
        source = generate_template(_instant_spec())
        compile(source, "<instant_template>", "exec")

    def test_planeswalker_template_execs_without_error(self):
        source = generate_template(_planeswalker_spec())
        compile(source, "<planeswalker_template>", "exec")

    def test_sorcery_template_compiles(self):
        source = generate_template(_sorcery_spec())
        compile(source, "<sorcery_template>", "exec")

    def test_enchantment_template_compiles(self):
        source = generate_template(_enchantment_spec())
        compile(source, "<enchantment_template>", "exec")

    def test_artifact_template_compiles(self):
        source = generate_template(_artifact_spec())
        compile(source, "<artifact_template>", "exec")

    def test_land_template_compiles(self):
        source = generate_template(_land_spec())
        compile(source, "<land_template>", "exec")

    def test_artifact_creature_template_compiles(self):
        source = generate_template(_artifact_creature_spec())
        compile(source, "<artifact_creature_template>", "exec")

    # --- Base class correctness ---

    def test_creature_base_class(self):
        source = generate_template(_creature_spec())
        assert "class StrixhavenProdigy(Creature):" in source

    def test_instant_base_class(self):
        source = generate_template(_instant_spec())
        assert "class LightningBolt(Instant):" in source

    def test_sorcery_base_class(self):
        source = generate_template(_sorcery_spec())
        assert "class LavaAxe(Sorcery):" in source

    def test_planeswalker_base_class(self):
        source = generate_template(_planeswalker_spec())
        assert "class JaceBeleren(Planeswalker):" in source

    def test_enchantment_base_class(self):
        source = generate_template(_enchantment_spec())
        assert "class Pacifism(Enchantment):" in source

    def test_artifact_base_class(self):
        source = generate_template(_artifact_spec())
        assert "class SolRing(Artifact):" in source

    def test_land_base_class(self):
        source = generate_template(_land_spec())
        assert "class Forest(Land):" in source

    def test_artifact_creature_base_class(self):
        source = generate_template(_artifact_creature_spec())
        assert "class BronzeSable(ArtifactCreature):" in source

    # --- Class name is PascalCase ---

    def test_class_name_matches_pascal_case(self):
        source = generate_template(_creature_spec())
        assert "StrixhavenProdigy" in source

    # --- Imports ---

    def test_template_imports_engine_card(self):
        source = generate_template(_creature_spec())
        assert "from engine.card import" in source

    def test_template_imports_engine_types(self):
        source = generate_template(_creature_spec())
        assert "from engine.types import" in source

    def test_template_imports_game_state(self):
        """Generated template must include GameState import (Item 13 / Issue #12)."""
        source = generate_template(_creature_spec())
        assert "from engine.game_state import GameState" in source

    def test_all_card_types_import_game_state(self):
        """GameState import must be present in templates for all card types."""
        specs = [
            _creature_spec(), _instant_spec(), _sorcery_spec(),
            _planeswalker_spec(), _enchantment_spec(), _artifact_spec(),
            _land_spec(), _artifact_creature_spec(),
        ]
        for spec in specs:
            source = generate_template(spec)
            assert "from engine.game_state import GameState" in source, (
                f"GameState import missing in template for {spec.get('type_line', 'unknown')}"
            )

    # --- Creature stubs: power/toughness ---

    def test_creature_has_power_stub(self):
        source = generate_template(_creature_spec())
        assert "base_power=2" in source or "power=2" in source

    def test_creature_has_toughness_stub(self):
        source = generate_template(_creature_spec())
        assert "base_toughness=3" in source or "toughness=3" in source

    def test_artifact_creature_has_power_toughness(self):
        source = generate_template(_artifact_creature_spec())
        assert "base_power=2" in source or "power=2" in source
        assert "base_toughness=1" in source or "toughness=1" in source

    # --- Planeswalker stubs: starting_loyalty ---

    def test_planeswalker_has_starting_loyalty(self):
        source = generate_template(_planeswalker_spec())
        assert "starting_loyalty=3" in source or "loyalty=3" in source

    def test_instant_no_power_toughness(self):
        source = generate_template(_instant_spec())
        assert "base_power" not in source
        assert "base_toughness" not in source

    def test_instant_no_loyalty(self):
        source = generate_template(_instant_spec())
        assert "starting_loyalty" not in source

    # --- card_types includes mandatory CardType (KEY_DECISION #6) ---

    def test_creature_card_types_include_creature(self):
        source = generate_template(_creature_spec())
        assert "CardType.CREATURE" in source

    def test_instant_card_types_include_instant(self):
        source = generate_template(_instant_spec())
        assert "CardType.INSTANT" in source

    def test_sorcery_card_types_include_sorcery(self):
        source = generate_template(_sorcery_spec())
        assert "CardType.SORCERY" in source

    def test_planeswalker_card_types_include_planeswalker(self):
        source = generate_template(_planeswalker_spec())
        assert "CardType.PLANESWALKER" in source

    def test_enchantment_card_types_include_enchantment(self):
        source = generate_template(_enchantment_spec())
        assert "CardType.ENCHANTMENT" in source

    def test_artifact_card_types_include_artifact(self):
        source = generate_template(_artifact_spec())
        assert "CardType.ARTIFACT" in source

    def test_land_card_types_include_land(self):
        source = generate_template(_land_spec())
        assert "CardType.LAND" in source

    def test_artifact_creature_card_types_include_both(self):
        source = generate_template(_artifact_creature_spec())
        assert "CardType.ARTIFACT" in source
        assert "CardType.CREATURE" in source

    # --- Docstring includes card name ---

    def test_template_has_docstring_with_name(self):
        source = generate_template(_creature_spec())
        assert "Strixhaven Prodigy" in source

    # --- Rules text included ---

    def test_template_includes_rules_text(self):
        source = generate_template(_creature_spec())
        assert "draw a card" in source

    # --- Mana cost included ---

    def test_template_includes_mana_cost(self):
        source = generate_template(_creature_spec())
        assert "{1}{U}" in source

    # --- Return type is str ---

    def test_returns_string(self):
        result = generate_template(_creature_spec())
        assert isinstance(result, str)

    # --- Full exec with engine imports ---

    def test_creature_full_exec(self):
        """Template should exec() successfully with engine modules available."""
        source = generate_template(_creature_spec())
        ns: dict = {}
        exec(source, ns)
        assert "StrixhavenProdigy" in ns

    def test_instant_full_exec(self):
        source = generate_template(_instant_spec())
        ns: dict = {}
        exec(source, ns)
        assert "LightningBolt" in ns

    def test_planeswalker_full_exec(self):
        source = generate_template(_planeswalker_spec())
        ns: dict = {}
        exec(source, ns)
        assert "JaceBeleren" in ns
