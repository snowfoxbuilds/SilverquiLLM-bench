"""Pytest bootstrap for the repo-level tests/ suite.

Adds the SOS workspace dir to ``sys.path`` so tests can use the same flat
imports (``from engine.X import …``, ``from cards.X import …``) that the
agent and the workspace's own pytest see.
"""
from __future__ import annotations

import sys
from pathlib import Path

_WORKSPACE = Path(__file__).resolve().parent.parent / "benchmarks" / "sos" / "workspace"
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))
