"""Mock agent adapter for deterministic smoke tests.

Provides a :class:`MockAdapter` that writes pre-baked implementations from
``cards/foundations/`` into the workspace without making any LLM calls.
Useful for end-to-end pipeline testing and ``--dry-run`` environment
validation.

The adapter can be configured to:
- Write a known-good ``card_impl.py`` from a foundations file.
- Optionally write a pre-baked ``tests.py`` (for ``impl_test`` mode).
- Sleep forever (to test timeout handling).
- Write nothing (to test ``no_output`` handling).
- Write to a protected path (to test violation detection).
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from silverquillm.adapters.base import AgentAdapter, register_adapter
from silverquillm.config import BenchmarkConfig

# Repo root — resolved once at import time (matches other adapters)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class MockAdapter(AgentAdapter):
    """Deterministic adapter that writes pre-baked implementations.

    Parameters
    ----------
    config:
        Benchmark configuration.
    card_name:
        Name of the foundations module to use (e.g. ``"simple_creatures"``).
        When ``None``, the adapter derives the name from the card spec.
    behavior:
        Controls adapter behavior:
        - ``"write"`` (default): write ``card_impl.py`` from foundations.
        - ``"write_with_tests"``: write both ``card_impl.py`` and ``tests.py``.
        - ``"timeout"``: sleep forever (tests timeout handling).
        - ``"no_output"``: write nothing (tests no_output handling).
        - ``"violation"``: write to a protected path.
    impl_source:
        Explicit source code for ``card_impl.py``.  When provided, overrides
        the foundations lookup.
    tests_source:
        Explicit source code for ``tests.py``.
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        card_name: str | None = None,
        behavior: str = "write",
        impl_source: str | None = None,
        tests_source: str | None = None,
    ) -> None:
        super().__init__(config)
        self.card_name = card_name
        self.behavior = behavior
        self.impl_source = impl_source
        self.tests_source = tests_source
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self) -> None:  # noqa: D401
        """No-op — mock adapter needs no setup."""

    def teardown(self) -> None:  # noqa: D401
        """No-op — mock adapter holds no resources."""

    def kill(self) -> None:
        """Unblock any waiting timeout behavior."""
        self._stop.set()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, prompt: str, workspace: Path) -> str:
        """Execute mock behavior in *workspace*.

        Returns a short string describing what the adapter did.
        """
        if self.behavior == "timeout":
            # Block until kill() sets the stop event or the strategy timeout fires
            self._stop.wait(timeout=86400)
            return ""

        if self.behavior == "no_output":
            # Remove any pre-seeded files so the harness detects no output
            for fname in ("card_impl.py", "tests.py"):
                seeded = workspace / fname
                if seeded.exists():
                    seeded.unlink()
            return "mock: no output written"

        if self.behavior == "violation":
            # Write to a protected path (outside workspace)
            protected = _REPO_ROOT / "cards" / "_mock_violation.py"
            protected.write_text("# violation test\n")
            # Also write a valid card_impl.py so files are still harvested
            self._write_impl(workspace)
            return "mock: violation written"

        if self.behavior in ("write", "write_with_tests"):
            self._write_impl(workspace)
            if self.behavior == "write_with_tests":
                self._write_tests(workspace)
            return "mock: implementation written"

        return f"mock: unknown behavior {self.behavior}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_card_name(self, workspace: Path) -> str | None:
        """Derive card name from the workspace's ``card_spec.json`` if not set."""
        if self.card_name is not None:
            return self.card_name
        spec_path = workspace / "card_spec.json"
        if spec_path.exists():
            try:
                spec = json.loads(spec_path.read_text())
                name = spec.get("name", "")
                # Convert card name to foundations filename convention:
                # "Mock Lightning Bolt" -> "mock_lightning_bolt"
                return name.lower().replace(" ", "_").replace("-", "_")
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def _write_impl(self, workspace: Path) -> None:
        """Write ``card_impl.py`` into the workspace."""
        if self.impl_source is not None:
            (workspace / "card_impl.py").write_text(self.impl_source)
            return

        # Look up from foundations
        foundations_dir = _REPO_ROOT / "cards" / "foundations"
        card_name = self._resolve_card_name(workspace)
        if card_name:
            src = foundations_dir / f"{card_name}.py"
            if src.exists():
                shutil.copy2(src, workspace / "card_impl.py")
                return

        # Fallback: write a minimal stub
        (workspace / "card_impl.py").write_text(
            "# Mock implementation\nclass MockCard:\n    pass\n"
        )

    def _write_tests(self, workspace: Path) -> None:
        """Write ``tests.py`` into the workspace."""
        if self.tests_source is not None:
            (workspace / "tests.py").write_text(self.tests_source)
            return

        # Default minimal test
        (workspace / "tests.py").write_text(
            "import pytest\n\ndef test_mock():\n    assert True\n"
        )


# Auto-register when module is imported
register_adapter("mock", MockAdapter)
