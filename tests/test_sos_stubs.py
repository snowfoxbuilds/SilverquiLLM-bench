"""Tests for SOS stub card class generation and registration (TODO item 6).

Validates:
- register_sos_stubs() registers exactly 346 cards
- All cards from sos.json can be instantiated
- Stubs derive correct attributes from Scryfall data
- Importing stubs does NOT auto-load default_registry
- Generator script produces deterministic output
- SOS conftest resolves stubs for numeric, soa_, and spg_ directories
"""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOS_JSON = PROJECT_ROOT / "benchmarks" / "sos" / "data" / "sos.json"


def _build_cn_lookup(registry):
    """Mirror the conftest's cn_to_entry logic for testing collector-key isolation.

    Only SOS base cards get plain numeric keys; SOA/SPG use set-prefixed keys.
    """
    cn_to_entry: dict[str, tuple[type, str]] = {}
    for card_name in registry.list_all():
        impl_class, meta = registry.get(card_name)
        if meta.collector_number:
            cn = meta.collector_number
            set_code = (meta.set_code or "").lower()
            if set_code == "sos" or not set_code:
                cn_to_entry[cn] = (impl_class, card_name)
            if set_code and set_code != "sos":
                prefixed = f"{set_code}_{cn}"
                cn_to_entry[prefixed] = (impl_class, card_name)
    return cn_to_entry, {}



@pytest.fixture
def sos_cards():
    """Load all 346 cards from sos.json."""
    with open(SOS_JSON) as f:
        return json.load(f)


@pytest.fixture
def fresh_registry():
    """Create a fresh CardRegistry with SOS stubs registered."""
    from benchmarks.sos.workspace.cards.registry import CardRegistry
    from benchmarks.sos.workspace.cards.stubs.sos_stubs import register_sos_stubs

    registry = CardRegistry()
    register_sos_stubs(registry)
    return registry


class TestRegisterSosStubs:
    """Tests for register_sos_stubs() function."""

    def test_registers_exactly_346_cards(self, fresh_registry):
        """register_sos_stubs populates the registry with exactly 346 cards."""
        assert len(fresh_registry) == 346

    def test_every_sos_json_card_is_registered(self, fresh_registry, sos_cards):
        """Every card name in sos.json must be in the registry."""
        for card in sos_cards:
            name = card["name"]
            assert name in fresh_registry, f"Card {name!r} not registered"

    def test_all_346_cards_instantiable(self, fresh_registry, sos_cards):
        """Every registered card can be instantiated via create_instance."""
        for card in sos_cards:
            name = card["name"]
            instance = fresh_registry.create_instance(name)
            assert instance is not None
            assert instance.name == name

    def test_no_extra_cards_beyond_sos_json(self, fresh_registry, sos_cards):
        """Registry should contain only the 346 SOS cards, nothing else."""
        expected_names = {card["name"] for card in sos_cards}
        registered_names = set(fresh_registry.list_all())
        assert registered_names == expected_names

    def test_register_is_idempotent(self):
        """Calling register_sos_stubs twice doesn't break the registry."""
        from benchmarks.sos.workspace.cards.registry import CardRegistry
        from benchmarks.sos.workspace.cards.stubs.sos_stubs import register_sos_stubs

        registry = CardRegistry()
        register_sos_stubs(registry)
        register_sos_stubs(registry)
        # Should still have 346 (last registration wins or is fine)
        assert len(registry) == 346


