"""Tests for cards/registry.py — CardMetadata dataclass and CardRegistry.

Verifies:
- CardMetadata construction with all fields and defaults.
- CardRegistry.register and get round-trip.
- CardRegistry.create_instance creates correct card type with owner.
- CardRegistry.list_all returns sorted registered names.
- get() for unregistered name → KeyError.
- create_instance for unregistered name → KeyError.
- Register same name twice → overwrites silently.
- default_registry singleton exists and is a CardRegistry.
- __contains__ and __len__ dunder methods.
"""

from __future__ import annotations

import pytest

from cards.registry import CardMetadata, CardRegistry, default_registry
from engine.card import CardImpl, Creature, Instant
from engine.player import DeterministicPlayer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(name: str = "TestPlayer") -> DeterministicPlayer:
    return DeterministicPlayer(name=name, script=[])


# ---------------------------------------------------------------------------
# CardMetadata construction
# ---------------------------------------------------------------------------

class TestCardMetadata:
    """Verify CardMetadata dataclass construction."""

    def test_all_fields_explicit(self) -> None:
        """CardMetadata constructed with all fields stores every value."""
        meta = CardMetadata(
            name="Lightning Bolt",
            mana_cost_str="{R}",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            power=None,
            toughness=None,
            colors=["R"],
            keywords=[],
            rarity="common",
            set_code="fdn",
            collector_number="132",
        )
        assert meta.name == "Lightning Bolt"
        assert meta.mana_cost_str == "{R}"
        assert meta.type_line == "Instant"
        assert meta.oracle_text == "Lightning Bolt deals 3 damage to any target."
        assert meta.power is None
        assert meta.toughness is None
        assert meta.colors == ["R"]
        assert meta.keywords == []
        assert meta.rarity == "common"
        assert meta.set_code == "fdn"
        assert meta.collector_number == "132"

    def test_creature_with_power_toughness(self) -> None:
        """CardMetadata for a creature stores power and toughness as strings."""
        meta = CardMetadata(
            name="Grizzly Bears",
            mana_cost_str="{1}{G}",
            type_line="Creature — Bear",
            oracle_text="",
            power="2",
            toughness="2",
            colors=["G"],
            keywords=[],
            rarity="common",
            set_code="10e",
            collector_number="268",
        )
        assert meta.power == "2"
        assert meta.toughness == "2"

    def test_defaults(self) -> None:
        """CardMetadata with no arguments uses sensible defaults."""
        meta = CardMetadata()
        assert meta.name == ""
        assert meta.mana_cost_str == ""
        assert meta.type_line == ""
        assert meta.oracle_text == ""
        assert meta.power is None
        assert meta.toughness is None
        assert meta.colors == []
        assert meta.keywords == []
        assert meta.rarity == ""
        assert meta.set_code == ""
        assert meta.collector_number == ""

    def test_colors_list_is_independent(self) -> None:
        """Two CardMetadata instances don't share the same default list."""
        m1 = CardMetadata()
        m2 = CardMetadata()
        m1.colors.append("W")
        assert m2.colors == []

    def test_keywords_list_is_independent(self) -> None:
        """Two CardMetadata instances don't share the same default keywords list."""
        m1 = CardMetadata()
        m2 = CardMetadata()
        m1.keywords.append("Flying")
        assert m2.keywords == []


# ---------------------------------------------------------------------------
# CardRegistry — register and get
# ---------------------------------------------------------------------------

class TestCardRegistryRegisterGet:
    """Verify register/get round-trip."""

    def test_register_and_get_roundtrip(self) -> None:
        """Registering a card and getting it returns the same class and metadata."""
        reg = CardRegistry()
        meta = CardMetadata(name="Lightning Bolt", mana_cost_str="{R}")
        reg.register("Lightning Bolt", Instant, meta)
        impl_cls, got_meta = reg.get("Lightning Bolt")
        assert impl_cls is Instant
        assert got_meta is meta

    def test_register_without_metadata_auto_creates(self) -> None:
        """Registering without metadata creates a default CardMetadata with the card name."""
        reg = CardRegistry()
        reg.register("MyCard", CardImpl)
        _, meta = reg.get("MyCard")
        assert isinstance(meta, CardMetadata)
        assert meta.name == "MyCard"

    def test_get_unregistered_raises_key_error(self) -> None:
        """Getting an unregistered card name raises KeyError."""
        reg = CardRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.get("Nonexistent Card")

    def test_register_same_name_overwrites(self) -> None:
        """Registering the same name twice overwrites the previous entry."""
        reg = CardRegistry()
        meta1 = CardMetadata(name="Card", rarity="common")
        meta2 = CardMetadata(name="Card", rarity="rare")
        reg.register("Card", Instant, meta1)
        reg.register("Card", Creature, meta2)
        impl_cls, got_meta = reg.get("Card")
        assert impl_cls is Creature
        assert got_meta.rarity == "rare"

    def test_register_is_case_sensitive(self) -> None:
        """Card names are case-sensitive."""
        reg = CardRegistry()
        reg.register("Lightning Bolt", Instant)
        with pytest.raises(KeyError):
            reg.get("lightning bolt")


