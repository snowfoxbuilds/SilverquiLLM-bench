"""The real grader container: parity with host grading and the sandbox boundary (ADR-013)."""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from silverquillm.evaluator import evaluate_run
from silverquillm.karn.benchmark import load_benchmark
from silverquillm.karn.grader import ContainerGrader

from . import test_karn_end_to_end as end_to_end
from .test_karn_execution import benchmark_data
from .test_karn_host import make_candidate

REPO, invoke = end_to_end.REPO, end_to_end.invoke
grader_image, python_image = end_to_end.grader_image, end_to_end.python_image


def outcomes(result):
    cards = {
        name: (
            card.tests_passed,
            card.tests_total,
            sorted((node["test_node"], node["outcome"]) for node in card.test_nodes),
        )
        for dimension in (result.sos_results, result.fdn_results)
        for name, card in dimension.items()
    }
    engine = result.engine_result
    return cards, (engine.tests_passed, engine.tests_total)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("benchmark_id", "source", "target"),
    [
        ("smoke", "workspace", None),
        ("hob-medium", "data/test_oracle_workspace", (69, 69)),
        ("hob-medium", "workspace", (14, 69)),
    ],
)
def test_container_grading_reproduces_host_grading(
    tmp_path,
    grader_image,
    benchmark_id,
    source,
    target,
):
    benchmark = load_benchmark(REPO, benchmark_id)
    workspace = benchmark.root / source
    contained = ContainerGrader(grader_image).evaluate_run(
        tmp_path, benchmark, workspace_source=workspace
    )
    direct = evaluate_run(tmp_path, benchmark, workspace_source=workspace)
    assert outcomes(contained) == outcomes(direct)
    if target is not None:
        passed = sum(card.tests_passed for card in contained.sos_results.values())
        total = sum(card.tests_total for card in contained.sos_results.values())
        assert (passed, total) == target


HOSTILE_ENGINE = """
import os, socket
from pathlib import Path

ATTEMPTS = {}

def _attempt(name, action):
    try:
        action()
        ATTEMPTS[name] = "allowed"
    except OSError:
        ATTEMPTS[name] = "denied"

_attempt("login_state", lambda: os.listdir(__STATE__))
_attempt("host_file", lambda: Path(__CANARY__).read_text())
_attempt("network", lambda: socket.create_connection(("1.1.1.1", 443), timeout=3).close())
_attempt("package_write", lambda: Path("/opt/sq/silverquillm/planted.py").write_text("x"))
_attempt("workspace_write", lambda: Path("/grade/workspace/planted.py").write_text("x"))
_attempt("root_write", lambda: Path("/planted").write_text("x"))
ATTEMPTS["operator_environment"] = "denied" if "SQ_CANARY" not in os.environ else "allowed"
"""


@pytest.mark.integration
def test_hostile_engine_is_contained_and_grading_still_completes(
    tmp_path,
    grader_image,
    monkeypatch,
):
    canary = tmp_path / "host-canary.txt"
    canary.write_text("host-only")
    monkeypatch.setenv("SQ_CANARY", "operator-secret")
    root = benchmark_data(tmp_path / "data")
    workspace = root / "benchmarks/example/workspace"
    (workspace / "engine/__init__.py").write_text(
        HOSTILE_ENGINE.replace(
            "__STATE__", repr(str(Path.home() / ".local/state/silverquillm"))
        ).replace("__CANARY__", repr(str(canary)))
    )
    (workspace / "engine_tests/test_contained.py").write_text(
        "import engine\n"
        "def test_every_escape_was_denied():\n"
        "    assert set(engine.ATTEMPTS.values()) == {'denied'}, engine.ATTEMPTS\n"
    )
    benchmark = load_benchmark(root, "example")
    grader = ContainerGrader(grader_image)
    assert grader.engine_health(workspace) == {"usable": True, "reason": None}
    result = grader.evaluate_run(tmp_path, benchmark, workspace_source=workspace)
    assert result.engine_result.tests_total == 2
    assert result.engine_result.tests_passed == 2, result.engine_result.errors
    assert not (REPO / "silverquillm/planted.py").exists()
    assert not (workspace / "planted.py").exists()


@pytest.mark.integration
def test_run_refuses_before_launch_without_the_grader_image(tmp_path, python_image):
    candidate = make_candidate(tmp_path, image=python_image)
    runs = tmp_path / "runs"
    result = invoke(
        "run",
        "--build-output",
        str(candidate.build_output),
        "--construct",
        "bare",
        "--benchmark",
        "smoke",
        "--bench-root",
        str(REPO),
        "--results-dir",
        str(runs),
        "--results-repo",
        str(tmp_path / "records"),
        "--state-root",
        str(tmp_path / "state"),
        "--grader-image",
        "silverquillm-grader:absent-" + uuid.uuid4().hex,
    )
    assert result.returncode != 0
    assert "grader_image_unavailable" in result.stderr
    assert not runs.exists()


FLOODING_ENGINE = """
import os, stat

for name in os.listdir(f"/proc/{os.getppid()}/fd"):
    try:
        path = f"/proc/{os.getppid()}/fd/{name}"
        if stat.S_ISFIFO(os.stat(path).st_mode):
            descriptor = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
            for _ in range(64):
                os.write(descriptor, b"x" * 65536)
    except OSError:
        pass
"""


