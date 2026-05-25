"""Regression test for the workspace_final snapshot crash class.

A prior run crashed in ``_harvest_results`` because the agent created a
recursive absolute symlink at ``workspace/benchmarks/sos/workspace`` to
satisfy the legacy ``benchmarks.sos.workspace.*`` import prefix. After the
container exited and the absolute target stopped resolving on the host,
``shutil.copytree`` errored with ``[Errno 2] No such file or directory``
when it tried to follow the dangling link.

The flat-import refactor removes the motivation for the symlink, but the
harvest also defensively excludes ``benchmarks/`` from the snapshot copy.
This test exercises that defense by staging a workspace with the exact
worst-case shape (a dangling absolute symlink under ``benchmarks/sos/``)
and asserting the harvest still completes.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from silverquillm.cli import _harvest_results


@pytest.fixture
def fake_workspace(tmp_path: Path) -> Path:
    """Build a minimal workspace tree with a dangling recursive symlink."""
    workspace = tmp_path / "workspace"
    (workspace / "cards" / "sos").mkdir(parents=True)
    (workspace / "engine").mkdir()
    (workspace / "engine" / "card.py").write_text("# stub\n")

    # Reproduce the crash shape: absolute symlink to a path that exists
    # inside the container (/workspace) but not on the host.
    nested = workspace / "benchmarks" / "sos"
    nested.mkdir(parents=True)
    (nested / "workspace").symlink_to("/workspace", target_is_directory=True)

    return workspace


def test_harvest_survives_dangling_recursive_symlink(
    fake_workspace: Path, tmp_path: Path
) -> None:
    """The harvest must complete even if ``workspace/benchmarks/`` contains a
    broken absolute symlink (the legacy crash trigger)."""
    output = tmp_path / "output"
    output.mkdir()
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    # If the ignore_patterns guard regresses, this call raises shutil.Error.
    run_dir = _harvest_results(
        workspace=fake_workspace,
        output=output,
        results_dir=results_dir,
        run_name="harvest-test",
        card_filter=[],  # skip per-card harvesting; we only care about the snapshot copy
    )

    workspace_final = run_dir / "workspace_final"
    assert workspace_final.is_dir()
    # The dangling-symlink path is excluded from the snapshot.
    assert not (workspace_final / "benchmarks" / "sos" / "workspace").exists()
    # Other workspace contents copied through fine.
    assert (workspace_final / "engine" / "card.py").is_file()
