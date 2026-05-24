"""CI-time workspace structure test.

Asserts that benchmarks/sos/workspace/ contains the expected top-level
entries.  Replaces per-file hard-error enumeration that used to live in
stage_workspace() — drift is now caught at PR-review time rather than at
run time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent / "benchmarks" / "sos" / "workspace"

EXPECTED_DIRS = [
    "engine",
    "cards/fdn",
    "cards/sos",
    "tests",
]

EXPECTED_FILES = [
    "AGENTS.md",
    "PROJECT_MAP.md",
    "rulebook.md",
    "pytest.ini",
    ".gitignore",
]


@pytest.mark.parametrize("relpath", EXPECTED_DIRS)
def test_required_directory_exists(relpath: str) -> None:
    """Each required directory must be present in the workspace."""
    target = WORKSPACE / relpath
    assert target.is_dir(), f"Missing required directory: {relpath}"


@pytest.mark.parametrize("relpath", EXPECTED_FILES)
def test_required_file_exists(relpath: str) -> None:
    """Each required file must be present in the workspace."""
    target = WORKSPACE / relpath
    assert target.is_file(), f"Missing required file: {relpath}"
