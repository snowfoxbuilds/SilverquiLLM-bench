"""Containerized grading: sandbox arguments, untrusted output, and failure recording."""

from __future__ import annotations

import copy
import itertools
import json
import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

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
from silverquillm.karn.records import validate_scores
from silverquillm.results_repo import InvalidRunRecordError

from .grader_fixtures import FIXTURE_IMAGE_ID, LocalDocker, local_grader
from .test_karn_execution import benchmark_data, options


def mounts(run):
    rows = []
    for name, value in run["options"]:
        if name == "--mount":
            fields = dict(field.split("=", 1) for field in value.split(",") if "=" in field)
            rows.append((fields["src"], fields["dst"], value.endswith(",readonly")))
    return rows


def test_every_grading_container_is_sandboxed_and_sees_only_declared_inputs(plain_run):
    opts, record = plain_run.opts, plain_run.record
    docker = opts["grader"].docker
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
        engine_result=EngineResult(
            tests_passed=3,
            tests_total=3,
            pass_rate=1.0,
            test_nodes=[
                {"test_node": "test_zones.py::test_a", "outcome": "pass"},
                {"test_node": "zone_change/test_lki.py::test_b[two]", "outcome": "pass"},
                {"test_node": "test_combat.py", "outcome": "pass"},
            ],
        ),
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
    assert result.engine_result.test_nodes == value["engine_result"]["test_nodes"]


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
        lambda v: v["engine_result"].pop("test_nodes"),
        lambda v: v["engine_result"].update(test_nodes={"test_zones.py::test_a": "pass"}),
        lambda v: v["engine_result"].update(test_nodes=[{"test_node": "x"}]),
        lambda v: v["engine_result"].update(
            test_nodes=[{"test_node": "x", "outcome": "pass", "extra": 1}]
        ),
        lambda v: v["engine_result"].update(test_nodes=[{"test_node": 7, "outcome": "pass"}]),
        lambda v: v["engine_result"].update(test_nodes=[{"test_node": "x", "outcome": "ok"}]),
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


def test_a_hob_medium_sized_engine_payload_fits_the_evaluation_cap():
    value = valid_evaluation()
    nodes = [
        {
            "test_node": f"test_continuous_effects_layers.py::TestLayerSystem::"
            f"test_characteristic_defining_ability_applies_in_layer_seven_{index:04d}[case]",
            "outcome": "fail" if index % 7 else "pass",
        }
        for index in range(3000)
    ]
    value["engine_result"].update(
        tests_passed=0,
        tests_failed=3000,
        tests_total=3000,
        pass_rate=0.0,
        test_nodes=nodes,
        errors=[f"FAILED engine_tests/{node['test_node']}" for node in nodes],
    )
    document = json.dumps(value).encode()
    assert len(document) < MAX_EVALUATION_BYTES
    assert evaluation_from_json(document).engine_result.test_nodes == nodes


def _engine_suite_options(tmp_path, *, audited: bool):
    docker = LocalDocker()
    opts = options(tmp_path, grader=local_grader(docker=docker))
    root = opts["bench_root"] / "benchmarks/example"
    (root / "workspace/conftest.py").write_text("")
    (root / "workspace/pytest.ini").write_text("[pytest]\naddopts = --import-mode=importlib\n")
    if audited:
        suite = root / "data/tests/audited/engine/test_audited.py"
        suite.parent.mkdir(parents=True)
        suite.write_text("from engine.card import value\ndef test_audited(): assert value == 1\n")
        (root / "workspace/engine_tests/test_engine.py").write_text(
            "def test_staged(): assert False\n"
        )
    return docker, opts


def _benchmark_mount_targets(docker) -> list[str]:
    worker = next(run for run in docker.runs if WORKER in run["command"])
    prefix = "/opt/sq/benchmarks/example/"
    return sorted(
        target.removeprefix(prefix) for _, target, _ in mounts(worker) if target.startswith(prefix)
    )


