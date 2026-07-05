"""Tests for cards.loader — registry population from card_impl modules."""

from __future__ import annotations

import pytest

from cards.loader import load_set_registry
from cards.registry import CardRegistry
from engine.card import CardImpl, Creature, Land


@pytest.fixture(scope="module")
def fdn_registry() -> CardRegistry:
    return load_set_registry("fdn")


class TestLoadSetRegistry:
    def test_loads_full_fdn_set(self, fdn_registry: CardRegistry) -> None:
        # 286 impl classes minus 2 known duplicate-name dirs
        # (Wardens of the Cycle, Bigfin Bouncer each appear twice).
        assert len(fdn_registry) >= 280

    def test_registers_plain_class_impls(self, fdn_registry: CardRegistry) -> None:
        impl_class, metadata = fdn_registry.get("Sire of Seven Deaths")
        assert issubclass(impl_class, Creature)
        assert metadata.collector_number == "1"

    def test_registers_factory_made_impls(self, fdn_registry: CardRegistry) -> None:
        # make_vanilla classes carry an engine.* __module__ but must register.
        impl_class, _ = fdn_registry.get("Quakestrider Ceratops")
        instance = impl_class()
        assert instance.name == "Quakestrider Ceratops"
        assert instance.power == 12

    def test_registers_lands(self, fdn_registry: CardRegistry) -> None:
        for name in ("Island", "Tranquil Cove", "Evolving Wilds"):
            impl_class, _ = fdn_registry.get(name)
            assert issubclass(impl_class, Land)

    def test_does_not_register_engine_bases(self, fdn_registry: CardRegistry) -> None:
        for base_name in ("Creature", "Land", "CardImpl", "Enchantment"):
            assert base_name not in fdn_registry

    def test_create_instance_sets_owner(self, fdn_registry: CardRegistry) -> None:
        card = fdn_registry.create_instance("Island", owner=None)
        assert isinstance(card, CardImpl)
        assert card.name == "Island"

    def test_metadata_comes_from_card_spec(self, fdn_registry: CardRegistry) -> None:
        _, metadata = fdn_registry.get("Evolving Wilds")
        assert "basic land" in metadata.oracle_text.lower()

    def test_unknown_set_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_set_registry("nonexistent_set")

    def test_populates_existing_registry(self) -> None:
        registry = CardRegistry()
        result = load_set_registry("fdn", registry=registry)
        assert result is registry
        assert len(registry) >= 280