class TestStubAttributes:
    """Tests that stub classes derive correct attributes from Scryfall data."""

    def test_creature_has_power_toughness(self, fresh_registry):
        """Creature stubs must have base_power and base_toughness set."""
        # The Dawning Archaic: 7/7 from sos.json
        instance = fresh_registry.create_instance("The Dawning Archaic")
        assert instance.base_power == 7
        assert instance.base_toughness == 7

    def test_creature_mana_cost(self, fresh_registry):
        """Creature stubs must have mana_cost parsed from cost string."""
        instance = fresh_registry.create_instance("The Dawning Archaic")
        # Mana cost is {10} — generic 10
        assert instance.mana_cost is not None
        assert instance.mana_cost.cmc == 10

    def test_instant_has_no_power_toughness(self, fresh_registry):
        """Non-creature stubs should not have power/toughness."""
        instance = fresh_registry.create_instance("Ajani's Response")
        assert not hasattr(instance, "base_power") or instance.base_power is None or instance.base_power == 0

    def test_card_types_set_correctly(self, fresh_registry):
        """Card types must be derived from the type line."""
        from benchmarks.sos.workspace.engine.types import CardType

        instance = fresh_registry.create_instance("The Dawning Archaic")
        assert CardType.CREATURE in instance.card_types

    def test_subtypes_from_type_line(self, fresh_registry):
        """Subtypes must be parsed from the type line."""
        instance = fresh_registry.create_instance("The Dawning Archaic")
        # Type line: "Legendary Creature — Avatar"
        assert "Avatar" in instance.subtypes

    def test_split_card_subtypes_exclude_separator_and_second_face(self, fresh_registry):
        """Split/adventure cards must not have '//' or second-face types in subtypes."""
        # Elite Interceptor // Rejoinder: type_line = "Creature — Human Wizard // Sorcery"
        instance = fresh_registry.create_instance("Elite Interceptor // Rejoinder")
        assert "//" not in instance.subtypes, "'//' must not appear in subtypes"
        assert "Sorcery" not in instance.subtypes, "Second-face card type must not be in subtypes"
        # Should only have the front-face subtypes
        assert "Human" in instance.subtypes
        assert "Wizard" in instance.subtypes

    def test_adventure_card_subtypes_exclude_second_face_types(self, fresh_registry, sos_cards):
        """Adventure/split cards with creature // instant must exclude Instant from subtypes."""
        # Emeritus of Truce // Swords to Plowshares: "Creature — Cat Cleric // Instant"
        instance = fresh_registry.create_instance("Emeritus of Truce // Swords to Plowshares")
        assert "Instant" not in instance.subtypes
        assert "//" not in instance.subtypes
        assert "Cat" in instance.subtypes
        assert "Cleric" in instance.subtypes

    def test_metadata_set_code_preserved(self, fresh_registry):
        """Metadata retains set_code for each card."""
        _impl_class, meta = fresh_registry.get("The Dawning Archaic")
        assert meta.set_code == "sos"

    def test_metadata_collector_number_preserved(self, fresh_registry):
        """Metadata retains collector_number for each card."""
        _impl_class, meta = fresh_registry.get("The Dawning Archaic")
        assert meta.collector_number == "1"

    def test_soa_card_attributes(self, fresh_registry, sos_cards):
        """SOA cards must be registered with set_code='soa'."""
        soa_cards = [c for c in sos_cards if c.get("set") == "soa"]
        assert len(soa_cards) == 65
        for card in soa_cards[:3]:  # spot-check first three
            _impl_class, meta = fresh_registry.get(card["name"])
            assert meta.set_code == "soa"

    def test_spg_card_attributes(self, fresh_registry, sos_cards):
        """SPG cards must be registered with set_code='spg'."""
        spg_cards = [c for c in sos_cards if c.get("set") == "spg"]
        assert len(spg_cards) == 10
        for card in spg_cards:
            _impl_class, meta = fresh_registry.get(card["name"])
            assert meta.set_code == "spg"

    def test_colors_from_scryfall(self, fresh_registry, sos_cards):
        """Cards with colors in sos.json must have colors in metadata."""
        # Find a card with colors
        colored_card = next(c for c in sos_cards if c.get("colors"))
        _impl_class, meta = fresh_registry.get(colored_card["name"])
        assert meta.colors == colored_card["colors"]

    def test_instance_exposes_colors_attribute(self, fresh_registry):
        """Instantiated colored stubs must have self.colors set from Scryfall data."""
        # Ajani's Response is a white instant
        instance = fresh_registry.create_instance("Ajani's Response")
        assert hasattr(instance, "colors"), "Instance must have a 'colors' attribute"
        assert instance.colors == ["W"]

    def test_multicolor_instance_colors(self, fresh_registry, sos_cards):
        """Multi-color cards must expose all their colors on the instance."""
        multi = next(c for c in sos_cards if len(c.get("colors", [])) > 1)
        instance = fresh_registry.create_instance(multi["name"])
        assert instance.colors == multi["colors"]

    def test_colorless_instance_has_no_colors(self, fresh_registry):
        """Colorless cards should have empty colors or not set colors."""
        # The Dawning Archaic is colorless
        instance = fresh_registry.create_instance("The Dawning Archaic")
        colors = getattr(instance, "colors", [])
        assert colors == [] or colors is None

    # --- Hybrid mana cost tests (reviewer fix) ---

    def test_hybrid_mana_abstract_paintmage(self, fresh_registry):
        """Abstract Paintmage ({U}{U/R}{R}) must have hybrid mana representation with CMC 3."""
        instance = fresh_registry.create_instance("Abstract Paintmage")
        mc = instance.mana_cost
        assert mc is not None, "Mana cost must not be None"
        assert mc.cmc == 3, f"CMC should be 3, got {mc.cmc}"
        # Must have at least one hybrid symbol
        assert len(mc.hybrid) >= 1, "Must have hybrid mana symbols for U/R"

    def test_hybrid_mana_stirring_honormancer(self, fresh_registry):
        """Stirring Honormancer ({2}{W}{W/B}{B}) must have hybrid mana with CMC 5."""
        instance = fresh_registry.create_instance("Stirring Honormancer")
        mc = instance.mana_cost
        assert mc is not None, "Mana cost must not be None"
        assert mc.cmc == 5, f"CMC should be 5, got {mc.cmc}"
        assert len(mc.hybrid) >= 1, "Must have hybrid mana symbols for W/B"

    def test_hybrid_mana_essenceknit_scholar(self, fresh_registry):
        """Essenceknit Scholar ({B}{B/G}{G}) must have hybrid mana with CMC 3."""
        instance = fresh_registry.create_instance("Essenceknit Scholar")
        mc = instance.mana_cost
        assert mc is not None
        assert mc.cmc == 3
        assert len(mc.hybrid) >= 1, "Must have hybrid mana symbols for B/G"

    def test_unsupported_hybrid_does_not_zero_cmc(self, fresh_registry):
        """Cards with unsupported special mana symbols (e.g. {2/R}) must not collapse to CMC 0.

        Magmablood Archaic has {2/R}{2/R}{2/R} — even if {2/R} can't be
        fully represented, the card's CMC must not be 0.
        """
        instance = fresh_registry.create_instance("Magmablood Archaic")
        mc = instance.mana_cost
        assert mc is not None, "Mana cost must not be None"
        assert mc.cmc > 0, f"CMC must not be 0 for Magmablood Archaic, got {mc.cmc}"

    # --- Planeswalker loyalty tests (reviewer fix) ---

    def test_planeswalker_ral_zarek_loyalty(self, fresh_registry):
        """Ral Zarek, Guest Lecturer must expose starting_loyalty=3."""
        instance = fresh_registry.create_instance("Ral Zarek, Guest Lecturer")
        assert hasattr(instance, "starting_loyalty"), "Planeswalker must have starting_loyalty"
        assert instance.starting_loyalty == 3
        assert instance.loyalty == 3

    def test_planeswalker_professor_dellian_loyalty(self, fresh_registry):
        """Professor Dellian Fel must expose starting_loyalty=5."""
        instance = fresh_registry.create_instance("Professor Dellian Fel")
        assert hasattr(instance, "starting_loyalty"), "Planeswalker must have starting_loyalty"
        assert instance.starting_loyalty == 5
        assert instance.loyalty == 5

    def test_planeswalker_is_planeswalker_type(self, fresh_registry):
        """Planeswalker stubs must have PLANESWALKER in card_types."""
        from benchmarks.sos.workspace.engine.types import CardType

        instance = fresh_registry.create_instance("Ral Zarek, Guest Lecturer")
        assert CardType.PLANESWALKER in instance.card_types

    # --- Vehicle / noncreature P/T tests (reviewer fix) ---

    def test_vehicle_has_power_toughness(self, fresh_registry):
        """Strixhaven Skycoach (Vehicle) must expose printed P/T despite being noncreature Artifact."""
        instance = fresh_registry.create_instance("Strixhaven Skycoach")
        assert instance.base_power == 3, f"Vehicle power should be 3, got {instance.base_power}"
        assert instance.base_toughness == 2, f"Vehicle toughness should be 2, got {instance.base_toughness}"

    def test_vehicle_is_artifact_not_creature(self, fresh_registry):
        """Strixhaven Skycoach should be an Artifact, not inherently a Creature."""
        from benchmarks.sos.workspace.engine.types import CardType

        instance = fresh_registry.create_instance("Strixhaven Skycoach")
        assert CardType.ARTIFACT in instance.card_types
        assert "Vehicle" in instance.subtypes


