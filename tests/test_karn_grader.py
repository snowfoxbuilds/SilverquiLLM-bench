"""Containerized grading: sandbox arguments, untrusted output, and failure recording."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm import evaluator
from silverquillm.cli import main
from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult
from silverquillm.karn import grader as grader_module
from silverquillm.karn.benchmark import load_benchmark
from silverquillm.karn.definition import KarnError
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.grader import (
    ENVIRONMENT,
    EVALUATION_SENTINEL,
    MAX_EVALUATION_BYTES,
    WORKER,
    DockerRun,
    GraderError,
    _evaluation_payload,
    evaluation_from_json,
)

from .grader_fixtures import FIXTURE_IMAGE_ID, LocalDocker, local_grader
from .test_karn_execution import benchmark_data, options


def mounts(run):
    rows = []
    for name, value in run["options"]:
        if name == "--mount":
            fields = dict(field.split("=", 1) for field in value.split(",") if "=" in field)
            rows.append((fields["src"], fields["dst"], value.endswith(",readonly")))
    return rows


def test_every_grading_container_is_sandboxed_and_sees_only_declared_inputs(tmp_path):
    docker = LocalDocker()
    opts = options(tmp_path, grader=local_grader(docker=docker))
    record = run_benchmark(**opts)
    assert all(score["tests_passed"] == 1 for score in record.scores.values())
    assert record.run_metadata["grading_isolation"] == {
        "mode": "container",
        "grader_image_id": FIXTURE_IMAGE_ID,
        "network": "none",
    }
    assert docker.runs, "grading and the engine probe must run in containers"
    for run in docker.runs:
        selected = dict(run["options"])
        assert run["image"] == FIXTURE_IMAGE_ID
        assert selected["--network"] == "none"
        assert selected["--pull"] == "never"
        assert selected["--user"] == f"{os.getuid()}:{os.getgid()}"
        assert selected["--cap-drop"] == "ALL"
        assert selected["--security-opt"] == "no-new-privileges"
        assert ("--read-only", None) in run["options"] and ("--rm", None) in run["options"]
        assert selected["--pids-limit"] == "512"
        assert selected["--memory"] == selected["--memory-swap"] == "8g"
        assert selected["--tmpfs"].startswith("/tmp:rw,nosuid,nodev,size=4g")
        environment = dict(v.split("=", 1) for k, v in run["options"] if k == "--env")
        assert environment == ENVIRONMENT
        assert [row for row in mounts(run) if not row[2]] == [], "nothing is mounted writable"
        assert selected["--log-driver"] == "json-file"
        assert [v for k, v in run["options"] if k == "--log-opt"] == ["max-size=1m", "max-file=1"]
        home_state = str(Path.home() / ".local/state")
        assert all(not source.startswith(home_state) for source, _, _ in mounts(run))
        assert all(not source.endswith("docker.sock") for source, _, _ in mounts(run))
        if WORKER in run["command"]:
            targets = {target for _, target, _ in mounts(run)}
            assert "/grade/workspace" in targets and "/opt/sq/silverquillm" in targets
            assert not any(target.startswith(str(opts["results_dir"])) for target in targets)
        else:
            assert [target for _, target, _ in mounts(run)] == ["/grade/workspace"]


def test_pytest_environment_is_an_allowlist_not_the_operator_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SQ_OPERATOR_TOKEN", "must-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    suite = tmp_path / "tests.py"
    suite.write_text(
        "import os\n"
        "def test_isolated():\n"
        "    assert 'SQ_OPERATOR_TOKEN' not in os.environ\n"
        "    assert 'OPENAI_API_KEY' not in os.environ\n"
    )
    passed, failed, total, errors = evaluator._run_pytest_with_pythonpath(suite, [str(tmp_path)])
    assert (passed, failed, total) == (1, 0, 1), errors


def valid_evaluation() -> dict:
    result = FullEvalResult(
        sos_results={
            "hob_12": CardResult(
                "hob_12",
                tests_passed=1,
                tests_failed=1,
                tests_total=2,
                pass_rate=0.5,
                errors=["FAILED tests.py::test_b"],
                test_nodes=[
                    {"test_node": "tests.py::test_a", "outcome": "pass"},
                    {"test_node": "tests.py::test_b", "outcome": "fail"},
                ],
                tests_hash="a" * 64,
            )
        },
        engine_result=EngineResult(tests_passed=3, tests_total=3, pass_rate=1.0),
    )
    result.compute_aggregates()
    return asdict(result)


def test_valid_output_round_trips_and_rates_are_recomputed():
    value = valid_evaluation()
    value["sos_pass_rate"] = 1.0
    value["sos_results"]["hob_12"]["pass_rate"] = 1.0
    result = evaluation_from_json(json.dumps(value).encode())
    assert result.sos_results["hob_12"].pass_rate == 0.5
    assert result.sos_pass_rate == 0.5
    assert result.engine_result.tests_passed == 3


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.update(extra=1),
        lambda v: v["engine_result"].update(tests_passed=-1),
        lambda v: v["engine_result"].update(tests_total=9),
        lambda v: v["engine_result"].update(tests_passed=True),
        lambda v: v["engine_result"].update(tests_passed=10**9, tests_total=10**9),
        lambda v: v["sos_results"]["hob_12"].update(
            tests_passed=10**4299, tests_failed=0, tests_total=10**4299, test_nodes=[]
        ),
        lambda v: v["sos_results"]["hob_12"].update(collector_number="hob_13"),
        lambda v: v["sos_results"]["hob_12"].update(
            test_nodes=[{"test_node": "x", "outcome": "ok"}]
        ),
        lambda v: v["sos_results"]["hob_12"].update(errors=[1]),
        lambda v: v["sos_results"]["hob_12"].update(tests_hash="../../etc"),
        lambda v: v["sos_results"]["hob_12"].update(skipped="no"),
        lambda v: v["sos_results"]["hob_12"].pop("errors"),
        lambda v: v["fdn_results"].update({"../x": v["sos_results"]["hob_12"]}),
    ],
)
def test_untrusted_output_of_the_wrong_shape_is_refused(mutate):
    value = valid_evaluation()
    mutate(value)
    with pytest.raises(GraderError):
        evaluation_from_json(json.dumps(value).encode())


@pytest.mark.parametrize(
    "raw", [b"not json", b'{"a": 1, "a": 2}', b'{"sos_pass_rate": NaN}', b"[]"]
)
def test_untrusted_output_that_is_not_strict_json_is_refused(raw):
    with pytest.raises(GraderError):
        evaluation_from_json(raw)


def test_grader_stdout_must_be_exactly_one_framed_line():
    document = json.dumps(valid_evaluation()).encode()
    assert _evaluation_payload(EVALUATION_SENTINEL + document + b"\n") == document
    with pytest.raises(GraderError, match="evaluation_missing"):
        _evaluation_payload(b"")
    for stdout in (
        document + b"\n",
        EVALUATION_SENTINEL + document,
        b"noise\n" + EVALUATION_SENTINEL + document + b"\n",
        EVALUATION_SENTINEL + document + b"\n" + EVALUATION_SENTINEL + document + b"\n",
    ):
        with pytest.raises(GraderError, match="evaluation_not_framed"):
            _evaluation_payload(stdout)
    with pytest.raises(GraderError, match="evaluation_too_large"):
        _evaluation_payload(EVALUATION_SENTINEL + b" " * (MAX_EVALUATION_BYTES + 1) + b"\n")


def test_candidate_prints_during_grading_do_not_reach_the_result_line(tmp_path):
    """The worker discards everything else written to stdout, including by graded code."""
    opts = options(tmp_path, grader=local_grader())
    engine = opts["bench_root"] / "benchmarks/example/workspace/engine/card.py"
    engine.write_text(
        engine.read_text()
        + "import os\n"
        + "print('noise')\n"
        + "try:\n"
        + "    parent = os.open(f'/proc/{os.getppid()}/fd/1', os.O_WRONLY)\n"
        + "    os.write(parent, b'noise written into the grader process stdout\\n')\n"
        + "except OSError:\n"
        + "    pass\n"
    )
    record = run_benchmark(**opts)
    assert "grading_failure" not in record.run_metadata
    assert all(score["evaluated"] for score in record.scores.values())


REAL_RUN = grader_module.DockerRunner.run


def fake_docker_client(tmp_path, monkeypatch, script: str):
    client = tmp_path / "bin/docker"
    client.parent.mkdir()
    client.write_text("#!/bin/sh\n" + script)
    client.chmod(0o755)
    monkeypatch.setenv("PATH", f"{client.parent}:{os.environ['PATH']}")


def test_runner_kills_the_client_once_stdout_passes_its_cap(tmp_path, monkeypatch):
    fake_docker_client(tmp_path, monkeypatch, "exec yes silverquillm\n")
    result = REAL_RUN(grader_module.DockerRunner(), ["run"], timeout=30, stdout_limit=4096)
    assert result == DockerRun(None, "", overflow=True)


def test_runner_kills_the_client_once_stderr_passes_its_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(grader_module, "MAX_STDERR_BYTES", 1024 * 1024)
    fake_docker_client(tmp_path, monkeypatch, "yes silverquillm >&2\n")
    result = REAL_RUN(grader_module.DockerRunner(), ["run"], timeout=30)
    assert result.overflow and result.code is None
    assert len(result.stderr_tail.encode()) <= grader_module.STDERR_TAIL_BYTES


def test_runner_returns_bounded_stdout_and_the_exit_code(tmp_path, monkeypatch):
    fake_docker_client(tmp_path, monkeypatch, "printf result; echo tail >&2; exit 3\n")
    result = REAL_RUN(grader_module.DockerRunner(), ["run"], timeout=30, stdout_limit=64)
    assert result == DockerRun(3, "tail\n", b"result")


def test_output_over_the_cap_is_refused_and_the_container_removed(tmp_path):
    docker = GradingFails(DockerRun(None, "", overflow=True))
    record = run_benchmark(**options(tmp_path, grader=local_grader(docker=docker)))
    assert record.run_metadata["grading_failure"]["reason"] == "output_too_large"
    for score in record.scores.values():
        assert score["missing_reasons"] == ["grading_container_failed:output_too_large"]
    assert docker.removed


class GradingFails(LocalDocker):
    """The engine probe runs; the grading container exits with the given result."""

    def __init__(self, result):
        super().__init__()
        self.result = result

    def run(self, arguments, *, timeout, stdout_limit=0):
        if WORKER in arguments:
            self.runs.append({"options": [], "image": None, "command": arguments})
            return self.result
        return super().run(arguments, timeout=timeout, stdout_limit=stdout_limit)


@pytest.mark.parametrize(
    ("result", "reason"), [((None, "slow"), "timeout"), ((1, "Traceback"), "exit_1")]
)
def test_grading_container_failure_is_recorded_and_the_run_still_written(tmp_path, result, reason):
    docker = GradingFails(DockerRun(*result))
    opts = options(tmp_path, grader=local_grader(docker=docker))
    record = run_benchmark(**opts)
    assert record.run_metadata["execution"]["status"] == "completed"
    assert record.run_metadata["grading_failure"] == {
        "reason": reason,
        "stderr_tail": result[1],
    }
    for score in record.scores.values():
        assert not score["evaluated"] and score["pass_rate"] is None
        assert score["missing_reasons"] == ["grading_container_failed:" + reason]
    assert (opts["results_dir"] / record.run_id / "run-record.json").is_file()
    if result[0] is None:
        assert docker.removed, "a timed-out grading container is force-removed"


def test_probe_timeout_marks_engine_unusable_and_docker_failure_is_not_blamed_on_candidate(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    (workspace / "engine").mkdir(parents=True)
    (workspace / "engine/card.py").write_text("value = 1\n")
    timed_out = local_grader(docker=LocalDocker(code=None))
    timed_out.docker.run = lambda arguments, timeout, stdout_limit=0: DockerRun(None, "")
    assert timed_out.engine_health(workspace) == {
        "usable": False,
        "reason": "engine_import_timeout",
    }
    assert timed_out.docker.removed
    with pytest.raises(GraderError, match="probe_container_failed"):
        local_grader(docker=LocalDocker(code=125)).engine_health(workspace)
    assert local_grader(docker=LocalDocker(code=1)).engine_health(workspace) == {
        "usable": False,
        "reason": "engine_import_failed",
    }


def test_missing_grader_image_refuses_before_any_run_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(grader_module.DockerRunner, "image_id", lambda self, reference: None)
    opts = options(tmp_path)
    opts.pop("grader")
    with pytest.raises(KarnError, match="grader_image_unavailable"):
        run_benchmark(**opts, grader_image="silverquillm-grader:missing")
    assert not opts["results_dir"].exists()


def test_scheduler_refuses_to_start_without_the_grader_image(tmp_path, monkeypatch):
    monkeypatch.setattr(grader_module.DockerRunner, "image_id", lambda self, reference: None)
    (tmp_path / "batches").mkdir()
    result = CliRunner().invoke(
        main,
        [
            "scheduler",
            "--once",
            "--batches-dir",
            str(tmp_path / "batches"),
            "--bench-root",
            str(tmp_path),
            "--results-dir",
            str(tmp_path / "runs"),
            "--results-repo",
            str(tmp_path / "records"),
            "--state-root",
            str(tmp_path / "state"),
        ],
    )
    assert result.exit_code != 0
    assert "grader_image_unavailable" in result.output


def test_grader_build_command_prints_the_built_image_id(monkeypatch):
    built = []
    monkeypatch.setattr(
        grader_module.DockerRunner,
        "build",
        lambda self, tag, context: built.append((tag, context)) or 0,
    )
    monkeypatch.setattr(
        grader_module.DockerRunner, "image_id", lambda self, reference: FIXTURE_IMAGE_ID
    )
    result = CliRunner().invoke(main, ["grader", "build", "--tag", "sq-grader:test"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == FIXTURE_IMAGE_ID
    assert built == [("sq-grader:test", grader_module.IMAGE_CONTEXT)]
    assert (grader_module.IMAGE_CONTEXT / "Dockerfile").is_file()
    assert "--require-hashes" in (grader_module.IMAGE_CONTEXT / "Dockerfile").read_text()


class CannedOutput(LocalDocker):
    """Records the legacy grading container and answers with a fixed evaluation."""

    def run(self, arguments, *, timeout, stdout_limit=0):
        self.runs.append(arguments)
        return DockerRun(0, "", EVALUATION_SENTINEL + json.dumps(valid_evaluation()).encode() + b"\n")


def test_legacy_evaluation_mounts_only_run_inputs_and_keeps_patch_errors(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "cards/1").mkdir(parents=True)
    (run_dir / "cards/1/card_impl.py").write_text("x = 1\n")
    (run_dir / "status.json").write_text('{"1": "completed"}')
    (run_dir / "engine_diff.patch").write_text("not a patch\n")
    (run_dir / "operator-notes.txt").write_text("private")
    engine = tmp_path / "engine"
    engine.mkdir()
    cards = tmp_path / "cards"
    cards.mkdir()
    docker = CannedOutput()
    result = local_grader(docker=docker).evaluate_legacy(run_dir, cards, engine)
    assert result.engine_result.errors[0].startswith("Failed to apply engine_diff.patch")
    [arguments] = docker.runs
    targets = {
        dict(f.split("=", 1) for f in arguments[i + 1].split(",") if "=" in f)["dst"]
        for i, value in enumerate(arguments)
        if value == "--mount"
    }
    assert {"/grade/run/status.json", "/grade/run/cards"} <= targets
    assert "/grade/out" not in targets
    assert {"/grade/legacy/workspace/cards", "/grade/legacy/workspace/engine"} <= targets
    assert "/grade/run" not in targets
    assert not any("operator-notes" in value for value in arguments)


def test_counts_too_large_to_record_still_produce_a_record_without_scores(tmp_path):
    """Scores that cannot be serialized fail inside the grading guard, not at the record write."""
    huge = FullEvalResult(
        sos_results={
            key: CardResult(
                collector_number=key, tests_passed=10**4299, tests_total=10**4299, pass_rate=1.0
            )
            for key in [f"hob_{number}" for number in range(10)]
        },
        engine_result=EngineResult(tests_passed=1, tests_total=1, pass_rate=1.0),
    )
    opts = options(tmp_path, grader=local_grader(), evaluator=lambda *a, **k: huge)
    record = run_benchmark(**opts)
    assert record.run_metadata["collection_error"] == {"stage": "grading", "reason": "KarnError"}
    for score in record.scores.values():
        assert not score["evaluated"]
        assert score["missing_reasons"] == ["collection_failed:grading"]
    assert (opts["results_dir"] / record.run_id / "run-record.json").is_file()


# ---- interruption cleanup ------------------------------------------------------------------


def started_clients(monkeypatch) -> list:
    clients, popen = [], subprocess.Popen

    def recording(*args, **kwargs):
        clients.append(popen(*args, **kwargs))
        return clients[-1]

    monkeypatch.setattr(grader_module.subprocess, "Popen", recording)
    return clients


@pytest.mark.parametrize("stdout_limit", [0, 4096])
def test_an_interrupted_runner_kills_and_reaps_its_client_and_releases_its_pipes(
    tmp_path, monkeypatch, stdout_limit
):
    from silverquillm.karn.interruption import terminate_as_interrupt

    fake_docker_client(tmp_path, monkeypatch, "exec sleep 600\n")
    clients = started_clients(monkeypatch)
    timer = threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGTERM))
    timer.start()
    started = time.monotonic()
    with pytest.raises(KeyboardInterrupt, match="signal"), terminate_as_interrupt():
        REAL_RUN(grader_module.DockerRunner(), ["run"], timeout=600, stdout_limit=stdout_limit)
    timer.join()
    assert time.monotonic() - started < 30
    [client] = clients
    assert client.returncode is not None, "the client was reaped"
    assert client.stderr.closed and (client.stdout is None or client.stdout.closed)
    assert not [t for t in threading.enumerate() if "drain_" in t.name and t.is_alive()]


def test_an_interruption_while_readers_drain_after_exit_still_propagates(tmp_path, monkeypatch):
    """A client that exited can leave a child holding its pipes; SIGTERM then must not vanish."""
    from silverquillm.karn.interruption import terminate_as_interrupt

    fake_docker_client(tmp_path, monkeypatch, "sleep 3 &\nexit 0\n")
    timer = threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGTERM))
    timer.start()
    with pytest.raises(KeyboardInterrupt, match="signal"), terminate_as_interrupt():
        REAL_RUN(grader_module.DockerRunner(), ["run"], timeout=30)
    timer.join()


class Interrupted(LocalDocker):
    """The container named by ``--name`` is interrupted during probing or grading."""

    def __init__(self, stage, *, removal_fails=False):
        super().__init__()
        self.stage, self.removal_fails, self.names = stage, removal_fails, []

    def run(self, arguments, *, timeout, stdout_limit=0):
        is_probe = grader_module.PROBE in arguments
        if (self.stage == "probe") == is_probe:
            self.names.append(arguments[arguments.index("--name") + 1])
            raise KeyboardInterrupt("original interruption")
        return super().run(arguments, timeout=timeout, stdout_limit=stdout_limit)

    def remove(self, name):
        super().remove(name)
        if self.removal_fails:
            raise KeyboardInterrupt("repeated interruption during cleanup")


@pytest.mark.parametrize("removal_fails", [False, True])
@pytest.mark.parametrize("stage", ["probe", "grading"])
def test_an_interrupted_container_is_removed_by_name_and_the_interruption_kept(
    tmp_path, stage, removal_fails
):
    root = benchmark_data(tmp_path / "data")
    workspace = root / "benchmarks/example/workspace"
    docker = Interrupted(stage, removal_fails=removal_fails)
    grader = local_grader(docker=docker)
    with pytest.raises(KeyboardInterrupt, match="original interruption"):
        if stage == "probe":
            grader.engine_health(workspace)
        else:
            grader.evaluate_run(
                tmp_path, load_benchmark(root, "example"), workspace_source=workspace
            )
    [name] = docker.names
    assert name.startswith("sq-grade-")
    assert docker.removed == [name]


@pytest.mark.parametrize("stage", ["probe", "grading"])
def test_a_grader_interruption_still_writes_the_interrupted_record(tmp_path, stage):
    docker = Interrupted(stage)
    opts = options(tmp_path, grader=local_grader(docker=docker))
    record = run_benchmark(**opts)
    execution = record.run_metadata["execution"]
    assert (execution["status"], execution["error"]) == ("interrupted", "operator_interruption")
    assert execution["workspace_stopped"]
    for score in record.scores.values():
        assert score["missing_reasons"] == ["interrupted_before_grading"]
    assert docker.removed == docker.names
    assert (opts["results_dir"] / record.run_id / "run-record.json").is_file()
