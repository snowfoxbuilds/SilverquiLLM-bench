"""Tests for _check_violations, _snapshot_all_protected, and _PROTECTED_DIRS.

Validates TODO item 1: Expand _check_violations to cover all protected
directories and return structured violations.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.agent_session import (
    _IGNORED_DIRS,
    _PROTECTED_DIRS,
    _check_violations,
    _snapshot_all_protected,
    _snapshot_mtimes,
)


# ---------------------------------------------------------------------------
# _PROTECTED_DIRS constant
# ---------------------------------------------------------------------------


class TestProtectedDirs:
    """Verify the _PROTECTED_DIRS constant covers all required directories."""

    def test_contains_all_required_dirs(self):
        required = {"cards", "tests", "silverquillm", "benchmarks", "docs"}
        assert set(_PROTECTED_DIRS) == required

    def test_is_tuple(self):
        assert isinstance(_PROTECTED_DIRS, tuple)


# ---------------------------------------------------------------------------
# _snapshot_all_protected
# ---------------------------------------------------------------------------


class TestSnapshotAllProtected:
    """Verify _snapshot_all_protected merges snapshots across protected dirs."""

    def test_snapshots_existing_protected_dirs(self, tmp_path):
        """Should snapshot files from multiple protected dirs that exist."""
        # Create some protected dirs with files
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "core.py").write_text("x")
        (tmp_path / "cards").mkdir()
        (tmp_path / "cards" / "card1.py").write_text("y")

        result = _snapshot_all_protected(tmp_path)

        assert tmp_path / "docs" / "core.py" in result
        assert tmp_path / "cards" / "card1.py" in result

    def test_skips_missing_dirs(self, tmp_path):
        """Should not error when a protected dir doesn't exist."""
        # Only create one dir
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "file.py").write_text("x")

        result = _snapshot_all_protected(tmp_path)

        # Should still have the docs file
        assert tmp_path / "docs" / "file.py" in result
        # Should not contain entries from non-existent dirs
        assert all("cards" not in str(p) or "docs" in str(p) for p in result)

    def test_empty_when_no_protected_dirs_exist(self, tmp_path):
        """Should return empty dict if none of the protected dirs exist."""
        result = _snapshot_all_protected(tmp_path)
        assert result == {}

    def test_includes_nested_files(self, tmp_path):
        """Should walk subdirectories within protected dirs."""
        (tmp_path / "docs" / "sub").mkdir(parents=True)
        (tmp_path / "docs" / "sub" / "nested.py").write_text("z")

        result = _snapshot_all_protected(tmp_path)

        assert tmp_path / "docs" / "sub" / "nested.py" in result


# ---------------------------------------------------------------------------
# _check_violations — no changes
# ---------------------------------------------------------------------------


class TestCheckViolationsNoChanges:
    """_check_violations returns empty list when nothing changed."""

    def test_returns_empty_list_when_nothing_changed(self, tmp_path):
        """If before == after, no violations should be reported."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "file.py").write_text("content")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert result == []

    def test_returns_empty_list_when_before_is_none(self, tmp_path):
        """When no before snapshot is provided, cannot detect violations."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        result = _check_violations(workspace, before=None)

        assert result == []


# ---------------------------------------------------------------------------
# _check_violations — detects created files
# ---------------------------------------------------------------------------


class TestCheckViolationsCreatedFiles:
    """_check_violations detects newly created files in protected dirs."""

    def test_detects_new_file_in_protected_dir(self, tmp_path):
        """A file created in a protected dir after snapshot should be flagged."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "existing.py").write_text("original")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        # Create a new file after the snapshot
        (tmp_path / "docs" / "new_file.py").write_text("injected")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert len(result) == 1
        assert "created" in result[0]
        assert "new_file.py" in result[0]

    def test_new_file_violation_contains_path(self, tmp_path):
        """Violation string should contain the path of the created file."""
        (tmp_path / "cards").mkdir()

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        (tmp_path / "cards" / "exploit.py").write_text("bad")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert any("exploit.py" in v for v in result)


# ---------------------------------------------------------------------------
# _check_violations — detects modified files
# ---------------------------------------------------------------------------


class TestCheckViolationsModifiedFiles:
    """_check_violations detects modified files in protected dirs."""

    def test_detects_modified_file_in_protected_dir(self, tmp_path):
        """A file modified after snapshot should be flagged as modified."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "core.py").write_text("original")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        # Ensure mtime changes
        time.sleep(0.05)
        (tmp_path / "docs" / "core.py").write_text("tampered")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert len(result) == 1
        assert "modified" in result[0]
        assert "core.py" in result[0]


# ---------------------------------------------------------------------------
# _check_violations — workspace exclusion
# ---------------------------------------------------------------------------


