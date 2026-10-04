"""The Known-Best Workspace's printed identity holds (DECISION-MODEL.md › Printed identity).

The checks import the workspace's own ``engine`` and ``cards`` packages, so they
run in a subprocess rooted at ``known_best/workspace``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO / "known_best/workspace"
CHECKS = Path(__file__).resolve().parent / "known_best_checks/printed_identity_checks.py"


def test_known_best_printed_identity_checks_pass():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": str(WORKSPACE), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
