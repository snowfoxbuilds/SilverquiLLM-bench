import pytest
import subprocess
import sys
from pathlib import Path

@pytest.mark.integration
@pytest.mark.timeout(120)
def test_smoke_container_lifecycle(tmp_path: Path) -> None:
    """Smoke test pipeline with minimal alpine container (no real agent)."""
    # Build a trivial image that writes expected /output/ files and exits
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
    image = "silverquillm-smoke-test:lifecycle"
    build = subprocess.run(
        ["docker", "build", "-t", image, str(tmp_path)],
        capture_output=True, timeout=60,
    )
    assert build.returncode == 0, build.stderr.decode()

    # Run smoke via CLI
    result = subprocess.run(
        [sys.executable, "-m", "silverquillm.cli", "smoke", "--image", image],
        capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert "PASS" in result.stdout.decode()