class TestCheckViolationsWorkspaceExclusion:
    """Files inside the workspace directory are NOT flagged."""

    def test_workspace_internal_changes_not_flagged(self, tmp_path):
        """Changes inside the workspace should be ignored even if it's a protected dir."""
        # Set up workspace inside a protected dir structure
        # The workspace IS inside the repo but changes there are expected
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "existing.py").write_text("ok")

        # Workspace is a subdir that could overlap with protected space
        workspace = tmp_path / "docs" / "workspace_area"
        workspace.mkdir()
        (workspace / "impl.py").write_text("before")

        before = _snapshot_all_protected(tmp_path)

        # Modify file inside workspace
        time.sleep(0.05)
        (workspace / "impl.py").write_text("after")
        # Also add new file inside workspace
        (workspace / "new.py").write_text("new")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert result == []

    def test_workspace_outside_protected_dirs(self, tmp_path):
        """A workspace outside protected dirs — protected dir changes still flagged."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "core.py").write_text("original")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        time.sleep(0.05)
        (tmp_path / "docs" / "core.py").write_text("hacked")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert len(result) == 1
        assert "modified" in result[0]


# ---------------------------------------------------------------------------
# _check_violations — multiple violations
# ---------------------------------------------------------------------------


class TestCheckViolationsMultiple:
    """Multiple violations (both created and modified) are all returned."""

    def test_returns_both_created_and_modified(self, tmp_path):
        """Should return violations for both new and modified files."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "existing.py").write_text("original")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        time.sleep(0.05)
        # Modify an existing file
        (tmp_path / "docs" / "existing.py").write_text("tampered")
        # Create a new file
        (tmp_path / "docs" / "injected.py").write_text("new code")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert len(result) == 2
        descriptions = " ".join(result)
        assert "modified" in descriptions
        assert "created" in descriptions

    def test_violations_across_multiple_protected_dirs(self, tmp_path):
        """Violations in different protected dirs are all detected."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "e.py").write_text("x")
        (tmp_path / "cards").mkdir()
        (tmp_path / "cards" / "c.py").write_text("y")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        time.sleep(0.05)
        (tmp_path / "docs" / "e.py").write_text("modified_x")
        (tmp_path / "cards" / "c.py").write_text("modified_y")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# Deletion detection
# ---------------------------------------------------------------------------


class TestCheckViolationsDeletion:
    """Deletion of a protected file outside the workspace is a violation."""

    def test_deleted_file_outside_workspace_is_violation(self, tmp_path):
        """Should detect deletion of a file in a protected directory."""
        (tmp_path / "docs").mkdir()
        protected_file = tmp_path / "docs" / "important.py"
        protected_file.write_text("do not delete")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        # Delete the protected file
        protected_file.unlink()

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert len(result) == 1
        assert "deleted" in result[0]
        assert "important.py" in result[0]

    def test_deleted_file_inside_workspace_is_not_violation(self, tmp_path):
        """Deleting a file inside the workspace should not be flagged."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        ws_file = workspace / "temp.py"
        ws_file.write_text("temporary")

        # Ensure workspace is treated as a protected dir for snapshotting
        (tmp_path / "docs").mkdir()

        before = _snapshot_all_protected(tmp_path)
        # Also add workspace file to before snapshot manually
        before[ws_file] = ws_file.stat().st_mtime

        ws_file.unlink()

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        # No violation since the deleted file is inside workspace
        assert result == []


# ---------------------------------------------------------------------------
# _IGNORED_DIRS — auto-generated cache directories are never contamination
# ---------------------------------------------------------------------------


class TestIgnoredDirs:
    """Files under _IGNORED_DIRS in protected dirs are not flagged."""

    def test_ignored_dirs_contains_pytest_cache(self):
        assert ".pytest_cache" in _IGNORED_DIRS

    def test_ignored_dirs_contains_pycache(self):
        assert "__pycache__" in _IGNORED_DIRS

    def test_pytest_cache_in_protected_dir_not_flagged(self, tmp_path):
        """Files created under .pytest_cache inside a protected dir are not violations."""
        (tmp_path / "tests").mkdir()
        cache_dir = tmp_path / "tests" / ".pytest_cache" / "v" / "cache"
        cache_dir.mkdir(parents=True)

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        # Simulate pytest writing its nodeids cache file
        (cache_dir / "nodeids").write_text("test_foo.py::test_bar")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert result == []

    def test_pycache_in_protected_dir_not_flagged(self, tmp_path):
        """Files created under __pycache__ inside a protected dir are not violations."""
        (tmp_path / "silverquillm").mkdir()
        pycache = tmp_path / "silverquillm" / "__pycache__"
        pycache.mkdir()

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        before = _snapshot_all_protected(tmp_path)

        (pycache / "module.cpython-312.pyc").write_bytes(b"\xfd\xf3\r\n")

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            result = _check_violations(workspace, before=before)

        assert result == []

    def test_snapshot_mtimes_prunes_ignored_dirs(self, tmp_path):
        """_snapshot_mtimes does not include files under _IGNORED_DIRS."""
        (tmp_path / ".pytest_cache").mkdir()
        (tmp_path / ".pytest_cache" / "nodeids").write_text("data")
        (tmp_path / "real_file.py").write_text("code")

        snap = _snapshot_mtimes(tmp_path)

        assert tmp_path / "real_file.py" in snap
        assert not any(".pytest_cache" in str(p) for p in snap)