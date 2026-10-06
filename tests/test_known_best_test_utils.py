"""The Known-Best Workspace's ``test_utils`` — the Reference Tests' helper
module, built on the Test Interface's scripted player — keeps working.

``test_utils`` is the candidate's module, so these checks are not Audited
Tests. They import the workspace's own ``engine``, ``cards`` and
``test_utils``, so they run in a subprocess rooted at ``known_best/workspace``.
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


@pytest.mark.parametrize(
    "checks",
    [
        "helper_checks.py",
        "helper_extra_checks.py",
        "intent_player_checks.py",
        "intent_test_utils_checks.py",
    ],
)
def test_known_best_test_utils_checks_pass(checks: str):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS / checks), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": str(WORKSPACE), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
