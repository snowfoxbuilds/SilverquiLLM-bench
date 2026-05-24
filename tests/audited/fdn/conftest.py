"""Conftest for FDN (Foundations) audited tests.

Provides automatic ``card_impl`` module injection so that tests can write::

    from card_impl import Plains

The conftest detects the current card under test from the test file's parent
collector-number directory (e.g. ``tests/audited/fdn/fdn_1/tests.py`` → ``fdn_1``),
looks up the card for that collector directory via the FDN registry, and
exposes the correct implementation class under its class name.

Basic lands (fdn_272, fdn_274, fdn_276, fdn_278, fdn_280) are mapped via
``_COLLECTOR_DIR_OVERRIDES`` since their registry entries have an empty
``collector_number``.

When the evaluator provides an explicit ``card_impl.py``, the conftest
detects it and does NOT override.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
import types
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_FDN_CARDS_DIR = _PROJECT_ROOT / "benchmarks" / "sos" / "workspace" / "cards" / "fdn"

# Maps collector-directory names to card names for cards whose registry
# metadata has an empty collector_number (basic lands).  The directory
# names mirror the corresponding benchmarks/sos/workspace/cards/fdn/ subdirectories.
_COLLECTOR_DIR_OVERRIDES: dict[str, str] = {
    "fdn_272": "Plains",
    "fdn_274": "Island",
    "fdn_276": "Swamp",
    "fdn_278": "Mountain",
    "fdn_280": "Forest",
}


def _card_name_to_class_name(name: str) -> str:
    """Convert a card name to a Python class name.

    e.g. 'Ajani, Caller of the Pride' → 'AjaniCallerOfThePride'
    """
    parts = re.sub(r"[^a-zA-Z0-9 ]", " ", name).split()
    return "".join(p.capitalize() for p in parts)


def _has_explicit_card_impl() -> bool:
    """Return True if an explicit ``card_impl.py`` is importable on sys.path."""
    existing = sys.modules.get("card_impl")
    if existing is not None:
        origin = getattr(existing, "__file__", None)
        if origin is not None and not origin.startswith("<synthetic:") and Path(origin).exists():
            return True
    if "card_impl" not in sys.modules:
        spec = importlib.util.find_spec("card_impl")
        if spec is not None and spec.origin is not None:
            return True
    return False


def _build_registry():
    """Build a CardRegistry populated with FDN cards and basic lands.

    Registers all five basic lands first (with empty collector_number so
    the override mechanism is needed for 001–005).  Then scans
    ``benchmarks/sos/workspace/cards/fdn/`` to register all FDN cards using minimal stubs for
    cards whose card_impl.py cannot be imported.
    """
    from benchmarks.sos.workspace.cards.registry import CardMetadata, CardRegistry
    from benchmarks.sos.workspace.engine.basic_lands import register_basic_lands
    from benchmarks.sos.workspace.engine.card import CardImpl

    registry = CardRegistry()
    register_basic_lands(registry)

    if not _FDN_CARDS_DIR.is_dir():
        return registry

    already_registered = set(registry.list_all())

    for card_dir in sorted(_FDN_CARDS_DIR.iterdir()):
        if not card_dir.is_dir():
            continue
        spec_path = card_dir / "card_spec.json"
        if not spec_path.is_file():
            continue
        try:
            data = json.loads(spec_path.read_text())
        except Exception:
            continue

        card_name = data.get("name", "").strip()
        if not card_name or card_name in already_registered:
            continue

        class_name = _card_name_to_class_name(card_name)
        collector_number = str(data.get("collector_number", ""))
        set_code = str(data.get("set_code", "fdn"))

        impl_class = None
        impl_path = card_dir / "card_impl.py"
        if impl_path.is_file():
            try:
                mod_spec = importlib.util.spec_from_file_location(
                    f"_fdn_tmp_{card_dir.name}", impl_path
                )
                if mod_spec is not None:
                    mod = importlib.util.module_from_spec(mod_spec)
                    mod.CardImpl = CardImpl  # type: ignore[attr-defined]
                    mod_spec.loader.exec_module(mod)  # type: ignore[union-attr]
                    impl_class = getattr(mod, class_name, None)
            except Exception:
                impl_class = None

        if impl_class is None or not (isinstance(impl_class, type) and issubclass(impl_class, CardImpl)):
            impl_class = type(class_name, (CardImpl,), {
                "__init__": lambda self, **kw: CardImpl.__init__(self, **kw),
            })

        metadata = CardMetadata(
            name=card_name,
            mana_cost_str=str(data.get("mana_cost") or ""),
            type_line=str(data.get("type_line") or ""),
            oracle_text=str(data.get("oracle_text") or ""),
            power=data.get("power"),
            toughness=data.get("toughness"),
            colors=list(data.get("colors") or []),
            keywords=list(data.get("keywords") or []),
            rarity=str(data.get("rarity") or ""),
            set_code=set_code,
            collector_number=collector_number,
        )
        registry.register(card_name, impl_class, metadata)
        already_registered.add(card_name)

    return registry


def _build_collector_maps(registry) -> tuple[dict, dict]:
    """Build lookup maps from the registry.

    Returns:
        cn_to_entry: maps collector-directory name → (impl_class, card_name)
        classname_to_class: maps Python class name → impl_class
    """
    cn_to_entry: dict[str, tuple[type, str]] = {}
    classname_to_class: dict[str, type] = {}

    for card_name in registry.list_all():
        impl_class, meta = registry.get(card_name)
        classname_to_class[impl_class.__name__] = impl_class
        if meta.collector_number:
            cn = meta.collector_number
            set_code = (meta.set_code or "fdn").lower()
            cn_to_entry[f"{set_code}_{cn}"] = (impl_class, card_name)

    # Apply overrides for basic lands (which have empty collector_number).
    for dir_key, name in _COLLECTOR_DIR_OVERRIDES.items():
        if name in registry.list_all():
            impl_class, _meta = registry.get(name)
            cn_to_entry[dir_key] = (impl_class, name)

    return cn_to_entry, classname_to_class


def _detect_collector_dir() -> str | None:
    """Inspect the call stack to find the collector-number directory.

    When ``from card_impl import ClassName`` is executed from a test file like
    ``tests/audited/fdn/fdn_1/tests.py``, the importing file's parent directory
    name (``fdn_1``) is the collector-number directory.
    """
    for frame_info in inspect.stack():
        caller_file = frame_info.filename
        if not caller_file:
            continue
        caller_path = Path(caller_file)
        if caller_path.name == "conftest.py":
            continue
        parts = caller_path.parts
        for i, part in enumerate(parts):
            if (
                part == "fdn"
                and i > 0
                and parts[i - 1] == "audited"
                and i + 1 < len(parts)
            ):
                return parts[i + 1]
    return None


def _make_card_impl_module(
    cn_to_entry: dict[str, tuple[type, str]],
    classname_to_class: dict[str, type],
) -> types.ModuleType:
    """Create a synthetic ``card_impl`` module for FDN."""
    mod = types.ModuleType("card_impl")
    mod.__doc__ = "Synthetic card_impl module — resolves FDN card classes."
    mod.__file__ = "<synthetic:fdn_conftest>"
    mod.__package__ = ""

    def _getattr(name: str) -> type:
        collector_dir = _detect_collector_dir()
        if collector_dir is not None:
            if collector_dir in cn_to_entry:
                impl_class, card_name = cn_to_entry[collector_dir]
                if impl_class.__name__ == name:
                    return impl_class
                raise AttributeError(
                    f"card_impl has no attribute {name!r} — collector directory "
                    f"{collector_dir!r} maps to {card_name!r} ({impl_class.__name__}), "
                    f"not {name!r}. Each audited test directory may only import its own card."
                ) from None
            raise AttributeError(
                f"card_impl has no attribute {name!r} — collector directory "
                f"{collector_dir!r} is not mapped to any FDN card."
            ) from None

        if name in classname_to_class:
            return classname_to_class[name]

        raise AttributeError(
            f"card_impl has no attribute {name!r} "
            f"(not found in FDN registry)"
        ) from None

    mod.__getattr__ = _getattr  # type: ignore[attr-defined]
    return mod


# ---------------------------------------------------------------------------
# Module-level injection
# ---------------------------------------------------------------------------

if not _has_explicit_card_impl():
    _cn_to_entry, _classname_to_class = _build_collector_maps(_build_registry())
    _synthetic_card_impl = _make_card_impl_module(_cn_to_entry, _classname_to_class)
    sys.modules["card_impl"] = _synthetic_card_impl
