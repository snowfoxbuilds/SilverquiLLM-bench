"""Grade candidate work in a network-less grader container; see ADR-013.

Candidate code runs only in the container, with no network, no host environment
and no host files beyond read-only grading inputs. What comes back is untrusted
data: one size-capped, framed line on the container's stdout whose shape is
checked field by field. Nothing in the container can write to the host.
Isolation protects the host, not score integrity: candidate code shares the
pytest process that counts its results.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import silverquillm
from silverquillm.evaluator import (
    _REPO_ROOT,
    CardResult,
    EnginePatchError,
    EngineResult,
    FullEvalResult,
    _prepare_engine_work,
    resolve_eval_paths,
)
from silverquillm.grade_worker import EVALUATION_SENTINEL

from .definition import KarnError, strict_json

# One pinned base per graded Python minor version: grading runs on the candidate's own
# minor version, never the bench's (KARN-BENCHMARK-CONTRACT.md, Grading isolation).
GRADER_BASES = {
    "3.13": "python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285",
    "3.14": "python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d",
}
# SilverquiLLM itself runs inside the grader, so no candidate can be older than it requires.
MINIMUM_PYTHON = (3, 13)
LEGACY_PYTHON = "3.13"
DEFAULT_GRADING_TIMEOUT = 3600
PROBE_TIMEOUT = 60
SUITE_TIMEOUT = 60
MAX_EVALUATION_BYTES = 1024 * 1024
# Past this much stderr the container is killed; only the tail is kept either way.
MAX_STDERR_BYTES = 64 * 1024 * 1024
MAX_TEST_COUNT = 10**9
STDERR_TAIL_BYTES = 4096
CLIENT_REAP_SECONDS = 10
READER_JOIN_SECONDS = 5
IMAGE_CONTEXT = Path(__file__).with_name("grader_image")
PACKAGE_ROOT = "/opt/sq"
GRADE_ROOT = "/grade"
GRADER_LABEL = "org.silverquillm.grader"
GRADER_PYTHON_LABEL = GRADER_LABEL + ".python"
DOCKER_FAILURES = {125, 126, 127}
# Attached output still reaches the daemon's log driver; cap what it keeps on disk.
LOG_OPTIONS = ("--log-driver", "json-file", "--log-opt", "max-size=1m", "--log-opt", "max-file=1")
ENVIRONMENT = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1",
    "SILVERQUILLM_BENCH_ROOT": PACKAGE_ROOT,
}
REPLAY_INPUTS = (
    "data/replays/golden",
    "data/replays/card_id_map.json",
    "data/replays/token_id_map.json",
    "scripts/triage_divergences.py",
)
WORKER = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from silverquillm.grade_worker import main; sys.exit(main(sys.argv[1], sys.argv[2]))"
)
# Reads only the interpreter's own version: -S skips site, so no candidate module is imported.
PYTHON_PROBE = "import sys; sys.stdout.write('%d.%d.%d\\n' % sys.version_info[:3])"
PYTHON_PROBE_BYTES = 64
PYTHON_PROBE_LIMITS = ("--pids-limit", "16", "--memory", "256m", "--memory-swap", "256m")
PYTHON_VERSION = re.compile(r"(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\n")
# Candidate output is discarded before its first import; only the exit code counts.
PROBE = (
    "import os, sys; quiet = os.open(os.devnull, os.O_WRONLY); os.dup2(quiet, 1); os.dup2(quiet, 2); "
    "sys.path.insert(0, sys.argv[1]); import engine.card, engine.game_state, engine.types"
)


class GraderError(KarnError):
    """Grading produced no accepted evaluation; ``reason`` says why."""

    def __init__(self, reason: str, stderr_tail: str = ""):
        super().__init__(reason)
        self.reason, self.stderr_tail = reason, stderr_tail

    def to_dict(self) -> dict:
        return {"reason": self.reason, "stderr_tail": self.stderr_tail}


@dataclass(frozen=True)
class DockerRun:
    """One ``docker run``: exit code (``None`` when killed), stderr tail, and capped stdout."""

    code: int | None
    stderr_tail: str
    stdout: bytes = b""
    overflow: bool = False


@dataclass(frozen=True)
class GraderLimits:
    memory: str = "8g"
    pids: int = 512
    tmpfs: str = "4g"


class DockerRunner:
    """The subprocess boundary: one bounded ``docker`` invocation per call."""

    def run(self, arguments: list[str], *, timeout: float, stdout_limit: int = 0) -> DockerRun:
        """Run the client once; kill it on timeout or when stdout or stderr passes its cap."""
        try:
            process = subprocess.Popen(
                ["docker", *arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if stdout_limit else subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError:
            raise GraderError("docker_unavailable") from None
        tail, stdout, overflow = deque(), bytearray(), threading.Event()

        def exceed():
            overflow.set()
            process.kill()

        def drain_stderr():
            size = total = 0
            while chunk := process.stderr.read(65536):
                tail.append(chunk)
                size, total = size + len(chunk), total + len(chunk)
                while size - len(tail[0]) >= STDERR_TAIL_BYTES:
                    size -= len(tail.popleft())
                if total > MAX_STDERR_BYTES:
                    exceed()
                    return

        def drain_stdout():
            while chunk := process.stdout.read(65536):
                if len(stdout) + len(chunk) > stdout_limit:
                    exceed()
                    return
                stdout.extend(chunk)

        readers = [threading.Thread(target=drain_stderr, daemon=True)]
        if stdout_limit:
            readers.append(threading.Thread(target=drain_stdout, daemon=True))
        for reader in readers:
            reader.start()
        try:
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                code = None
        except BaseException:
            # An interruption must not leave the client running or its readers holding pipes.
            with contextlib.suppress(BaseException):
                process.kill()
            with contextlib.suppress(BaseException):
                process.wait(timeout=CLIENT_REAP_SECONDS)
            with contextlib.suppress(BaseException):
                _release(process, readers)
            raise
        # Unguarded: a SIGTERM delivered here is the only one terminate_as_interrupt raises.
        _release(process, readers)
        text = b"".join(tail)[-STDERR_TAIL_BYTES:].decode(errors="replace")
        if overflow.is_set():
            return DockerRun(None, text, overflow=True)
        return DockerRun(code, text, bytes(stdout))

    def remove(self, name: str) -> None:
        # -v: a candidate image's declared VOLUMEs become anonymous volumes, which a forced
        # removal would otherwise leave behind with whatever the container wrote to them.
        try:
            subprocess.run(
                ["docker", "rm", "-f", "-v", name], capture_output=True, timeout=60, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _inspect(self, reference: str, template: str) -> str | None:
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", "--format", template, reference],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return None if result.returncode else result.stdout.decode(errors="replace").strip()

    def image_id(self, reference: str) -> str | None:
        value = self._inspect(reference, "{{.Id}}")
        return value if value and re.fullmatch(r"sha256:[0-9a-f]{64}", value) else None

    def image_python(self, reference: str) -> str | None:
        """The minor version a grader image was built for, from its build label."""
        return self._inspect(reference, f'{{{{index .Config.Labels "{GRADER_PYTHON_LABEL}"}}}}')

    def build(self, tag: str, context: Path, *, base: str, python: str) -> int:
        arguments = [
            "docker", "build", "--pull=false", "--build-arg", f"BASE={base}",
            "--label", f"{GRADER_PYTHON_LABEL}={python}", "-t", tag, str(context),
        ]  # fmt: skip
        try:
            return subprocess.run(arguments, timeout=1800, check=False).returncode
        except (OSError, subprocess.TimeoutExpired):
            return 1


def _release(process: subprocess.Popen, readers: list[threading.Thread]) -> None:
    """Join the output readers, bounded, then close the pipes they no longer read."""
    for reader in readers:
        reader.join(timeout=READER_JOIN_SECONDS)
    # Closing a pipe another thread is still blocked reading could hand its descriptor
    # number to an unrelated file, so a pipe held by a live reader is left to that reader.
    if not any(reader.is_alive() for reader in readers):
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                with contextlib.suppress(OSError):
                    stream.close()


def grader_tag(python: str) -> str:
    return f"silverquillm-grader:py{python}"


def build_grader_image(
    python: str, tag: str | None = None, *, docker: DockerRunner | None = None
) -> str:
    """Build the grader for one Python minor version explicitly; runs never build it."""
    if python not in GRADER_BASES:
        raise GraderError("grader_python_unsupported")
    docker = docker or DockerRunner()
    tag = tag or grader_tag(python)
    if docker.build(tag, IMAGE_CONTEXT, base=GRADER_BASES[python], python=python):
        raise GraderError("grader_image_build_failed")
    image_id = docker.image_id(tag)
    if image_id is None:
        raise GraderError("grader_image_unavailable")
    return image_id


def candidate_python(image_id: str, docker: DockerRunner | None = None) -> str:
    """The version of ``python3`` on the candidate image's default PATH, as ``X.Y.Z``.

    The image is candidate-supplied, so the probe is sandboxed like a grading container,
    with no mounts and a few bytes of accepted output. A wrong answer can only misgrade
    the candidate that gave it: it selects among bench-built graders, nothing else.
    """
    docker = docker or DockerRunner()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise GraderError("candidate_image_id_invalid")
    name = "sq-probe-" + uuid.uuid4().hex
    arguments = [
        "run", "--rm", "--pull", "never", "--name", name, "--label", GRADER_LABEL + "=1",
        "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--no-healthcheck",
        *PYTHON_PROBE_LIMITS,
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m,mode=1777", "--workdir", "/tmp",
        *LOG_OPTIONS, "--entrypoint", "python3", image_id, "-I", "-S", "-c", PYTHON_PROBE,
    ]  # fmt: skip
    try:
        result = docker.run(arguments, timeout=PROBE_TIMEOUT, stdout_limit=PYTHON_PROBE_BYTES)
    except BaseException:
        with contextlib.suppress(BaseException):
            docker.remove(name)
        raise
    if result.code is None or result.code in DOCKER_FAILURES:
        docker.remove(name)
    if result.code == 125:
        # Docker itself failed before running anything; that is not the candidate's answer.
        raise GraderError("python_probe_container_failed", result.stderr_tail)
    match = PYTHON_VERSION.fullmatch(result.stdout.decode("ascii", errors="replace"))
    if result.code != 0 or match is None:
        raise GraderError("candidate_python_unsupported", result.stderr_tail)
    version = tuple(int(part) for part in match.groups())
    if version[:2] < MINIMUM_PYTHON:
        raise GraderError("candidate_python_unsupported")
    return ".".join(map(str, version))


def grader_for(
    python: str,
    reference: str | None = None,
    *,
    docker: DockerRunner | None = None,
    **options,
) -> ContainerGrader:
    """The local grader built for ``python``'s minor version; ``reference`` overrides its tag.

    An override must still be a grader built for that minor version.
    """
    docker = docker or DockerRunner()
    minor = python.rpartition(".")[0]
    if reference is None and minor not in GRADER_BASES:
        raise GraderError("grader_image_unavailable")
    image_id = docker.image_id(reference or grader_tag(minor))
    if image_id is None:
        raise GraderError("grader_image_unavailable")
    if docker.image_python(image_id) != minor:
        raise GraderError("grader_python_mismatch")
    return ContainerGrader(image_id, docker=docker, candidate_python=python, **options)


def legacy_grader(
    reference: str | None = None, *, docker: DockerRunner | None = None, **options
) -> ContainerGrader:
    """The 3.13 grader for work that predates grading on the candidate's Python.

    Like every grader it must carry its build label, so an image built before graders
    were labeled is refused until `grader build` rebuilds it.
    """
    docker = docker or DockerRunner()
    image_id = docker.image_id(reference or grader_tag(LEGACY_PYTHON))
    if image_id is None:
        raise GraderError("grader_image_unavailable")
    if docker.image_python(image_id) != LEGACY_PYTHON:
        raise GraderError("grader_python_mismatch")
    return ContainerGrader(image_id, docker=docker, **options)


def select_grader(
    candidate_image_id: str,
    reference: str | None = None,
    *,
    docker: DockerRunner | None = None,
    **options,
) -> ContainerGrader:
    """Refuse before launch unless a grader exists for the candidate's own Python."""
    docker = docker or DockerRunner()
    python = candidate_python(candidate_image_id, docker)
    return grader_for(python, reference, docker=docker, **options)


