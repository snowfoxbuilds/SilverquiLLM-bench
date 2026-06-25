"""Build a CardRegistry from a benchmark workspace's card implementations.

Harness-side validation tooling for replay validation. The replay executor
exercises a card's real behaviour only when its implementation is in the
registry; with no registry every card becomes a generic ``CardImpl`` placeholder
and *nothing diverges* (the validation is a silent no-op). This module discovers
every ``<workspace>/cards/<set>/<dir>/card_impl.py``, imports it, finds the
concrete ``CardImpl`` subclass, and registers it under its ``card_spec.json``
name so the replay actually drives the implementation.

The caller chooses **which workspace to import from** by passing ``workspace``;
the loader puts that workspace at the front of ``sys.path`` so the card impls'
flat ``from engine...`` / ``from cards...`` imports resolve against *that*
workspace's engine. (Python caches imported modules, so a single process can
only bind one workspace's ``engine``/``cards`` packages — fine for the CLI,
which runs fresh per invocation.)

Discovery handles two shapes seen in the FDN impls:

* ``class FleetingFlight(Instant): ...`` — a subclass defined in the module.
* ``HealersHawk = make_vanilla(...)`` — a class produced by a factory whose
  ``__module__`` is ``engine.creatures``; found by scanning module attributes
  rather than filtering on ``__module__``.

Unimplemented stubs (``class X(CardImpl): pass`` with ``CardImpl`` never
imported) raise on import and are recorded as skipped rather than crashing the
run.
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RegistryLoadReport:
    """Coverage report for a registry build, surfaced in the validation output."""

    workspace: str = ""
    set_code: str = ""
    registered: int = 0
    basic_lands_registered: int = 0
    name_to_dir: dict[str, str] = field(default_factory=dict)
    skipped_import_error: dict[str, str] = field(default_factory=dict)
    skipped_no_class: list[str] = field(default_factory=list)
    collisions: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def skipped(self) -> int:
        return len(self.skipped_import_error) + len(self.skipped_no_class)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "set_code": self.set_code,
            "registered": self.registered,
            "basic_lands_registered": self.basic_lands_registered,
            "skipped_import_error": self.skipped_import_error,
            "skipped_no_class": self.skipped_no_class,
            "collisions": [
                {"name": n, "kept": kept, "dropped": dropped}
                for n, kept, dropped in self.collisions
            ],
        }


def ensure_workspace_on_path(workspace: Path) -> None:
    """Put *workspace* at the front of ``sys.path`` for flat workspace imports."""
    p = str(Path(workspace).resolve())
    if sys.path[:1] != [p]:
        # Move to front so this workspace's engine/cards win over any other.
        while p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)


def _dir_sort_key(p: Path) -> tuple:
    """Natural sort: ``fdn_2`` before ``fdn_15``; lower collector wins collisions."""
    name = p.name
    prefix, sep, num = name.rpartition("_")
    if sep and num.isdigit():
        return (prefix, 0, int(num), "")
    return (name, 1, 0, name)


def _pick_card_class(candidates: list[type], spec_name: str | None) -> type:
    """Choose the concrete card class, preferring one whose name matches the spec."""
    if len(candidates) == 1 or not spec_name:
        return candidates[0]
    for cls in candidates:
        try:
            if cls(owner=None).name == spec_name:
                return cls
        except Exception:
            continue
    return candidates[0]


def build_registry(
    workspace: Path | str,
    set_code: str = "fdn",
    registry: Any | None = None,
    include_basic_lands: bool = True,
) -> tuple[Any, RegistryLoadReport]:
    """Build a ``CardRegistry`` from a workspace's card implementations.

    Args:
        workspace: The workspace directory to import card impls from. Placed at
            the front of ``sys.path`` so its ``engine``/``cards`` packages bind.
        set_code: The card-set subdirectory under ``cards/`` (e.g. ``"fdn"``).
        registry: An existing registry to populate; a fresh one is created if
            ``None``.
        include_basic_lands: Also register the five engine-provided basic lands
            (Plains/Island/Swamp/Mountain/Forest). They are implemented in
            ``engine.basic_lands`` rather than under ``cards/``, so without this
            they would otherwise be flagged ``MISSING_CARD`` in every game.

    Returns:
        ``(registry, RegistryLoadReport)``.

    Raises:
        FileNotFoundError: If ``<workspace>/cards/<set_code>`` does not exist.
    """
    workspace = Path(workspace).resolve()
    set_dir = workspace / "cards" / set_code
    if not set_dir.is_dir():
        raise FileNotFoundError(f"No card set dir at {set_dir}")

    ensure_workspace_on_path(workspace)

    # Resolved against the chosen workspace now on sys.path.
    import engine.card as _ecard
    from engine.card import CardImpl
    from cards.registry import CardRegistry, CardMetadata

    if registry is None:
        registry = CardRegistry()

    report = RegistryLoadReport(workspace=str(workspace), set_code=set_code)

    # Base/abstract classes re-exported into a card module (Creature, Instant,
    # CardImpl, ...) — never the card itself.
    base_classes = {
        c
        for c in vars(_ecard).values()
        if isinstance(c, type) and issubclass(c, CardImpl)
    }

    card_dirs = sorted(
        (
            d
            for d in set_dir.iterdir()
            if d.is_dir() and (d / "card_impl.py").exists()
        ),
        key=_dir_sort_key,
    )

    for d in card_dirs:
        modname = f"cards.{set_code}.{d.name}.card_impl"
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:  # unimplemented stub / broken import
            report.skipped_import_error[d.name] = f"{type(exc).__name__}: {exc}"
            continue

        candidates = [
            v
            for v in vars(mod).values()
            if isinstance(v, type)
            and issubclass(v, CardImpl)
            and v not in base_classes
        ]
        if not candidates:
            report.skipped_no_class.append(d.name)
            continue

        spec = d / "card_spec.json"
        spec_data: dict[str, Any] = {}
        if spec.exists():
            try:
                spec_data = json.loads(spec.read_text())
            except Exception:
                spec_data = {}

        cls = _pick_card_class(candidates, spec_data.get("name"))
        name = spec_data.get("name")
        if not name:
            try:
                name = cls(owner=None).name
            except Exception:
                name = cls.__name__

        if name in registry:
            report.collisions.append(
                (name, report.name_to_dir.get(name, "?"), d.name)
            )
            continue  # keep the first (lowest collector number) deterministically

        metadata = CardMetadata(
            name=name,
            mana_cost_str=spec_data.get("mana_cost", ""),
            type_line=spec_data.get("type_line", ""),
            oracle_text=spec_data.get("oracle_text", ""),
            rarity=spec_data.get("rarity", ""),
            set_code=spec_data.get("set_code", set_code),
            collector_number=str(spec_data.get("collector_number", "")),
        )
        registry.register(name, cls, metadata)
        report.name_to_dir[name] = d.name
        report.registered += 1

    if include_basic_lands:
        try:
            from engine.basic_lands import register_basic_lands

            register_basic_lands(registry)
            # Count canonical basics now resolvable (register_basic_lands
            # overwrites any same-named set impl, e.g. an FDN "Plains" dir), so
            # this is "basics available", not "newly added".
            report.basic_lands_registered = sum(
                1
                for b in ("Plains", "Island", "Swamp", "Mountain", "Forest")
                if b in registry
            )
        except Exception:
            pass

    return registry, report
