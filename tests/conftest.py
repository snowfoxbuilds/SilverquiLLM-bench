"""Pytest bootstrap for the repo-level tests/ suite.

Puts the SOS workspace dir on ``sys.path`` so tests can use the same flat
imports (``from engine.X import …``, ``from cards.X import …``,
``from test_utils import …``) that the agent and the workspace's own pytest see.
"""
from __future__ import annotations

import pytest

from silverquillm._bootstrap import ensure_workspace_on_path

ensure_workspace_on_path()


@pytest.fixture(autouse=True)
def _grader_docker_is_integration_only(request, monkeypatch):
    """Unit tests inject ``tests.grader_fixtures.local_grader()``; only integration tests reach Docker."""
    if request.node.get_closest_marker("integration"):
        return
    from silverquillm.karn import grader

    def refuse(*args, **kwargs):
        raise AssertionError("unit test reached the grader's Docker client; inject local_grader()")

    for name in ("run", "image_id", "build", "remove"):
        monkeypatch.setattr(grader.DockerRunner, name, refuse)
