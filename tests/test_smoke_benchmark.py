"""Platform test for the smoke benchmark (``benchmarks/smoke/``).

The smoke benchmark is a tiny, never-leaderboard-published FDN benchmark for
pipeline validation / candidate calibration. These tests:

- pin its structure (config identity + tier + `leaderboard.eligible: false`,
  the one target staged as its Known-Best implementation without flying, the
  audited tree and pool present),
- pin the staged instructions to the smoke task (add flying to the FDN target —
  never a `cards/hob/` tree, which the smoke workspace does not have), and
- prove the audited suite is green against a **correct** implementation using
  the engine the smoke benchmark actually ships: the *smoke* workspace is
  copied to an isolated temporary overlay, only the target `card_impl.py` is
  replaced by the Test Oracle Impl from smoke's Test Oracle Workspace, and the
  copied audited suite runs there — so a green smoke run means the pipeline
  works, and a smoke engine the target cannot work on would be caught here —
  and that it fails against the staged target, so a candidate that changes
  nothing scores nothing.
"""

from __future__ import annotations

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
ORACLE = SMOKE / "data" / "test_oracle_workspace"

TARGETS = ["fdn_142"]
TARGET_IMPL_PATHS = [f"cards/fdn/{t}/card_impl.py" for t in TARGETS]
STARTING_PATCH = SMOKE / "data" / "starting_patches" / "fdn_142.patch"
# The docstring silverquillm/tools/generate_printed_classes.py gives a face stub.
STUB_MARKER = "Implementation task: see card_spec.json."


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
        assert cfg["cards"] == ["142"]

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
        assert {c["collector_number"] for c in pool} == {"142"}
        for c in pool:
            assert c["name"] and c["type_line"]
            assert "mana_cost_str" in c and "oracle_text" in c

    def test_audited_tree_holds_each_target_suite(self) -> None:
        for t in TARGETS:
            assert (SMOKE / "data" / "tests" / "audited" / "fdn" / t / "tests.py").is_file()

    def test_target_tests_were_moved_out_of_the_workspace(self) -> None:
        for t in TARGETS:
            assert not (SMOKE / "workspace" / "cards" / "fdn" / t / "tests.py").exists()

    def test_target_is_the_known_best_hawk_without_flying(self) -> None:
        """The target is staged from its Starting Patch: the Test Oracle Impl
        with flying removed and nothing else changed."""
        staged = (SMOKE_WS / TARGET_IMPL_PATHS[0]).read_text()
        oracle = (ORACLE / TARGET_IMPL_PATHS[0]).read_text()
        assert "keywords=Keyword.FLYING | Keyword.LIFELINK," in oracle
        assert staged == oracle.replace(
            "keywords=Keyword.FLYING | Keyword.LIFELINK,", "keywords=Keyword.LIFELINK,"
        )
        assert STARTING_PATCH.is_file()

    def test_no_fdn_card_is_a_stub(self) -> None:
        """Every FDN card, the target included, is a filled implementation."""
        stubbed = [
            p.parent.name
            for p in (SMOKE_WS / "cards" / "fdn").glob("*/card_impl.py")
            if STUB_MARKER in p.read_text()
        ]
        assert stubbed == [], f"unexpected stubs: {stubbed}"


# ---------------------------------------------------------------------------
# Staged instructions describe the smoke task
# ---------------------------------------------------------------------------


class TestSmokeStagedInstructions:
    """The agent-facing docs staged into the smoke container must describe the
    smoke task — verified at repository test time, before any candidate run
    can consume them."""

    @pytest.mark.parametrize("doc", ["AGENTS.md", "PROJECT_MAP.md"])
    def test_names_the_target_path(self, doc: str) -> None:
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

    def test_names_the_writable_target(self) -> None:
        assert "writable target" in (SMOKE_WS / "AGENTS.md").read_text()

    def test_asks_for_flying(self) -> None:
        assert "Give it flying" in (SMOKE_WS / "AGENTS.md").read_text()

    def test_no_stale_hand_maintained_test_list(self) -> None:
        """PROJECT_MAP.md defers to `find` for the FDN cards that ship a
        `tests.py`; it must not claim a list that discovery can contradict."""
        text = (SMOKE_WS / "PROJECT_MAP.md").read_text()
        assert "find cards/fdn -mindepth 2 -maxdepth 2 -name tests.py" in text
        for stale in ("listed below", "This is the canonical list"):
            assert stale not in text, f"PROJECT_MAP.md still says {stale!r}"

    def test_engine_envelope_matches_the_hob_contract(self) -> None:
        """Smoke calibrates the V2/HOB candidate contract, so its envelope
        language is the HOB one: the engine is freely modifiable."""
        text = (SMOKE_WS / "AGENTS.md").read_text()
        assert "The engine is yours to change" in text
        assert not re.search(r"Additive-only|MUST NOT rename|no renaming, no refactoring", text)


# ---------------------------------------------------------------------------
# The audited suite is green against a correct implementation — on the
# smoke engine, in an isolated overlay
# ---------------------------------------------------------------------------


_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git")


