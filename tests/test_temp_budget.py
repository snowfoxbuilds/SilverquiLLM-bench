"""The retained-temp budget and the retention policy it relies on (#140)."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from .temp_budget import over_budget, tree_bytes

REPO = Path(__file__).resolve().parent.parent


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_passed_tests_tmp_paths_are_removed_at_teardown():
    options = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["pytest"]["ini_options"]
    assert options["tmp_path_retention_policy"] == "failed"


def test_tree_bytes_counts_nested_files_but_not_symlink_targets(tmp_path):
    _write(tmp_path / "a" / "one", 100)
    _write(tmp_path / "a" / "b" / "two", 50)
    (tmp_path / "a" / "link").symlink_to(tmp_path / "a" / "one")
    assert tree_bytes(tmp_path) == 150 + (tmp_path / "a" / "link").lstat().st_size


def test_within_budget_reports_nothing(tmp_path):
    _write(tmp_path / "small0" / "data", 100)
    assert over_budget(tmp_path, budget=100) == []


def test_over_budget_names_the_largest_directories(tmp_path):
    _write(tmp_path / "big0" / "data", 3 * 2**20)
    _write(tmp_path / "small0" / "data", 2**20)
    problems = over_budget(tmp_path, budget=2**20)
    assert "4 MiB" in problems[0] and "1 MiB budget" in problems[0]
    assert problems[1].endswith("big0") and problems[2].endswith("small0")


def test_xdist_worker_basetemps_are_looked_inside(tmp_path):
    _write(tmp_path / "popen-gw0" / "big0" / "data", 3 * 2**20)
    _write(tmp_path / "popen-gw1" / "small0" / "data", 2**20)
    (tmp_path / "popen-gw1" / "smallcurrent").symlink_to(tmp_path / "popen-gw1" / "small0")
    problems = over_budget(tmp_path, budget=2**20)
    assert "4 MiB" in problems[0]
    assert problems[1].endswith("popen-gw0/big0") and problems[2].endswith("popen-gw1/small0")
    assert len(problems) == 3


_GUARDED_PROJECT_CONFTEST = """
import tests.temp_budget as temp_budget

temp_budget.RETAINED_TEMP_BUDGET_BYTES = 1024

from tests.conftest import pytest_sessionfinish, pytest_terminal_summary  # noqa: E402,F401
"""

_GUARDED_PROJECT_TESTS = """
import pytest


@pytest.fixture(scope="module")
def kept(tmp_path_factory):
    path = tmp_path_factory.mktemp("kept")
    (path / "data").write_bytes(b"x" * {size})
    return path


@pytest.mark.parametrize("n", range(4))
def test_keeps(kept, n):
    assert kept.is_dir()
"""


@pytest.mark.parametrize("workers", [[], ["-n", "2"]], ids=["serial", "xdist"])
@pytest.mark.parametrize("size, fails", [(4096, True), (16, False)], ids=["over", "within"])
def test_the_session_guard_fails_a_passing_run_that_keeps_too_much(tmp_path, workers, size, fails):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pytest.ini").write_text("[pytest]\n")
    (project / "conftest.py").write_text(_GUARDED_PROJECT_CONFTEST)
    (project / "test_kept.py").write_text(_GUARDED_PROJECT_TESTS.format(size=size))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "--basetemp", str(tmp_path / "basetemp"), *workers],
        cwd=project,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")])},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = result.stdout + result.stderr
    assert "4 passed" in output, output
    if fails:
        assert result.returncode == pytest.ExitCode.TESTS_FAILED, output
        assert "temp footprint over budget" in output and "kept0" in output, output
    else:
        assert result.returncode == pytest.ExitCode.OK, output
