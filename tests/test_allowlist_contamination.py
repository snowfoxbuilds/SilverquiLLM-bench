"""Tests for TODO item 11: Allowlist-based contamination checker.

Validates that _check_violations uses an allowlist approach:
- Files in workspace → allowed
- Files in engine/ → allowed
- Files outside workspace and engine/ → violation
- __pycache__, .pyc, .log files → ignored (no false positives)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.agent_session import (
    _check_violations,
    _is_allowed_path,
    _snapshot_all_protected,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_repo(tmp_path):
    """Create a fake repo root with protected and allowed directories."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # Protected dirs
    for dirname in ("cards", "tests", "silverquillm", "benchmarks", "docs"):
        d = repo / dirname
        d.mkdir()
        (d / "existing.py").write_text(f"# {dirname}\n")
    # Allowed dir: engine/
    engine = repo / "engine"
    engine.mkdir()
    (engine / "card.py").write_text("# engine card\n")
    # Create a nested test structure
    audited = repo / "tests" / "audited" / "sos" / "001"
    audited.mkdir(parents=True)
    (audited / "tests.py").write_text("# audited tests\n")
    return repo


@pytest.fixture()
def workspace(fake_repo):
    """Create a workspace directory inside the fake repo."""
    ws = fake_repo / ".workspace" / "card_001"
    ws.mkdir(parents=True)
    return ws


# ---------------------------------------------------------------------------
# Helper to run _check_violations against fake repo
# ---------------------------------------------------------------------------


def _run_check(fake_repo: Path, workspace: Path, modify_fn=None):
    """Snapshot, apply modifications, then check violations."""
    with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
        before = _snapshot_all_protected(fake_repo)
        if modify_fn:
            modify_fn()
            # Ensure mtime changes are detectable
            time.sleep(0.05)
        return _check_violations(workspace, before=before)


# ---------------------------------------------------------------------------
# 1-3: Allowed writes (no violations)
# ---------------------------------------------------------------------------