def test_grading_mounts_the_audited_engine_tests_and_never_the_staged_copy(tmp_path):
    docker, opts = _engine_suite_options(tmp_path, audited=True)
    record = run_benchmark(**opts)
    assert _benchmark_mount_targets(docker) == [
        "data/tests/audited/engine",
        "data/tests/audited/fdn",
        "workspace/conftest.py",
        "workspace/pytest.ini",
        "workspace/test_utils.py",
    ]
    engine = record.scores["engine_regression"]
    assert engine["tests_passed"] == engine["tests_total"] == 1
    assert engine["test_nodes"] == [
        {"test_node": "test_audited.py::test_audited", "outcome": "pass"}
    ]
    validate_scores(record.scores)


def test_grading_mounts_without_audited_engine_tests_are_unchanged(tmp_path):
    docker, opts = _engine_suite_options(tmp_path, audited=False)
    # Graded code that prints, even into the grader process's own stdout, never reaches the
    # worker's result line.
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
    assert _benchmark_mount_targets(docker) == [
        "data/tests/audited/fdn",
        "workspace/conftest.py",
        "workspace/engine_tests",
        "workspace/pytest.ini",
        "workspace/test_utils.py",
    ]
    assert record.scores["engine_regression"]["test_nodes"] == [
        {"test_node": "test_engine.py::test_value", "outcome": "pass"}
    ]


REAL_RUN = grader_module.DockerRunner.run
REAL_BUILD = grader_module.DockerRunner.build
REAL_IMAGE_PYTHON = grader_module.DockerRunner.image_python
REAL_REMOVE = grader_module.DockerRunner.remove


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


CANDIDATE_IMAGE_ID = "sha256:" + "c" * 64
PYTHON_3_14 = DockerRun(0, "", b"3.14.4\n")


class ProbedDocker(LocalDocker):
    """Answers the candidate-Python probe and labels each grader image with its version."""

    def __init__(self, answer=PYTHON_3_14, graders=None, **kwargs):
        super().__init__(**kwargs)
        self.answer, self.probes = answer, []
        self.graders = {"silverquillm-grader:py3.14": "3.14"} if graders is None else graders

    def image_id(self, reference):
        return FIXTURE_IMAGE_ID if reference in self.graders else None

    def image_python(self, reference):
        assert reference == FIXTURE_IMAGE_ID
        return next(iter(self.graders.values()))

    def run(self, arguments, *, timeout, stdout_limit=0):
        if "--entrypoint" in arguments:
            self.probes.append({"arguments": arguments, "timeout": timeout, "limit": stdout_limit})
            return self.answer
        return super().run(arguments, timeout=timeout, stdout_limit=stdout_limit)


def test_the_python_probe_runs_the_candidate_image_sandboxed_and_reads_only_a_version():
    docker = ProbedDocker()
    assert grader_module.candidate_python(CANDIDATE_IMAGE_ID, docker) == "3.14.4"
    [probe] = docker.probes
    arguments = probe["arguments"]
    options = dict(itertools.pairwise(arguments))
    assert arguments[:2] == ["run", "--rm"]
    assert options["--pull"] == "never" and options["--network"] == "none"
    assert options["--user"] == f"{os.getuid()}:{os.getgid()}"
    assert "--read-only" in arguments and options["--cap-drop"] == "ALL"
    assert options["--security-opt"] == "no-new-privileges"
    assert "--no-healthcheck" in arguments
    assert options["--memory"] == options["--memory-swap"] and options["--pids-limit"]
    assert "--mount" not in arguments and "--env" not in arguments and "-v" not in arguments
    assert options["--entrypoint"] == "python3"
    assert arguments[arguments.index(CANDIDATE_IMAGE_ID) + 1 :] == [
        "-I", "-S", "-c", grader_module.PYTHON_PROBE,
    ]  # fmt: skip
    assert probe["limit"] == grader_module.PYTHON_PROBE_BYTES
    assert probe["timeout"] == grader_module.PROBE_TIMEOUT


@pytest.mark.parametrize(
    "stdout",
    [
        b"3.12.9\n", b"2.7.18\n", b"3.14\n", b"3.14.4", b"3.14.4\n\n", b" 3.14.4\n",
        b"03.14.4\n", b"3.14.4rc1\n", b"3.14.4\r\n", b"", b"\xff\n", b"3.1414.4\n",
    ],
)  # fmt: skip
def test_any_answer_but_a_supported_release_refuses_the_candidate(stdout):
    docker = ProbedDocker(answer=DockerRun(0, "", stdout))
    with pytest.raises(GraderError, match="candidate_python_unsupported"):
        grader_module.candidate_python(CANDIDATE_IMAGE_ID, docker)


