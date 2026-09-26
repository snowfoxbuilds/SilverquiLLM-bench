"""A ``docker run`` stand-in for the grader container, for tests without Docker.

It interprets the exact arguments ``ContainerGrader`` builds: each bind mount is
linked at its container path under a scratch root, container paths in the
command and environment are rewritten into that root, and the real worker runs
with only the declared environment. Sandbox enforcement itself (no network,
read-only mounts) is exercised by the integration tests against real Docker.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from silverquillm.karn.grader import ContainerGrader, DockerRun

FIXTURE_IMAGE_ID = "sha256:" + "0" * 64
VALUE_OPTIONS = {
    "--name", "--label", "--network", "--user", "--pids-limit", "--memory", "--memory-swap",
    "--tmpfs", "--workdir", "--env", "--mount", "--security-opt", "--cap-drop", "--pull",
    "--log-driver", "--log-opt",
}  # fmt: skip
FLAG_OPTIONS = {"--rm", "--read-only"}
CONTAINER_ROOTS = ("/opt/sq", "/grade", "/tmp")


class LocalDocker:
    def __init__(self, *, image_id: str | None = FIXTURE_IMAGE_ID, code: int | None = None):
        self.fixed_image_id, self.code = image_id, code
        self.runs, self.removed = [], []

    def image_id(self, reference):
        return self.fixed_image_id

    def remove(self, name):
        self.removed.append(name)

    def run(self, arguments, *, timeout, stdout_limit=0):
        assert arguments[0] == "run"
        options, index = [], 1
        while arguments[index].startswith("--"):
            name = arguments[index]
            if name in FLAG_OPTIONS:
                options.append((name, None))
                index += 1
            else:
                assert name in VALUE_OPTIONS, name
                options.append((name, arguments[index + 1]))
                index += 2
        image, command = arguments[index], arguments[index + 1 :]
        self.runs.append({"options": options, "image": image, "command": command})
        if self.code is not None:
            return DockerRun(self.code, "fixture failure")
        with tempfile.TemporaryDirectory(prefix="sq-fake-container-") as scratch:
            root = Path(scratch)
            (root / "tmp").mkdir()

            def remap(value: str) -> str:
                for prefix in CONTAINER_ROOTS:
                    if value == prefix or value.startswith(prefix + "/"):
                        return str(root) + value
                return value

            for name, value in options:
                if name == "--mount":
                    fields = dict(field.split("=", 1) for field in value.split(",") if "=" in field)
                    target = root / fields["dst"].lstrip("/")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(fields["src"])
            environment = dict(value.split("=", 1) for name, value in options if name == "--env")
            environment = {key: remap(value) for key, value in environment.items()}
            assert command[:3] == ["python3", "-I", "-c"]
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", "-c", command[3], *map(remap, command[4:])],
                    env=environment,
                    cwd=root / "tmp",
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return DockerRun(None, "")
            tail = completed.stderr.decode(errors="replace")[-4096:]
            if stdout_limit and len(completed.stdout) > stdout_limit:
                return DockerRun(None, tail, overflow=True)
            return DockerRun(completed.returncode, tail, completed.stdout if stdout_limit else b"")


def local_grader(**options) -> ContainerGrader:
    docker = options.pop("docker", None) or LocalDocker()
    return ContainerGrader(FIXTURE_IMAGE_ID, docker=docker, **options)
