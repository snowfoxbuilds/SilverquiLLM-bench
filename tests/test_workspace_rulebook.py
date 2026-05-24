"""Tests for TODO 1.2: rulebook.md lives in the workspace."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.fixture()
def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture()
def workspace(repo_root: Path) -> Path:
    """Return the workspace root directory."""
    return repo_root / "benchmarks" / "sos" / "workspace"


@pytest.fixture()
def rulebook(workspace: Path) -> Path:
    """Return the rulebook path."""
    return workspace / "rulebook.md"


# ------------------------------------------------------------------
# Existence
# ------------------------------------------------------------------


class TestRulebookExists:
    """rulebook.md must exist at the correct workspace path."""

    def test_rulebook_exists(self, rulebook: Path):
        assert rulebook.is_file(), "benchmarks/sos/workspace/rulebook.md must exist"

    def test_no_rulebook_at_repo_root(self, repo_root: Path):
        assert not (repo_root / "rulebook.md").exists(), (
            "rulebook.md should not exist at the repo root"
        )

    def test_no_rulebook_in_docs(self, repo_root: Path):
        assert not (repo_root / "docs" / "rulebook.md").exists(), (
            "rulebook.md should not exist in docs/"
        )

    def test_no_rulebook_in_benchmarks_root(self, repo_root: Path):
        assert not (repo_root / "benchmarks" / "rulebook.md").exists(), (
            "rulebook.md should not exist at benchmarks/ root"
        )


# ------------------------------------------------------------------
# Content quality
# ------------------------------------------------------------------


class TestRulebookContent:
    """rulebook.md must contain meaningful MTG rules content."""

    @pytest.fixture()
    def content(self, rulebook: Path) -> str:
        return rulebook.read_text()

    def test_not_empty(self, content: str):
        assert len(content.strip()) > 100, "rulebook.md must have substantial content"

    def test_mentions_creature(self, content: str):
        assert "creature" in content.lower()

    def test_mentions_mana(self, content: str):
        assert "mana" in content.lower()

    def test_mentions_life(self, content: str):
        assert "life" in content.lower()

    def test_mentions_graveyard(self, content: str):
        assert "graveyard" in content.lower()

    def test_mentions_stack_or_priority(self, content: str):
        assert "stack" in content.lower() or "priority" in content.lower()


# ------------------------------------------------------------------
# References in other markdown files
# ------------------------------------------------------------------


class TestRulebookReferences:
    """Any markdown reference to rulebook.md should use the workspace path."""

    @pytest.fixture()
    def markdown_files(self, repo_root: Path) -> list[Path]:
        """All markdown files in the repo excluding meta/planning files."""
        rulebook_path = repo_root / "benchmarks" / "sos" / "workspace" / "rulebook.md"
        excluded_names = {"TODO.md", "FILES_MODIFIED.md", "KEY_DECISIONS.md", "CONTEXT.md", "RUN_DECISIONS.md"}
        return [
            p
            for p in repo_root.rglob("*.md")
            if p != rulebook_path
            and ".git" not in p.parts
            and p.name not in excluded_names
        ]

    def test_no_broken_rulebook_references(
        self, markdown_files: list[Path], repo_root: Path
    ):
        """No markdown file should reference rulebook.md at an old/wrong path.

        Valid references include:
        - workspace/rulebook.md (full workspace-relative path)
        - /workspace/rulebook.md (absolute workspace path from agent POV)
        - bare `rulebook.md` in docs describing workspace contents (listing)
        - references in TODO/changelog about the move itself
        """
        # We specifically check for references that place rulebook.md
        # outside the workspace (e.g., docs/rulebook.md, ./rulebook.md at root)
        wrong_path_patterns = [
            re.compile(r"\bdocs/rulebook\.md\b"),
            re.compile(r"\./rulebook\.md\b"),
            re.compile(r"benchmarks/sos/rulebook\.md\b"),
            re.compile(r"benchmarks/rulebook\.md\b"),
        ]
        issues: list[str] = []
        for md_file in markdown_files:
            content = md_file.read_text(errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                for pat in wrong_path_patterns:
                    if pat.search(line):
                        rel = md_file.relative_to(repo_root)
                        issues.append(f"{rel}:{i}: {line.strip()}")
                        break
        assert not issues, (
            f"Found references to rulebook.md at wrong paths:\n"
            + "\n".join(issues)
        )
