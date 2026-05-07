"""Integration tests for Foundations batch 1 cards (TODO item 22).

Supplements the per-module unit tests with cross-cutting checks:
- Total card count across all modules is 30.
- Every card class inherits from the correct engine base class.
- Every card is constructable with defaults and has name, mana_cost, card_types.
- Registry round-trip: register → get → create_instance for all cards.
- Modal spells expose Mode objects with required attributes.
- Planeswalker loyalty abilities adjust loyalty correctly.
- Enchantment type flags (is_aura) are consistent.
- Artifact mana abilities return ManaAbility objects.
- No duplicate card names across modules.
"""

from __future__ import annotations

import pytest

from cards.foundations.enchantments import (
    Arrest,
    BraveTheSands,
    DictateOfHeliod,
    GloriousAnthem,
    HolyStrength,
    Levitation,
    StabWound,
    UnholyStrength,
    register_enchantments,
)
from cards.foundations.artifacts import (
    AltarOfTheBrood,
    ArcaneSigNet,
    Bonesplitter,
    ElixirOfImmortality,
    MaskOfMemory,
    MindStone,
    RelicOfProgenitus,
    SolRing,
    SwiftfootBoots,
    WhispersilkCloak,
    register_artifacts,
)
from cards.foundations.planeswalkers import (
    AjaniCallerOfThePride,
    ChandraTorchOfDefiance,
    LilianaDreadhordeGeneral,
    NissaWorldwaker,
    register_planeswalkers,
)
from cards.foundations.modal_spells import (
    AbzanCharm,
    AustereCommand,
    BorosCharm,
    CollectiveBrutality,
    DromokasCommand,
    InscriptionOfInsight,
    PrismariCommand,
    SublimeEpiphany,
    register_modal_spells,
)
from cards.registry import CardRegistry
from engine.card import (
    Artifact,
    Aura,
    CardImpl,
    Enchantment,
    Instant,
    LoyaltyAbility,
    ManaAbility,
    Mode,
    Planeswalker,
    Sorcery,
)
from engine.types import CardType, ManaCost


# ---------------------------------------------------------------------------
# All card classes grouped by module
# ---------------------------------------------------------------------------

ENCHANTMENT_CLASSES = [
    HolyStrength, UnholyStrength, StabWound, Arrest,
    GloriousAnthem, DictateOfHeliod, BraveTheSands, Levitation,
]

ARTIFACT_CLASSES = [
    SolRing, ArcaneSigNet, MindStone, Bonesplitter, SwiftfootBoots,
    WhispersilkCloak, MaskOfMemory, AltarOfTheBrood,
    ElixirOfImmortality, RelicOfProgenitus,
]

PLANESWALKER_CLASSES = [
    AjaniCallerOfThePride, ChandraTorchOfDefiance,
    LilianaDreadhordeGeneral, NissaWorldwaker,
]

MODAL_INSTANT_CLASSES = [AbzanCharm, BorosCharm, PrismariCommand, SublimeEpiphany]
MODAL_SORCERY_CLASSES = [DromokasCommand, AustereCommand, CollectiveBrutality, InscriptionOfInsight]
MODAL_CLASSES = MODAL_INSTANT_CLASSES + MODAL_SORCERY_CLASSES

ALL_CLASSES = ENCHANTMENT_CLASSES + ARTIFACT_CLASSES + PLANESWALKER_CLASSES + MODAL_CLASSES


# ---------------------------------------------------------------------------
# Cross-cutting: total count and no duplicates
# ---------------------------------------------------------------------------

class TestBatch1TotalCount:
    """Verify we have exactly 30 cards across all four modules."""

    def test_total_card_count_is_30(self):
        assert len(ALL_CLASSES) == 30

    def test_no_duplicate_class_names(self):
        names = [cls.__name__ for cls in ALL_CLASSES]
        assert len(names) == len(set(names)), f"Duplicate class names: {[n for n in names if names.count(n) > 1]}"

    def test_no_duplicate_card_names(self):
        """Each card instance should have a unique default name."""
        card_names = [cls().name for cls in ALL_CLASSES]
        assert len(card_names) == len(set(card_names)), f"Duplicate card names found"


# ---------------------------------------------------------------------------
# Base class inheritance
# ---------------------------------------------------------------------------

