"""Known-Best engine checks that are not Audited Tests: they drive the
engine directly or test its internals, in positions no FDN card reaches
through play (ADR-018). They import the workspace's own ``engine`` and
``cards``, so they run in a subprocess rooted at ``known_best/workspace``.
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


@pytest.mark.parametrize("checks", sorted(p.name for p in CHECKS.glob("*_internal_checks.py")))
def test_known_best_engine_internal_checks_pass(checks: str):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS / checks), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": f"{WORKSPACE}{os.pathsep}{REPO}", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
