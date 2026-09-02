"""Platform test for the smoke benchmark (``benchmarks/smoke/``).

The smoke benchmark is a tiny, never-leaderboard-published FDN benchmark for
pipeline validation / candidate calibration. These tests:

- pin its structure (config identity + tier + `leaderboard.eligible: false`,
  the target cards reduced to stubs, the audited tree and pool present),
- pin the staged instructions to the smoke task (the three FDN target stubs —
  never a `cards/hob/` tree, which the smoke workspace does not have), and
- prove the audited suite is green against a **correct** implementation using
  the engine the smoke benchmark actually ships: the *smoke* workspace is
  copied to an isolated temporary overlay, only the three target
  `card_impl.py` stubs are replaced by hob-medium's known-good versions, and
  the copied audited suites run there — so a green smoke run means the
  pipeline works, not that the tests are trivially satisfiable, and a smoke
  engine that drifted from hob-medium's would be caught here.
"""

from __future__ import annotations

import ast
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE = REPO_ROOT / "benchmarks" / "smoke"
SMOKE_WS = SMOKE / "workspace"
AUDITED = SMOKE / "data" / "tests" / "audited" / "fdn"
HOB_WS = REPO_ROOT / "benchmarks" / "hob-medium" / "workspace"

TARGETS = ["fdn_129", "fdn_205", "fdn_232"]
TARGET_IMPL_PATHS = [f"cards/fdn/{t}/card_impl.py" for t in TARGETS]
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
# Staged instructions describe the smoke task
# ---------------------------------------------------------------------------


class TestSmokeStagedInstructions:
    """The agent-facing docs staged into the smoke container must describe the
    smoke task — verified at repository test time, before any candidate run
    can consume them."""

    @pytest.mark.parametrize("doc", ["AGENTS.md", "PROJECT_MAP.md"])
    def test_names_the_three_target_paths(self, doc: str) -> None:
        text = (SMOKE_WS / doc).read_text()
        for path in TARGET_IMPL_PATHS:
            assert path in text, f"{doc} must name the target {path}"

    @pytest.mark.parametrize("doc", ["AGENTS.md", "PROJECT_MAP.md", "test_utils.md"])
    def test_no_hob_task_language(self, doc: str) -> None:
        """The smoke workspace has no `cards/hob/` tree; instructions pointing
        candidates there describe a different benchmark."""
        text = (SMOKE_WS / doc).read_text()
        for pattern in (r"cards/hob", r"cards\.hob", r"implementing HOB", r"hob_<N>"):
            assert not re.search(pattern, text), f"{doc} still says {pattern!r}"

    def test_targets_are_writable_and_authoritative_tests_are_host_side(self) -> None:
        text = (SMOKE_WS / "AGENTS.md").read_text()
        assert "writable targets" in text
        assert "host-side" in text

    def test_no_stale_hand_maintained_test_list(self) -> None:
        """PROJECT_MAP.md defers to `find` for the FDN cards that ship a
        `tests.py`; it must not claim a list that discovery can contradict."""
        text = (SMOKE_WS / "PROJECT_MAP.md").read_text()
        assert "find cards/fdn -mindepth 2 -maxdepth 2 -name tests.py" in text
        for stale in ("listed below", "This is the canonical list"):
            assert stale not in text, f"PROJECT_MAP.md still says {stale!r}"

    def test_engine_envelope_matches_the_hob_contract(self) -> None:
        """Smoke calibrates the V2/HOB candidate contract, so its envelope
        language is the HOB one — tests-as-envelope, not additive-only."""
        text = (SMOKE_WS / "AGENTS.md").read_text()
        assert "no additive-only rule and no diff policing" in text
        assert not re.search(r"Additive-only|MUST NOT rename|no renaming, no refactoring", text)


# ---------------------------------------------------------------------------
# The audited suite is green against a correct implementation — on the
# smoke engine, in an isolated overlay
# ---------------------------------------------------------------------------


_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git")


def _build_overlay(root: Path) -> Path:
    """Copy the smoke workspace into ``root`` and overlay hob-medium's
    known-good implementations of the three targets. Also copy the targets'
    audited suites in, so the whole run is rooted inside the overlay (the
    workspace's own ``pytest.ini`` / ``conftest.py`` govern, exactly as they
    would for a candidate). Nothing under ``benchmarks/`` is touched."""
    ws = root / "workspace"
    shutil.copytree(SMOKE_WS, ws, ignore=_IGNORE)
    for t in TARGETS:
        shutil.copy2(HOB_WS / "cards" / "fdn" / t / "card_impl.py",
                     ws / "cards" / "fdn" / t / "card_impl.py")
        shutil.copytree(AUDITED / t, ws / "_audited" / t, ignore=_IGNORE)
    return ws


