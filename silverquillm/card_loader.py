"""Card-spec loading and filtering utilities for CLI use.

Pure utility functions with no side effects.  The CLI composes these
to select which cards to run benchmarks against.

Public API:
- ``load_card_specs`` — walk a specs directory and return parsed card specs.
- ``load_prototype_cards`` — load prototype_cards.json and extract collector numbers.
- ``filter_by_collectors`` — filter specs to a given set of collector numbers.
- ``filter_by_prototype`` — filter specs to those listed in a prototype file.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "load_card_specs",
    "load_prototype_cards",
    "filter_by_collectors",
    "filter_by_prototype",
]


def load_card_specs(specs_dir: str) -> list[dict]:
    """Walk *specs_dir* and return parsed card spec dicts.

    Each subdirectory containing a ``card_spec.json`` file is loaded and
    its contents appended to the result list.  The returned list is sorted
    by ``collector_number`` (numerically where possible, lexicographically
    otherwise).

    Parameters
    ----------
    specs_dir:
        Path to the directory containing per-card subdirectories
        (e.g., ``benchmarks/sos/cards/``).

    Returns
    -------
    list[dict]
        Sorted list of card spec dictionaries.
    """
    specs_path = Path(specs_dir)
    specs: list[dict] = []

    for child in specs_path.iterdir():
        if not child.is_dir():
            continue
        spec_file = child / "card_spec.json"
        if spec_file.exists():
            with open(spec_file, "r", encoding="utf-8") as f:
                spec = json.load(f)
            spec["card_dir_name"] = child.name  # e.g. "6", "soa_6"
            specs.append(spec)

    specs.sort(key=_collector_number_sort_key)
    return specs


def load_prototype_cards(prototype_path: str) -> list[str]:
    """Load *prototype_path* and return collector numbers.

    Reads a JSON array of objects, each containing at least a
    ``collector_number`` field, and returns the collector numbers
    as a flat list of strings.

    Parameters
    ----------
    prototype_path:
        Path to a ``prototype_cards.json`` file.

    Returns
    -------
    list[str]
        The list of collector number strings extracted from the file.
    """
    with open(prototype_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    return [entry["collector_number"] for entry in entries]


def filter_by_collectors(
    specs: list[dict], collector_numbers: list[str]
) -> list[dict]:
    """Filter *specs* to only those whose card ID is in *collector_numbers*.

    The card ID is the directory name (``card_dir_name``) when present, which
    is unique across subsets (e.g. ``"6"`` vs ``"soa_6"``).  Falls back to
    ``collector_number`` for specs loaded without ``card_dir_name``.

    Parameters
    ----------
    specs:
        Full list of card spec dicts.
    collector_numbers:
        The card IDs to keep (directory names or collector numbers).

    Returns
    -------
    list[dict]
        Filtered subset of *specs*, preserving original order.

    Raises
    ------
    ValueError
        If any requested collector number is not found in *specs*.
    """
    available = {_card_id(s) for s in specs}
    missing = [cn for cn in collector_numbers if cn not in available]
    if missing:
        raise ValueError(
            f"Card ID(s) not found in specs: {missing}. "
            f"Available: {sorted(available)}"
        )

    requested = set(collector_numbers)
    return [s for s in specs if _card_id(s) in requested]


def filter_by_prototype(specs: list[dict], prototype_path: str) -> list[dict]:
    """Filter *specs* to only those listed in the prototype file.

    Loads collector numbers from *prototype_path* and returns the matching
    full spec dicts from *specs*.  This ensures the returned dicts contain
    all fields (``keywords``, ``colors``, ``rarity``, etc.) that the
    prototype JSON may lack.

    Parameters
    ----------
    specs:
        Full list of card spec dicts.
    prototype_path:
        Path to a ``prototype_cards.json`` file.

    Returns
    -------
    list[dict]
        Filtered subset of *specs* matching the prototype collector numbers.

    Raises
    ------
    ValueError
        If any prototype collector number is not found in *specs*.
    """
    collector_numbers = load_prototype_cards(prototype_path)
    return filter_by_collectors(specs, collector_numbers)


def _card_id(spec: dict) -> str:
    """Return the unique card identifier (directory name if set, else collector_number)."""
    return spec.get("card_dir_name", spec.get("collector_number", ""))


def _collector_number_sort_key(spec: dict) -> tuple[int, str]:
    """Return a sort key that orders numerically when possible."""
    cn = spec.get("collector_number", "")
    try:
        return (0, str(int(cn)).zfill(10))
    except (ValueError, TypeError):
        return (1, cn)
