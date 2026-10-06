"""Known-Best gameplay regressions played at the table: enters triggers keep
what was fixed as they went on the stack, and combat damage follows the
creatures in combat (rule 510.4).

The checks import the workspace's own ``engine``, ``cards`` and
``test_interface``, so they run in a subprocess rooted at
``known_best/workspace``; the repo root is on the path for ``silverquillm.table``.
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


@pytest.mark.parametrize("checks", ["trigger_lifetime_checks.py", "combat_damage_checks.py", "targeted_trigger_checks.py",
                                    "reflexive_trigger_checks.py"])
def test_known_best_gameplay_regressions_pass(checks: str):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS / checks), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (WORKSPACE, REPO))), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
