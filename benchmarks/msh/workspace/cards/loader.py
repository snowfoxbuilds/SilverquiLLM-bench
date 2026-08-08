"""Registry loader — populate a CardRegistry from per-card implementation modules.

Walks ``cards/<set_code>/<dir>/card_impl.py`` directories, imports each
module, and registers every :class:`~engine.card.CardImpl` subclass defined
in it (by the card's ``name`` attribute) together with metadata from the
colocated ``card_spec.json``.

Used by tests, harnesses, and the replay validation pipeline — anything
that needs to resolve a card *name* to its implementation class.
"""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import sys
from pathlib import Path

from engine.card import CardImpl

from cards.registry import CardMetadata, CardRegistry

logger = logging.getLogger(__name__)

_CARDS_ROOT = Path(__file__).resolve().parent


def _is_engine_base(cls: type) -> bool:
    """True if *cls* is a class the engine itself exports (Creature, Land, …).

    Card modules import these as bases; they must not be registered as cards.
    Factory-made classes (e.g. ``make_vanilla``) carry an ``engine.*``
    ``__module__`` too but are *not* attributes of that module, so they pass.
    """
    if not cls.__module__.startswith("engine."):
        return False
    module = sys.modules.get(cls.__module__)
    return module is not None and getattr(module, cls.__name__, None) is cls


def _defines_card(module: object, cls: type) -> bool:
    """True if *cls* is a card class this module defines (vs. imports).

    Factory-made classes (``make_vanilla``, ``make_gainlife_tapland``) carry
    the *factory's* module name but are not attributes of that module — that
    asymmetry is what distinguishes a product built for this card module
    from a class merely imported out of another module.
    """
    if cls.__module__ == module.__name__:  # type: ignore[attr-defined]
        return True
    if cls.__module__.endswith(".card_impl"):
        return False  # imported from another card's module
    if _is_engine_base(cls):
        return False
    factory_module = sys.modules.get(cls.__module__)
    return (
        factory_module is None
        or getattr(factory_module, cls.__name__, None) is not cls
    )


def _metadata_from_spec(spec_path: Path) -> CardMetadata | None:
    """Build CardMetadata from a card_spec.json, or None if unreadable."""
    try:
        spec = json.loads(spec_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return CardMetadata(
        name=spec.get("name", ""),
        mana_cost_str=spec.get("mana_cost", ""),
        type_line=spec.get("type_line", ""),
        oracle_text=spec.get("oracle_text", ""),
        power=spec.get("power"),
        toughness=spec.get("toughness"),
        colors=spec.get("colors", []),
        keywords=spec.get("keywords", []),
        rarity=spec.get("rarity", ""),
        set_code=spec.get("set", spec.get("set_code", "")),
        collector_number=spec.get("collector_number", ""),
    )


def load_set_registry(
    set_code: str = "fdn",
    registry: CardRegistry | None = None,
    strict: bool = False,
) -> CardRegistry:
    """Load every card implementation of *set_code* into a registry.

    Imports ``cards.<set_code>.<dir>.card_impl`` for each card directory and
    registers each :class:`CardImpl` subclass *defined in that module* under
    its instance ``name``. A module that fails to import or a class that
    fails to instantiate is logged and skipped unless *strict* is True.

    Parameters:
        set_code: Card set directory under ``cards/`` (e.g. ``"fdn"``).
        registry: Registry to populate; a new one is created if ``None``.
        strict: Raise on the first import/instantiation failure instead of
            logging and skipping.

    Returns:
        The populated :class:`CardRegistry`.
    """
    if registry is None:
        registry = CardRegistry()

    set_root = _CARDS_ROOT / set_code
    if not set_root.is_dir():
        raise FileNotFoundError(f"No card set directory at {set_root}")

    # Track the module that first registered each name so a collision can name
    # both offenders (a card slot squatting on another card's printed name).
    registered_by: dict[str, str] = {}

    for card_dir in sorted(set_root.iterdir()):
        impl_path = card_dir / "card_impl.py"
        if not impl_path.is_file():
            continue
        module_name = f"cards.{set_code}.{card_dir.name}.card_impl"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            if strict:
                raise
            logger.warning("Skipping %s — import failed: %s", module_name, exc)
            continue

        metadata = _metadata_from_spec(card_dir / "card_spec.json")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if not (issubclass(cls, CardImpl) and _defines_card(module, cls)):
                continue
            try:
                instance = cls()
            except Exception as exc:
                if strict:
                    raise
                logger.warning(
                    "Skipping %s.%s — instantiation failed: %s",
                    module_name, cls.__name__, exc,
                )
                continue
            if instance.name in registry:
                # A card name must map to exactly one implementation. Two dirs
                # claiming the same printed name means one is squatting on the
                # other's slot (a real card would silently resolve as the
                # wrong impl). Hard-fail, naming both offenders.
                raise ValueError(
                    f"Duplicate card name {instance.name!r}: "
                    f"{module_name}.{cls.__name__} collides with the earlier "
                    f"registration from {registered_by.get(instance.name, '<unknown>')}"
                )
            registry.register(instance.name, cls, metadata)
            registered_by[instance.name] = f"{module_name}.{cls.__name__}"

    return registry
