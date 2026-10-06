"""Known-Best tests place, choose, route and assert by predefined classes, never by
a name string (DECISION-MODEL.md › Printed identity › No raw strings; ADR-017).

``scripts/printed_identity_codemod.py --check`` is the enforcement: it fails while
any Known-Best test still passes a card name to a test_utils helper, matches a
``name`` attr in a Decision or GameRef pattern, chooses a mode by name, or
compares an object's name with a predefined card's name. The behavioural checks
run in a subprocess rooted at ``known_best/workspace`` because they import the
workspace's own ``engine`` and ``test_utils``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO / "known_best/workspace"
CODEMOD = REPO / "scripts/printed_identity_codemod.py"
CHECKS = Path(__file__).resolve().parent / "known_best_checks/printed_identity_routing_checks.py"
KNOWN_BEST_TESTS = (
    REPO / "known_best/data/tests/audited",
    WORKSPACE / "cards",
    *sorted((REPO / "tests/known_best_checks").glob("*_checks.py")),
)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd, capture_output=True, text=True, timeout=600, check=False,
        env={**os.environ, "PYTHONPATH": str(WORKSPACE), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_known_best_tests_identify_cards_by_predefined_class():
    result = _run(
        [str(CODEMOD), "--workspace", str(WORKSPACE), "--check", *map(str, KNOWN_BEST_TESTS)],
        cwd=REPO,
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]


def test_known_best_printed_routing_checks_pass():
    result = _run(
        ["-m", "pytest", str(CHECKS), "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
         "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE)],
        cwd=WORKSPACE,
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
