"""The retained-temp budget and the retention policy it relies on (#140)."""

from __future__ import annotations

import tomllib
from pathlib import Path

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
