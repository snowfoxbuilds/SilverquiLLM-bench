"""The Known-Best Workspace declares attackers and blockers, divides combat
damage and orders triggered abilities through Player Queries
(DECISION-MODEL.md › Priority actions › Options › Combat declarations).

The checks import the workspace's own ``engine`` and ``test_utils``, so they
run in a subprocess rooted at ``known_best/workspace``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO / "known_best/workspace"
CHECKS = Path(__file__).resolve().parent / "known_best_checks"


@pytest.mark.parametrize("checks", ["combat_query_checks.py", "trigger_order_checks.py"])
def test_known_best_combat_query_checks_pass(checks):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS / checks), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": str(WORKSPACE), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
