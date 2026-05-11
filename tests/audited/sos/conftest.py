"""Conftest for SOS (Starlight of Silvermoon) audited tests.

Provides automatic ``card_impl`` module injection so that tests can write::

    from card_impl import SomeSOSCard

The conftest detects the current card under test from the test file's parent
collector-number directory (e.g. ``tests/audited/sos/042/tests.py`` → ``042``),
imports ``cards.stubs.sos_stubs``, calls ``register_sos_stubs(registry)``,
finds the card for the current collector directory, and exposes the correct
implementation class under its class name.

The injection happens at **load time** (not fixture time) because
``from card_impl import …`` runs during test module collection, before any
fixtures execute.

When the evaluator provides an explicit ``card_impl.py`` (via ``shutil.copy2``
into a temp dir on ``PYTHONPATH``), the conftest detects it and does NOT
override.

If SOS stubs are not yet available (item 6), the conftest replaces any
existing synthetic ``card_impl`` in ``sys.modules`` with a clear SOS error
module so that SOS tests collected in the same pytest process do not produce
unrelated FDN errors.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
import types
from pathlib import Path


def _has_explicit_card_impl() -> bool:
    """Return True if an explicit ``card_impl.py`` is importable on sys.path.

    When the evaluator provides ``card_impl.py`` (via ``shutil.copy2`` into a
    temp dir on ``PYTHONPATH``), we must NOT override it.  Synthetic modules
    injected by other conftest files (e.g. FDN conftest) are NOT considered
    explicit — they have ``__file__`` set to ``<synthetic:...>``.
    """
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


def _load_sos_stubs_and_build_registry() -> tuple:
    """Import SOS stubs, register them in a CardRegistry, and build lookup maps.

    Calls ``register_sos_stubs(registry)`` from ``cards.stubs.sos_stubs``.

    Returns:
        A tuple of (cn_to_entry, classname_to_class) mappings.

    Raises:
        ImportError: If ``cards.stubs.sos_stubs`` is not available yet
            (expected to be created by TODO item 6).
    """
    try:
        sos_stubs = importlib.import_module("cards.stubs.sos_stubs")
    except (ImportError, ModuleNotFoundError) as exc:
        raise ImportError(
            "SOS stub classes are not available yet. "
            "Ensure cards/stubs/sos_stubs.py has been created (TODO item 6). "
            f"Original error: {exc}"
        ) from exc

    from cards.registry import CardRegistry

    registry = CardRegistry()
    register_fn = getattr(sos_stubs, "register_sos_stubs", None)
    if register_fn is None:
        raise ImportError(
            "cards.stubs.sos_stubs does not have register_sos_stubs(). "
            "Ensure it was created correctly (TODO item 6)."
        )
    register_fn(registry)

    # Build lookup maps.
    # SOS uses plain numeric directories for base SOS cards (e.g. ``042``)
    # and set-prefixed directories for subset cards (e.g. ``soa_1``,
    # ``spg_149``).  The set-prefixed form prevents collector-number
    # collisions across SOA/SPG subsets.
    cn_to_entry: dict[str, tuple[type, str]] = {}
    classname_to_class: dict[str, type] = {}
    for card_name in registry.list_all():
        impl_class, meta = registry.get(card_name)
        classname_to_class[impl_class.__name__] = impl_class
        if meta.collector_number:
            cn = meta.collector_number
            set_code = (meta.set_code or "").lower()
            # Only base SOS cards get plain numeric keys to avoid
            # SOA/SPG collector numbers overwriting SOS mappings.
            if set_code == "sos" or not set_code:
                cn_to_entry[cn] = (impl_class, card_name)
            # SOA/SPG cards get only set-prefixed keys (e.g. "soa_1", "spg_149")
            if set_code and set_code != "sos":
                prefixed = f"{set_code}_{cn}"
                cn_to_entry[prefixed] = (impl_class, card_name)

    return cn_to_entry, classname_to_class


def _detect_collector_dir() -> str | None:
    """Inspect the call stack to find the collector-number directory.

    When ``from card_impl import ClassName`` is executed from a test file like
    ``tests/audited/sos/042/tests.py``, the importing file's parent directory
    name (``042``) is the collector-number directory.

    For SOS subsets, directories use a set-prefix format like ``soa_1`` or
    ``spg_149`` to distinguish collector numbers that collide across sets.

    Returns the directory name or ``None`` if detection fails.
    """
    for frame_info in inspect.stack():
        caller_file = frame_info.filename
        if not caller_file:
            continue
        caller_path = Path(caller_file)
        # Skip conftest files — they sit at audited/sos/conftest.py, not
        # inside a per-card collector directory.
        if caller_path.name == "conftest.py":
            continue
        parts = caller_path.parts
        for i, part in enumerate(parts):
            if (
                part == "sos"
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
    """Create a synthetic ``card_impl`` module for SOS.

    The module uses ``__getattr__`` to resolve class names by:

    1. Detecting the caller's collector-number directory.
    2. Looking up the card for that collector number via the SOS stubs registry.
    3. Returning the implementation class under its ``__name__``.

    Falls back to class-name lookup if collector detection fails.
    """
    mod = types.ModuleType("card_impl")
    mod.__doc__ = "Synthetic card_impl module — resolves SOS card stub classes."
    mod.__file__ = "<synthetic:sos_conftest>"
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
                f"{collector_dir!r} is not mapped to any SOS card."
            ) from None

        # Outside an audited test directory — resolve by class name across
        # the full registry (used by infrastructure tests, evaluator, etc.).
        if name in classname_to_class:
            return classname_to_class[name]

        raise AttributeError(
            f"card_impl has no attribute {name!r} "
            f"(not found in SOS stubs module)"
        ) from None

    mod.__getattr__ = _getattr  # type: ignore[attr-defined]
    return mod


def _make_error_module(msg: str) -> types.ModuleType:
    """Create a card_impl module that raises ImportError on any attribute access.

    This ensures SOS tests get a clear error message rather than silently
    falling back to an unrelated FDN card_impl.
    """
    mod = types.ModuleType("card_impl")
    mod.__doc__ = "Placeholder card_impl — SOS stubs not available."
    mod.__file__ = "<synthetic:sos_conftest:error>"
    mod.__package__ = ""

    def _getattr(name: str) -> type:
        raise ImportError(
            f"Cannot import {name!r} from card_impl: {msg}"
        )

    mod.__getattr__ = _getattr  # type: ignore[attr-defined]
    return mod


# ---------------------------------------------------------------------------
# Module-level injection — runs at conftest load time (before test collection)
# ---------------------------------------------------------------------------

if not _has_explicit_card_impl():
    try:
        _cn_to_entry, _classname_to_class = _load_sos_stubs_and_build_registry()
        _synthetic_card_impl = _make_card_impl_module(_cn_to_entry, _classname_to_class)
        sys.modules["card_impl"] = _synthetic_card_impl
    except ImportError as _stub_err:
        # Stubs not available yet (item 6).  Replace any existing synthetic
        # card_impl (e.g. from FDN conftest) with an SOS error module so that
        # SOS tests get a clear "stubs not available" error rather than
        # unrelated FDN AttributeErrors.
        import warnings as _warnings

        _warnings.warn(
            f"SOS stubs not available: {_stub_err}. "
            "SOS audited tests will fail until cards/stubs/sos_stubs.py is created.",
            stacklevel=1,
        )

        _err_msg = str(_stub_err)
        sys.modules["card_impl"] = _make_error_module(_err_msg)
