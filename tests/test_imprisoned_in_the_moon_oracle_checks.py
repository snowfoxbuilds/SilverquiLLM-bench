"""Imprisoned in the Moon's internal checks against the Test Oracle Workspaces
that carry its Known-Best fix by hand: the Known-Best checks against smoke's
and fra-hard-v2's, and the copy-lifecycle checks against fra-hard-v2's, the
only one with copy effects. Like the Known-Best internal checks they import
the workspace's own ``engine`` and ``cards``, so they run in a subprocess
rooted at that workspace.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
KNOWN_BEST_CHECKS = TESTS / "known_best_checks/fdn_156_internal_checks.py"
COPY_CHECKS = TESTS / "oracle_checks/fra_hard_v2_fdn_156_copy_checks.py"


@pytest.mark.parametrize(("benchmark", "checks"), [
    ("smoke", KNOWN_BEST_CHECKS),
    ("fra-hard-v2", KNOWN_BEST_CHECKS),
    ("fra-hard-v2", COPY_CHECKS),
])
def test_imprisoned_in_the_moon_oracle_checks_pass(benchmark: str, checks: Path):
    workspace = REPO / "benchmarks" / benchmark / "data/test_oracle_workspace"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(checks), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(workspace / "pytest.ini"), "--rootdir", str(workspace)],
        cwd=workspace, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": f"{workspace}{os.pathsep}{REPO}", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
