"""Integration tests for the smoke-test pipeline.

These tests require Docker and (for the full smoke test) a local model
server running llama.cpp at 192.168.86.22:8080.

Run with::

    pytest -m integration tests/test_smoke_integration.py
"""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.integration
@pytest.mark.timeout(300)  # 5 min max
def test_smoke_pi_blind(tmp_path):
    """Full smoke test: build Pi blind image, run against local model."""
    image = "silverquillm-pi-blind:test"
    # Build image
    result = subprocess.run(
        ["docker", "build", "-t", image, "docker/homelab-pi-blind/"],
        capture_output=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr.decode()
    # Run smoke
    result = subprocess.run(
        ["silverquillm", "smoke", "--image", image],
        capture_output=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert "PASS" in result.stdout.decode()


@pytest.mark.integration
@pytest.mark.timeout(120)
def test_smoke_container_lifecycle(tmp_path):
    """Lightweight lifecycle test using alpine — no model server needed.

    Verifies the runner can stage a workspace, launch a container,
    and harvest results (or hit the timeout) without requiring a real
    agent or model server.
    """
    tag = "silverquillm-lifecycle-test:latest"
    dockerfile = tmp_path / "Dockerfile"
    entrypoint = tmp_path / "entrypoint.sh"

    # Minimal Dockerfile whose entrypoint creates the hello.py file
    # that ``silverquillm smoke`` checks for, then exits 0.  This
    # satisfies the smoke contract so the CLI reports PASS.
    dockerfile.write_text(
        "FROM alpine:3.19\n"
        "COPY entrypoint.sh /entrypoint.sh\n"
        "RUN chmod +x /entrypoint.sh\n"
        'ENTRYPOINT ["/entrypoint.sh"]\n'
    )
    entrypoint.write_text(
        "#!/bin/sh\n"
        "# Create the artefact that silverquillm smoke expects\n"
        'echo \'print("Hello World")\' > /workspace/hello.py\n'
        "exit 0\n"
    )

    # Build the throwaway image
    result = subprocess.run(
        ["docker", "build", "-t", tag, str(tmp_path)],
        capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()

    # Run via the CLI — smoke is the lightest path
    result = subprocess.run(
        ["silverquillm", "smoke", "--image", tag],
        capture_output=True, timeout=60,
    )
    # The alpine container creates hello.py and exits 0, so the CLI
    # should report PASS with exit code 0.  This proves the full
    # lifecycle: staging → container launch → artefact check → PASS.
    assert result.returncode == 0, (
        f"Expected exit code 0 (PASS), got {result.returncode}.\n"
        f"stdout: {result.stdout.decode()}\n"
        f"stderr: {result.stderr.decode()}"
    )
    assert "PASS" in result.stdout.decode(), (
        f"Expected 'PASS' in stdout: {result.stdout.decode()}"
    )

    # Cleanup
    subprocess.run(["docker", "rmi", tag], capture_output=True)
