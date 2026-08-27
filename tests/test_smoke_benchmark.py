"""Platform test for the smoke benchmark (``benchmarks/smoke/``).

The smoke benchmark is a tiny, never-leaderboard-published FDN benchmark for
pipeline validation / candidate calibration. These tests:

- pin its structure (config identity + tier + `leaderboard.eligible: false`,
  the target cards reduced to stubs, the audited tree and pool present), and
- prove the audited suite is green against a **correct** implementation — the
  target cards' audited tests run against the original hob-medium reference
  impls + the (shared) workspace engine — so a green smoke run means the
  pipeline works, not that the tests are trivially satisfiable.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE = REPO_ROOT / "benchmarks" / "smoke"
HOB_WS = REPO_ROOT / "benchmarks" / "hob-medium" / "workspace"

TARGETS = ["fdn_129", "fdn_205", "fdn_232"]
TARGET_CLASSES = {
    "fdn_129": "LeylineAxe",
    "fdn_205": "SeismicRupture",
    "fdn_232": "ScavengingOoze",
}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestSmokeConfig:
    def _config(self) -> dict:
        return json.loads((SMOKE / "config.json").read_text())

    def test_identity(self) -> None:
        cfg = self._config()
        assert cfg["id"] == "smoke"
        assert cfg["tier"] == "Beta"
        assert cfg["draft_set"]["primary_set_code"] == "FDN"
        assert cfg["cards"] == ["129", "205", "232"]

    def test_leaderboard_ineligible(self) -> None:
        """`leaderboard.eligible: false` is the never-published marker."""
        assert self._config()["leaderboard"]["eligible"] is False


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


class TestSmokeStructure:
    def test_workspace_is_a_full_hard_copy(self) -> None:
        # sibling benchmarks never share — smoke has its own engine + cards.
        assert (SMOKE / "workspace" / "engine").is_dir()
        assert (SMOKE / "workspace" / "engine_tests").is_dir()
        assert (SMOKE / "workspace" / "cards" / "fdn").is_dir()

    def test_pool_covers_the_targets(self) -> None:
        pool = json.loads((SMOKE / "data" / "pool.json").read_text())
        assert {c["collector_number"] for c in pool} == {"129", "205", "232"}
        for c in pool:
            assert c["name"] and c["type_line"]
            assert "mana_cost_str" in c and "oracle_text" in c

    def test_pool_spans_at_least_two_card_types(self) -> None:
        pool = json.loads((SMOKE / "data" / "pool.json").read_text())
        primaries = {c["type_line"].split("—")[0].strip().split()[-1] for c in pool}
        assert len(primaries) >= 2, f"targets should span >=2 types, got {primaries}"

    def test_audited_tree_holds_each_target_suite(self) -> None:
        for t in TARGETS:
            assert (SMOKE / "data" / "tests" / "audited" / "fdn" / t / "tests.py").is_file()

    def test_target_tests_were_moved_out_of_the_workspace(self) -> None:
        for t in TARGETS:
            assert not (SMOKE / "workspace" / "cards" / "fdn" / t / "tests.py").exists()

    def test_targets_are_stubs(self) -> None:
        """Each target impl is a bare CardImpl stub: class name pinned, TODO
        docstring, no behavior."""
        for t, cls in TARGET_CLASSES.items():
            src = (SMOKE / "workspace" / "cards" / "fdn" / t / "card_impl.py").read_text()
            tree = ast.parse(src)
            classdef = next(
                n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef) and n.name == cls
            )
            bases = {b.id for b in classdef.bases if isinstance(b, ast.Name)}
            assert "CardImpl" in bases, f"{cls} must subclass CardImpl"
            assert "TODO" in (ast.get_docstring(classdef) or "")
            methods = [
                n for n in classdef.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            assert not methods, f"{cls} stub should define no behavior"

    def test_only_the_targets_are_stubbed(self) -> None:
        """No non-target FDN card was accidentally reduced to a stub."""
        stubbed = [
            p.parent.name
            for p in (SMOKE / "workspace" / "cards" / "fdn").glob("*/card_impl.py")
            if "TODO: Implement" in p.read_text()
        ]
        assert sorted(stubbed) == sorted(TARGETS), f"unexpected stubs: {stubbed}"


# ---------------------------------------------------------------------------
# The audited suite is green against a correct implementation
# ---------------------------------------------------------------------------


class TestSmokeAuditedSuiteGreen:
    def test_audited_tests_pass_against_reference_impls(self) -> None:
        """Run the smoke audited suite against the original hob-medium reference
        impls (+ the shared workspace engine) via a sys.path fixture — proving
        the suite is green against a correct implementation."""
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(HOB_WS), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        test_paths = [
            str(SMOKE / "data" / "tests" / "audited" / "fdn" / t / "tests.py")
            for t in TARGETS
        ]
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest", *test_paths,
                "-q", "--no-header", "--tb=short",
                "-p", "no:cacheprovider",
                "--import-mode=importlib",
                "--rootdir", str(HOB_WS),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,  # returncode asserted below
        )
        assert result.returncode == 0, (
            f"smoke audited suite failed against reference impls "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
        # Sanity: the run actually collected the target suites, not zero tests.
        assert "passed" in result.stdout, result.stdout