def _mount(source: Path, target: str, readonly: bool) -> str:
    source = Path(source).resolve()
    if any(character in str(source) for character in ',"\n') or not source.exists():
        raise GraderError("grader_mount_source_unsupported")
    return f"type=bind,src={source},dst={target}" + (",readonly" if readonly else "")


class ContainerGrader:
    def __init__(
        self,
        image_id: str,
        *,
        timeout: int = DEFAULT_GRADING_TIMEOUT,
        limits: GraderLimits | None = None,
        docker: DockerRunner | None = None,
        candidate_python: str | None = None,
    ):
        self.image_id, self.timeout = image_id, timeout
        self.candidate_python = candidate_python
        self.limits = limits or GraderLimits()
        self.docker = docker or DockerRunner()

    @classmethod
    def from_image(cls, reference: str, **options) -> ContainerGrader:
        docker = options.pop("docker", None) or DockerRunner()
        image_id = docker.image_id(reference)
        if image_id is None:
            raise GraderError("grader_image_unavailable")
        return cls(image_id, docker=docker, **options)

    def isolation(self) -> dict:
        isolation = {"mode": "container", "grader_image_id": self.image_id, "network": "none"}
        if self.candidate_python is not None:
            isolation["candidate_python"] = self.candidate_python
            isolation["grader_python"] = self.candidate_python.rpartition(".")[0]
        return isolation

    def _container(
        self, mounts, command: list[str], timeout: float, *, stdout_limit: int = 0
    ) -> DockerRun:
        name = "sq-grade-" + uuid.uuid4().hex
        arguments = [
            "run", "--rm", "--pull", "never", "--name", name, "--label", GRADER_LABEL + "=1",
            "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.limits.pids),
            "--memory", self.limits.memory, "--memory-swap", self.limits.memory,
            "--tmpfs", f"/tmp:rw,nosuid,nodev,size={self.limits.tmpfs},mode=1777",
            "--workdir", "/tmp", *LOG_OPTIONS,
        ]  # fmt: skip
        for key, value in ENVIRONMENT.items():
            arguments += ["--env", f"{key}={value}"]
        targets = set()
        for source, target, readonly in mounts:
            if target not in targets:
                targets.add(target)
                arguments += ["--mount", _mount(source, target, readonly)]
        arguments += [self.image_id, "python3", "-I", "-c", *command]
        try:
            result = self.docker.run(arguments, timeout=timeout, stdout_limit=stdout_limit)
        except BaseException:
            # The client is already reaped, so nothing can start the container after this;
            # removal is bounded and never replaces the interruption being propagated.
            with contextlib.suppress(BaseException):
                self.docker.remove(name)
            raise
        if result.code is None or result.code in DOCKER_FAILURES:
            # A killed client or failed start can leave the container behind.
            self.docker.remove(name)
        return result

    def engine_health(self, workspace: Path) -> dict:
        probe = self._container(
            [(Path(workspace), GRADE_ROOT + "/workspace", True)],
            [PROBE, GRADE_ROOT + "/workspace"],
            PROBE_TIMEOUT,
        )
        code, tail = probe.code, probe.stderr_tail
        if code is None:
            return {"usable": False, "reason": "engine_import_timeout"}
        if code in DOCKER_FAILURES:
            raise GraderError("probe_container_failed", tail)
        return {"usable": code == 0, "reason": None if code == 0 else "engine_import_failed"}

    def evaluate_run(self, run_dir, benchmark, *, workspace_source: Path) -> FullEvalResult:
        root = Path(benchmark.root).resolve()
        paths = resolve_eval_paths(root, benchmark.target_set)
        inputs = (
            paths.audited_target,
            paths.audited_fdn,
            paths.engine_tests,
            paths.engine_tests.parent / "conftest.py",
            paths.engine_tests.parent / "pytest.ini",
            paths.test_utils,
        )
        container_root = f"{PACKAGE_ROOT}/benchmarks/{root.name}"
        mounts = [
            (path, f"{container_root}/{path.relative_to(root).as_posix()}", True)
            for path in inputs
            if path.exists()
        ]
        mounts += [(Path(workspace_source), GRADE_ROOT + "/workspace", True)]
        mounts += _replay_inputs(root.parent.parent)
        job = {
            "kind": "karn",
            "benchmark": root.name,
            "target_set": benchmark.target_set,
            "cards": list(benchmark.cards),
            "timeout": SUITE_TIMEOUT,
        }
        return self._grade(job, mounts)

    def evaluate_legacy(self, run_dir: Path, cards_dir: Path, engine_dir: Path) -> FullEvalResult:
        """The ``--image`` lineage's SOS evaluation; an engine patch is applied host-side as data."""
        run_dir, engine_dir = Path(run_dir), Path(engine_dir)
        preparation_error = None
        try:
            engine_work, staging = _prepare_engine_work(run_dir, engine_dir)
        except EnginePatchError as error:
            preparation_error, engine_work, staging = str(error), engine_dir, None
        try:
            sos = _REPO_ROOT / "benchmarks" / "sos"
            paths = resolve_eval_paths(sos, "sos")
            inputs = (
                paths.audited_target,
                paths.audited_fdn,
                paths.engine_tests,
                paths.engine_tests.parent / "conftest.py",
                paths.engine_tests.parent / "pytest.ini",
                paths.engine_tests.parent / "test_utils.py",
                sos / "data" / "test_oracle_workspace" / "test_utils.py",
            )
            mounts = [
                (path, f"{PACKAGE_ROOT}/benchmarks/sos/{path.relative_to(sos).as_posix()}", True)
                for path in inputs
                if path.exists()
            ]
            for name in ("status.json", "cards"):
                if (run_dir / name).exists():
                    mounts.append((run_dir / name, f"{GRADE_ROOT}/run/{name}", True))
            mounts += [
                (Path(cards_dir), GRADE_ROOT + "/legacy/workspace/cards", True),
                (engine_work, GRADE_ROOT + "/legacy/workspace/engine", True),
                *_replay_inputs(_REPO_ROOT),
            ]
            result = self._grade({"kind": "legacy", "timeout": SUITE_TIMEOUT}, mounts)
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
        if preparation_error is not None:
            result.engine_result.errors.insert(0, preparation_error)
        return result

    def _grade(self, job: dict, mounts: list) -> FullEvalResult:
        package = Path(silverquillm.__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix="sq-grade-") as scratch:
            job_file = Path(scratch) / "job.json"
            job_file.write_text(json.dumps(job))
            result = self._container(
                [
                    (package, PACKAGE_ROOT + "/silverquillm", True),
                    (job_file, GRADE_ROOT + "/job.json", True),
                    *mounts,
                ],
                [WORKER, PACKAGE_ROOT, GRADE_ROOT],
                self.timeout,
                stdout_limit=len(EVALUATION_SENTINEL) + MAX_EVALUATION_BYTES + 1,
            )
        if result.overflow:
            raise GraderError("output_too_large", result.stderr_tail)
        if result.code is None:
            raise GraderError("timeout", result.stderr_tail)
        if result.code:
            raise GraderError(f"exit_{result.code}", result.stderr_tail)
        return evaluation_from_json(_evaluation_payload(result.stdout))