class TestNoAutoLoad:
    """Tests that importing sos_stubs does NOT affect default_registry."""

    def test_import_does_not_populate_default_registry(self):
        """Importing cards.stubs.sos_stubs must not auto-register in default_registry."""
        from benchmarks.sos.workspace.cards.registry import default_registry

        # Record current state
        before_count = len(default_registry)

        # Re-import the stubs module (force reload to be thorough)
        import benchmarks.sos.workspace.cards.stubs.sos_stubs
        importlib.reload(benchmarks.sos.workspace.cards.stubs.sos_stubs)

        after_count = len(default_registry)
        assert after_count == before_count, (
            f"Importing sos_stubs changed default_registry size from "
            f"{before_count} to {after_count}"
        )

    def test_default_registry_does_not_contain_sos_cards(self):
        """default_registry should not have SOS stub cards by default."""
        from benchmarks.sos.workspace.cards.registry import default_registry

        # The Dawning Archaic is an SOS card that shouldn't be in default
        assert "The Dawning Archaic" not in default_registry


class TestGeneratorScript:
    """Tests for the generator script itself."""

    def test_generator_script_exists(self):
        """scripts/generate_audited_stubs.py must exist."""
        script_path = PROJECT_ROOT / "scripts" / "generate_audited_stubs.py"
        assert script_path.exists()

    def test_generated_output_exists(self):
        """cards/stubs/sos_stubs.py must exist."""
        output_path = PROJECT_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "stubs" / "sos_stubs.py"
        assert output_path.exists()

    def test_stubs_module_importable(self):
        """cards.stubs.sos_stubs must be importable."""
        mod = importlib.import_module("benchmarks.sos.workspace.cards.stubs.sos_stubs")
        assert hasattr(mod, "register_sos_stubs")

    def test_register_function_callable(self):
        """register_sos_stubs must be callable."""
        from benchmarks.sos.workspace.cards.stubs.sos_stubs import register_sos_stubs
        assert callable(register_sos_stubs)

    def test_generator_deterministic(self):
        """Running the generator twice should produce identical output."""
        import subprocess

        script_path = PROJECT_ROOT / "scripts" / "generate_audited_stubs.py"
        output_path = PROJECT_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "stubs" / "sos_stubs.py"

        # Read current output
        original_content = output_path.read_text()

        # Run generator
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Generator failed: {result.stderr}"

        # Compare
        new_content = output_path.read_text()
        assert new_content == original_content, "Generator output is not deterministic"


