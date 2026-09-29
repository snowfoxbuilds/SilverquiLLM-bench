"""Re-grading retained runs on current grading inputs without touching their records."""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.karn import regrade as regrade_module
from silverquillm.karn.definition import KarnError
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.grader import DockerRun, GraderError
from silverquillm.karn.records import read_record
from silverquillm.karn.regrade import LiveContainers, recorded_grader, regrade

from .grader_fixtures import FIXTURE_IMAGE_ID, LocalDocker
from .test_karn_execution import options
from .test_karn_host import make_candidate


class FailingDocker(LocalDocker):
    """Fails the grading container of any run whose artifacts live under ``failing``."""

    def __init__(self, failing: Path, **kwargs):
        super().__init__(**kwargs)
        self.failing = str(failing)

    def run(self, arguments, *, timeout, stdout_limit=0):
        if any(self.failing in argument for argument in arguments):
            return DockerRun(125, "grader start failed")
        return super().run(arguments, timeout=timeout, stdout_limit=stdout_limit)


@pytest.fixture
def retained(tmp_path):
    """Two graded runs of one candidate and one of another, recorded as a run would."""
    opts = options(tmp_path)
    second = make_candidate(tmp_path / "second", main=["python3", "-c", "pass  # second"])
    records = [
        run_benchmark(**opts, run_id="run-a"),
        run_benchmark(**opts, run_id="run-b"),
        run_benchmark(**{**opts, "build_output": second.build_output}, run_id="run-c"),
    ]
    return SimpleNamespace(opts=opts, records=records, out=tmp_path / "regrade")


def invoke(retained, docker=None, **changes):
    return regrade(
        **{
            "bench_root": retained.opts["bench_root"],
            "benchmark_id": "example",
            "results_repo": retained.opts["results_repo"],
            "results_dir": retained.opts["results_dir"],
            "out": retained.out,
            "docker": docker or LocalDocker(),
            **changes,
        }
    )


def tree_digest(root: Path) -> dict:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def output_file(retained, run_id):
    return next(retained.out.glob(f"*/{run_id}.json"), retained.out / "missing" / run_id)


def output(retained, run_id):
    return json.loads(output_file(retained, run_id).read_text())


def graded(retained):
    return sorted(path.name for path in retained.out.glob("*/*.json"))


def test_unchanged_inputs_reproduce_each_records_scores_and_leave_records_untouched(retained):
    records_before = tree_digest(retained.opts["results_repo"])
    runs_before = tree_digest(retained.opts["results_dir"])

    summary = invoke(retained)

    for record in retained.records:
        result = output(retained, record.run_id)
        assert result["scores"] == record.scores
        assert result["grading_inputs_digest"] == record.run_metadata["grading_inputs"]["digest"]
        assert result["source"]["grading_inputs_digest"] == result["grading_inputs_digest"]
        assert result["grading_isolation"]["grader_image_id"] == FIXTURE_IMAGE_ID
        assert result["benchmark_configuration_changed"] is False
    assert tree_digest(retained.opts["results_repo"]) == records_before
    assert tree_digest(retained.opts["results_dir"]) == runs_before
    assert [row["runs"] for row in summary["candidates"]] in ([2, 1], [1, 2])
    assert summary["skipped"] == summary["errors"] == []
    assert json.loads((retained.out / "summary.json").read_text()) == summary


def test_selection_by_run_and_candidate_prefix_and_other_benchmarks_are_ignored(retained):
    other = retained.opts["results_repo"] / "results" / ("f" * 64) / "elsewhere"
    other.mkdir(parents=True)
    (other / "manifest.json").write_text('{"benchmark": "another", "schema_version": 2}')

    summary = invoke(retained, runs=["run-a"])
    assert graded(retained) == ["run-a.json"]
    assert summary["skipped"] == []

    candidate = retained.records[2].candidate.hash
    invoke(retained, candidates=[candidate[:10]])
    assert graded(retained) == ["run-a.json", "run-c.json"]

    with pytest.raises(KarnError, match="regrade_selection_matched_nothing:missing"):
        invoke(retained, runs=["missing"])
    # A run prefix is matched against run ids only, never candidate hashes.
    with pytest.raises(KarnError, match="matched_nothing"):
        invoke(retained, runs=["run-a", candidate[:8]])