def _replay_inputs(data_root: Path) -> list:
    return [
        (data_root / relative, f"{PACKAGE_ROOT}/{relative}", True)
        for relative in REPLAY_INPUTS
        if (data_root / relative).exists()
    ]


def _evaluation_payload(stdout: bytes) -> bytes:
    """The worker's stdout must be exactly one sentinel-framed line and nothing else."""
    if not stdout:
        raise GraderError("evaluation_missing")
    if (
        not stdout.startswith(EVALUATION_SENTINEL)
        or not stdout.endswith(b"\n")
        or stdout.count(b"\n") != 1
    ):
        raise GraderError("evaluation_not_framed")
    payload = stdout[len(EVALUATION_SENTINEL) : -1]
    if len(payload) > MAX_EVALUATION_BYTES:
        raise GraderError("evaluation_too_large")
    return payload


CARD_FIELDS = {
    "collector_number", "tests_passed", "tests_failed", "tests_total", "pass_rate",
    "errors", "skipped", "test_nodes", "tests_hash",
}  # fmt: skip
ENGINE_FIELDS = {"tests_passed", "tests_failed", "tests_total", "pass_rate", "errors"}
RESULT_FIELDS = {
    "sos_results", "fdn_results", "engine_result",
    "sos_pass_rate", "fdn_pass_rate", "engine_pass_rate",
}  # fmt: skip
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


