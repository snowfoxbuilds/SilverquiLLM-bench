"""Tests verifying audited tests relocation to benchmarks/sos/data/tests/audited/."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAuditedTestsRelocation:
    """Verify the structural move of tests/audited/ to benchmarks/sos/data/tests/audited/."""

    def test_old_audited_directory_does_not_exist(self) -> None:
        """The top-level tests/audited/ directory must no longer exist."""
        old_audited = REPO_ROOT / "tests" / "audited"
        assert not old_audited.exists(), (
            f"Old tests/audited/ directory still exists at {old_audited}"
        )

    def test_new_audited_fdn_directory_exists(self) -> None:
        """benchmarks/sos/data/tests/audited/fdn/ must exist."""
        fdn_dir = REPO_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn"
        assert fdn_dir.is_dir(), f"fdn/ directory not found at {fdn_dir}"

    def test_new_audited_fdn_contains_test_directories(self) -> None:
        """benchmarks/sos/data/tests/audited/fdn/ must contain card test directories."""
        fdn_dir = REPO_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn"
        subdirs = [p for p in fdn_dir.iterdir() if p.is_dir() and p.name.startswith("fdn_")]
        assert len(subdirs) > 0, (
            f"No fdn_* test directories found in {fdn_dir}"
        )

    def test_new_audited_sos_directory_exists(self) -> None:
        """benchmarks/sos/data/tests/audited/sos/ must exist."""
        sos_dir = REPO_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"
        assert sos_dir.is_dir(), f"sos/ directory not found at {sos_dir}"

    def test_new_audited_sos_contains_test_directories(self) -> None:
        """benchmarks/sos/data/tests/audited/sos/ must contain card test directories."""
        sos_dir = REPO_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"
        subdirs = [p for p in sos_dir.iterdir() if p.is_dir() and p.name.startswith("soa_")]
        assert len(subdirs) > 0, (
            f"No soa_* test directories found in {sos_dir}"
        )

    def test_evaluator_references_new_audited_path(self) -> None:
        """silverquillm/evaluator.py must reference the new audited tests path."""
        evaluator = REPO_ROOT / "silverquillm" / "evaluator.py"
        content = evaluator.read_text()
        # Must contain the new path
        assert "benchmarks" in content and "sos" in content and "data" in content, (
            "evaluator.py does not reference benchmarks/sos/data/ path"
        )
        # Specifically check the audited_sos and audited_fdn assignments
        assert 'benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"' in content or \
               'benchmarks/sos/data/tests/audited/sos' in content, (
            "evaluator.py does not reference new audited SOS path"
        )
        assert 'benchmarks" / "sos" / "data" / "tests" / "audited" / "fdn"' in content or \
               'benchmarks/sos/data/tests/audited/fdn' in content, (
            "evaluator.py does not reference new audited FDN path"
        )

    def test_evaluator_no_old_audited_path(self) -> None:
        """silverquillm/evaluator.py must NOT reference the old tests/audited path directly under repo root."""
        evaluator = REPO_ROOT / "silverquillm" / "evaluator.py"
        content = evaluator.read_text()
        # The old pattern was _REPO_ROOT / "tests" / "audited" / ...
        # The new pattern is _REPO_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited" / ...
        # We check that no line has REPO_ROOT / "tests" / "audited" without benchmarks prefix
        lines = content.split("\n")
        old_pattern_lines = [
            line for line in lines
            if '_REPO_ROOT / "tests" / "audited"' in line
            and '"benchmarks"' not in line
        ]
        assert len(old_pattern_lines) == 0, (
            f"evaluator.py still references old tests/audited path: {old_pattern_lines}"
        )

    def test_audited_test_files_use_correct_engine_imports(self) -> None:
        """Audited test files must use flat ``from engine.X`` imports.

        The legacy ``benchmarks.sos.workspace.engine`` prefix should not
        appear.
        """
        audited_dir = REPO_ROOT / "benchmarks" / "sos" / "data" / "tests" / "audited"
        result = subprocess.run(
            [
                "grep",
                "-rln",
                "--include=*.py",
                "-P",
                r"benchmarks\.sos\.workspace\.engine",
                str(audited_dir),
            ],
            capture_output=True,
            text=True,
        )
        stale_files = [f for f in result.stdout.strip().split("\n") if f]
        assert len(stale_files) == 0, (
            f"Found {len(stale_files)} audited test files with legacy "
            f"benchmarks.sos.workspace.engine prefix: {stale_files[:5]}"
        )
