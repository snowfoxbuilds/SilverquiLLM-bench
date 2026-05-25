"""Pytest bootstrap for the repo-level tests/ suite.

Puts the SOS workspace dir on ``sys.path`` so tests can use the same flat
imports (``from engine.X import …``, ``from cards.X import …``,
``from test_utils import …``) that the agent and the workspace's own pytest see.
"""
from __future__ import annotations

from silverquillm._bootstrap import ensure_workspace_on_path

ensure_workspace_on_path()