@pytest.mark.parametrize(
    ("answer", "reason", "removed"),
    [
        (
            DockerRun(127, "python3: executable file not found"),
            "candidate_python_unsupported",
            True,
        ),
        (DockerRun(1, "Traceback"), "candidate_python_unsupported", False),
        (DockerRun(None, "", overflow=True), "candidate_python_unsupported", True),
        (DockerRun(None, ""), "candidate_python_unsupported", True),
        (DockerRun(125, "daemon error"), "python_probe_container_failed", True),
    ],
)
def test_a_failed_probe_refuses_and_removes_a_container_it_may_leave(answer, reason, removed):
    docker = ProbedDocker(answer=answer)
    with pytest.raises(GraderError, match=reason):
        grader_module.candidate_python(CANDIDATE_IMAGE_ID, docker)
    assert bool(docker.removed) == removed
    assert all(name.startswith("sq-probe-") for name in docker.removed)


def test_the_probe_names_only_an_image_id():
    with pytest.raises(GraderError, match="candidate_image_id_invalid"):
        grader_module.candidate_python("python:3.14-slim", ProbedDocker())
    with pytest.raises(GraderError, match="candidate_image_id_invalid"):
        grader_module.candidate_python("--privileged", ProbedDocker())


def test_the_grader_is_the_one_built_for_the_candidates_minor_version():
    docker = ProbedDocker(graders={"silverquillm-grader:py3.14": "3.14"})
    grader = grader_module.select_grader(CANDIDATE_IMAGE_ID, docker=docker, timeout=7)
    assert grader.image_id == FIXTURE_IMAGE_ID and grader.timeout == 7
    assert grader.isolation() == {
        "mode": "container",
        "grader_image_id": FIXTURE_IMAGE_ID,
        "network": "none",
        "candidate_python": "3.14.4",
        "grader_python": "3.14",
    }


@pytest.mark.parametrize(
    ("answer", "graders", "reference", "reason"),
    [
        # A supported version whose grader was never built.
        (b"3.13.7\n", {"silverquillm-grader:py3.14": "3.14"}, None, "grader_image_unavailable"),
        # A version newer than every pinned base.
        (b"3.15.0\n", {"silverquillm-grader:py3.15": "3.15"}, None, "grader_image_unavailable"),
        # An override must exist and still be built for the candidate's version.
        (b"3.14.4\n", {"custom": "3.14"}, "missing", "grader_image_unavailable"),
        (b"3.14.4\n", {"custom": "3.13"}, "custom", "grader_python_mismatch"),
        # A tag that was retagged onto another version's grader is refused, not trusted.
        (b"3.14.4\n", {"silverquillm-grader:py3.14": "3.13"}, None, "grader_python_mismatch"),
        (b"3.14.4\n", {"silverquillm-grader:py3.14": None}, None, "grader_python_mismatch"),
    ],
)
def test_a_missing_or_mismatched_grader_refuses(answer, graders, reference, reason):
    docker = ProbedDocker(answer=DockerRun(0, "", answer), graders=graders)
    with pytest.raises(GraderError, match=reason):
        grader_module.select_grader(CANDIDATE_IMAGE_ID, reference, docker=docker)


def test_an_override_built_for_the_candidates_version_is_used():
    docker = ProbedDocker(graders={"custom": "3.14"})
    grader = grader_module.select_grader(CANDIDATE_IMAGE_ID, "custom", docker=docker)
    assert grader.isolation()["grader_python"] == "3.14"


def test_a_direct_run_grades_on_the_probed_version_and_records_it(tmp_path, monkeypatch):
    docker = ProbedDocker()
    monkeypatch.setattr(grader_module, "DockerRunner", lambda: docker)
    opts = options(tmp_path)
    opts.pop("grader")
    record = run_benchmark(**opts)
    assert len(docker.probes) == 1
    assert record.run_metadata["grading_isolation"]["candidate_python"] == "3.14.4"
    assert record.run_metadata["grading_isolation"]["grader_python"] == "3.14"
    assert all(score["tests_passed"] == 1 for score in record.scores.values())
    run_input = json.loads((opts["results_dir"] / record.run_id / "run-input.json").read_text())
    assert run_input["candidate_python"] == "3.14.4"