class TestAllowedWrites:
    """Files written in workspace or engine/ should not trigger violations."""

    def test_write_card_impl_in_workspace_no_violation(self, fake_repo, workspace):
        """Agent writes card_impl.py in workspace → no violation."""
        def modify():
            (workspace / "card_impl.py").write_text("class Card: pass\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert violations == []

    def test_write_tests_py_in_workspace_no_violation(self, fake_repo, workspace):
        """Agent writes tests.py in workspace → no violation."""
        def modify():
            (workspace / "tests.py").write_text("def test_foo(): pass\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert violations == []

    def test_modify_engine_card_py_no_violation(self, fake_repo, workspace):
        """Agent modifies engine/card.py → no violation (engine is allowed)."""
        def modify():
            (fake_repo / "engine" / "card.py").write_text("# modified engine card\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert violations == []

    def test_create_new_file_in_engine_no_violation(self, fake_repo, workspace):
        """Agent creates a new file in engine/ → no violation."""
        def modify():
            (fake_repo / "engine" / "new_helper.py").write_text("# new\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert violations == []


# ---------------------------------------------------------------------------
# 4, 8-9: Violations detected
# ---------------------------------------------------------------------------


class TestViolationsDetected:
    """Files outside workspace and engine/ should trigger violations."""

    def test_modify_audited_test_is_violation(self, fake_repo, workspace):
        """Agent modifies tests/audited/sos/001/tests.py → violation detected."""
        def modify():
            target = fake_repo / "tests" / "audited" / "sos" / "001" / "tests.py"
            target.write_text("# tampered\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) > 0
        assert any("tests" in v for v in violations)

    def test_modify_other_card_spec_is_violation(self, fake_repo, workspace):
        """Agent modifies another card's spec → violation detected.

        Uses os.utime() to explicitly bump mtime so the test is reliable
        on filesystems with coarse timestamp resolution.
        """
        other_card = fake_repo / "cards" / "other_card.json"
        other_card.write_text('{"name": "original"}\n')

        def modify():
            other_card.write_text('{"name": "tampered"}\n')
            # Explicitly bump mtime forward to avoid coarse-resolution flakiness
            st = other_card.stat()
            os.utime(other_card, (st.st_atime, st.st_mtime + 2))

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) > 0
        assert any("cards" in v for v in violations)

    def test_modify_docs_is_violation(self, fake_repo, workspace):
        """Agent modifies files in docs/ → violation."""
        def modify():
            (fake_repo / "docs" / "existing.py").write_text("# tampered\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) > 0

    def test_create_file_in_silverquillm_is_violation(self, fake_repo, workspace):
        """Agent creates file in silverquillm/ → violation."""
        def modify():
            (fake_repo / "silverquillm" / "backdoor.py").write_text("# evil\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) > 0

    def test_modify_file_outside_workspace_and_engine_is_violation(self, fake_repo, workspace):
        """Agent modifies files outside workspace AND engine → violation."""
        def modify():
            (fake_repo / "benchmarks" / "existing.py").write_text("# changed\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) > 0

    def test_create_file_in_scripts_is_violation(self, fake_repo, workspace):
        """Agent creates file in scripts/ → violation (expanded allowlist scope)."""
        scripts = fake_repo / "scripts"
        scripts.mkdir(exist_ok=True)

        def modify():
            (scripts / "helper.sh").write_text("#!/bin/bash\necho pwned\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) > 0
        assert any("scripts" in v for v in violations)

    def test_create_file_in_data_is_violation(self, fake_repo, workspace):
        """Agent creates file in data/ → violation (expanded allowlist scope)."""
        data = fake_repo / "data"
        data.mkdir(exist_ok=True)

        def modify():
            (data / "poisoned.csv").write_text("a,b,c\n1,2,3\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) > 0
        assert any("data" in v for v in violations)

    def test_create_file_at_repo_root_is_violation(self, fake_repo, workspace):
        """Agent creates file at repo root → violation."""
        def modify():
            (fake_repo / "malicious.py").write_text("# pwned\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) > 0
        assert any("malicious.py" in v for v in violations)


# ---------------------------------------------------------------------------
# 5-7: Ignored artefacts (no false positives)
# ---------------------------------------------------------------------------


class TestIgnoredArtefacts:
    """__pycache__, .pyc, and .log files should be ignored."""

    def test_pycache_files_ignored(self, fake_repo, workspace):
        """Agent creates __pycache__ files → no violation."""
        pycache = fake_repo / "tests" / "__pycache__"
        pycache.mkdir(exist_ok=True)

        def modify():
            (pycache / "test_foo.cpython-311.pyc").write_text("bytecode\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert violations == []

    def test_pyc_files_ignored(self, fake_repo, workspace):
        """Agent creates .pyc files → no violation."""
        def modify():
            (fake_repo / "tests" / "compiled.pyc").write_text("bytecode\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert violations == []

    def test_log_files_ignored(self, fake_repo, workspace):
        """Agent creates .log files → no violation."""
        def modify():
            (fake_repo / "tests" / "output.log").write_text("log data\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert violations == []


# ---------------------------------------------------------------------------
# 10: No changes
# ---------------------------------------------------------------------------


class TestNoChanges:
    """No file changes at all → no violations."""

    def test_no_changes_no_violations(self, fake_repo, workspace):
        """When nothing is modified, no violations should be reported."""
        violations = _run_check(fake_repo, workspace, modify_fn=None)
        assert violations == []


# ---------------------------------------------------------------------------
# 11-12: Multiple and mixed changes
# ---------------------------------------------------------------------------


class TestMultipleAndMixed:
    """Multiple violations are all reported; mixed changes flag only disallowed."""

    def test_multiple_violations_all_reported(self, fake_repo, workspace):
        """Multiple disallowed changes → all reported as violations."""
        def modify():
            (fake_repo / "docs" / "hack1.py").write_text("# hack1\n")
            (fake_repo / "cards" / "evil.py").write_text("# evil\n")
            (fake_repo / "tests" / "existing.py").write_text("# modified\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) >= 3

    def test_mixed_allowed_and_disallowed_only_disallowed_flagged(self, fake_repo, workspace):
        """Mixed changes: only disallowed files are reported as violations."""
        def modify():
            # Allowed: workspace file
            (workspace / "card_impl.py").write_text("# ok\n")
            # Allowed: engine file
            (fake_repo / "engine" / "card.py").write_text("# ok engine\n")
            # Disallowed: docs file
            (fake_repo / "docs" / "hack.py").write_text("# bad\n")
            # Ignored: log file
            (fake_repo / "tests" / "run.log").write_text("log\n")

        violations = _run_check(fake_repo, workspace, modify)
        assert len(violations) == 1
        assert any("docs" in v for v in violations)
        # Ensure workspace and engine files are NOT in violations
        for v in violations:
            assert "card_impl" not in v
            assert "engine" not in v
            assert ".log" not in v

    def test_no_before_snapshot_returns_empty(self, fake_repo, workspace):
        """When before snapshot is None, _check_violations returns empty list."""
        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            violations = _check_violations(workspace, before=None)
        assert violations == []


# ---------------------------------------------------------------------------
# _is_allowed_path unit tests
# ---------------------------------------------------------------------------


class TestIsAllowedPath:
    """Direct tests for _is_allowed_path helper."""

    def test_workspace_path_allowed(self, workspace):
        p = workspace / "card_impl.py"
        assert _is_allowed_path(p, workspace.resolve(), None, []) is True

    def test_engine_path_allowed(self, fake_repo, workspace):
        engine_resolved = (fake_repo / "engine").resolve()
        p = fake_repo / "engine" / "card.py"
        assert _is_allowed_path(p, workspace.resolve(), None, [engine_resolved]) is True

    def test_pycache_path_allowed(self, workspace):
        p = Path("/some/path/__pycache__/foo.pyc")
        assert _is_allowed_path(p, workspace.resolve(), None, []) is True

    def test_pyc_suffix_allowed(self, workspace):
        p = Path("/some/path/foo.pyc")
        assert _is_allowed_path(p, workspace.resolve(), None, []) is True

    def test_log_suffix_allowed(self, workspace):
        p = Path("/some/path/foo.log")
        assert _is_allowed_path(p, workspace.resolve(), None, []) is True

    def test_unrelated_path_not_allowed(self, workspace):
        p = Path("/some/random/path/evil.py")
        assert _is_allowed_path(p, workspace.resolve(), None, []) is False

    def test_protected_dir_path_not_allowed(self, fake_repo, workspace):
        p = fake_repo / "cards" / "evil.py"
        assert _is_allowed_path(p, workspace.resolve(), None, []) is False
