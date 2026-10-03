"""Pytest bootstrap for the repo-level tests/ suite.

Puts the SOS workspace dir on ``sys.path`` so tests can use the same flat
imports (``from engine.X import …``, ``from cards.X import …``,
``from test_utils import …``) that the agent and the workspace's own pytest see.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm._bootstrap import ensure_workspace_on_path

from . import unit_environment
from .temp_budget import over_budget

ensure_workspace_on_path()

_BASETEMP = pytest.StashKey[Path]()
_OVER_BUDGET = pytest.StashKey[list[str]]()


@pytest.fixture(scope="session", autouse=True)
def _record_basetemp(request, tmp_path_factory):
    request.config.stash[_BASETEMP] = tmp_path_factory.getbasetemp()


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Fail a passing session that leaves more temp data behind than ``tests/temp_budget.py`` allows."""
    basetemp = session.config.stash.get(_BASETEMP, None)
    if exitstatus != pytest.ExitCode.OK or basetemp is None or not basetemp.is_dir():
        return
    problems = over_budget(basetemp)
    if problems:
        session.config.stash[_OVER_BUDGET] = problems
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    problems = config.stash.get(_OVER_BUDGET, None)
    if problems:
        terminalreporter.write_sep("=", "temp footprint over budget", red=True)
        for line in problems:
            terminalreporter.write_line(line)


@pytest.fixture(autouse=True)
def _unit_environment(request, monkeypatch):
    """Unit tests never reach the grader's Docker client and record a clean run provenance."""
    if not request.node.get_closest_marker("integration"):
        unit_environment.apply(monkeypatch)


@pytest.fixture(scope="session")
def plain_run(tmp_path_factory):
    """One successful simulated benchmark of the toy benchmark, built once; read it, never change it."""
    from .retained_runs import build_plain_run

    return build_plain_run(tmp_path_factory.mktemp("plain-run"))


@pytest.fixture
def plain_run_clone(plain_run, tmp_path):
    """A copy of ``plain_run`` for a test that changes its records or artifacts."""
    from .retained_runs import clone

    return clone(plain_run, tmp_path)


@pytest.fixture(scope="session")
def staged_sos_workspace(tmp_path_factory):
    """``stage_workspace(output_dir)`` of the SOS Workspace, staged once; read it, never change it."""
    from silverquillm.workspace import stage_workspace

    return stage_workspace(tmp_path_factory.mktemp("staged-sos"))
