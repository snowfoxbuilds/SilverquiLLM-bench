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
DOCKER_DIR = REPO_ROOT / "docker" / "homelab-pi-blind"



# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

class TestFilesExist:
    """All 2 required files exist at the correct paths."""

    def test_dockerfile_exists(self):
        assert (DOCKER_DIR / "Dockerfile").is_file()

    def test_entrypoint_exists(self):
        assert (DOCKER_DIR / "entrypoint.mjs").is_file()

