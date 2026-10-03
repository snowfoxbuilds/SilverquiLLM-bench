"""Pytest bootstrap for the repo-level tests/ suite.

Puts the SOS workspace dir on ``sys.path`` so tests can use the same flat
imports (``from engine.X import …``, ``from cards.X import …``,
``from test_utils import …``) that the agent and the workspace's own pytest see.
"""

from __future__ import annotations

import pytest

from silverquillm._bootstrap import ensure_workspace_on_path

from .temp_budget import over_budget

ensure_workspace_on_path()

_OVER_BUDGET = pytest.StashKey[list[str]]()


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Fail a passing session that leaves more temp data behind than ``tests/temp_budget.py`` allows.

    Under pytest-xdist each worker's basetemp is a ``popen-gw<N>`` directory inside the
    controller's, and a worker's exit status never reaches the run's, so only the controller
    (or a serial session) checks, once, over the whole tree.
    """
    if exitstatus != pytest.ExitCode.OK or hasattr(session.config, "workerinput"):
        return
    # The same factory pytest-xdist reads to place each worker's basetemp.
    basetemp = session.config._tmp_path_factory.getbasetemp()
    if not basetemp.is_dir():
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
def _grader_docker_is_integration_only(request, monkeypatch):
    """Unit tests inject ``tests.grader_fixtures.local_grader()``; only integration tests reach Docker."""
    if request.node.get_closest_marker("integration"):
        return
    from silverquillm.karn import grader

    def refuse(*args, **kwargs):
        raise AssertionError("unit test reached the grader's Docker client; inject local_grader()")

    for name in ("run", "image_id", "image_python", "build", "remove"):
        monkeypatch.setattr(grader.DockerRunner, name, refuse)


#: The provenance a clean run records; unit tests run from checkouts with work in progress.
CLEAN_PROVENANCE = {
    "host_label": "test-host",
    "host_label_source": "env",
    "bench": {"commit": "0" * 40, "dirty": False},
    "benchmark_root": {"commit": "0" * 40, "dirty": False},
    "recipe_revision": "1" * 40,
    "allow_dirty": False,
    "dirty_reasons": [],
}


@pytest.fixture(autouse=True)
def _runs_record_clean_provenance(request, monkeypatch):
    """Runs built in unit tests record a clean provenance instead of inspecting this checkout.

    ``tests/test_karn_provenance.py`` exercises the real rule directly.
    """
    if request.node.get_closest_marker("integration"):
        return
    from silverquillm.karn import execution

    monkeypatch.setattr(
        execution,
        "collect_provenance",
        lambda labels, bench_root, *, allow_dirty: {**CLEAN_PROVENANCE, "allow_dirty": allow_dirty},
    )