def test_an_unreadable_record_of_the_benchmark_is_skipped(retained):
    broken = retained.opts["results_repo"] / "results" / ("e" * 64) / "broken"
    broken.mkdir(parents=True)
    (broken / "manifest.json").write_text('{"benchmark": "example", "schema_version": 2}')
    (broken / "scores.json").write_text("{}")

    summary = invoke(retained)

    assert summary["skipped"] == [{"run_id": "broken", "reason": "invalid_record"}]
    assert len(graded(retained)) == 3


def test_a_run_without_local_artifacts_is_graded_from_its_workspace_archive(retained, tmp_path):
    moved = tmp_path / "moved"
    shutil.move(retained.opts["results_dir"] / "run-a", moved / "run-a")

    summary = invoke(retained, runs=["run-a"])

    assert summary["skipped"] == summary["errors"] == []
    result = output(retained, "run-a")
    assert result["source"]["workspace"] == "results_repo"
    assert result["scores"] == retained.records[0].scores
    assert sorted(path.name for path in retained.out.iterdir()) == [
        retained.records[0].candidate.hash,
        "summary.json",
    ]


def test_a_missing_workspace_is_skipped_unless_results_dir_holds_the_moved_artifacts(
    retained, tmp_path
):
    moved = tmp_path / "moved"
    shutil.move(retained.opts["results_dir"] / "run-a", moved / "run-a")
    shutil.rmtree(next((retained.opts["results_repo"] / "workspaces").glob("*/run-a")))

    summary = invoke(retained)
    assert summary["skipped"] == [{"run_id": "run-a", "reason": "workspace_unavailable"}]
    assert not output_file(retained, "run-a").exists()

    summary = invoke(retained, results_dir=moved)
    assert summary["skipped"] == []
    assert output(retained, "run-a")["source"]["workspace"] == "run_artifacts"
    assert output(retained, "run-a")["scores"] == retained.records[0].scores


def test_a_grading_source_outside_the_run_artifacts_is_refused(retained):
    manifest = retained.opts["results_repo"] / "results"
    path = next(manifest.glob("*/run-a/manifest.json"))
    value = json.loads(path.read_text())
    value["run_metadata"]["grading_source"]["selected"] = "../run-b/workspace_final"
    path.write_text(json.dumps(value))
    read_record(path.parent)

    summary = invoke(retained)

    assert {"run_id": "run-a", "reason": "grading_source_invalid"} in summary["skipped"]


def test_a_missing_grader_image_skips_every_run(retained):
    summary = invoke(retained, docker=LocalDocker(image_id=None))
    assert {row["reason"] for row in summary["skipped"]} == {"grader_image_unavailable"}
    assert graded(retained) == []


def test_a_grader_built_for_another_python_is_refused():
    docker = SimpleNamespace(image_id=lambda ref: ref, image_python=lambda ref: "3.13")
    record = SimpleNamespace(
        run_metadata={
            "grading_isolation": {
                "grader_image_id": FIXTURE_IMAGE_ID,
                "candidate_python": "3.14.4",
                "grader_python": "3.14",
            }
        }
    )
    with pytest.raises(regrade_module.Skip, match="grader_python_mismatch"):
        recorded_grader(record, docker, 60)


def test_one_failing_run_is_recorded_and_the_others_are_graded(retained):
    docker = FailingDocker(retained.opts["results_dir"].resolve() / "run-b")

    summary = invoke(retained, docker=docker)

    failed = output(retained, "run-b")
    assert failed["error"]["reason"] == "exit_125"
    assert "scores" not in failed
    assert [row["run_id"] for row in summary["errors"]] == ["run-b"]
    assert output(retained, "run-a")["scores"] == retained.records[0].scores
    assert output(retained, "run-c")["scores"] == retained.records[2].scores


