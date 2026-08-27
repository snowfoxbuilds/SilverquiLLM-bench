"""Tests for cards.loader — registry population from card_impl modules."""

from __future__ import annotations

import pytest

from cards.loader import load_set_registry
from cards.registry import CardRegistry
from engine.card import CardImpl, Creature, Land


class _PreRegisteredTwin(Creature):
    """A prior, unrelated implementation already holding ``"Twin Slot"``.

    Used by the pre-populated-registry collision test: it lives in *this*
    module (not under ``cards/``), so the loader can only name it by
    recovering the class from the registry itself.
    """

    def __init__(self, **kw: object) -> None:
        kw.setdefault("name", "Twin Slot")
        super().__init__(**kw)


@pytest.fixture(scope="module")
def fdn_registry() -> CardRegistry:
    return load_set_registry("fdn")


class TestLoadSetRegistry:
    def test_loads_full_fdn_set(self, fdn_registry: CardRegistry) -> None:
        # All 286 impl classes register under distinct names, with zero
        # collisions: fdn_15/fdn_205 now hold Hare Apparent / Seismic Rupture
        # (real cards) rather than duplicate-name squatters, so nothing is
        # shadowed anymore.
        assert len(fdn_registry) == 286

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
        assert len(registry) == 286

    def test_populates_nonempty_noncolliding_registry(self) -> None:
        """A caller-supplied, non-empty registry whose names do not collide
        with the set is populated normally, keeping its pre-existing entry."""
        registry = CardRegistry()
        registry.register("_Sentinel Not In FDN", _PreRegisteredTwin)
        result = load_set_registry("fdn", registry=registry)
        assert result is registry
        # 286 FDN impls added on top of the one pre-existing entry.
        assert len(registry) == 287
        assert "_Sentinel Not In FDN" in registry
        assert "Sire of Seven Deaths" in registry


class TestDuplicateRegistration:
    """A card name must map to exactly one implementation; two dirs claiming
    the same printed name is a hard error naming both offenders."""

    def test_duplicate_card_name_raises(self) -> None:
        import importlib
        import shutil
        import sys
        from pathlib import Path

        import cards

        cards_root = Path(cards.__file__).resolve().parent
        set_name = "_dup_fixture_set"
        set_dir = cards_root / set_name
        if set_dir.exists():
            shutil.rmtree(set_dir)
        set_dir.mkdir()
        impl = (
            "from engine.card import Creature\n\n\n"
            "class {cls}(Creature):\n"
            "    def __init__(self, **kw):\n"
            "        kw.setdefault('name', 'Twin Slot')\n"
            "        super().__init__(**kw)\n"
        )
        try:
            (set_dir / "__init__.py").write_text("")
            for sub, cls in (("aaa_first", "TwinA"), ("bbb_second", "TwinB")):
                sub_dir = set_dir / sub
                sub_dir.mkdir()
                (sub_dir / "card_impl.py").write_text(impl.format(cls=cls))

            with pytest.raises(ValueError) as excinfo:
                load_set_registry(set_name)

            message = str(excinfo.value)
            assert "Twin Slot" in message          # the colliding name
            assert "aaa_first" in message           # the earlier registration
            assert "bbb_second" in message          # the colliding module
        finally:
            shutil.rmtree(set_dir, ignore_errors=True)
            for name in list(sys.modules):
                if name.startswith(f"cards.{set_name}"):
                    del sys.modules[name]
            importlib.invalidate_caches()

    def test_preexisting_registry_duplicate_names_both(self) -> None:
        """A collision against an entry the *caller* pre-registered (absent
        from this load's own tracking) must still name both implementations:
        the loader recovers the prior class from ``registry.get(name)`` rather
        than emitting a ``<unknown>`` placeholder."""
        import importlib
        import shutil
        import sys
        from pathlib import Path

        import cards

        cards_root = Path(cards.__file__).resolve().parent
        set_name = "_prepop_dup_fixture_set"
        set_dir = cards_root / set_name
        if set_dir.exists():
            shutil.rmtree(set_dir)
        set_dir.mkdir()
        impl = (
            "from engine.card import Creature\n\n\n"
            "class NewTwin(Creature):\n"
            "    def __init__(self, **kw):\n"
            "        kw.setdefault('name', 'Twin Slot')\n"
            "        super().__init__(**kw)\n"
        )
        try:
            (set_dir / "__init__.py").write_text("")
            sub_dir = set_dir / "ccc_only"
            sub_dir.mkdir()
            (sub_dir / "card_impl.py").write_text(impl)

            # Caller supplies a non-empty registry that already binds the name
            # the synthetic set will also provide — via a class from a totally
            # different module, never seen by this load.
            registry = CardRegistry()
            registry.register("Twin Slot", _PreRegisteredTwin)

            with pytest.raises(ValueError) as excinfo:
                load_set_registry(set_name, registry=registry)

            message = str(excinfo.value)
            assert "Twin Slot" in message                       # the card
            assert _PreRegisteredTwin.__module__ in message      # prior module
            assert _PreRegisteredTwin.__name__ in message        # prior class
            assert "ccc_only" in message                         # new module
            assert "NewTwin" in message                          # new class
            # Never a placeholder for a valid existing entry.
            assert "<unknown>" not in message
        finally:
            shutil.rmtree(set_dir, ignore_errors=True)
            for name in list(sys.modules):
                if name.startswith(f"cards.{set_name}"):
                    del sys.modules[name]
            importlib.invalidate_caches()
