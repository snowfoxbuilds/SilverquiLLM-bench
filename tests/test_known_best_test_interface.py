"""The Known-Best Workspace's Test Interface and the host-side table hold
(TEST-INTERFACE.md).

The checks import the workspace's own ``engine``, ``cards`` and
``test_interface``, so they run in a subprocess rooted at
``known_best/workspace``, where ``table`` lives too.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO / "known_best/workspace"
CHECKS = Path(__file__).resolve().parent / "known_best_checks/interface_checks.py"


def _pytest(target: Path, *paths: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(target), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (WORKSPACE, *paths))), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_known_best_test_interface_checks_pass():
    result = _pytest(CHECKS, REPO)
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]


def test_the_staged_demonstration_tests_pass():
    # Only the Workspace: the demonstrations use nothing from the host.
    result = _pytest(WORKSPACE / "test_test_interface.py")
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
