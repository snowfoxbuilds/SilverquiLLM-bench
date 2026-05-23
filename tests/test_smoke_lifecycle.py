import os

import pytest
import subprocess
import sys
from pathlib import Path


@pytest.fixture()
def smoke_image(tmp_path: Path):
    """Build a trivial smoke-test Docker image and clean up after the test."""
    image_tag = f"silverquillm-smoke-test:{os.getpid()}"
    dockerfile = tmp_path / "Dockerfile"
    entrypoint = tmp_path / "entrypoint.sh"
    dockerfile.write_text(
        "FROM alpine:latest\n"
        "COPY entrypoint.sh /entrypoint.sh\n"
        "RUN chmod +x /entrypoint.sh\n"
        'ENTRYPOINT ["/entrypoint.sh"]\n'
    )
    entrypoint.write_text(
        '#!/bin/sh\n'
        'echo "[00:00:01] Starting" >> /output/system.log\n'
        'echo "hello from agent" > /workspace/hello.py\n'
        'echo 0 > /output/exit_code\n'
    )
    build = subprocess.run(
        ["docker", "build", "-t", image_tag, str(tmp_path)],
        capture_output=True, timeout=60,
    )
    assert build.returncode == 0, build.stderr.decode()
    yield image_tag
    result = subprocess.run(["docker", "rmi", "-f", image_tag], capture_output=True, timeout=30)
    if result.returncode != 0 and b"No such image" not in result.stderr:
        import warnings
        warnings.warn(f"Failed to remove Docker image {image_tag}: {result.stderr.decode()}")


@pytest.mark.integration
@pytest.mark.timeout(120)
def test_smoke_container_lifecycle(smoke_image: str) -> None:
    """Smoke test pipeline with minimal alpine container (no real agent)."""
    # Run smoke via CLI
    result = subprocess.run(
        [sys.executable, "-m", "silverquillm.cli", "smoke", "--image", smoke_image],
        capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert "PASS" in result.stdout.decode()
