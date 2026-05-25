"""Benchmark runner package.

Set-agnostic runner code for SilverquiLLM benchmark suites.
Individual benchmark sets live under ``benchmarks/{set_code}/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Workspace code (``engine``, ``cards``, ``tests``) is mounted at ``/workspace``
# in the agent container.  In the repo it lives at ``benchmarks/sos/workspace/``.
# Put it on sys.path so harness code can use the same flat imports
# (``from engine.card import …``) that the agent and pytest see.
_WORKSPACE = Path(__file__).resolve().parent.parent / "benchmarks" / "sos" / "workspace"
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

__all__: list[str] = []
