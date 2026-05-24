"""Integration tests for stage_workspace — four-step copytree form.

Verifies:
- The staged directory matches benchmarks/sos/workspace/ byte-for-byte
  (source tree files like rulebook.md, test_utils.md are copytree integrity)
- Per-run overlay files (prompt.md, run_manifest.json) are written correctly
- A git repository is initialized with exactly one commit
- The source workspace structure is preserved intact
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from silverquillm.workspace import stage_workspace

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKSPACE_SRC = _REPO_ROOT / "benchmarks" / "sos" / "workspace"


@pytest.fixture()
def staged(tmp_path: Path):
    """Stage workspace and return (workspace, output) paths."""
    return stage_workspace(tmp_path)


class TestCopytreeIntegrity:
    """Staged tree must equal source tree (plus per-run overlay files)."""

    # Only files written per-run on top of the copytree
    _OVERLAY_FILES = {"prompt.md", "run_manifest.json"}

    def test_all_source_files_present_in_staged(self, staged):
        """Every file in benchmarks/sos/workspace/ must exist in staged workspace."""
        workspace, _ = staged
        for src_file in _WORKSPACE_SRC.rglob("*"):
            if "__pycache__" in str(src_file) or ".pytest_cache" in str(src_file):
                continue
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(_WORKSPACE_SRC)
            staged_file = workspace / rel
            assert staged_file.exists(), f"Missing staged file: {rel}"

    def test_source_files_byte_match(self, staged):
        """Non-overlay source files must be byte-for-byte identical to source."""
        workspace, _ = staged
        for src_file in _WORKSPACE_SRC.rglob("*"):
            if "__pycache__" in str(src_file) or ".pytest_cache" in str(src_file):
                continue
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(_WORKSPACE_SRC)
            # Skip files that the per-run overlay overwrites
            if str(rel) in self._OVERLAY_FILES:
                continue
            staged_file = workspace / rel
            assert staged_file.exists(), f"Missing: {rel}"
            assert src_file.read_bytes() == staged_file.read_bytes(), (
                f"Content mismatch: {rel}"
            )

    def test_rulebook_md_present_from_source_tree(self, staged):
        """rulebook.md exists in source tree and must be present after copytree."""
        workspace, _ = staged
        assert (workspace / "rulebook.md").is_file()

    def test_no_pycache_in_staged(self, staged):
        """__pycache__ directories must not be staged."""
        workspace, _ = staged
        pycache_dirs = list(workspace.rglob("__pycache__"))
        assert pycache_dirs == []

    def test_no_pytest_cache_in_staged(self, staged):
        """.pytest_cache must not be staged."""
        workspace, _ = staged
        cache_dirs = list(workspace.rglob(".pytest_cache"))
        assert cache_dirs == []


class TestPerRunOverlays:
    """Per-run files written on top of the copytree: prompt.md and run_manifest.json."""

    def test_prompt_md_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "prompt.md").is_file()

    def test_prompt_md_has_content(self, staged):
        workspace, _ = staged
        text = (workspace / "prompt.md").read_text()
        assert len(text) > 100

    def test_run_manifest_json_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "run_manifest.json").is_file()

    def test_run_manifest_json_is_valid(self, staged):
        workspace, _ = staged
        data = json.loads((workspace / "run_manifest.json").read_text())
        assert isinstance(data, dict)


class TestRunManifest:
    """run_manifest.json is a per-run overlay with run metadata."""

    def test_run_manifest_has_expected_keys(self, staged):
        """run_manifest.json should contain at minimum benchmark_set info."""
        workspace, _ = staged
        data = json.loads((workspace / "run_manifest.json").read_text())
        assert "benchmark_set" in data or "cards" in data or "timestamp" in data, (
            f"run_manifest.json has no recognizable metadata keys: {list(data.keys())}"
        )


class TestPreflightCheck:
    """Pre-flight assertion catches missing/empty workspace dir."""

    def test_missing_workspace_dir_raises(self, tmp_path, monkeypatch):
        import silverquillm.workspace as ws_mod
        fake_root = tmp_path / "empty_repo"
        fake_root.mkdir()
        monkeypatch.setattr(ws_mod, "_REPO_ROOT", fake_root)
        with pytest.raises(FileNotFoundError, match="missing or empty"):
            stage_workspace(tmp_path / "out")

    def test_empty_workspace_dir_raises(self, tmp_path, monkeypatch):
        import silverquillm.workspace as ws_mod
        fake_root = tmp_path / "repo"
        (fake_root / "benchmarks" / "sos" / "workspace").mkdir(parents=True)
        monkeypatch.setattr(ws_mod, "_REPO_ROOT", fake_root)
        with pytest.raises(FileNotFoundError, match="missing or empty"):
            stage_workspace(tmp_path / "out")


class TestGitInit:
    """Staged workspace must be a git repo with exactly one commit."""

    def test_staged_dir_is_git_repo(self, staged):
        """The staged workspace must contain a .git directory."""
        workspace, _ = staged
        assert (workspace / ".git").is_dir()

    def test_exactly_one_commit(self, staged):
        """git log --oneline should show exactly one commit."""
        workspace, _ = staged
        result = subprocess.run(
            ["git", "-C", str(workspace), "log", "--oneline"],
            capture_output=True, text=True, check=True,
        )
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        assert len(lines) == 1, (
            f"Expected exactly 1 commit, got {len(lines)}: {result.stdout}"
        )

    def test_working_tree_is_clean(self, staged):
        """After staging, no uncommitted changes should remain."""
        workspace, _ = staged
        result = subprocess.run(
            ["git", "-C", str(workspace), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        assert result.stdout.strip() == "", (
            f"Working tree not clean:\n{result.stdout}"
        )


class TestTopLevelEntries:
    """Staged workspace should contain expected top-level entries from source."""

    def test_engine_dir_present(self, staged):
        workspace, _ = staged
        assert (workspace / "engine").is_dir()

    def test_cards_dir_present(self, staged):
        workspace, _ = staged
        assert (workspace / "cards").is_dir()

    def test_tests_dir_present(self, staged):
        workspace, _ = staged
        assert (workspace / "tests").is_dir()

    def test_pytest_ini_present(self, staged):
        workspace, _ = staged
        assert (workspace / "pytest.ini").is_file()

    def test_agents_md_present(self, staged):
        workspace, _ = staged
        assert (workspace / "AGENTS.md").is_file()

    def test_project_map_present(self, staged):
        workspace, _ = staged
        assert (workspace / "PROJECT_MAP.md").is_file()