def _subprocess_env(ws: Path) -> dict[str, str]:
    """Environment for the overlay run: the overlay is the *only* PYTHONPATH
    entry, so neither the committed workspaces nor an inherited PYTHONPATH can
    supply ``engine`` / ``cards``."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = str(ws)
    return env


@pytest.fixture(scope="class")
def overlay() -> Iterator[Path]:
    """Isolated smoke-derived workspace; removed on success, failure, and
    interruption alike (``TemporaryDirectory`` cleans up in ``__exit__``)."""
    with tempfile.TemporaryDirectory(prefix="smoke-overlay-") as tmp:
        yield _build_overlay(Path(tmp))


class TestSmokeAuditedSuiteGreen:
    def test_overlay_is_the_smoke_workspace_plus_known_good_targets(
        self, overlay: Path,
    ) -> None:
        """The overlay engine is byte-identical to the committed *smoke*
        engine, and exactly the three targets differ from the committed smoke
        workspace — each now equal to hob-medium's non-stub implementation."""
        cmp = filecmp.dircmp(SMOKE_WS / "engine", overlay / "engine", ignore=["__pycache__"])
        assert not cmp.diff_files and not cmp.left_only and not cmp.right_only, (
            f"overlay engine drifted from the smoke engine: {cmp.diff_files} "
            f"{cmp.left_only} {cmp.right_only}"
        )
        for t in TARGETS:
            rel = Path("cards") / "fdn" / t / "card_impl.py"
            assert filecmp.cmp(HOB_WS / rel, overlay / rel, shallow=False)
            assert not filecmp.cmp(SMOKE_WS / rel, overlay / rel, shallow=False), (
                f"{rel} in the overlay is still the smoke stub"
            )
            assert "TODO: Implement" not in (overlay / rel).read_text()
        # The committed workspaces were not mutated.
        for t in TARGETS:
            src = (SMOKE_WS / "cards" / "fdn" / t / "card_impl.py").read_text()
            assert "TODO: Implement" in src, f"committed smoke stub {t} was modified"

    def test_subprocess_resolves_engine_from_the_overlay(self, overlay: Path) -> None:
        """Negative regression: the run's ``engine`` and ``cards`` come from
        the smoke-derived overlay — not from hob-medium's workspace, not from
        the committed smoke workspace, and not from a repo-level package."""
        probe = (
            "import engine, cards, test_utils\n"
            "from cards.fdn.fdn_129 import card_impl\n"
            "print(engine.__file__); print(cards.__file__); "
            "print(test_utils.__file__); print(card_impl.__file__)"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(overlay), env=_subprocess_env(overlay),
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        resolved = [Path(line).resolve() for line in result.stdout.split()]
        assert len(resolved) == 4, result.stdout
        for path in resolved:
            assert path.is_relative_to(overlay.resolve()), (
                f"{path} resolved outside the smoke-derived overlay"
            )
            assert not path.is_relative_to(HOB_WS.resolve())
            assert not path.is_relative_to(SMOKE_WS.resolve())

    def test_audited_tests_pass_against_reference_impls(self, overlay: Path) -> None:
        """Run the copied smoke audited suites inside the overlay: smoke engine,
        hob-medium's known-good target impls. A probe test in the same pytest
        process asserts ``engine.__file__`` is the overlay's, so a rewrite that
        pointed the run back at hob-medium's workspace would fail here too."""
        probe_dir = overlay / "_audited" / "_probe"
        probe_dir.mkdir()
        (probe_dir / "test_engine_origin.py").write_text(
            "from pathlib import Path\n"
            "import engine, cards\n"
            f"OVERLAY = Path({str(overlay.resolve())!r})\n"
            "def test_engine_is_the_overlay_engine():\n"
            "    assert Path(engine.__file__).resolve().is_relative_to(OVERLAY)\n"
            "    assert Path(cards.__file__).resolve().is_relative_to(OVERLAY)\n"
        )
        test_paths = [str(overlay / "_audited" / t / "tests.py") for t in TARGETS]
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                *test_paths, str(probe_dir / "test_engine_origin.py"),
                "-q", "--no-header", "--tb=short",
                "-p", "no:cacheprovider",
                "-c", str(overlay / "pytest.ini"),
                "--rootdir", str(overlay),
            ],
            cwd=str(overlay),
            env=_subprocess_env(overlay),
            capture_output=True,
            text=True,
            check=False,  # returncode asserted below
        )
        assert result.returncode == 0, (
            f"smoke audited suite failed on the smoke engine + reference impls "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
        # Sanity: the run collected the three target suites (each a substantive
        # behavioral suite, >=8 tests) plus the probe — never zero tests.
        m = re.search(r"(\d+) passed", result.stdout)
        assert m, f"no pass count in output:\n{result.stdout}"
        assert int(m.group(1)) >= 3 * 8 + 1, result.stdout
        assert "failed" not in result.stdout and "error" not in result.stdout.lower(), (
            result.stdout
        )
