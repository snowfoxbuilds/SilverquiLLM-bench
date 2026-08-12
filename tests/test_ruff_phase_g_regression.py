"""Ruff regression pin for the Phase G (replay-gap cadence) amended files.

The PR's verification contract is "zero NEW Ruff findings on the files it
touches, measured base-vs-head". This test makes that claim executable: it
runs Ruff (the repo config, ``ruff.toml``) over exactly the files Phase G
amended and asserts each file's per-rule finding count never exceeds the
count measured at the PR's base commit (``d5455415``, merged main). A finding
Phase G removed may stay removed (counts may only go down); any new rule code
on an amended file, or a count above the base budget, fails.

The budget below is the base-commit measurement (ruff 0.16.1): 111 findings
across the amended set. Head measured 101 — the 10 removed are pinned in the
PR description. If the repo's Ruff version/config changes and shifts these
numbers wholesale, re-measure the budget at the base SHA rather than loosening
entries ad hoc.
"""

from __future__ import annotations

import collections
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Every file the Phase G branch amends (base d5455415..head, *.py).
AMENDED_FILES = [
    "benchmarks/msh/workspace/cards/fdn/fdn_153/card_impl.py",
    "benchmarks/msh/workspace/cards/fdn/fdn_153/tests.py",
    "benchmarks/msh/workspace/cards/fdn/fdn_160/card_impl.py",
    "benchmarks/msh/workspace/cards/fdn/fdn_160/tests.py",
    "benchmarks/msh/workspace/cards/fdn/fdn_165/tests.py",
    "benchmarks/msh/workspace/cards/fdn/fdn_48/card_impl.py",
    "benchmarks/msh/workspace/cards/fdn/fdn_48/tests.py",
    "benchmarks/msh/workspace/cards/fdn/gainlife_taplands.py",
    "benchmarks/msh/workspace/engine/casting.py",
    "benchmarks/msh/workspace/engine/refs_registry.py",
    "benchmarks/msh/workspace/engine/stack.py",
    "benchmarks/msh/workspace/engine_tests/test_casting.py",
    "benchmarks/msh/workspace/engine_tests/test_gainlife_taplands.py",
    "benchmarks/msh/workspace/engine_tests/test_replay_simulate.py",
    "benchmarks/msh/workspace/engine_tests/test_stack.py",
    "silverquillm/replay/executor.py",
    "tests/test_replay_executor.py",
    "tests/test_ruff_phase_g_regression.py",
]

# (file, rule) -> finding count at the base commit. Files absent here (the
# new test files, this file) have a zero budget everywhere: they must be
# Ruff-clean.
BASE_BUDGET: dict[tuple[str, str], int] = {
    ("benchmarks/msh/workspace/cards/fdn/fdn_153/card_impl.py", "F401"): 7,
    ("benchmarks/msh/workspace/cards/fdn/fdn_153/card_impl.py", "I001"): 2,
    ("benchmarks/msh/workspace/cards/fdn/fdn_153/card_impl.py", "RUF100"): 1,
    ("benchmarks/msh/workspace/cards/fdn/fdn_160/card_impl.py", "F401"): 1,
    ("benchmarks/msh/workspace/cards/fdn/fdn_160/card_impl.py", "I001"): 1,
    ("benchmarks/msh/workspace/cards/fdn/fdn_160/card_impl.py", "RUF100"): 1,
    ("benchmarks/msh/workspace/cards/fdn/fdn_160/card_impl.py", "UP037"): 4,
    ("benchmarks/msh/workspace/cards/fdn/fdn_48/card_impl.py", "F401"): 2,
    ("benchmarks/msh/workspace/cards/fdn/fdn_48/card_impl.py", "RUF100"): 1,
    ("benchmarks/msh/workspace/cards/fdn/fdn_48/card_impl.py", "UP037"): 4,
    ("benchmarks/msh/workspace/cards/fdn/gainlife_taplands.py", "UP037"): 3,
    ("benchmarks/msh/workspace/engine/casting.py", "BLE001"): 1,
    ("benchmarks/msh/workspace/engine/casting.py", "F401"): 2,
    ("benchmarks/msh/workspace/engine/casting.py", "SIM103"): 2,
    ("benchmarks/msh/workspace/engine/refs_registry.py", "UP035"): 1,
    ("benchmarks/msh/workspace/engine/refs_registry.py", "UP037"): 1,
    ("benchmarks/msh/workspace/engine/stack.py", "UP035"): 1,
    ("benchmarks/msh/workspace/engine_tests/test_casting.py", "C401"): 1,
    ("benchmarks/msh/workspace/engine_tests/test_casting.py", "I001"): 2,
    ("benchmarks/msh/workspace/engine_tests/test_replay_simulate.py", "F401"): 1,
    ("benchmarks/msh/workspace/engine_tests/test_replay_simulate.py", "F841"): 4,
    ("benchmarks/msh/workspace/engine_tests/test_replay_simulate.py", "I001"): 5,
    ("benchmarks/msh/workspace/engine_tests/test_replay_simulate.py", "RUF007"): 1,
    ("benchmarks/msh/workspace/engine_tests/test_replay_simulate.py", "RUF012"): 1,
    ("benchmarks/msh/workspace/engine_tests/test_stack.py", "I001"): 2,
    ("benchmarks/msh/workspace/engine_tests/test_stack.py", "RUF059"): 6,
    ("silverquillm/replay/executor.py", "BLE001"): 16,
    ("silverquillm/replay/executor.py", "F401"): 7,
    ("silverquillm/replay/executor.py", "I001"): 5,
    ("silverquillm/replay/executor.py", "LOG014"): 1,
    ("silverquillm/replay/executor.py", "RUF012"): 6,
    ("silverquillm/replay/executor.py", "S110"): 2,
    ("silverquillm/replay/executor.py", "SIM102"): 4,
    ("tests/test_replay_executor.py", "F401"): 2,
    ("tests/test_replay_executor.py", "F821"): 5,
    ("tests/test_replay_executor.py", "I001"): 1,
    ("tests/test_replay_executor.py", "RUF012"): 1,
    ("tests/test_replay_executor.py", "RUF059"): 3,
}


class TestPhaseGRuffRegression:
    def test_amended_files_introduce_no_new_ruff_finding(self) -> None:
        ruff = shutil.which("ruff") or str(REPO_ROOT / "venv" / "bin" / "ruff")
        if not Path(ruff).exists():
            pytest.skip("ruff not installed")

        present = [f for f in AMENDED_FILES if (REPO_ROOT / f).exists()]
        proc = subprocess.run(
            [ruff, "check", "--output-format=json", *present],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,  # findings exit 1; asserted below
        )
        # Exit code 1 just means findings exist; anything else is a tool error.
        assert proc.returncode in (0, 1), proc.stderr

        counts: collections.Counter[tuple[str, str]] = collections.Counter()
        for item in json.loads(proc.stdout or "[]"):
            rel = str(Path(item["filename"]).resolve().relative_to(REPO_ROOT))
            counts[(rel, item["code"])] += 1

        over_budget = {
            key: (n, BASE_BUDGET.get(key, 0))
            for key, n in sorted(counts.items())
            if n > BASE_BUDGET.get(key, 0)
        }
        assert not over_budget, (
            "NEW Ruff findings on Phase G amended files (found > base budget): "
            f"{over_budget}"
        )
