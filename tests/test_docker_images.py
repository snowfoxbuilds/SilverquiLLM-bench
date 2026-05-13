"""Tests for TODO item 6: Docker images for opencode-tested and opencode-blind.

Validates file existence, content, and correctness of the 4 Docker files:
- docker/opencode-tested/Dockerfile
- docker/opencode-tested/entrypoint.sh
- docker/opencode-blind/Dockerfile
- docker/opencode-blind/entrypoint.sh
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTED_DIR = REPO_ROOT / "docker" / "opencode-tested"
BLIND_DIR = REPO_ROOT / "docker" / "opencode-blind"


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

class TestFilesExist:
    """All 4 required files exist at the correct paths."""

    def test_tested_dockerfile_exists(self):
        assert (TESTED_DIR / "Dockerfile").is_file()

    def test_tested_entrypoint_exists(self):
        assert (TESTED_DIR / "entrypoint.sh").is_file()

    def test_blind_dockerfile_exists(self):
        assert (BLIND_DIR / "Dockerfile").is_file()

    def test_blind_entrypoint_exists(self):
        assert (BLIND_DIR / "entrypoint.sh").is_file()


# ---------------------------------------------------------------------------
# Dockerfile validation
# ---------------------------------------------------------------------------

class TestDockerfiles:
    """Both Dockerfiles contain required directives."""

    @pytest.fixture(params=["tested", "blind"])
    def dockerfile_content(self, request) -> str:
        d = TESTED_DIR if request.param == "tested" else BLIND_DIR
        return (d / "Dockerfile").read_text()

    def test_base_image_python312(self, dockerfile_content):
        assert "FROM python:3.12-slim" in dockerfile_content

    def test_entrypoint_directive(self, dockerfile_content):
        assert "ENTRYPOINT" in dockerfile_content

    def test_workdir_workspace(self, dockerfile_content):
        assert "WORKDIR /workspace" in dockerfile_content

    def test_installs_git(self, dockerfile_content):
        assert "git" in dockerfile_content

    def test_installs_curl(self, dockerfile_content):
        assert "curl" in dockerfile_content

    def test_installs_pytest(self, dockerfile_content):
        assert "pytest" in dockerfile_content


# ---------------------------------------------------------------------------
# Entrypoint script validation
# ---------------------------------------------------------------------------

class TestEntrypointScripts:
    """Both entrypoint scripts are valid bash with required structure."""

    @pytest.fixture(params=["tested", "blind"])
    def entrypoint_content(self, request) -> str:
        d = TESTED_DIR if request.param == "tested" else BLIND_DIR
        return (d / "entrypoint.sh").read_text()

    def test_starts_with_shebang(self, entrypoint_content):
        assert entrypoint_content.startswith("#!/bin/bash")

    def test_set_euo_pipefail(self, entrypoint_content):
        assert "set -euo pipefail" in entrypoint_content

    def test_writes_started_event(self, entrypoint_content):
        # In bash, JSON may use escaped quotes like \"event\"
        assert "started" in entrypoint_content
        assert "progress.jsonl" in entrypoint_content

    def test_traps_sigterm(self, entrypoint_content):
        assert "trap" in entrypoint_content
        assert "SIGTERM" in entrypoint_content

    def test_writes_timed_out_on_sigterm(self, entrypoint_content):
        assert "timed_out" in entrypoint_content

    def test_copies_engine_to_engine_work(self, entrypoint_content):
        assert "engine_work" in entrypoint_content
        assert "cp" in entrypoint_content

    def test_progress_jsonl_path(self, entrypoint_content):
        assert "/output/progress.jsonl" in entrypoint_content


# ---------------------------------------------------------------------------
# Mode-specific prompt content
# ---------------------------------------------------------------------------

class TestTestedModePrompt:
    """Tested mode appends test-related instructions to the prompt."""

    @pytest.fixture
    def content(self) -> str:
        return (TESTED_DIR / "entrypoint.sh").read_text()

    def test_contains_test_instructions(self, content):
        # Should mention writing tests or running pytest
        lower = content.lower()
        assert "test" in lower
        assert "pytest" in lower

    def test_contains_write_tests_instruction(self, content):
        lower = content.lower()
        assert "write tests" in lower or "write test" in lower


class TestBlindModePrompt:
    """Blind mode appends no-test instructions to the prompt."""

    @pytest.fixture
    def content(self) -> str:
        return (BLIND_DIR / "entrypoint.sh").read_text()

    def test_contains_no_test_instruction(self, content):
        assert "Do not write or run tests" in content

    def test_does_not_instruct_to_write_tests(self, content):
        # The blind mode should NOT tell the agent to write tests
        # (it may mention "test" in the negative instruction, but not as a positive command)
        lines = content.split("\n")
        # Filter to lines that are NOT the "Do not write or run tests" instruction
        other_lines = [l for l in lines if "Do not write or run tests" not in l]
        other_text = "\n".join(other_lines).lower()
        assert "write tests" not in other_text or "do not" in other_text