class TestSosConftestIntegration:
    """Tests that the SOS audited conftest correctly resolves stubs."""

    def test_conftest_loads_stubs_successfully(self):
        """SOS conftest can load and register stubs without error."""
        # Simulate what the conftest does
        from benchmarks.sos.workspace.cards.stubs.sos_stubs import register_sos_stubs
        from benchmarks.sos.workspace.cards.registry import CardRegistry

        registry = CardRegistry()
        register_sos_stubs(registry)
        assert len(registry) == 346

    def test_numeric_directory_resolves_sos_card(self, fresh_registry):
        """Plain numeric collector dir (e.g. '1') maps to SOS base card."""
        _impl_class, meta = fresh_registry.get("The Dawning Archaic")
        assert meta.collector_number == "1"
        assert meta.set_code == "sos"

    def test_plain_numeric_keys_cannot_be_overwritten_by_soa(self):
        """SOA cards with colliding collector numbers must NOT overwrite plain numeric keys.

        Example: SOS cn 1 = The Dawning Archaic, SOA cn 1 = Akroma's Will.
        The conftest registry lookup for plain '1' must always return the SOS card.
        """
        from benchmarks.sos.workspace.cards.stubs.sos_stubs import register_sos_stubs
        from benchmarks.sos.workspace.cards.registry import CardRegistry

        registry = CardRegistry()
        register_sos_stubs(registry)

        cn_to_entry, _ = _build_cn_lookup(registry)

        # Plain '1' must map to SOS card, not SOA card
        assert "1" in cn_to_entry
        impl_class, card_name = cn_to_entry["1"]
        assert card_name == "The Dawning Archaic", (
            f"Plain numeric key '1' maps to {card_name!r}, expected 'The Dawning Archaic'"
        )
        # SOA card with same cn should only be reachable via "soa_1"
        assert "soa_1" in cn_to_entry
        soa_impl, soa_name = cn_to_entry["soa_1"]
        assert soa_name == "Akroma's Will"

    def test_plain_numeric_keys_not_overwritten_by_spg(self):
        """SPG cards with colliding collector numbers must NOT overwrite plain numeric keys.

        SPG cn 149-158 don't collide with SOS cn 1-271 in practice, but
        the mechanism must still ensure SPG uses only prefixed keys.
        """
        from benchmarks.sos.workspace.cards.stubs.sos_stubs import register_sos_stubs
        from benchmarks.sos.workspace.cards.registry import CardRegistry

        registry = CardRegistry()
        register_sos_stubs(registry)

        cn_to_entry, _ = _build_cn_lookup(registry)

        # SPG cards should only appear under prefixed keys
        for key, (impl_class, card_name) in cn_to_entry.items():
            if key.startswith("spg_"):
                continue
            # If it's a plain numeric key, it must be SOS (not SPG)
            if key.isdigit():
                _, meta = registry.get(card_name)
                assert meta.set_code == "sos" or not meta.set_code, (
                    f"Plain numeric key '{key}' maps to non-SOS card "
                    f"'{card_name}' (set={meta.set_code})"
                )

    def test_soa_prefixed_directory_resolves(self, fresh_registry, sos_cards):
        """Set-prefixed dir 'soa_1' maps to first SOA card."""
        soa_card = next(c for c in sos_cards if c.get("set") == "soa" and c.get("collector_number") == "1")
        _impl_class, meta = fresh_registry.get(soa_card["name"])
        assert meta.set_code == "soa"
        assert meta.collector_number == "1"

    def test_spg_prefixed_directory_resolves(self, fresh_registry, sos_cards):
        """Set-prefixed dir 'spg_149' maps to first SPG card."""
        spg_card = next(c for c in sos_cards if c.get("set") == "spg" and c.get("collector_number") == "149")
        _impl_class, meta = fresh_registry.get(spg_card["name"])
        assert meta.set_code == "spg"
        assert meta.collector_number == "149"

    def test_stubs_absent_simulation_with_monkeypatch(self, monkeypatch):
        """When stubs module is not importable, conftest produces clear error."""
        from tests.audited.sos.conftest import _load_sos_stubs_and_build_registry

        def fail_import_module(name):
            if name == "benchmarks.sos.workspace.cards.stubs.sos_stubs":
                raise ImportError("Simulated: stubs not available")
            return importlib.import_module(name)

        # Remove cached module and patch importlib.import_module
        monkeypatch.delitem(sys.modules, "benchmarks.sos.workspace.cards.stubs.sos_stubs", raising=False)
        monkeypatch.setattr(
            "tests.audited.sos.conftest.importlib.import_module",
            fail_import_module,
        )
        with pytest.raises(ImportError, match="not available"):
            _load_sos_stubs_and_build_registry()


class TestStubClassHierarchy:
    """Tests that stubs use correct engine base classes."""

    def test_creature_is_creature_subclass(self, fresh_registry):
        """Creature stubs must inherit from benchmarks.sos.workspace.engine.card.Creature."""
        from benchmarks.sos.workspace.engine.card import Creature

        instance = fresh_registry.create_instance("The Dawning Archaic")
        assert isinstance(instance, Creature)

    def test_instant_is_instant_subclass(self, fresh_registry):
        """Instant stubs must inherit from benchmarks.sos.workspace.engine.card.Instant."""
        from benchmarks.sos.workspace.engine.card import Instant

        instance = fresh_registry.create_instance("Ajani's Response")
        assert isinstance(instance, Instant)

    def test_land_is_land_subclass(self, fresh_registry, sos_cards):
        """Land stubs must inherit from benchmarks.sos.workspace.engine.card.Land."""
        from benchmarks.sos.workspace.engine.card import Land

        land_card = next(c for c in sos_cards if "Land" in c.get("type_line", "") and "Creature" not in c.get("type_line", ""))
        instance = fresh_registry.create_instance(land_card["name"])
        assert isinstance(instance, Land)
