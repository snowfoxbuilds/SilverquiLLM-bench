"""Conftest for SOS audited tests in the test_oracle_workspace.

Provides a synthetic ``card_impl`` module so that tests can write::

    from card_impl import TheDawningArchaic

The conftest detects the current card's collector directory from the
importing test file's path and maps it to the correct card_impl module
under ``cards/sos/<collector_dir>/card_impl.py``.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path

# Workspace root: benchmarks/sos/data/test_oracle_workspace
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Cards directory
_CARDS_DIR = _WORKSPACE_ROOT / "cards" / "sos"


def _find_card_impl_class(collector_dir: str, class_name: str) -> type:
    """Import and return the requested class from the card_impl module."""
    card_impl_path = _CARDS_DIR / collector_dir / "card_impl.py"
    if not card_impl_path.exists():
        raise ImportError(
            f"No card_impl.py found at {card_impl_path} for collector dir {collector_dir!r}"
        )

    spec = importlib.util.spec_from_file_location(
        f"cards.sos.{collector_dir}.card_impl",
        card_impl_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {card_impl_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cls = getattr(module, class_name, None)
    if cls is None:
        raise AttributeError(
            f"card_impl for {collector_dir!r} has no class {class_name!r}"
        )
    return cls


def _detect_collector_dir_from_stack() -> str | None:
    """Detect the collector directory from the call stack."""
    import inspect

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
                part == "sos"
                and i > 0
                and parts[i - 1] == "audited"
                and i + 1 < len(parts)
            ):
                return parts[i + 1]
    return None


def _make_card_impl_module() -> types.ModuleType:
    """Create a synthetic card_impl module for the workspace."""
    mod = types.ModuleType("card_impl")
    mod.__doc__ = "Synthetic card_impl — resolves workspace card classes."
    mod.__file__ = "<synthetic:sos_workspace_conftest>"
    mod.__package__ = ""

    def _getattr(name: str) -> type:
        collector_dir = _detect_collector_dir_from_stack()
        if collector_dir is None:
            raise AttributeError(
                f"card_impl has no attribute {name!r} — cannot detect collector directory"
            )
        return _find_card_impl_class(collector_dir, name)

    mod.__getattr__ = _getattr  # type: ignore[attr-defined]
    return mod


# Inject the synthetic module at load time
sys.modules["card_impl"] = _make_card_impl_module()
