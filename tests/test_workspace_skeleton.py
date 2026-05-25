"""Tests for TODO 1.1: workspace skeleton and static files."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def workspace() -> Path:
    """Return the workspace root directory."""
    return Path(__file__).resolve().parent.parent / "benchmarks" / "sos" / "workspace"


# ------------------------------------------------------------------
# Directory structure
# ------------------------------------------------------------------


class TestDirectoryStructure:
    """Verify the workspace directory tree exists."""

    def test_workspace_root_exists(self, workspace: Path):
        assert workspace.is_dir()

    def test_engine_dir_exists(self, workspace: Path):
        assert (workspace / "engine").is_dir()

    def test_cards_fdn_dir_exists(self, workspace: Path):
        assert (workspace / "cards" / "fdn").is_dir()

    def test_cards_sos_dir_exists(self, workspace: Path):
        assert (workspace / "cards" / "sos").is_dir()

    def test_tests_engine_dir_exists(self, workspace: Path):
        assert (workspace / "engine_tests").is_dir()


# ------------------------------------------------------------------
# Python package discovery (__init__.py files)
# ------------------------------------------------------------------


class TestPackageDiscovery:
    """__init__.py files exist for Python package discovery."""

    @pytest.mark.parametrize(
        "relpath",
        [
            "engine/__init__.py",
            "cards/__init__.py",
            "cards/fdn/__init__.py",
            "cards/sos/__init__.py",
            "engine_tests/__init__.py",
        ],
    )
    def test_init_file_exists(self, workspace: Path, relpath: str):
        assert (workspace / relpath).is_file()


# ------------------------------------------------------------------
# Static files existence
# ------------------------------------------------------------------


class TestStaticFilesExist:
    """The four required static files must exist."""

    @pytest.mark.parametrize(
        "filename",
        ["AGENTS.md", "PROJECT_MAP.md", "pytest.ini", ".gitignore"],
    )
    def test_file_exists(self, workspace: Path, filename: str):
        assert (workspace / filename).is_file()


# ------------------------------------------------------------------
# AGENTS.md content
# ------------------------------------------------------------------


class TestAgentsMd:
    """AGENTS.md must contain required orientation content."""

    @pytest.fixture()
    def content(self, workspace: Path) -> str:
        return (workspace / "AGENTS.md").read_text()

    def test_mentions_card_impl_py(self, content: str):
        assert "card_impl.py" in content

    def test_mentions_additive_only(self, content: str):
        assert "additive" in content.lower()

    def test_mentions_pytest(self, content: str):
        assert "pytest" in content.lower()

    def test_mentions_project_map(self, content: str):
        assert "PROJECT_MAP.md" in content

    def test_mentions_cards_sos_path(self, content: str):
        assert "cards/sos/" in content


# ------------------------------------------------------------------
# PROJECT_MAP.md content
# ------------------------------------------------------------------


class TestProjectMapMd:
    """PROJECT_MAP.md is a directory summary."""

    @pytest.fixture()
    def content(self, workspace: Path) -> str:
        return (workspace / "PROJECT_MAP.md").read_text()

    def test_not_empty(self, content: str):
        assert len(content.strip()) > 10

    def test_mentions_engine(self, content: str):
        assert "engine" in content

    def test_mentions_cards(self, content: str):
        assert "cards" in content


# ------------------------------------------------------------------
# pytest.ini content
# ------------------------------------------------------------------


class TestPytestIni:
    """pytest.ini must have correct settings."""

    @pytest.fixture()
    def content(self, workspace: Path) -> str:
        return (workspace / "pytest.ini").read_text()

    def test_timeout_30(self, content: str):
        assert "timeout = 30" in content or "timeout=30" in content

    def test_python_files_pattern(self, content: str):
        assert "test_*.py" in content

    def test_python_files_tests_py(self, content: str):
        assert "tests.py" in content


# ------------------------------------------------------------------
# .gitignore content
# ------------------------------------------------------------------


class TestGitignore:
    """`.gitignore` must cover the specified patterns."""

    @pytest.fixture()
    def content(self, workspace: Path) -> str:
        return (workspace / ".gitignore").read_text()

    @pytest.mark.parametrize(
        "pattern",
        [
            "__pycache__/",
            "*.pyc",
            ".pytest_cache/",
            "*.log",
            "*.jsonl",
            ".coverage",
            "htmlcov/",
            "decisions.md.tmp",
        ],
    )
    def test_pattern_present(self, content: str, pattern: str):
        assert pattern in content
