"""Tests for TODO item 4: Migrate FDN card implementations into per-card templates.

Tests verify:
- All 260+ card_impl.py files are non-empty (not just templates with pass).
- Each card_impl.py contains a CardImpl subclass.
- Registry imports resolve without errors via register_fdn_cards().
- No references to ``cards.foundations`` in registry.py.
- cards/fdn/utils.py exists and its exports are importable.
- Spot-check: specific cards import and instantiate correctly.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from engine.card import CardImpl

REPO_ROOT = Path(__file__).resolve().parent.parent
FDN_DIR = REPO_ROOT / "cards" / "fdn"
REGISTRY_PATH = REPO_ROOT / "cards" / "registry.py"

# Minimum number of card_impl.py files expected
MIN_CARD_COUNT = 260


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card_dirs() -> list[Path]:
    """Return all numbered card directories under cards/fdn/."""
    return sorted(
        d for d in FDN_DIR.iterdir()
        if d.is_dir() and (d / "card_impl.py").exists()
    )


def _load_spec(card_dir: Path) -> dict[str, Any]:
    """Load card_spec.json from a card directory."""
    spec_file = card_dir / "card_spec.json"
    with open(spec_file) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test: All card_impl.py files are non-empty
# ---------------------------------------------------------------------------

class TestCardImplFilesNonEmpty:
    """Verify that all card_impl.py files contain real implementations."""

    def test_at_least_260_card_impl_files_exist(self) -> None:
        """There should be at least 260 card_impl.py files in cards/fdn/."""
        card_dirs = _card_dirs()
        assert len(card_dirs) >= MIN_CARD_COUNT, (
            f"Expected at least {MIN_CARD_COUNT} card_impl.py files, "
            f"found {len(card_dirs)}"
        )

    def test_no_card_impl_is_trivially_empty(self) -> None:
        """No card_impl.py should be empty or contain only whitespace."""
        for card_dir in _card_dirs():
            impl_file = card_dir / "card_impl.py"
            content = impl_file.read_text().strip()
            assert len(content) > 50, (
                f"card_impl.py in {card_dir.name} appears to be a stub/template "
                f"(only {len(content)} chars)"
            )


# ---------------------------------------------------------------------------
# Test: Each card_impl.py contains a CardImpl subclass
# ---------------------------------------------------------------------------

class TestCardImplContainsClass:
    """Verify each card_impl.py has an importable CardImpl subclass."""

    def test_every_card_impl_has_cardimpl_subclass(self) -> None:
        """Each card_impl.py module must export at least one CardImpl subclass."""
        failures: list[str] = []
        for card_dir in _card_dirs():
            mod_name = f"cards.fdn.{card_dir.name}.card_impl"
            try:
                mod = importlib.import_module(mod_name)
            except Exception as exc:
                failures.append(f"{card_dir.name}: import error — {exc}")
                continue

            found = any(
                isinstance(getattr(mod, attr, None), type)
                and issubclass(getattr(mod, attr), CardImpl)
                and getattr(mod, attr) is not CardImpl
                and getattr(mod, attr).__module__ == mod.__name__
                for attr in dir(mod)
            )
            if not found:
                failures.append(f"{card_dir.name}: no CardImpl subclass found")

        assert not failures, (
            f"{len(failures)} card_impl.py file(s) missing CardImpl subclass:\n"
            + "\n".join(failures[:20])
        )


# ---------------------------------------------------------------------------
# Test: Registry imports resolve without errors
# ---------------------------------------------------------------------------

class TestRegistryImports:
    """Verify register_fdn_cards() works and populates the registry."""

    def test_register_fdn_cards_succeeds(self) -> None:
        """register_fdn_cards() should complete without raising."""
        from cards.registry import CardRegistry, register_fdn_cards

        registry = CardRegistry()
        result = register_fdn_cards(registry)
        assert result is registry

    def test_register_fdn_cards_populates_all_spec_dirs(self) -> None:
        """The registry must contain one entry per cards/fdn/*/card_spec.json directory."""
        from cards.registry import CardRegistry, register_fdn_cards

        registry = CardRegistry()
        register_fdn_cards(registry)

        expected_count = len(_card_dirs())
        actual_count = len(registry)
        assert actual_count == expected_count, (
            f"Expected {expected_count} registered cards (one per card dir), "
            f"found {actual_count}. "
            f"{expected_count - actual_count} card(s) failed to register."
        )

    def test_all_spec_names_present_in_registry(self) -> None:
        """Every card_spec.json name must appear in the registry — no silent losses."""
        from cards.registry import CardRegistry, register_fdn_cards

        registry = CardRegistry()
        register_fdn_cards(registry)
        registered_names = set(registry.list_all())

        missing: list[str] = []
        for card_dir in _card_dirs():
            spec = _load_spec(card_dir)
            card_name = spec["name"]
            if card_name not in registered_names:
                missing.append(f"{card_dir.name}: {card_name}")

        assert not missing, (
            f"{len(missing)} card(s) from card_spec.json not found in registry:\n"
            + "\n".join(missing[:30])
        )


# ---------------------------------------------------------------------------
# Test: No references to cards.foundations in registry.py
# ---------------------------------------------------------------------------

class TestNoOldFoundationsReferences:
    """Registry.py should not reference the old cards.foundations module."""

    def test_no_cards_foundations_import_in_registry(self) -> None:
        """registry.py must not contain 'cards.foundations' imports."""
        content = REGISTRY_PATH.read_text()
        assert "cards.foundations" not in content, (
            "registry.py still references 'cards.foundations' — "
            "should import from cards.fdn instead"
        )

    def test_no_from_foundations_import_in_registry(self) -> None:
        """registry.py must not contain 'from foundations' imports."""
        content = REGISTRY_PATH.read_text()
        # Check for relative imports like "from .foundations" or "from foundations"
        lines = content.splitlines()
        bad_lines = [
            line for line in lines
            if "foundations" in line.lower()
            and ("import" in line.lower() or "from" in line.lower())
        ]
        assert not bad_lines, (
            f"registry.py has foundations import references:\n"
            + "\n".join(bad_lines)
        )


# ---------------------------------------------------------------------------
# Test: cards/fdn/utils.py exists and is importable
# ---------------------------------------------------------------------------

class TestFdnUtils:
    """Verify cards/fdn/utils.py exists and its exports work."""

    def test_utils_file_exists(self) -> None:
        """cards/fdn/utils.py must exist."""
        utils_path = FDN_DIR / "utils.py"
        assert utils_path.exists(), "cards/fdn/utils.py does not exist"

    def test_utils_is_importable(self) -> None:
        """cards.fdn.utils must be importable without errors."""
        mod = importlib.import_module("cards.fdn.utils")
        assert mod is not None

    def test_utils_exports_make_vanilla(self) -> None:
        """cards.fdn.utils should export make_vanilla helper."""
        from cards.fdn.utils import make_vanilla
        assert callable(make_vanilla)

    def test_utils_exports_gainland(self) -> None:
        """cards.fdn.utils should export GainLand base class."""
        from cards.fdn.utils import GainLand
        assert isinstance(GainLand, type)

    def test_utils_exports_tapland(self) -> None:
        """cards.fdn.utils should export TapLand base class."""
        from cards.fdn.utils import TapLand
        assert isinstance(TapLand, type)


# ---------------------------------------------------------------------------
# Test: Spot-check specific cards import and instantiate
# ---------------------------------------------------------------------------

class TestSpotCheckCards:
    """Spot-check that specific well-known cards instantiate correctly."""

    def test_card_1_sire_of_seven_deaths(self) -> None:
        """Card #1 — Sire of Seven Deaths should instantiate as a Creature."""
        from cards.fdn import __path__  # noqa: F401 — ensure package
        mod = importlib.import_module("cards.fdn.1.card_impl")
        cls = mod.SireOfSevenDeaths
        assert issubclass(cls, CardImpl)
        instance = cls(name="Sire of Seven Deaths", owner=None)
        assert instance.name == "Sire of Seven Deaths"

    def test_card_10_divine_resilience(self) -> None:
        """Card #10 — Divine Resilience should instantiate as an Instant."""
        mod = importlib.import_module("cards.fdn.10.card_impl")
        cls = mod.DivineResilience
        assert issubclass(cls, CardImpl)
        instance = cls(owner=None)
        assert instance.name == "Divine Resilience"

    def test_card_via_registry_lookup(self) -> None:
        """A registered card should be retrievable by name from the registry."""
        from cards.registry import CardRegistry, register_fdn_cards

        registry = CardRegistry()
        register_fdn_cards(registry)
        # Look up a known card
        impl_class, metadata = registry.get("Sire of Seven Deaths")
        assert issubclass(impl_class, CardImpl)
        assert metadata.name == "Sire of Seven Deaths"
        assert metadata.set_code == "fdn"

    def test_registry_create_instance(self) -> None:
        """create_instance should return a CardImpl for a registered FDN card."""
        from cards.registry import CardRegistry, register_fdn_cards

        registry = CardRegistry()
        register_fdn_cards(registry)
        instance = registry.create_instance("Sire of Seven Deaths", owner=None)
        assert isinstance(instance, CardImpl)
        assert instance.name == "Sire of Seven Deaths"