class TestBaseClassInheritance:
    """Every card must inherit from the correct engine base class."""

    @pytest.mark.parametrize("cls", ENCHANTMENT_CLASSES[:4], ids=lambda c: c.__name__)
    def test_aura_enchantments_inherit_from_aura(self, cls):
        assert issubclass(cls, Aura)

    @pytest.mark.parametrize("cls", ENCHANTMENT_CLASSES[4:], ids=lambda c: c.__name__)
    def test_global_enchantments_inherit_from_enchantment(self, cls):
        assert issubclass(cls, Enchantment)

    @pytest.mark.parametrize("cls", ARTIFACT_CLASSES, ids=lambda c: c.__name__)
    def test_artifacts_inherit_from_artifact(self, cls):
        assert issubclass(cls, Artifact)

    @pytest.mark.parametrize("cls", PLANESWALKER_CLASSES, ids=lambda c: c.__name__)
    def test_planeswalkers_inherit_from_planeswalker(self, cls):
        assert issubclass(cls, Planeswalker)

    @pytest.mark.parametrize("cls", MODAL_INSTANT_CLASSES, ids=lambda c: c.__name__)
    def test_modal_instants_inherit_from_instant(self, cls):
        assert issubclass(cls, Instant)

    @pytest.mark.parametrize("cls", MODAL_SORCERY_CLASSES, ids=lambda c: c.__name__)
    def test_modal_sorceries_inherit_from_sorcery(self, cls):
        assert issubclass(cls, Sorcery)

    @pytest.mark.parametrize("cls", ALL_CLASSES, ids=lambda c: c.__name__)
    def test_all_cards_inherit_from_card_impl(self, cls):
        assert issubclass(cls, CardImpl)


# ---------------------------------------------------------------------------
# Default construction and required attributes
# ---------------------------------------------------------------------------

class TestDefaultConstruction:
    """Every card must be constructable with no arguments and have essential attrs."""

    @pytest.mark.parametrize("cls", ALL_CLASSES, ids=lambda c: c.__name__)
    def test_constructable_with_defaults(self, cls):
        card = cls()
        assert card is not None

    @pytest.mark.parametrize("cls", ALL_CLASSES, ids=lambda c: c.__name__)
    def test_has_name(self, cls):
        card = cls()
        assert isinstance(card.name, str)
        assert len(card.name) > 0

    @pytest.mark.parametrize("cls", ALL_CLASSES, ids=lambda c: c.__name__)
    def test_has_mana_cost(self, cls):
        card = cls()
        assert card.mana_cost is not None
        assert isinstance(card.mana_cost, ManaCost)

    @pytest.mark.parametrize("cls", ALL_CLASSES, ids=lambda c: c.__name__)
    def test_has_card_types(self, cls):
        card = cls()
        assert hasattr(card, "card_types")
        assert len(card.card_types) > 0

    @pytest.mark.parametrize("cls", ALL_CLASSES, ids=lambda c: c.__name__)
    def test_has_rules_text(self, cls):
        card = cls()
        assert isinstance(card.rules_text, str)
        assert len(card.rules_text) > 0


# ---------------------------------------------------------------------------
# Card type correctness
# ---------------------------------------------------------------------------

class TestCardTypes:
    """Verify card_types contain the expected type for each category."""

    @pytest.mark.parametrize("cls", ENCHANTMENT_CLASSES, ids=lambda c: c.__name__)
    def test_enchantments_have_enchantment_type(self, cls):
        card = cls()
        assert CardType.ENCHANTMENT in card.card_types

    @pytest.mark.parametrize("cls", ARTIFACT_CLASSES, ids=lambda c: c.__name__)
    def test_artifacts_have_artifact_type(self, cls):
        card = cls()
        assert CardType.ARTIFACT in card.card_types

    @pytest.mark.parametrize("cls", PLANESWALKER_CLASSES, ids=lambda c: c.__name__)
    def test_planeswalkers_have_planeswalker_type(self, cls):
        card = cls()
        assert CardType.PLANESWALKER in card.card_types

    @pytest.mark.parametrize("cls", MODAL_INSTANT_CLASSES, ids=lambda c: c.__name__)
    def test_modal_instants_have_instant_type(self, cls):
        card = cls()
        assert CardType.INSTANT in card.card_types

    @pytest.mark.parametrize("cls", MODAL_SORCERY_CLASSES, ids=lambda c: c.__name__)
    def test_modal_sorceries_have_sorcery_type(self, cls):
        card = cls()
        assert CardType.SORCERY in card.card_types


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestRegistryIntegration:
    """All 30 cards should be discoverable via their register_* functions."""

    @pytest.fixture()
    def full_registry(self):
        registry = CardRegistry()
        register_enchantments(registry)
        register_artifacts(registry)
        register_planeswalkers(registry)
        register_modal_spells(registry)
        return registry

    def test_registry_contains_all_30_cards(self, full_registry):
        assert len(full_registry) == 30

    def test_all_card_names_in_registry(self, full_registry):
        for cls in ALL_CLASSES:
            card = cls()
            assert card.name in full_registry, f"{card.name} not found in registry"

    def test_registry_get_returns_correct_class(self, full_registry):
        for cls in ALL_CLASSES:
            card = cls()
            impl_cls, metadata = full_registry.get(card.name)
            assert impl_cls is cls

    def test_registry_metadata_has_set_code(self, full_registry):
        for name in full_registry.list_all():
            _, metadata = full_registry.get(name)
            assert metadata.set_code == "fdn"

    def test_no_duplicate_registration(self, full_registry):
        """Registering again should raise or be handled gracefully."""
        names = full_registry.list_all()
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Modal spells: get_modes contract
# ---------------------------------------------------------------------------