def test_the_command_exits_non_zero_when_a_run_errors(retained, monkeypatch):
    monkeypatch.setattr(
        regrade_module,
        "DockerRunner",
        lambda: FailingDocker(retained.opts["results_dir"].resolve() / "run-b"),
    )
    arguments = [
        "regrade", "--benchmark", "example", "--out", str(retained.out),
        "--bench-root", str(retained.opts["bench_root"]),
        "--results-repo", str(retained.opts["results_repo"]),
        "--results-dir", str(retained.opts["results_dir"]),
    ]  # fmt: skip

    result = CliRunner().invoke(main, arguments)

    assert result.exit_code == 1, result.output
    assert "error run-b: exit_125" in result.output


def test_graded_runs_are_reused_until_forced_or_the_grading_inputs_change(retained):
    invoke(retained)
    docker = LocalDocker()
    invoke(retained, docker=docker)
    assert docker.runs == []

    invoke(retained, docker=docker, force=True)
    assert len(docker.runs) == 3

    suite = retained.opts["bench_root"] / "benchmarks/example/data/tests/audited/fdn/fdn_1/tests.py"
    suite.write_text(suite.read_text() + "def test_another(): assert value == 1\n")
    changed = LocalDocker()
    summary = invoke(retained, docker=changed)
    assert len(changed.runs) == 3
    result = output(retained, "run-a")
    assert result["grading_inputs_digest"] != result["source"]["grading_inputs_digest"]
    assert result["scores"]["fdn_regression"]["tests_total"] == 2
    assert summary["grading_inputs_digest"] == result["grading_inputs_digest"]


def test_an_errored_run_is_graded_again_on_the_next_invocation(retained):
    invoke(retained, docker=FailingDocker(retained.opts["results_dir"].resolve() / "run-b"))
    docker = LocalDocker()
    invoke(retained, docker=docker)
    assert len(docker.runs) == 1
    assert "scores" in output(retained, "run-b")


@pytest.mark.parametrize(
    ("kept", "inside", "name"),
    [
        ("results_repo", "regrade", "results_repo"),
        ("results_dir", "run-a/regrade", "results_dir"),
        ("results_dir", "run-a/workspace_final", "results_dir"),
        ("results_repo", "..", "results_repo"),
    ],
)
def test_output_overlapping_the_records_or_run_artifacts_is_refused(retained, kept, inside, name):
    records_before = tree_digest(retained.opts["results_repo"])
    runs_before = tree_digest(retained.opts["results_dir"])
    with pytest.raises(KarnError, match="regrade_output_overlaps_" + name):
        invoke(retained, out=retained.opts[kept] / inside)
    assert tree_digest(retained.opts["results_repo"]) == records_before
    assert tree_digest(retained.opts["results_dir"]) == runs_before


def edit_manifest(retained, run_id, change):
    path = next((retained.opts["results_repo"] / "results").glob(f"*/{run_id}/manifest.json"))
    value = json.loads(path.read_text())
    change(value)
    path.write_text(json.dumps(value))


def workspace_mounts(docker):
    return [
        dict(field.split("=", 1) for field in value.split(",") if "=" in field)["src"]
        for run in docker.runs
        for name, value in run["options"]
        if name == "--mount" and "dst=/grade/workspace" in value
    ]