def _build_overlay(root: Path, *, oracle: bool = True) -> Path:
    """Copy the smoke workspace into ``root``, overlay the target's Test Oracle
    Impl unless ``oracle`` is false, and copy the target's audited suite in, so
    the whole run is rooted inside the overlay (the workspace's own
    ``pytest.ini`` / ``conftest.py`` govern, exactly as they would for a
    candidate). Nothing under ``benchmarks/`` is touched."""
    ws = root / "workspace"
    shutil.copytree(SMOKE_WS, ws, ignore=_IGNORE)
    for t in TARGETS:
        if oracle:
            shutil.copy2(ORACLE / "cards" / "fdn" / t / "card_impl.py",
                         ws / "cards" / "fdn" / t / "card_impl.py")
        shutil.copytree(AUDITED / t, ws / "_audited" / t, ignore=_IGNORE)
    return ws


def _run_target_suites(ws: Path, *extra: Path) -> subprocess.CompletedProcess[str]:
    test_paths = [str(ws / "_audited" / t / "tests.py") for t in TARGETS]
    return subprocess.run(
        [
            sys.executable, "-m", "pytest",
            *test_paths, *map(str, extra),
            "-q", "--no-header", "--tb=short", "-rf",
            "-p", "no:cacheprovider",
            "-c", str(ws / "pytest.ini"),
            "--rootdir", str(ws),
        ],
        cwd=str(ws),
        env=_subprocess_env(ws),
        capture_output=True,
        text=True,
        check=False,  # returncode asserted by the caller
    )


def _subprocess_env(ws: Path) -> dict[str, str]:
    """Environment for the overlay run: the overlay (which holds ``table``,
    the Audited Test helpers), then the repo root; the repo root has no
    ``engine`` / ``cards``, so neither the committed workspaces nor an
    inherited PYTHONPATH can supply them."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = os.pathsep.join((str(ws), str(REPO_ROOT)))
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
        engine, and exactly the target differs from the committed smoke
        workspace — now equal to its Test Oracle Impl."""
        cmp = filecmp.dircmp(SMOKE_WS / "engine", overlay / "engine", ignore=["__pycache__"])
        assert not cmp.diff_files and not cmp.left_only and not cmp.right_only, (
            f"overlay engine drifted from the smoke engine: {cmp.diff_files} "
            f"{cmp.left_only} {cmp.right_only}"
        )
        for t in TARGETS:
            rel = Path("cards") / "fdn" / t / "card_impl.py"
            assert filecmp.cmp(ORACLE / rel, overlay / rel, shallow=False)
            assert not filecmp.cmp(SMOKE_WS / rel, overlay / rel, shallow=False), (
                f"{rel} in the overlay is still the staged target"
            )
        # The committed workspace was not mutated.
        for t in TARGETS:
            src = (SMOKE_WS / "cards" / "fdn" / t / "card_impl.py").read_text()
            assert "keywords=Keyword.LIFELINK," in src, f"committed smoke target {t} was modified"

    def test_subprocess_resolves_engine_from_the_overlay(self, overlay: Path) -> None:
        """Negative regression: the run's ``engine`` and ``cards`` come from
        the smoke-derived overlay — not from the Test Oracle Workspace, not from
        the committed smoke workspace, and not from a repo-level package."""
        probe = (
            "import engine, cards, test_utils\n"
            "from cards.fdn.fdn_142 import card_impl\n"
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
            assert not path.is_relative_to(ORACLE.resolve())
            assert not path.is_relative_to(SMOKE_WS.resolve())

    def test_audited_tests_pass_against_reference_impls(self, overlay: Path) -> None:
        """Run the copied smoke audited suite inside the overlay: smoke engine,
        the target's Test Oracle Impl. A probe test in the same pytest
        process asserts ``engine.__file__`` is the overlay's, so a rewrite that
        pointed the run back at the Test Oracle Workspace would fail here too."""
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
        result = _run_target_suites(overlay, probe_dir / "test_engine_origin.py")
        assert result.returncode == 0, (
            f"smoke audited suite failed on the smoke engine + reference impls "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
        # Sanity: the run collected the target suite (9 tests) plus the
        # probe — never zero tests.
        m = re.search(r"(\d+) passed", result.stdout)
        assert m, f"no pass count in output:\n{result.stdout}"
        assert int(m.group(1)) >= 9 + 1, result.stdout
        assert "failed" not in result.stdout and "error" not in result.stdout.lower(), (
            result.stdout
        )


class TestSmokeStagedTargetFails:
    def test_audited_suite_fails_without_flying(self, tmp_path: Path) -> None:
        """A candidate that leaves the staged target alone does not implement
        it: the flying tests fail, and the lifelink-only tests still pass."""
        result = _run_target_suites(_build_overlay(tmp_path, oracle=False))
        assert result.returncode == 1, result.stdout + result.stderr
        failed = set(re.findall(r"^FAILED \S+::(\w+)", result.stdout, re.MULTILINE))
        assert failed == {
            "test_has_flying_and_lifelink",
            "test_ground_creature_cannot_block_flying_attacker",
        }, result.stdout
        assert "7 passed" in result.stdout, result.stdout
