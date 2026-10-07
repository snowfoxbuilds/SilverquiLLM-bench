"""Known-Best gameplay regressions played at the table: enters triggers keep
what was fixed as they went on the stack, combat damage follows the
creatures in combat (rule 510.4), additional costs are paid (rule 601.2h),
and control effects apply in dependency order and leave a permanent
summoning sick only when its controller changes (rules 613.8, 302.6), and a
spell copied after it left the stack keeps its own choices (rule 707.10). The
FDN Audited Tests also hold with every question's options reversed, and Etali's
free casts however the engine asks which spells to cast.

The checks import the workspace's own ``engine``, ``cards`` and
``test_interface``, so they run in a subprocess rooted at
``known_best/workspace``, where ``table`` lives too.
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
        "trigger_lifetime_checks.py",
        "combat_damage_checks.py",
        "targeted_trigger_checks.py",
        "reflexive_trigger_checks.py",
        "source_identity_checks.py",
        "departed_spell_copy_checks.py",
        "additional_cost_checks.py",
        "additional_cost_portability_checks.py",
        "reversed_option_checks.py",
        "optional_choice_presentation_checks.py",
        "made_object_label_checks.py",
        "control_effect_checks.py",
    ],
)
def test_known_best_gameplay_regressions_pass(checks: str):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS / checks), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (WORKSPACE, REPO))), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
