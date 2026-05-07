"""Tests for TODO item 19: Capture engine diffs as per-card artifacts.

Tests verify:
- compute_engine_diff() returns empty patch when no engine changes.
- compute_engine_diff() detects modified files and produces valid unified diff.
- compute_engine_diff() detects new files added to engine.
- compute_engine_diff() detects deleted files from engine.
- Diff output uses valid unified diff format (--- / +++ / @@ markers).
- engine_diff.patch is written to the card's results directory.
- Empty patch file when no changes.
- Multiple files changed produces combined diff.
- Binary files are handled gracefully (noted, not diffed).
- save_engine_final() copies final engine state as run artifact.
- Edge cases: missing engine dirs, results dir auto-created.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.agent_session import compute_engine_diff, save_engine_final


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_dirs(tmp_path: Path):
    """Create workspace, run_engine, and results dirs."""
    workspace = tmp_path / "workspace"
    run_engine = tmp_path / "run_engine"
    results = tmp_path / "results"
    workspace.mkdir()
    run_engine.mkdir()
    results.mkdir()
    return workspace, run_engine, results


# ---------------------------------------------------------------------------
# No changes
# ---------------------------------------------------------------------------


class TestNoChanges:
    """Patch should be empty when card engine matches run engine."""

    def test_identical_files_produce_empty_patch(self, tmp_path: Path) -> None:
        """When engine files are identical, patch file should be empty."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (run_engine / "foo.py").write_text("print('hello')\n")
        (card_engine / "foo.py").write_text("print('hello')\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)

        assert patch_path == results / "engine_diff.patch"
        assert patch_path.exists()
        assert patch_path.read_text() == ""

    def test_both_engine_dirs_empty(self, tmp_path: Path) -> None:
        """Empty engines should produce an empty patch."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        (workspace / "engine").mkdir()

        patch_path = compute_engine_diff(workspace, run_engine, results)
        assert patch_path.read_text() == ""

    def test_no_card_engine_no_run_engine(self, tmp_path: Path) -> None:
        """When neither engine dir exists, patch should be empty."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run_engine = tmp_path / "run_engine"  # does not exist
        results = tmp_path / "results"

        patch_path = compute_engine_diff(workspace, run_engine, results)
        assert patch_path.exists()
        assert patch_path.read_text() == ""


# ---------------------------------------------------------------------------
# Modified files
# ---------------------------------------------------------------------------


class TestModifiedFiles:
    """Detect modifications and produce valid unified diffs."""

    def test_modified_file_produces_diff(self, tmp_path: Path) -> None:
        """A modified file should appear in the patch output."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (run_engine / "base.py").write_text("old line\n")
        (card_engine / "base.py").write_text("new line\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert content != ""
        assert "old line" in content
        assert "new line" in content

    def test_unified_diff_format_markers(self, tmp_path: Path) -> None:
        """Output must contain unified diff markers: ---, +++, @@."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (run_engine / "x.py").write_text("a\n")
        (card_engine / "x.py").write_text("b\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert "---" in content
        assert "+++" in content
        assert "@@" in content

    def test_diff_labels_include_engine_path(self, tmp_path: Path) -> None:
        """Diff labels should reference a/engine/ and b/engine/."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (run_engine / "utils.py").write_text("old\n")
        (card_engine / "utils.py").write_text("new\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert "a/engine/utils.py" in content
        assert "b/engine/utils.py" in content


# ---------------------------------------------------------------------------
# New files
# ---------------------------------------------------------------------------


class TestNewFiles:
    """Detect files added in the card engine but absent from run engine."""

    def test_new_file_appears_in_diff(self, tmp_path: Path) -> None:
        """A file only in card engine should show as added."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (card_engine / "new_module.py").write_text("print('new')\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert content != ""
        assert "new_module.py" in content
        assert "print('new')" in content

    def test_new_file_uses_dev_null_as_source(self, tmp_path: Path) -> None:
        """New files should diff from /dev/null."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (card_engine / "added.py").write_text("content\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert "/dev/null" in content


# ---------------------------------------------------------------------------
# Deleted files
# ---------------------------------------------------------------------------


class TestDeletedFiles:
    """Detect files present in run engine but removed from card engine."""

    def test_deleted_file_appears_in_diff(self, tmp_path: Path) -> None:
        """A file only in run engine should show as deleted."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (run_engine / "removed.py").write_text("old content\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert content != ""
        assert "removed.py" in content

    def test_deleted_file_uses_dev_null_as_target(self, tmp_path: Path) -> None:
        """Deleted files should diff to /dev/null."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (run_engine / "gone.py").write_text("bye\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert "/dev/null" in content


# ---------------------------------------------------------------------------
# Multiple files
# ---------------------------------------------------------------------------


class TestMultipleFiles:
    """Combined diff for multiple changes."""

    def test_multiple_files_combined(self, tmp_path: Path) -> None:
        """Changes to multiple files should all appear in one patch."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (run_engine / "a.py").write_text("old_a\n")
        (card_engine / "a.py").write_text("new_a\n")

        (run_engine / "b.py").write_text("old_b\n")
        (card_engine / "b.py").write_text("new_b\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert "a.py" in content
        assert "b.py" in content
        assert "old_a" in content
        assert "new_a" in content
        assert "old_b" in content
        assert "new_b" in content

    def test_mixed_add_modify_delete(self, tmp_path: Path) -> None:
        """Patch should handle a mix of added, modified, and deleted files."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        # Modified
        (run_engine / "mod.py").write_text("old\n")
        (card_engine / "mod.py").write_text("new\n")

        # Deleted
        (run_engine / "del.py").write_text("deleted\n")

        # Added
        (card_engine / "add.py").write_text("added\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert "mod.py" in content
        assert "del.py" in content
        assert "add.py" in content


# ---------------------------------------------------------------------------
# Binary files
# ---------------------------------------------------------------------------


class TestBinaryFiles:
    """Binary files should be handled gracefully."""

    def test_binary_modified_file_noted(self, tmp_path: Path) -> None:
        """Binary files should be noted as differing, not diffed line-by-line."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (run_engine / "data.bin").write_bytes(b"\x00\x01\x02")
        (card_engine / "data.bin").write_bytes(b"\x00\x01\x03")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert "data.bin" in content
        # Should mention binary, not produce unified diff hunks
        assert "Binary" in content or "binary" in content

    def test_new_binary_file_handled_gracefully(self, tmp_path: Path) -> None:
        """A new binary file should not crash; it should appear in output."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        (card_engine / "img.png").write_bytes(b"\x89PNG\x00\x00")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        # Should handle without crashing; file should be mentioned
        assert "img.png" in content


# ---------------------------------------------------------------------------
# Subdirectories
# ---------------------------------------------------------------------------


class TestSubdirectories:
    """Files in nested subdirectories should be handled."""

    def test_nested_file_in_diff(self, tmp_path: Path) -> None:
        """Changes to files in subdirectories should appear in the patch."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        card_engine = workspace / "engine"
        card_engine.mkdir()

        sub = run_engine / "sub" / "dir"
        sub.mkdir(parents=True)
        (sub / "nested.py").write_text("old\n")

        card_sub = card_engine / "sub" / "dir"
        card_sub.mkdir(parents=True)
        (card_sub / "nested.py").write_text("new\n")

        patch_path = compute_engine_diff(workspace, run_engine, results)
        content = patch_path.read_text()

        assert "sub/dir/nested.py" in content or "sub\\dir\\nested.py" in content


# ---------------------------------------------------------------------------
# Edge cases: results_dir auto-creation
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases around directory existence."""

    def test_results_dir_created_if_missing(self, tmp_path: Path) -> None:
        """Results dir should be auto-created if it doesn't exist."""
        workspace, run_engine, _ = _setup_dirs(tmp_path)
        (workspace / "engine").mkdir()
        results = tmp_path / "nonexistent" / "results"

        patch_path = compute_engine_diff(workspace, run_engine, results)

        assert results.is_dir()
        assert patch_path.exists()

    def test_return_value_is_patch_path(self, tmp_path: Path) -> None:
        """compute_engine_diff should return the path to engine_diff.patch."""
        workspace, run_engine, results = _setup_dirs(tmp_path)
        (workspace / "engine").mkdir()

        patch_path = compute_engine_diff(workspace, run_engine, results)

        assert patch_path.name == "engine_diff.patch"
        assert patch_path.parent == results


# ---------------------------------------------------------------------------
# save_engine_final
# ---------------------------------------------------------------------------


class TestSaveEngineFinal:
    """save_engine_final copies engine state as a run artifact."""

    def test_copies_engine_to_output_dir(self, tmp_path: Path) -> None:
        """Final engine state should be copied to output_dir/engine_final/."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "base.py").write_text("final content\n")
        output = tmp_path / "output"
        output.mkdir()

        result = save_engine_final(run_engine, output)

        assert result == output / "engine_final"
        assert result.is_dir()
        assert (result / "base.py").read_text() == "final content\n"

    def test_overwrites_existing_engine_final(self, tmp_path: Path) -> None:
        """If engine_final already exists, it should be replaced."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "new.py").write_text("new\n")

        output = tmp_path / "output"
        old_final = output / "engine_final"
        old_final.mkdir(parents=True)
        (old_final / "stale.py").write_text("stale\n")

        save_engine_final(run_engine, output)

        assert (output / "engine_final" / "new.py").exists()
        assert not (output / "engine_final" / "stale.py").exists()

    def test_preserves_subdirectory_structure(self, tmp_path: Path) -> None:
        """Subdirectories in the engine should be preserved."""
        run_engine = tmp_path / "run_engine"
        sub = run_engine / "sub"
        sub.mkdir(parents=True)
        (sub / "deep.py").write_text("deep\n")

        output = tmp_path / "output"
        output.mkdir()

        save_engine_final(run_engine, output)

        assert (output / "engine_final" / "sub" / "deep.py").read_text() == "deep\n"