def test_a_records_artifact_pointer_never_chooses_the_mounted_directory(retained, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    def point_elsewhere(value):
        value["artifact_pointers"][0]["location"] = "/"
        value["run_metadata"]["grading_source"]["selected"] = str(elsewhere.relative_to("/"))

    edit_manifest(retained, "run-a", point_elsewhere)
    docker = LocalDocker()
    summary = invoke(retained, docker=docker, runs=["run-a"])

    # The archive belongs to the recorded graded copy, so it is refused for another path.
    assert summary["skipped"] == [
        {"run_id": "run-a", "reason": "workspace_archive_refused:graded_digest_unrecorded"}
    ]
    assert str(elsewhere) not in workspace_mounts(docker)


def test_an_execution_run_id_that_is_not_a_run_id_is_refused(retained):
    edit_manifest(retained, "run-a", lambda v: v["run_metadata"].update(execution_run_id="/"))
    docker = LocalDocker()
    summary = invoke(retained, docker=docker, runs=["run-a"])
    assert summary["skipped"] == [{"run_id": "run-a", "reason": "grading_source_invalid"}]
    assert docker.runs == []


@pytest.mark.parametrize(
    "previous", ["[]", '{"scores": {}}', "not json", '{"run_id": "run-a", "scores": {}}']
)
def test_a_malformed_previous_output_is_graded_again(retained, previous):
    path = retained.out / retained.records[0].candidate.hash / "run-a.json"
    path.parent.mkdir(parents=True)
    path.write_text(previous)

    summary = invoke(retained)

    assert summary["errors"] == []
    assert output(retained, "run-a")["scores"] == retained.records[0].scores


def test_an_output_graded_by_other_grading_code_is_graded_again(retained, monkeypatch):
    invoke(retained)
    monkeypatch.setattr(regrade_module, "grading_code_digest", lambda: "sha256:" + "9" * 64)
    docker = LocalDocker()
    invoke(retained, docker=docker)
    assert len(docker.runs) == 3
    assert output(retained, "run-a")["grading_code_digest"] == "sha256:" + "9" * 64


class LateDocker:
    """``docker rm -f`` before the daemon has created the container removes nothing."""

    def __init__(self):
        self.registered, self.go = threading.Event(), threading.Event()
        self.running, self.removed = set(), []

    def run(self, arguments, **options):
        name = arguments[arguments.index("--name") + 1]
        self.registered.set()
        self.go.wait(10)
        self.running.add(name)
        return DockerRun(0, "")

    def remove(self, name):
        self.removed.append(name)
        self.running.discard(name)


def test_a_container_created_after_the_stop_is_still_removed():
    docker = LateDocker()
    live = LiveContainers(docker)
    worker = threading.Thread(target=live.run, args=(["run", "--name", "sq-grade-z", "image"],))
    worker.start()
    assert docker.registered.wait(10)

    stopping = threading.Thread(target=live.stop, kwargs={"seconds": 5})
    stopping.start()
    time.sleep(0.2)
    docker.go.set()
    worker.join(10)
    stopping.join(10)

    assert docker.running == set()
    assert not stopping.is_alive()


class BlockingDocker:
    def __init__(self):
        self.started, self.release = threading.Event(), threading.Event()
        self.removed = []

    def run(self, arguments, **options):
        self.started.set()
        self.release.wait(10)
        return DockerRun(137, "")

    def remove(self, name):
        self.removed.append(name)
        self.release.set()


def test_stopping_removes_running_grader_containers_and_refuses_new_ones():
    docker = BlockingDocker()
    live = LiveContainers(docker)
    worker = threading.Thread(
        target=live.run, args=(["run", "--rm", "--name", "sq-grade-x", "image"],)
    )
    worker.start()
    assert docker.started.wait(10)

    live.stop()
    worker.join(10)

    assert set(docker.removed) == {"sq-grade-x"}
    assert live.names == set()
    with pytest.raises(GraderError, match="regrade_interrupted"):
        live.run(["run", "--name", "sq-grade-y", "image"])


def test_an_interrupt_stops_the_batch_and_writes_no_partial_output(retained, monkeypatch):
    calls = []

    def interrupt(*args, **kwargs):
        calls.append(args)
        raise KeyboardInterrupt

    monkeypatch.setattr(regrade_module, "_regrade_one", interrupt)
    with pytest.raises(KeyboardInterrupt):
        invoke(retained, workers=1)
    assert calls
    assert not (retained.out / "summary.json").exists()
