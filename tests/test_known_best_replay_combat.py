"""The replay executor declares combat through the query protocol on ported
engines (tests/known_best_checks/replay_combat_checks.py), run in a
subprocess inside each workspace so its ``engine`` package is the one
imported."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKS = REPO / "tests/known_best_checks/replay_combat_checks.py"


@pytest.mark.parametrize("workspace", ["known_best/workspace", "benchmarks/smoke/workspace"])
def test_replay_declares_combat_through_queries(workspace):
    root = REPO / workspace
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(root / "pytest.ini"), "--rootdir", str(root)],
        cwd=root, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": f"{root}{os.pathsep}{REPO}", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