def _counts(value: dict) -> tuple[int, int, int]:
    counts = tuple(value[key] for key in ("tests_passed", "tests_failed", "tests_total"))
    if (
        any(type(count) is not int or not 0 <= count < MAX_TEST_COUNT for count in counts)
        or counts[2] != sum(counts[:2])
    ):
        raise GraderError("evaluation_invalid_counts")
    rate = value["pass_rate"]
    if type(rate) not in (int, float) or not math.isfinite(rate) or not 0 <= rate <= 1:
        raise GraderError("evaluation_invalid_rate")
    return counts


def _strings(value) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GraderError("evaluation_invalid_strings")
    return value


def _card(key: str, value) -> CardResult:
    if not isinstance(value, dict) or set(value) != CARD_FIELDS or value["collector_number"] != key:
        raise GraderError("evaluation_invalid_card")
    passed, failed, total = _counts(value)
    nodes = value["test_nodes"]
    if not isinstance(nodes, list) or not all(
        isinstance(node, dict)
        and set(node) == {"test_node", "outcome"}
        and isinstance(node["test_node"], str)
        and node["outcome"] in ("pass", "fail")
        for node in nodes
    ):
        raise GraderError("evaluation_invalid_test_nodes")
    tests_hash = value["tests_hash"]
    if (
        type(value["skipped"]) is not bool
        or not isinstance(tests_hash, str)
        or not re.fullmatch(r"(?:[0-9a-f]{64})?", tests_hash)
    ):
        raise GraderError("evaluation_invalid_card")
    return CardResult(
        collector_number=key,
        tests_passed=passed,
        tests_failed=failed,
        tests_total=total,
        pass_rate=passed / total if total else 0.0,
        errors=_strings(value["errors"]),
        skipped=value["skipped"],
        test_nodes=[dict(node) for node in nodes],
        tests_hash=value["tests_hash"],
    )


