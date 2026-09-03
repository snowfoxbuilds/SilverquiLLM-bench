"""The Contract Run test double: the REAL production harness, no Docker.

:class:`LocalHarnessEngine` implements the container ``Engine`` protocol behind
:func:`theozolith_worker.api.container_session_factory` (launch / alive / wait /
remove) by running ``theozolith_worker.harness.main.run_harness`` — the function
the ``theozolith-harness`` console script (the run image's ``ENTRYPOINT``)
calls — in a thread against the job dir the ``ContainerSpec`` bind-mounts at
``/job``.  It is the same shape as the-ozolith's own ``ThreadEngine`` session
double.  Nothing else is faked: the harness reads the staged manifest, asserts
the schema stamp, launches the adapter's real argv (``claude -p <pointer>
--dangerously-skip-permissions --output-format stream-json --verbose``) in the
manifest's workdir with ``THEOZOLITH_JOB`` set, captures stdout as
``output/transcript.txt``, writes ``output/status.json`` phase by phase, and
serves the driver's jobs over ``input/jobs/`` ↔ ``output/jobs/`` until the
shutdown request.  ``claude`` resolves on ``PATH`` to :mod:`tests.fake_claude`,
a scripted stand-in for the Claude CLI driven by a JSON playbook.

``job_runner`` is the harness's own job-execution seam — the container-side
shell that runs gate commands.  The security tests inject a recorder there, so
a candidate-authored gate command provably executes nowhere while still
travelling the jobs channel exactly as it would in production.

The harness entry point is an internal of the pinned worker revision (only
``theozolith_worker.api`` carries a stability promise); moving the pin is the
one event that can break this double, and it breaks loudly.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from theozolith_worker import api
from theozolith_worker.harness.main import run_harness

TESTS_DIR = Path(__file__).resolve().parent
FAKE_CLAUDE = TESTS_DIR / "fake_claude.py"

#: The environment variable naming the fake CLI's playbook file.
PLAYBOOK_ENV = "SQM_FAKE_CLAUDE_PLAYBOOK"

# (command, cwd, timeout) -> (ok, exit code, output): the harness's JobRunner.
JobRunner = Callable[[str, Path, float], tuple[bool, int, str]]


#: Credentials a real agent CLI could authenticate with.  The rig scrubs them
#: from the harness environment: even if a regression ever let a real CLI
#: resolve, it would hold no credential.
_MODEL_CREDENTIAL_ENV = (
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "COPILOT_GITHUB_TOKEN",
)


def _executable_bin_dir(preferred: Path) -> Path:
    """*preferred* if scripts can execute from it, else a fallback that can.

    ``tmp_path`` often sits on a ``noexec`` tmpfs; a shim that cannot exec
    would silently fall through the PATH search to a real ``claude``.  The
    fallback lives under the user cache (idempotent, shared, tiny).
    """
    for candidate in (preferred, Path.home() / ".cache" / "silverquillm-tests" / "fakebin"):
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / f".exec-probe-{os.getpid()}"
        probe.write_text("#!/bin/sh\n", encoding="utf-8")
        probe.chmod(0o755)
        executable = os.access(probe, os.X_OK)
        probe.unlink()
        if executable:
            return candidate
    raise RuntimeError("no filesystem allows executing the fake claude shim")


def install_fake_claude(bin_dir: Path) -> Path:
    """Put a ``claude`` executable in (or near) *bin_dir* that runs
    :mod:`fake_claude`; the returned script is guaranteed executable."""
    bin_dir = _executable_bin_dir(bin_dir)
    script = bin_dir / "claude"
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f"sys.path.insert(0, {str(TESTS_DIR)!r})\n"
        "from fake_claude import main\n"
        "sys.exit(main(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def mounted_job_dir(spec: api.ContainerSpec) -> Path:
    """The host path the spec bind-mounts at the container job path."""
    for host, container in spec.mounts:
        if container == api.CONTAINER_JOB_PATH:
            return Path(host)
    raise AssertionError(f"{spec.name} mounts no job dir at {api.CONTAINER_JOB_PATH}")


class LocalHarnessEngine:
    """``api.DockerEngine`` stand-in: "launching the container" runs the real
    production harness against the mounted job dir in a daemon thread."""

    def __init__(
        self,
        *,
        identity_root: Path,
        job_runner: JobRunner | None = None,
        poll_seconds: float = 0.05,
    ):
        self._identity_root = Path(identity_root)
        self._runner = job_runner
        self._poll = poll_seconds
        self.launched: list[api.ContainerSpec] = []
        self.removed: list[str] = []
        self.exit_codes: dict[str, int] = {}
        self.crashes: dict[str, BaseException] = {}
        self._threads: dict[str, threading.Thread] = {}

    def launch(self, spec: api.ContainerSpec) -> None:
        job = mounted_job_dir(spec)
        kwargs: dict[str, Any] = {
            "poll_seconds": self._poll,
            "identity_root": self._identity_root,
        }
        if self._runner is not None:
            kwargs["runner"] = self._runner

        def target() -> None:
            try:
                self.exit_codes[spec.name] = run_harness(job, **kwargs)
            except BaseException as exc:  # noqa: BLE001 - a crashed harness is a dead container
                self.crashes[spec.name] = exc
                self.exit_codes[spec.name] = 1

        thread = threading.Thread(target=target, name=f"harness-{spec.name}", daemon=True)
        self._threads[spec.name] = thread
        self.launched.append(spec)
        thread.start()

    def alive(self, name: str) -> bool:
        thread = self._threads.get(name)
        return thread is not None and thread.is_alive()

    def wait(self, name: str, timeout: float) -> int | None:
        thread = self._threads.get(name)
        if thread is None:
            return 0
        thread.join(timeout)
        return None if thread.is_alive() else self.exit_codes.get(name, 0)

    def remove(self, name: str) -> None:
        self.removed.append(name)


class DeadEngine:
    """A container that exits at once without ever running a harness — an
    image whose entrypoint is not the harness, or a crash before status.json."""

    def __init__(self) -> None:
        self.launched: list[api.ContainerSpec] = []
        self.removed: list[str] = []

    def launch(self, spec: api.ContainerSpec) -> None:
        self.launched.append(spec)

    def alive(self, name: str) -> bool:
        return False

    def wait(self, name: str, timeout: float) -> int | None:
        return 1

    def remove(self, name: str) -> None:
        self.removed.append(name)


@dataclass
class HarnessRig:
    """Everything a test needs to drive a Contract Run through the real harness."""

    engine: LocalHarnessEngine
    session_factory: api.SessionFactory
    playbook: Path
    identity_root: Path
    bin_dir: Path


def make_rig(
    tmp_path: Path,
    monkeypatch,
    *,
    playbook: dict[str, Any],
    job_runner: JobRunner | None = None,
    poll_seconds: float = 0.05,
) -> HarnessRig:
    """Install the fake ``claude`` on PATH, write the playbook, and build the
    engine + production session factory over it.

    Refuses to proceed — no launch of anything — unless the shim actually wins
    ``claude`` resolution: the one unacceptable failure mode is the harness
    silently launching a REAL agent CLI with ``--dangerously-skip-permissions``.
    Model credentials are scrubbed from the environment as well.
    """
    script = install_fake_claude(tmp_path / "fakebin")
    bin_dir = script.parent
    playbook_path = tmp_path / "playbook.json"
    playbook_path.write_text(json.dumps(playbook, indent=2), encoding="utf-8")
    identity_root = tmp_path / "identity-root"
    identity_root.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv(PLAYBOOK_ENV, str(playbook_path))
    for name in _MODEL_CREDENTIAL_ENV:
        monkeypatch.delenv(name, raising=False)
    resolved = shutil.which("claude")
    if resolved != str(script):
        raise RuntimeError(
            f"the fake claude shim at {script} did not win PATH resolution"
            f" (which found {resolved!r}); refusing to run — the harness would"
            " launch a real agent CLI"
        )
    engine = LocalHarnessEngine(
        identity_root=identity_root, job_runner=job_runner, poll_seconds=poll_seconds
    )
    return HarnessRig(
        engine=engine,
        session_factory=api.container_session_factory(engine),
        playbook=playbook_path,
        identity_root=identity_root,
        bin_dir=bin_dir,
    )