@pytest.mark.parametrize(
    ("answer", "graders", "reason"),
    [
        (DockerRun(0, "", b"3.12.3\n"), None, "candidate_python_unsupported"),
        (DockerRun(127, ""), None, "candidate_python_unsupported"),
        (DockerRun(0, "", b"3.14.4\n"), {}, "grader_image_unavailable"),
    ],
)
def test_a_direct_run_refuses_before_any_run_directory(
    tmp_path, monkeypatch, answer, graders, reason
):
    docker = ProbedDocker(answer=answer, graders=graders)
    monkeypatch.setattr(grader_module, "DockerRunner", lambda: docker)
    opts = options(tmp_path)
    opts.pop("grader")
    with pytest.raises(KarnError, match=reason):
        run_benchmark(**opts)
    assert not opts["results_dir"].exists()


def test_recorded_versions_must_agree_and_older_records_stay_valid(plain_run):
    record = copy.deepcopy(plain_run.record)
    assert set(record.run_metadata["grading_isolation"]) == {"mode", "grader_image_id", "network"}
    record.validate()
    isolation = record.run_metadata["grading_isolation"]
    isolation.update(candidate_python="3.14.4", grader_python="3.14")
    record.validate()
    for bad in (
        {"grader_python": "3.13"},
        {"candidate_python": "3.14"},
        {"candidate_python": 3.14},
        {"candidate_python": "3.14.4 "},
    ):
        record.run_metadata["grading_isolation"] = {**isolation, **bad}
        with pytest.raises(InvalidRunRecordError, match="invalid grading isolation"):
            record.validate()
    record.run_metadata["grading_isolation"] = {
        key: value for key, value in isolation.items() if key != "grader_python"
    }
    with pytest.raises(InvalidRunRecordError, match="invalid grading isolation"):
        record.validate()


def test_scheduler_refuses_to_start_without_an_explicit_grader_image(tmp_path, monkeypatch):
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
            "--grader-image",
            "silverquillm-grader:missing",
        ],
    )
    assert result.exit_code != 0
    assert "grader_image_unavailable" in result.output


def test_grader_build_builds_every_pinned_version_with_its_label(monkeypatch):
    built = []
    monkeypatch.setattr(
        grader_module.DockerRunner,
        "build",
        lambda self, tag, context, *, base, python: built.append((tag, context, base, python)) or 0,
    )
    monkeypatch.setattr(
        grader_module.DockerRunner, "image_id", lambda self, reference: FIXTURE_IMAGE_ID
    )
    result = CliRunner().invoke(main, ["grader", "build"])
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"silverquillm-grader:py3.13 {FIXTURE_IMAGE_ID}",
        f"silverquillm-grader:py3.14 {FIXTURE_IMAGE_ID}",
    ]
    assert built == [
        (f"silverquillm-grader:py{version}", grader_module.IMAGE_CONTEXT, base, version)
        for version, base in sorted(grader_module.GRADER_BASES.items())
    ]
    for base in grader_module.GRADER_BASES.values():
        assert re.fullmatch(r"python:3\.[0-9]+-slim@sha256:[0-9a-f]{64}", base)
    dockerfile = (grader_module.IMAGE_CONTEXT / "Dockerfile").read_text()
    assert "--require-hashes" in dockerfile and "FROM ${BASE}" in dockerfile


