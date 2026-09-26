"""Containerized grading: sandbox arguments, untrusted output, and failure recording."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm import evaluator
from silverquillm.cli import main
from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult
from silverquillm.karn import grader as grader_module
from silverquillm.karn.definition import KarnError
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.grader import (
    ENVIRONMENT,
    MAX_EVALUATION_BYTES,
    WORKER,
    GraderError,
    _read_output,
    evaluation_from_json,
)

from .grader_fixtures import FIXTURE_IMAGE_ID, LocalDocker, local_grader
from .test_karn_execution import options


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
        writable = [row for row in mounts(run) if not row[2]]
        home_state = str(Path.home() / ".local/state")
        assert all(not source.startswith(home_state) for source, _, _ in mounts(run))
        assert all(not source.endswith("docker.sock") for source, _, _ in mounts(run))
        if WORKER in run["command"]:
            assert [target for _, target, _ in writable] == ["/grade/out"]
            targets = {target for _, target, _ in mounts(run)}
            assert "/grade/workspace" in targets and "/opt/sq/silverquillm" in targets
            assert not any(target.startswith(str(opts["results_dir"])) for target in targets)
        else:
            assert writable == []
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


def test_output_file_must_be_a_bounded_regular_file(tmp_path):
    with pytest.raises(GraderError, match="evaluation_missing"):
        _read_output(tmp_path, "evaluation.json")
    secret = tmp_path.parent / "host-secret"
    secret.write_text("secret")
    (tmp_path / "evaluation.json").symlink_to(secret)
    with pytest.raises(GraderError, match="evaluation_missing"):
        _read_output(tmp_path, "evaluation.json")
    (tmp_path / "evaluation.json").unlink()
    os.mkfifo(tmp_path / "evaluation.json")
    with pytest.raises(GraderError, match="evaluation_not_regular"):
        _read_output(tmp_path, "evaluation.json")
    (tmp_path / "evaluation.json").unlink()
    (tmp_path / "evaluation.json").write_bytes(b" " * (MAX_EVALUATION_BYTES + 1))
    with pytest.raises(GraderError, match="evaluation_too_large"):
        _read_output(tmp_path, "evaluation.json")


class GradingFails(LocalDocker):
    """The engine probe runs; the grading container exits with the given result."""

    def __init__(self, result):
        super().__init__()
        self.result = result

    def run(self, arguments, *, timeout):
        if WORKER in arguments:
            self.runs.append({"options": [], "image": None, "command": arguments})
            return self.result
        return super().run(arguments, timeout=timeout)


@pytest.mark.parametrize(
    ("result", "reason"), [((None, "slow"), "timeout"), ((1, "Traceback"), "exit_1")]
)
def test_grading_container_failure_is_recorded_and_the_run_still_written(tmp_path, result, reason):
    docker = GradingFails(result)
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
    timed_out.docker.run = lambda arguments, timeout: (None, "")
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

    def run(self, arguments, *, timeout):
        self.runs.append(arguments)
        for index, value in enumerate(arguments):
            if value == "--mount" and "dst=/grade/out" in arguments[index + 1]:
                fields = dict(f.split("=", 1) for f in arguments[index + 1].split(","))
                Path(fields["src"], "evaluation.json").write_text(json.dumps(valid_evaluation()))
        return 0, ""


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
    assert {"/grade/run/status.json", "/grade/run/cards", "/grade/out"} <= targets
    assert {"/grade/legacy/workspace/cards", "/grade/legacy/workspace/engine"} <= targets
    assert "/grade/run" not in targets
    assert not any("operator-notes" in value for value in arguments)