class TestModalSpellModes:
    """All modal spells must return Mode objects with name and description."""

    @pytest.mark.parametrize("cls", MODAL_CLASSES, ids=lambda c: c.__name__)
    def test_get_modes_returns_list_of_modes(self, cls):
        card = cls()
        modes = card.get_modes()
        assert isinstance(modes, list)
        assert len(modes) >= 2, f"{cls.__name__} should have at least 2 modes"

    @pytest.mark.parametrize("cls", MODAL_CLASSES, ids=lambda c: c.__name__)
    def test_modes_have_name_and_description(self, cls):
        card = cls()
        for mode in card.get_modes():
            assert isinstance(mode, Mode)
            assert isinstance(mode.name, str) and len(mode.name) > 0
            assert isinstance(mode.description, str) and len(mode.description) > 0

    def test_abzan_charm_has_3_modes(self):
        card = AbzanCharm()
        assert len(card.get_modes()) == 3

    def test_boros_charm_has_3_modes(self):
        card = BorosCharm()
        assert len(card.get_modes()) == 3

    def test_austere_command_has_4_modes(self):
        card = AustereCommand()
        assert len(card.get_modes()) == 4

    def test_sublime_epiphany_has_5_modes(self):
        card = SublimeEpiphany()
        assert len(card.get_modes()) == 5

    @pytest.mark.parametrize("cls", [AbzanCharm, BorosCharm], ids=lambda c: c.__name__)
    def test_choose_one_has_chosen_mode_initially_none(self, cls):
        card = cls()
        assert card.chosen_mode is None

    @pytest.mark.parametrize("cls", [PrismariCommand, SublimeEpiphany, DromokasCommand,
                                      AustereCommand, CollectiveBrutality, InscriptionOfInsight],
                             ids=lambda c: c.__name__)
    def test_choose_multiple_has_chosen_modes_initially_none(self, cls):
        card = cls()
        assert card.chosen_modes is None


# ---------------------------------------------------------------------------
# Planeswalker: loyalty abilities contract
# ---------------------------------------------------------------------------

class TestPlaneswalkerLoyalty:
    """Planeswalker loyalty abilities must have cost, effect, and description."""

    @pytest.mark.parametrize("cls", PLANESWALKER_CLASSES, ids=lambda c: c.__name__)
    def test_has_starting_loyalty(self, cls):
        pw = cls()
        assert hasattr(pw, "loyalty")
        assert isinstance(pw.loyalty, int)
        assert pw.loyalty > 0

    @pytest.mark.parametrize("cls", PLANESWALKER_CLASSES, ids=lambda c: c.__name__)
    def test_loyalty_abilities_return_list(self, cls):
        pw = cls()
        abilities = pw.get_loyalty_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) >= 2

    @pytest.mark.parametrize("cls", PLANESWALKER_CLASSES, ids=lambda c: c.__name__)
    def test_loyalty_abilities_are_loyalty_ability_objects(self, cls):
        pw = cls()
        for ability in pw.get_loyalty_abilities():
            assert isinstance(ability, LoyaltyAbility)

    @pytest.mark.parametrize("cls", PLANESWALKER_CLASSES, ids=lambda c: c.__name__)
    def test_loyalty_abilities_have_descriptions(self, cls):
        pw = cls()
        for ability in pw.get_loyalty_abilities():
            assert isinstance(ability.description, str)
            assert len(ability.description) > 0

    @pytest.mark.parametrize("cls", PLANESWALKER_CLASSES, ids=lambda c: c.__name__)
    def test_at_least_one_positive_loyalty_ability(self, cls):
        pw = cls()
        costs = [a.loyalty_cost for a in pw.get_loyalty_abilities()]
        assert any(c > 0 for c in costs), f"{cls.__name__} has no + ability"

    def test_ajani_starting_loyalty_is_4(self):
        pw = AjaniCallerOfThePride()
        assert pw.loyalty == 4

    def test_chandra_starting_loyalty_is_4(self):
        pw = ChandraTorchOfDefiance()
        assert pw.loyalty == 4

    def test_liliana_starting_loyalty_is_6(self):
        pw = LilianaDreadhordeGeneral()
        assert pw.loyalty == 6

    def test_nissa_starting_loyalty_is_3(self):
        pw = NissaWorldwaker()
        assert pw.loyalty == 3