# ---------------------------------------------------------------------------
# CardRegistry — create_instance
# ---------------------------------------------------------------------------

class TestCardRegistryCreateInstance:
    """Verify create_instance factory method."""

    def test_create_instance_returns_correct_type(self) -> None:
        """create_instance returns an instance of the registered impl class."""
        reg = CardRegistry()
        reg.register("Bolt", Instant)
        card = reg.create_instance("Bolt")
        assert isinstance(card, Instant)

    def test_create_instance_sets_name(self) -> None:
        """create_instance sets the card's name to the registered name."""
        reg = CardRegistry()
        reg.register("Bolt", Instant)
        card = reg.create_instance("Bolt")
        assert card.name == "Bolt"

    def test_create_instance_sets_owner(self) -> None:
        """create_instance forwards the owner argument to the card."""
        reg = CardRegistry()
        reg.register("Bear", Creature)
        player = _make_player("Alice")
        card = reg.create_instance("Bear", owner=player)
        assert card.owner is player

    def test_create_instance_without_owner(self) -> None:
        """create_instance with no owner sets owner to None."""
        reg = CardRegistry()
        reg.register("Bear", Creature)
        card = reg.create_instance("Bear")
        assert card.owner is None

    def test_create_instance_unregistered_raises_key_error(self) -> None:
        """create_instance for an unregistered name raises KeyError."""
        reg = CardRegistry()
        with pytest.raises(KeyError):
            reg.create_instance("Missing Card")

    def test_create_instance_returns_new_instances(self) -> None:
        """Each call to create_instance returns a distinct object."""
        reg = CardRegistry()
        reg.register("Bear", Creature)
        c1 = reg.create_instance("Bear")
        c2 = reg.create_instance("Bear")
        assert c1 is not c2
        assert c1.object_id != c2.object_id


# ---------------------------------------------------------------------------
# CardRegistry — list_all
# ---------------------------------------------------------------------------

class TestCardRegistryListAll:
    """Verify list_all returns sorted registered names."""

    def test_list_all_empty(self) -> None:
        """list_all on an empty registry returns an empty list."""
        reg = CardRegistry()
        assert reg.list_all() == []

    def test_list_all_sorted(self) -> None:
        """list_all returns names in sorted order."""
        reg = CardRegistry()
        reg.register("Zephyr", Instant)
        reg.register("Bolt", Instant)
        reg.register("Mox", Instant)
        assert reg.list_all() == ["Bolt", "Mox", "Zephyr"]

    def test_list_all_after_overwrite(self) -> None:
        """list_all after overwriting a name has no duplicates."""
        reg = CardRegistry()
        reg.register("Bolt", Instant)
        reg.register("Bolt", Creature)
        assert reg.list_all() == ["Bolt"]


# ---------------------------------------------------------------------------
# CardRegistry — dunder methods
# ---------------------------------------------------------------------------

class TestCardRegistryDunders:
    """Verify __contains__ and __len__."""

    def test_contains_registered(self) -> None:
        """Registered name is in the registry."""
        reg = CardRegistry()
        reg.register("Bolt", Instant)
        assert "Bolt" in reg

    def test_contains_unregistered(self) -> None:
        """Unregistered name is not in the registry."""
        reg = CardRegistry()
        assert "Bolt" not in reg

    def test_len_empty(self) -> None:
        """Empty registry has length 0."""
        reg = CardRegistry()
        assert len(reg) == 0

    def test_len_after_registrations(self) -> None:
        """Length reflects number of unique registered cards."""
        reg = CardRegistry()
        reg.register("A", Instant)
        reg.register("B", Instant)
        assert len(reg) == 2


# ---------------------------------------------------------------------------
# default_registry singleton
# ---------------------------------------------------------------------------

class TestDefaultRegistry:
    """Verify the module-level default_registry."""

    def test_default_registry_is_card_registry(self) -> None:
        """default_registry is an instance of CardRegistry."""
        assert isinstance(default_registry, CardRegistry)

    def test_default_registry_is_module_level_singleton(self) -> None:
        """Importing default_registry twice returns the same object."""
        from cards.registry import default_registry as dr2
        assert default_registry is dr2