@pytest.mark.parametrize(
    ("variable", "graders", "reason"),
    [
        (None, {"silverquillm-grader:py3.13": "3.13"}, None),
        ("custom", {"custom": "3.13"}, None),
        # An unlabeled image, such as the old silverquillm-grader:local or alpine, is refused.
        ("alpine:latest", {"alpine:latest": None}, "grader_python_mismatch"),
        ("custom", {"custom": "3.14"}, "grader_python_mismatch"),
        (None, {}, "grader_image_unavailable"),
    ],
)
def test_the_legacy_lineage_grades_only_on_a_grader_labeled_313(
    tmp_path, monkeypatch, variable, graders, reason
):
    docker = ProbedDocker(graders=graders)
    docker.run = lambda arguments, *, timeout, stdout_limit=0: DockerRun(
        0, "", EVALUATION_SENTINEL + json.dumps(valid_evaluation()).encode() + b"\n"
    )
    monkeypatch.setattr(grader_module, "DockerRunner", lambda: docker)
    if variable is None:
        monkeypatch.delenv("SILVERQUILLM_GRADER_IMAGE", raising=False)
    else:
        monkeypatch.setenv("SILVERQUILLM_GRADER_IMAGE", variable)
    cards, engine = tmp_path / "cards", tmp_path / "engine"
    cards.mkdir()
    engine.mkdir()
    if reason is None:
        result = grader_module.evaluate_legacy(tmp_path, cards, engine)
        assert (
            result.engine_result.tests_total == valid_evaluation()["engine_result"]["tests_total"]
        )
    else:
        with pytest.raises(GraderError, match=reason):
            grader_module.evaluate_legacy(tmp_path, cards, engine)


def test_grader_build_takes_one_version_and_an_optional_tag(monkeypatch):
    built = []
    monkeypatch.setattr(
        grader_module.DockerRunner,
        "build",
        lambda self, tag, context, *, base, python: built.append((tag, python)) or 0,
    )
    monkeypatch.setattr(
        grader_module.DockerRunner, "image_id", lambda self, reference: FIXTURE_IMAGE_ID
    )
    result = CliRunner().invoke(main, ["grader", "build", "--python", "3.14", "--tag", "sq:t"])
    assert result.exit_code == 0, result.output
    assert built == [("sq:t", "3.14")]
    refused = CliRunner().invoke(main, ["grader", "build", "--tag", "sq:t"])
    assert refused.exit_code != 0 and "--tag needs exactly one --python" in refused.output
    unknown = CliRunner().invoke(main, ["grader", "build", "--python", "3.12"])
    assert unknown.exit_code != 0


def test_the_docker_runner_builds_with_the_pinned_base_and_version_label(monkeypatch):
    calls = []
    monkeypatch.setattr(
        grader_module.subprocess,
        "run",
        lambda arguments, **kwargs: calls.append(arguments) or SimpleNamespace(returncode=0),
    )
    REAL_BUILD(
        grader_module.DockerRunner(),
        "tag",
        Path("/context"),
        base="python:x@sha256:1",
        python="3.14",
    )
    monkeypatch.setattr(
        grader_module.subprocess,
        "run",
        lambda arguments, **kwargs: (
            calls.append(arguments) or SimpleNamespace(returncode=0, stdout=b"3.14\n")
        ),
    )
    assert REAL_IMAGE_PYTHON(grader_module.DockerRunner(), FIXTURE_IMAGE_ID) == "3.14"
    assert calls[-1] == [
        "docker", "image", "inspect", "--format",
        '{{index .Config.Labels "org.silverquillm.grader.python"}}', FIXTURE_IMAGE_ID,
    ]  # fmt: skip
    assert calls[0] == [
        "docker", "build", "--pull=false", "--build-arg", "BASE=python:x@sha256:1",
        "--label", "org.silverquillm.grader.python=3.14", "-t", "tag", "/context",
    ]  # fmt: skip


def test_a_removed_container_takes_its_anonymous_volumes_with_it(monkeypatch):
    calls = []
    monkeypatch.setattr(
        grader_module.subprocess, "run", lambda arguments, **kwargs: calls.append(arguments)
    )
    REAL_REMOVE(grader_module.DockerRunner(), "sq-probe-x")
    assert calls == [["docker", "rm", "-f", "-v", "sq-probe-x"]]


class CannedOutput(LocalDocker):
    """Records the legacy grading container and answers with a fixed evaluation."""

    def run(self, arguments, *, timeout, stdout_limit=0):
        self.runs.append(arguments)
        return DockerRun(
            0, "", EVALUATION_SENTINEL + json.dumps(valid_evaluation()).encode() + b"\n"
        )


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