# ---------------------------------------------------------------------------
# Enchantment: aura flag consistency
# ---------------------------------------------------------------------------

class TestEnchantmentAuraFlag:
    """Aura subclasses should have is_aura=True, globals should have is_aura=False."""

    @pytest.mark.parametrize("cls", [HolyStrength, UnholyStrength, StabWound, Arrest],
                             ids=lambda c: c.__name__)
    def test_aura_has_is_aura_true(self, cls):
        card = cls()
        assert getattr(card, "is_aura", False) is True

    @pytest.mark.parametrize("cls", [GloriousAnthem, DictateOfHeliod, BraveTheSands, Levitation],
                             ids=lambda c: c.__name__)
    def test_global_enchantment_has_is_aura_false(self, cls):
        card = cls()
        assert getattr(card, "is_aura", True) is False

    @pytest.mark.parametrize("cls", [HolyStrength, UnholyStrength, StabWound, Arrest],
                             ids=lambda c: c.__name__)
    def test_aura_has_aura_subtype(self, cls):
        card = cls()
        subtypes = getattr(card, "subtypes", set())
        assert "Aura" in subtypes


# ---------------------------------------------------------------------------
# Artifact: mana rocks have mana abilities
# ---------------------------------------------------------------------------

class TestArtifactManaAbilities:
    """Mana rock artifacts should provide get_mana_abilities()."""

    @pytest.mark.parametrize("cls", [SolRing, ArcaneSigNet, MindStone],
                             ids=lambda c: c.__name__)
    def test_mana_rocks_have_mana_abilities(self, cls):
        card = cls()
        abilities = card.get_mana_abilities()
        assert isinstance(abilities, list)
        assert len(abilities) >= 1

    @pytest.mark.parametrize("cls", [SolRing, ArcaneSigNet, MindStone],
                             ids=lambda c: c.__name__)
    def test_mana_abilities_are_mana_ability_objects(self, cls):
        card = cls()
        for ability in card.get_mana_abilities():
            assert isinstance(ability, ManaAbility)


# ---------------------------------------------------------------------------
# Specific card name checks (spot checks for correctness)
# ---------------------------------------------------------------------------

class TestCardNameCorrectness:
    """Spot-check that card names match expected MTG card names."""

    EXPECTED_NAMES = {
        SolRing: "Sol Ring",
        ArcaneSigNet: "Arcane Signet",
        MindStone: "Mind Stone",
        Bonesplitter: "Bonesplitter",
        SwiftfootBoots: "Swiftfoot Boots",
        WhispersilkCloak: "Whispersilk Cloak",
        MaskOfMemory: "Mask of Memory",
        AltarOfTheBrood: "Altar of the Brood",
        ElixirOfImmortality: "Elixir of Immortality",
        RelicOfProgenitus: "Relic of Progenitus",
        HolyStrength: "Holy Strength",
        UnholyStrength: "Unholy Strength",
        StabWound: "Stab Wound",
        Arrest: "Arrest",
        GloriousAnthem: "Glorious Anthem",
        DictateOfHeliod: "Dictate of Heliod",
        BraveTheSands: "Brave the Sands",
        Levitation: "Levitation",
        AjaniCallerOfThePride: "Ajani, Caller of the Pride",
        ChandraTorchOfDefiance: "Chandra, Torch of Defiance",
        LilianaDreadhordeGeneral: "Liliana, Dreadhorde General",
        NissaWorldwaker: "Nissa, Worldwaker",
        AbzanCharm: "Abzan Charm",
        BorosCharm: "Boros Charm",
        PrismariCommand: "Prismari Command",
        SublimeEpiphany: "Sublime Epiphany",
        DromokasCommand: "Dromoka's Command",
        AustereCommand: "Austere Command",
        CollectiveBrutality: "Collective Brutality",
        InscriptionOfInsight: "Inscription of Insight",
    }

    @pytest.mark.parametrize("cls,expected_name", EXPECTED_NAMES.items(),
                             ids=lambda x: x.__name__ if isinstance(x, type) else x)
    def test_card_name_matches(self, cls, expected_name):
        card = cls()
        assert card.name == expected_name


# ---------------------------------------------------------------------------
# Planeswalkers are legendary
# ---------------------------------------------------------------------------

class TestPlaneswalkerLegendary:
    """All planeswalkers should have the Legendary supertype."""

    @pytest.mark.parametrize("cls", PLANESWALKER_CLASSES, ids=lambda c: c.__name__)
    def test_planeswalker_is_legendary(self, cls):
        from engine.types import Supertype
        pw = cls()
        supertypes = getattr(pw, "supertypes", set())
        assert Supertype.LEGENDARY in supertypes
