"""``silverquillm audit check-promotion`` through the public CLI, with its checkout root unpatched.

The module's own tests pass ``main(repo_root=...)``; these run the command as an
operator does, so the root comes from the imported package.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.tools import REPO_ROOT

SMOKE_TEST = REPO_ROOT / "benchmarks" / "smoke" / "data" / "tests" / "audited" / "fdn" / "fdn_129" / "tests.py"


def _status() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--untracked-files=all", "--", "benchmarks"],
        capture_output=True, text=True, check=True,
    ).stdout


def _run(*args: str):
    return CliRunner().invoke(main, ["audit", "check-promotion", *args])


@pytest.fixture
def elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    workdir = tmp_path / "unrelated"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir


def test_the_root_is_the_checkout_the_package_comes_from() -> None:
    assert (REPO_ROOT / "silverquillm" / "__init__.py").is_file()
    assert (REPO_ROOT / "benchmarks").is_dir()


def test_a_valid_candidate_passes_all_three_checks_from_any_directory(elsewhere: Path) -> None:
    before = _status()
    result = _run(str(SMOKE_TEST), "--card", "fdn_129", "--bench", "smoke")
    assert result.exit_code == 0, result.output
    assert "[PASS] tier" in result.output
    assert "[PASS] canonical_api" in result.output
    assert "[PASS] oracle_gate" in result.output
    assert "VERDICT: ALLOWED" in result.output
    assert _status() == before


def test_a_missing_benchmark_is_rejected(elsewhere: Path) -> None:
    result = _run(str(SMOKE_TEST), "--card", "fdn_129", "--bench", "no-such-bench")
    assert result.exit_code != 0
    assert "VERDICT: REJECTED" in result.output


def test_a_failing_candidate_is_rejected(elsewhere: Path) -> None:
    before = _status()
    candidate = elsewhere / "tests.py"
    candidate.write_text("def test_fails():\n    assert False\n")
    result = _run(str(candidate), "--card", "fdn_129", "--bench", "smoke")
    assert result.exit_code != 0
    assert "[FAIL] oracle_gate" in result.output
    assert "VERDICT: REJECTED" in result.output
    assert _status() == before


def test_a_released_benchmark_is_refused(elsewhere: Path) -> None:
    result = _run(str(SMOKE_TEST), "--card", "fdn_129", "--bench", "hob-medium")
    assert result.exit_code != 0
    assert "[FAIL] tier" in result.output
    assert "VERDICT: REJECTED" in result.output
