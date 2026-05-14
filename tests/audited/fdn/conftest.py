"""Conftest for FDN (Foundations) audited tests.

Provides automatic ``card_impl`` module injection so that tests can write::

    from card_impl import Plains

The conftest detects the current card under test from the test file's parent
collector-number directory (e.g. ``tests/audited/fdn/001/tests.py`` → ``001``),
looks up that card's registered implementation in a :class:`CardRegistry`, and
creates a per-card synthetic ``card_impl`` module exposing the implementation
class under its class name (e.g. ``Plains``, ``AjaniCallerOfThePride``).

The injection happens at **load time** (not fixture time) because
``from card_impl import …`` runs during test module collection, before any
fixtures execute.

The conftest will NOT override an explicit ``card_impl.py`` provided by the
evaluator (detected via a real file on ``sys.path``).
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
import types
from pathlib import Path

from cards.registry import CardRegistry

# Explicit collector-directory → card-name overrides for FDN cards whose
# registry metadata lacks a collector_number.  These are maintained manually
# and only need entries for cards that have audited test directories.
_COLLECTOR_DIR_OVERRIDES: dict[str, str] = {
    "001": "Plains",
    "002": "Island",
    "003": "Swamp",
    "004": "Mountain",
    "005": "Forest",
    # Collector-number collisions — use explicit overrides to resolve.
    # CN 7: AntiquitiesOnTheLoose (simple_spells_batch2) collides with
    # CrystalBarricade (artifacts_batch2).  Directory "7" → in-scope sorcery.
    "7": "Antiquities on the Loose",
    # CN 7 collision — use "7b" for Crystal Barricade.
    "7b": "Crystal Barricade",
    # CN 105: FellingBlow (simple_spells_batch3) collides with
    # WitheringCurse (simple_spells_batch2).  Directory "105" stays
    # WitheringCurse (already existing tests); "105b" → FellingBlow.
    "105b": "Felling Blow",
    # CN 61: Muse's Encouragement (simple_spells_batch2) collides with
    # HighSocietyHunter (death_trigger_creatures).  Directory "61" stays
    # Muse's Encouragement; "61b" → High-Society Hunter.
    "61b": "High-Society Hunter",
    # CN 219: Rapturous Moment (simple_spells_batch2) collides with
    # ElvishArchdruid (activated_creatures).  Directory "219" stays
    # Rapturous Moment; "219b" → Elvish Archdruid.
    "219b": "Elvish Archdruid",
    # CN 228: Social Snub (simple_spells_batch2) collides with
    # MildManneredLibrarian (activated_creatures).  Directory "228" stays
    # Social Snub; "228b" → Mild-Mannered Librarian.
    "228b": "Mild-Mannered Librarian",
    # CN 129: SeizeTheSpoils (simple_spells_batch2) collides with
    # LeylineAxe (equipment).  Directory "129" stays Seize the Spoils;
    # "129b" → Leyline Axe.
    "129b": "Leyline Axe",
    # CN 75: VampireSoulcaller (death_trigger_creatures) collides with
    # SphinxsTutelage (special_guests SPG).  Directory "75" stays
    # Vampire Soulcaller; "75b" → Sphinx's Tutelage.
    "75b": "Sphinx's Tutelage",
    # CN 76: VengefulBloodwitch (death_trigger_creatures) collides with
    # GrimTutor (special_guests SPG).  Directory "76" stays
    # Vengeful Bloodwitch; "76b" → Grim Tutor.
    "76b": "Grim Tutor",
    # CN 81: ChandraFlameshaper (planeswalkers_batch2) collides with
    # AkromasMemorial (special_guests SPG).  Directory "81" stays
    # Chandra, Flameshaper; "81b" → Akroma's Memorial.
    "81b": "Akroma's Memorial",
    # --- Synthetic directories for cards without collector_number in registry ---
    # Artifacts (from artifacts.py with empty collector_number)
    "800": "Sol Ring",
    "801": "Arcane Signet",
    "802": "Mind Stone",
    "803": "Bonesplitter",
    "804": "Swiftfoot Boots",
    "805": "Whispersilk Cloak",
    "806": "Mask of Memory",
    "807": "Altar of the Brood",
    "808": "Elixir of Immortality",
    "809": "Relic of Progenitus",
    # Enchantments (from enchantments.py with empty collector_number)
    "810": "Holy Strength",
    "811": "Unholy Strength",
    "812": "Stab Wound",
    "813": "Arrest",
    "814": "Glorious Anthem",
    "815": "Dictate of Heliod",
    "816": "Brave the Sands",
    "817": "Levitation",
    # Planeswalkers (from planeswalkers.py with empty collector_number)
    "818": "Ajani, Caller of the Pride",
    "819": "Chandra, Torch of Defiance",
    "820": "Liliana, Dreadhorde General",
    "821": "Nissa, Worldwaker",
    # Modal/complex spells (from modal_spells.py with empty collector_number)
    "822": "Abzan Charm",
    "823": "Boros Charm",
    "824": "Prismari Command",
    "825": "Sublime Epiphany",
    "826": "Dromoka's Command",
    "827": "Austere Command",
    "828": "Collective Brutality",
    "829": "Inscription of Insight",
}

# All FDN register_* functions.
_REGISTER_FUNCTIONS: list[tuple[str, str]] = [
    ("cards.fdn._legacy.basic_lands", "register_basic_lands"),
    ("cards.fdn._legacy.simple_creatures", "register_simple_creatures"),
    ("cards.fdn._legacy.vanilla_creatures_batch2", "register_vanilla_creatures_batch2"),
    ("cards.fdn._legacy.simple_spells", "register_simple_spells"),
    ("cards.fdn._legacy.simple_spells_batch2", "register_simple_spells_batch2"),
    ("cards.fdn._legacy.simple_spells_batch3", "register_simple_spells_batch3"),
    ("cards.fdn._legacy.simple_permanents", "register_simple_permanents"),
    ("cards.fdn._legacy.enchantments", "register_enchantments"),
    ("cards.fdn._legacy.auras_batch2", "register_auras_batch2"),
    ("cards.fdn._legacy.global_enchantments", "register_global_enchantments"),
    ("cards.fdn._legacy.planeswalkers", "register_planeswalkers"),
    ("cards.fdn._legacy.planeswalkers_batch2", "register_planeswalkers_batch2"),
    ("cards.fdn._legacy.modal_spells", "register_modal_spells"),
    ("cards.fdn._legacy.complex_spells", "register_complex_spells"),
    ("cards.fdn._legacy.artifacts", "register_artifacts"),
    ("cards.fdn._legacy.artifacts_batch2", "register_artifacts_batch2"),
    ("cards.fdn._legacy.equipment", "register_equipment"),
    ("cards.fdn._legacy.lands", "register_lands"),
    ("cards.fdn._legacy.etb_creatures", "register_etb_creatures"),
    ("cards.fdn._legacy.death_trigger_creatures", "register_death_trigger_creatures"),
    ("cards.fdn._legacy.activated_creatures", "register_activated_creatures"),
    ("cards.fdn._legacy.special_guests", "register_special_guests"),
]


def _has_explicit_card_impl() -> bool:
    """Return True if an explicit ``card_impl.py`` is importable on sys.path.

    When the evaluator provides ``card_impl.py`` (via ``shutil.copy2`` into a
    temp dir on ``PYTHONPATH``), we must NOT override it.  Synthetic modules
    injected by other conftest files are NOT considered explicit — they have
    ``__file__`` set to ``<synthetic:...>``.
    """
    # Check if card_impl is already in sys.modules and backed by a real file
    existing = sys.modules.get("card_impl")
    if existing is not None:
        origin = getattr(existing, "__file__", None)
        if origin is not None and not origin.startswith("<synthetic:") and Path(origin).exists():
            return True

    # Only check importlib.util.find_spec if card_impl is NOT already in
    # sys.modules (avoids ValueError when __spec__ is None on synthetic modules).
    if "card_impl" not in sys.modules:
        spec = importlib.util.find_spec("card_impl")
        if spec is not None and spec.origin is not None:
            return True

    return False


def _build_registry() -> CardRegistry:
    """Build a CardRegistry with all FDN cards registered."""
    registry = CardRegistry()
    for module_path, func_name in _REGISTER_FUNCTIONS:
        mod = importlib.import_module(module_path)
        register_fn = getattr(mod, func_name)
        register_fn(registry)
    return registry


def _build_collector_maps(
    registry: CardRegistry,
) -> tuple[dict[str, tuple[type, str]], dict[str, type]]:
    """Build lookup maps from a populated registry.

    Returns:
        A tuple of:
        - ``cn_to_entry``: collector_number → (impl_class, card_name)
        - ``classname_to_class``: impl_class.__name__ → impl_class

    Entries from ``_COLLECTOR_DIR_OVERRIDES`` are merged in for cards whose
    registry metadata has an empty ``collector_number``.
    """
    cn_to_entry: dict[str, tuple[type, str]] = {}
    classname_to_class: dict[str, type] = {}
    # name → (impl_class, meta) for override resolution
    name_to_class: dict[str, type] = {}
    for card_name in registry.list_all():
        impl_class, meta = registry.get(card_name)
        classname_to_class[impl_class.__name__] = impl_class
        name_to_class[card_name] = impl_class
        if meta.collector_number:
            cn_to_entry[meta.collector_number] = (impl_class, card_name)

    # Merge explicit overrides — always take precedence over registry
    # mappings.  This resolves collector-number collisions where two
    # different cards share the same CN (e.g. CN 7: AntiquitiesOnTheLoose
    # vs CrystalBarricade).
    for collector_dir, card_name in _COLLECTOR_DIR_OVERRIDES.items():
        if card_name in name_to_class:
            cn_to_entry[collector_dir] = (name_to_class[card_name], card_name)

    return cn_to_entry, classname_to_class


def _detect_collector_dir() -> str | None:
    """Inspect the call stack to find the collector-number directory.

    When ``from card_impl import ClassName`` is executed from a test file like
    ``tests/audited/fdn/001/tests.py``, the importing file's parent directory
    name (``001``) is the collector-number directory.

    Returns the directory name or ``None`` if detection fails.
    """
    # Walk up the stack to find the first frame whose file is inside an
    # audited/fdn/<collector_dir>/ path.  Skip conftest.py itself — the
    # collector directory is the per-card subdirectory, not the set-level
    # conftest directory.
    for frame_info in inspect.stack():
        caller_file = frame_info.filename
        if not caller_file:
            continue
        caller_path = Path(caller_file)
        # Skip conftest files — they sit at audited/fdn/conftest.py, not
        # inside a per-card collector directory.
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
    """Create a synthetic ``card_impl`` module for FDN.

    The module uses ``__getattr__`` so that ``from card_impl import ClassName``
    resolves *ClassName* by:

    1. Detecting the caller's collector-number directory.
    2. Looking up the card for that collector number.
    3. Returning the implementation class under its ``__name__``.

    If collector-number detection fails or the collector number is unknown,
    falls back to a class-name lookup across the full FDN registry.
    """
    mod = types.ModuleType("card_impl")
    mod.__doc__ = "Synthetic card_impl module — resolves FDN card classes from CardRegistry."
    mod.__file__ = "<synthetic:fdn_conftest>"
    mod.__package__ = ""

    def _getattr(name: str) -> type:
        # Try collector-directory-based lookup first.
        collector_dir = _detect_collector_dir()
        if collector_dir is not None:
            # Inside an audited test directory — only expose the card for
            # this collector directory.  Raise a clear error if the test
            # imports the wrong class.
            if collector_dir in cn_to_entry:
                impl_class, _card_name = cn_to_entry[collector_dir]
                if impl_class.__name__ == name:
                    return impl_class
                raise AttributeError(
                    f"card_impl has no attribute {name!r} — collector directory "
                    f"{collector_dir!r} maps to {impl_class.__name__!r}, not {name!r}. "
                    f"Each audited test directory may only import its own card."
                ) from None
            raise AttributeError(
                f"card_impl has no attribute {name!r} — collector directory "
                f"{collector_dir!r} is not mapped to any FDN card. "
                f"Add an entry to _COLLECTOR_DIR_OVERRIDES or fix the "
                f"registry's collector_number metadata."
            ) from None

        # Outside an audited test directory — resolve by class name across
        # the full registry (used by infrastructure tests, evaluator, etc.).
        if name in classname_to_class:
            return classname_to_class[name]

        raise AttributeError(
            f"card_impl has no attribute {name!r} "
            f"(not found in FDN CardRegistry)"
        ) from None

    mod.__getattr__ = _getattr  # type: ignore[attr-defined]

    return mod


# ---------------------------------------------------------------------------
# Module-level injection — runs at conftest load time (before test collection)
# ---------------------------------------------------------------------------

# Known limitation: this writes to the global sys.modules["card_impl"] at
# conftest load time.  If both FDN and SOS conftests are loaded in the same
# pytest process (e.g. `pytest tests/audited/`), the SOS conftest loads after
# FDN's and overwrites this synthetic module with its own.  This is intentional
# and handled correctly: _has_explicit_card_impl() treats any module whose
# __file__ starts with "<synthetic:" as non-explicit, so SOS always overwrites
# FDN's synthetic.  Each per-card test directory is isolated by
# _detect_collector_dir() so tests only resolve their own card's class.
# If a third audited set is added, its conftest must follow the same pattern.
if not _has_explicit_card_impl():
    _fdn_registry = _build_registry()
    _cn_to_entry, _classname_to_class = _build_collector_maps(_fdn_registry)
    _synthetic_card_impl = _make_card_impl_module(_cn_to_entry, _classname_to_class)
    sys.modules["card_impl"] = _synthetic_card_impl
