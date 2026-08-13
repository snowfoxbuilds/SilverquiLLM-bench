"""Card-spec loading and filtering utilities for CLI use.

Pure utility functions with no side effects.  The CLI composes these
to select which cards to run benchmarks against.

Public API (legacy dict-based):
- ``load_card_specs`` — walk a specs directory and return parsed card specs.
- ``load_prototype_cards`` — load prototype_cards.json and extract collector numbers.
- ``filter_by_collectors`` — filter specs to a given set of collector numbers.
- ``filter_by_prototype`` — filter specs to those listed in a prototype file.

Public API (unified card layout):
- ``load_card_spec`` — load one card spec JSON from benchmarks/sos/workspace/cards/{set}/{collector}/.
- ``load_all_card_specs`` — load all card specs for a set, sorted by collector number.
- ``load_card_impl`` — return path to card_impl.py for a given card.
- ``is_template`` — check if a card_impl.py is an empty template.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

__all__ = [
    "load_card_specs",
    "load_prototype_cards",
    "filter_by_collectors",
    "filter_by_prototype",
    "load_card_spec",
    "load_all_card_specs",
    "load_card_impl",
    "is_template",
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


def _dir_name_sort_key(dir_name: str) -> tuple[int, int, str]:
    """Return a sort key for directory names with natural sort order.

    Pure numeric directories sort first (numerically), then directories
    with numeric prefixes (e.g. "105b") sort by their numeric prefix,
    then fully non-numeric names sort lexicographically at the end.
    """
    # Pure numeric
    try:
        return (0, int(dir_name), "")
    except (ValueError, TypeError):
        pass
    # Numeric prefix with suffix (e.g. "105b", "7b")
    m = re.match(r"^(\d+)(.+)$", dir_name)
    if m:
        return (0, int(m.group(1)), m.group(2))
    # Fully non-numeric (e.g. "soa_1", "spg_149")
    return (1, 0, dir_name)


# ---------------------------------------------------------------------------
# Unified card layout functions (cards/{set_code}/{collector_number}/)
# ---------------------------------------------------------------------------


def load_card_spec(cards_dir: Path, set_code: str, collector_number: str) -> dict:
    """Load one card spec JSON from the unified layout.

    Parameters
    ----------
    cards_dir:
        Root cards directory (e.g. ``Path("cards")``).
    set_code:
        Set code subdirectory (e.g. ``"sos"``).
    collector_number:
        Collector number subdirectory (e.g. ``"42"`` or ``"soa_6"``).

    Returns
    -------
    dict
        Parsed card spec dictionary.

    Raises
    ------
    FileNotFoundError
        If the card_spec.json does not exist.
    """
    spec_path = cards_dir / set_code / collector_number / "card_spec.json"
    if not spec_path.exists():
        raise FileNotFoundError(
            f"Card spec not found: {spec_path}"
        )
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    # Always use path-derived identifiers as canonical
    spec["set_code"] = set_code
    spec["collector_number"] = collector_number
    return spec


def load_all_card_specs(cards_dir: Path, set_code: str) -> list[dict]:
    """Load all card specs for a set, sorted by collector number.

    Numeric collector numbers sort first (numerically), followed by
    non-numeric ones (lexicographically).

    Parameters
    ----------
    cards_dir:
        Root cards directory.
    set_code:
        Set code subdirectory.

    Returns
    -------
    list[dict]
        Sorted list of card spec dictionaries.
    """
    set_dir = cards_dir / set_code
    if not set_dir.exists():
        return []

    specs: list[tuple[str, dict]] = []
    for child in set_dir.iterdir():
        if not child.is_dir():
            continue
        spec_file = child / "card_spec.json"
        if spec_file.exists():
            with open(spec_file, "r", encoding="utf-8") as f:
                spec = json.load(f)
            # Store original JSON collector_number for filter matching
            spec["json_collector_number"] = spec.get("collector_number", child.name)
            # Always use directory name as collector_number (canonical in unified layout)
            spec["collector_number"] = child.name
            if not spec.get("set_code"):
                spec["set_code"] = set_code
            specs.append((child.name, spec))

    specs.sort(key=lambda pair: _dir_name_sort_key(pair[0]))
    return [spec for _, spec in specs]


def load_card_impl(cards_dir: Path, set_code: str, collector_number: str) -> Path:
    """Return the path to card_impl.py for a given card.

    Parameters
    ----------
    cards_dir:
        Root cards directory.
    set_code:
        Set code subdirectory.
    collector_number:
        Collector number subdirectory.

    Returns
    -------
    Path
        Absolute path to the card_impl.py file.

    Raises
    ------
    FileNotFoundError
        If the card_impl.py does not exist.
    """
    impl_path = cards_dir / set_code / collector_number / "card_impl.py"
    if not impl_path.exists():
        raise FileNotFoundError(
            f"Card implementation not found: {impl_path}"
        )
    return impl_path


def is_template(card_impl_path: Path) -> bool:
    """Check if a card_impl.py is an empty template.

    A file is considered a template if all methods in all classes
    contain only ``pass`` statements (or ellipsis) and no other
    meaningful code.

    Parameters
    ----------
    card_impl_path:
        Path to a card_impl.py file.

    Returns
    -------
    bool
        True if the file is an empty template, False otherwise.
    """
    source = card_impl_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    # Find all function/method definitions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if body is only pass/Ellipsis/docstring
            for stmt in node.body:
                if isinstance(stmt, ast.Pass):
                    continue
                if isinstance(stmt, ast.Expr):
                    # Allow docstrings and Ellipsis only
                    if isinstance(stmt.value, ast.Constant):
                        if isinstance(stmt.value.value, str):
                            continue  # docstring
                        if stmt.value.value is ...:
                            continue  # Ellipsis
                    # Any other expression (e.g. function calls) means real code
                    return False
                # Any other statement means it's not a template
                return False

    # If there are no functions at all, it's also a template
    return True
