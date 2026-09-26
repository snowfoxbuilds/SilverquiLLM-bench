"""Grade candidate work in a network-less grader container; see ADR-013.

Candidate code runs only in the container, with no network, no host environment
and no host files beyond read-only grading inputs. What comes back is untrusted
data: one size-capped regular file whose shape is checked field by field.
Isolation protects the host, not score integrity: candidate code shares the
pytest process that counts its results.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import stat
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

from .definition import KarnError, strict_json

DEFAULT_GRADER_IMAGE = "silverquillm-grader:local"
DEFAULT_GRADING_TIMEOUT = 3600
PROBE_TIMEOUT = 60
SUITE_TIMEOUT = 60
MAX_EVALUATION_BYTES = 1024 * 1024
STDERR_TAIL_BYTES = 4096
IMAGE_CONTEXT = Path(__file__).with_name("grader_image")
PACKAGE_ROOT = "/opt/sq"
GRADE_ROOT = "/grade"
GRADER_LABEL = "org.silverquillm.grader"
DOCKER_FAILURES = {125, 126, 127}
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
class GraderLimits:
    memory: str = "8g"
    pids: int = 512
    tmpfs: str = "4g"


class DockerRunner:
    """The subprocess boundary: one bounded ``docker`` invocation per call."""

    def run(self, arguments: list[str], *, timeout: float) -> tuple[int | None, str]:
        """Return the exit code, or ``None`` on timeout, and a bounded stderr tail."""
        try:
            process = subprocess.Popen(
                ["docker", *arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError:
            raise GraderError("docker_unavailable") from None
        tail, size = deque(), 0

        def drain():
            nonlocal size
            while chunk := process.stderr.read(65536):
                tail.append(chunk)
                size += len(chunk)
                while size - len(tail[0]) >= STDERR_TAIL_BYTES:
                    size -= len(tail.popleft())

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            code = None
        reader.join(timeout=5)
        text = b"".join(tail)[-STDERR_TAIL_BYTES:].decode(errors="replace")
        return code, text

    def remove(self, name: str) -> None:
        try:
            subprocess.run(
                ["docker", "rm", "-f", name], capture_output=True, timeout=60, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    def image_id(self, reference: str) -> str | None:
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", reference],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        value = result.stdout.decode(errors="replace").strip()
        return (
            value if not result.returncode and re.fullmatch(r"sha256:[0-9a-f]{64}", value) else None
        )

    def build(self, tag: str, context: Path) -> int:
        try:
            return subprocess.run(
                ["docker", "build", "--pull=false", "-t", tag, str(context)],
                timeout=1800,
                check=False,
            ).returncode
        except (OSError, subprocess.TimeoutExpired):
            return 1


def build_grader_image(
    tag: str = DEFAULT_GRADER_IMAGE, *, docker: DockerRunner | None = None
) -> str:
    """Build the pinned grader image explicitly; runs never build it implicitly."""
    docker = docker or DockerRunner()
    if docker.build(tag, IMAGE_CONTEXT):
        raise GraderError("grader_image_build_failed")
    image_id = docker.image_id(tag)
    if image_id is None:
        raise GraderError("grader_image_unavailable")
    return image_id


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
    ):
        self.image_id, self.timeout = image_id, timeout
        self.limits = limits or GraderLimits()
        self.docker = docker or DockerRunner()

    @classmethod
    def from_image(cls, reference: str = DEFAULT_GRADER_IMAGE, **options) -> ContainerGrader:
        docker = options.pop("docker", None) or DockerRunner()
        image_id = docker.image_id(reference)
        if image_id is None:
            raise GraderError("grader_image_unavailable")
        return cls(image_id, docker=docker, **options)

    def isolation(self) -> dict:
        return {"mode": "container", "grader_image_id": self.image_id, "network": "none"}

    def _container(self, mounts, command: list[str], timeout: float) -> tuple[int | None, str]:
        name = "sq-grade-" + uuid.uuid4().hex
        arguments = [
            "run", "--rm", "--pull", "never", "--name", name, "--label", GRADER_LABEL + "=1",
            "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.limits.pids),
            "--memory", self.limits.memory, "--memory-swap", self.limits.memory,
            "--tmpfs", f"/tmp:rw,nosuid,nodev,size={self.limits.tmpfs},mode=1777",
            "--workdir", "/tmp",
        ]  # fmt: skip
        for key, value in ENVIRONMENT.items():
            arguments += ["--env", f"{key}={value}"]
        targets = set()
        for source, target, readonly in mounts:
            if target not in targets:
                targets.add(target)
                arguments += ["--mount", _mount(source, target, readonly)]
        arguments += [self.image_id, "python3", "-I", "-c", *command]
        code, tail = self.docker.run(arguments, timeout=timeout)
        if code is None or code in DOCKER_FAILURES:
            # A timed-out client or failed start can leave the container behind.
            self.docker.remove(name)
        return code, tail

    def engine_health(self, workspace: Path) -> dict:
        code, tail = self._container(
            [(Path(workspace), GRADE_ROOT + "/workspace", True)],
            [PROBE, GRADE_ROOT + "/workspace"],
            PROBE_TIMEOUT,
        )
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
            output = Path(scratch) / "out"
            output.mkdir()
            job_file = Path(scratch) / "job.json"
            job_file.write_text(json.dumps(job))
            code, tail = self._container(
                [
                    (package, PACKAGE_ROOT + "/silverquillm", True),
                    (job_file, GRADE_ROOT + "/job.json", True),
                    (output, GRADE_ROOT + "/out", False),
                    *mounts,
                ],
                [WORKER, PACKAGE_ROOT, GRADE_ROOT],
                self.timeout,
            )
            if code is None:
                raise GraderError("timeout", tail)
            if code:
                raise GraderError(f"exit_{code}", tail)
            return evaluation_from_json(_read_output(output, "evaluation.json"))


def _replay_inputs(data_root: Path) -> list:
    return [
        (data_root / relative, f"{PACKAGE_ROOT}/{relative}", True)
        for relative in REPLAY_INPUTS
        if (data_root / relative).exists()
    ]


def _read_output(directory: Path, name: str) -> bytes:
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        except OSError:
            raise GraderError("evaluation_missing") from None
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise GraderError("evaluation_not_regular")
            raw = source.read(MAX_EVALUATION_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(raw) > MAX_EVALUATION_BYTES:
        raise GraderError("evaluation_too_large")
    return raw


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
    if any(type(count) is not int or count < 0 for count in counts) or counts[2] != sum(counts[:2]):
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
    grader = ContainerGrader.from_image(
        os.environ.get("SILVERQUILLM_GRADER_IMAGE", DEFAULT_GRADER_IMAGE)
    )
    return grader.evaluate_legacy(run_dir, cards_dir, engine_dir)
