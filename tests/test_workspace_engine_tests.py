"""Tests for engine test staging into workspace (ADR-006)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.workspace import stage_workspace, _PROMPT_TEXT


@pytest.fixture()
def staged(tmp_path: Path):
    """Run stage_workspace and return (workspace, output) paths."""
    return stage_workspace(tmp_path)


@pytest.fixture()
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------
# Engine tests ARE staged
# ------------------------------------------------------------------


class TestEngineTestsStaged:
    """Engine regression tests must be staged into workspace/tests/engine/."""

    def test_tests_engine_directory_exists(self, staged):
        workspace, _ = staged
        assert (workspace / "tests" / "engine").is_dir()

    def test_engine_test_files_are_present(self, staged, repo_root):
        """At least some .py test files from tests/engine/ are staged."""
        workspace, _ = staged
        staged_dir = workspace / "tests" / "engine"
        staged_files = list(staged_dir.glob("*.py"))
        assert len(staged_files) > 0, "No .py files staged in tests/engine/"

    def test_staged_files_match_source(self, staged, repo_root):
        """Every .py file in source tests/engine/ should appear in workspace."""
        workspace, _ = staged
        src_dir = repo_root / "tests" / "engine"
        staged_dir = workspace / "tests" / "engine"
        src_files = {f.name for f in src_dir.glob("*.py") if f.name != "__init__.py" or True}
        staged_files = {f.name for f in staged_dir.glob("*.py")}
        # All source files should be staged (except __pycache__ contents)
        for f in src_files:
            assert f in staged_files, f"Source file {f} not found in staged tests/engine/"


# ------------------------------------------------------------------
# __pycache__ and .pyc excluded
# ------------------------------------------------------------------


class TestPycacheExcluded:
    """__pycache__ dirs and .pyc files must not be staged."""

    def test_no_pycache_directory(self, staged):
        workspace, _ = staged
        staged_dir = workspace / "tests" / "engine"
        pycache_dirs = list(staged_dir.rglob("__pycache__"))
        assert pycache_dirs == [], f"Found __pycache__: {pycache_dirs}"

    def test_no_pyc_files(self, staged):
        workspace, _ = staged
        staged_dir = workspace / "tests" / "engine"
        pyc_files = list(staged_dir.rglob("*.pyc"))
        assert pyc_files == [], f"Found .pyc files: {pyc_files}"


# ------------------------------------------------------------------
# FDN and SOS tests NOT staged
# ------------------------------------------------------------------


class TestFdnSosNotStaged:
    """FDN and SOS card tests must NOT be staged into workspace."""

    def test_no_fdn_tests_in_workspace(self, staged):
        workspace, _ = staged
        assert not (workspace / "tests" / "audited" / "fdn").exists()

    def test_no_sos_tests_in_workspace(self, staged):
        workspace, _ = staged
        assert not (workspace / "tests" / "audited" / "sos").exists()

    def test_no_audited_directory_at_all(self, staged):
        workspace, _ = staged
        assert not (workspace / "tests" / "audited").exists()


# ------------------------------------------------------------------
# Prompt contains no-modify rule
# ------------------------------------------------------------------


class TestPromptNoModifyRule:
    """Prompt must instruct agent not to modify staged tests."""

    def test_prompt_text_contains_no_modify_instruction(self):
        assert "do not modify" in _PROMPT_TEXT.lower() or "Do not modify" in _PROMPT_TEXT

    def test_prompt_text_references_workspace_tests_engine(self):
        assert "workspace/tests/engine/" in _PROMPT_TEXT or "workspace/tests/engine" in _PROMPT_TEXT

    def test_staged_prompt_file_contains_no_modify(self, staged):
        workspace, _ = staged
        prompt = (workspace / "prompt.md").read_text(encoding="utf-8")
        assert "Do not modify" in prompt or "do not modify" in prompt.lower()


# ------------------------------------------------------------------
# Graceful handling when source doesn't exist
# ------------------------------------------------------------------


class TestGracefulMissing:
    """If tests/engine/ doesn't exist in repo, staging should not crash."""

    def test_no_crash_when_source_missing(self, tmp_path, monkeypatch):
        """stage_workspace should not raise if tests/engine/ is absent."""
        import silverquillm.workspace as ws_mod

        # Point _REPO_ROOT to a fake dir that has no tests/engine/
        fake_root = tmp_path / "fake_repo"
        fake_root.mkdir()
        # Create minimal structure needed for stage_workspace to work
        (fake_root / "engine").mkdir()
        (fake_root / "engine" / "card.py").write_text("# stub")
        (fake_root / "cards" / "sos").mkdir(parents=True)
        (fake_root / "cards" / "fdn").mkdir(parents=True)
        (fake_root / "docs").mkdir()
        (fake_root / "docs" / "test_utils.md").write_text("# stub")
        (fake_root / "benchmarks" / "sos" / "data").mkdir(parents=True)
        (fake_root / "benchmarks" / "sos" / "data" / "comprehensive_rules.txt").write_text("rules")
        (fake_root / "benchmarks" / "sos" / "data" / "rules_overview.md").write_text("overview")

        out_dir = tmp_path / "run_output"
        out_dir.mkdir()

        monkeypatch.setattr(ws_mod, "_REPO_ROOT", fake_root)
        # Should not raise
        workspace, output = stage_workspace(out_dir)
        # tests/engine/ should simply not exist
        assert not (workspace / "tests" / "engine").exists()