@pytest.mark.integration
def test_grader_output_past_its_cap_is_refused(tmp_path, grader_image):
    """Graded code flooding the worker's result stream ends as output_too_large, not a host write."""
    from silverquillm.karn.grader import GraderError

    root = benchmark_data(tmp_path / "data")
    workspace = root / "benchmarks/example/workspace"
    (workspace / "engine/card.py").write_text(
        (workspace / "engine/card.py").read_text() + FLOODING_ENGINE
    )
    benchmark = load_benchmark(root, "example")
    with pytest.raises(GraderError) as refused:
        ContainerGrader(grader_image).evaluate_run(tmp_path, benchmark, workspace_source=workspace)
    assert refused.value.reason in {"output_too_large", "evaluation_not_framed"}


INTERRUPTED_GRADER = r"""
import sys
from pathlib import Path

from silverquillm.karn import grader as grader_module
from silverquillm.karn.benchmark import load_benchmark
from silverquillm.karn.interruption import terminate_as_interrupt

stage, image, root, scratch = sys.argv[1:5]
real_run = grader_module.DockerRunner.run


def announcing(self, arguments, **options):
    print(arguments[arguments.index("--name") + 1], flush=True)
    return real_run(self, arguments, **options)


grader_module.DockerRunner.run = announcing
grader = grader_module.ContainerGrader(image)
workspace = Path(root) / "benchmarks/example/workspace"
try:
    with terminate_as_interrupt():
        if stage == "probe":
            grader.engine_health(workspace)
        else:
            grader.evaluate_run(
                Path(scratch), load_benchmark(Path(root), "example"), workspace_source=workspace
            )
except KeyboardInterrupt:
    print("interrupted", flush=True)
    sys.exit(130)
print("finished", flush=True)
"""


@pytest.mark.integration
@pytest.mark.parametrize(
    "number", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP], ids=["SIGINT", "SIGTERM", "SIGHUP"]
)
@pytest.mark.parametrize("stage", ["probe", "grading"])
def test_an_interrupted_hanging_grader_leaves_no_client_or_container(
    tmp_path, grader_image, stage, number
):
    root = benchmark_data(tmp_path / "data")
    (root / "benchmarks/example/workspace/engine/__init__.py").write_text(
        "import time\ntime.sleep(10**6)\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", INTERRUPTED_GRADER, stage, grader_image, str(root), str(tmp_path)],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    name = child.stdout.readline().strip()
    try:
        assert name.startswith("sq-grade-"), child.stderr.read()
        deadline = time.monotonic() + 60
        while (
            subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", name],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            != "true"
        ):
            assert child.poll() is None and time.monotonic() < deadline
            time.sleep(0.2)
        child.send_signal(number)
        output, errors = child.communicate(timeout=90)
        assert child.returncode == 130, errors
        assert output.strip() == "interrupted"
        clients = subprocess.run(["pgrep", "-f", name], capture_output=True, check=False)
        assert clients.returncode == 1, clients.stdout
        gone = subprocess.run(["docker", "inspect", name], capture_output=True, check=False)
        assert gone.returncode != 0, "the interrupted grader container was removed"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        if name.startswith("sq-grade-"):
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


# BuildKit resolves FROM by name, so this builds on the tag python_image checked.
HANGING_CANDIDATE = """\
FROM python:3.13-slim
RUN mkdir /hang && printf '#!/bin/sh\\nexec sleep 1000\\n' > /hang/python3 && chmod 755 /hang/python3
ENV PATH=/hang:/usr/local/bin:/usr/bin:/bin
VOLUME /data
"""


@pytest.mark.integration
def test_a_timed_out_python_probe_leaves_no_container_or_volume(python_image, monkeypatch):
    from silverquillm.karn import grader as grader_module

    tag = "sq-test-hanging-candidate:" + uuid.uuid4().hex
    built = subprocess.run(
        ["docker", "build", "--pull=false", "-q", "-t", tag, "-"],
        input=HANGING_CANDIDATE.encode(),
        capture_output=True,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    name = "sq-probe-" + uuid.uuid4().hex
    monkeypatch.setattr(
        grader_module, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex=name[9:]))
    )
    monkeypatch.setattr(grader_module, "PROBE_TIMEOUT", 8)
    volumes, done = set(), threading.Event()

    def watch():
        while not done.is_set():
            mounted = subprocess.run(
                ["docker", "inspect", "-f", "{{range .Mounts}}{{.Name}} {{end}}", name],
                capture_output=True,
                text=True,
                check=False,
            )
            volumes.update(mounted.stdout.split())
            time.sleep(0.2)

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        with pytest.raises(grader_module.GraderError, match="candidate_python_unsupported"):
            grader_module.candidate_python(built.stdout.decode().strip())
    finally:
        done.set()
        watcher.join()
        subprocess.run(["docker", "rm", "-f", "-v", name], capture_output=True, check=False)
        subprocess.run(["docker", "rmi", tag], capture_output=True, check=False)
    assert volumes, "the probe container mounted the image's declared volume"
    assert (
        subprocess.run(["docker", "inspect", name], capture_output=True, check=False).returncode
        != 0
    )
    for volume in volumes:
        leftover = subprocess.run(
            ["docker", "volume", "rm", volume], capture_output=True, check=False
        )
        assert leftover.returncode != 0, f"anonymous volume {volume} outlived the probe"