def _cards(value) -> dict[str, CardResult]:
    if not isinstance(value, dict) or not all(NAME.fullmatch(key) for key in value):
        raise GraderError("evaluation_invalid_cards")
    return {key: _card(key, row) for key, row in value.items()}


def evaluation_from_json(raw: bytes) -> FullEvalResult:
    """Rebuild a result from grader output, accepting only the exact result shape."""
    try:
        value = strict_json(raw)
    except KarnError:
        raise GraderError("evaluation_not_json") from None
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        raise GraderError("evaluation_invalid_shape")
    engine = value["engine_result"]
    if not isinstance(engine, dict) or set(engine) != ENGINE_FIELDS:
        raise GraderError("evaluation_invalid_engine")
    passed, failed, total = _counts(engine)
    result = FullEvalResult(
        sos_results=_cards(value["sos_results"]),
        fdn_results=_cards(value["fdn_results"]),
        engine_result=EngineResult(
            tests_passed=passed,
            tests_failed=failed,
            tests_total=total,
            pass_rate=passed / total if total else 0.0,
            errors=_strings(engine["errors"]),
        ),
    )
    result.compute_aggregates()
    return result


def evaluate_legacy(run_dir: Path, cards_dir: Path, engine_dir: Path) -> FullEvalResult:
    # The --image lineage predates grading on the candidate's Python and keeps 3.13.
    grader = legacy_grader(os.environ.get("SILVERQUILLM_GRADER_IMAGE") or None)
    return grader.evaluate_legacy(run_dir, cards_dir, engine_dir)
