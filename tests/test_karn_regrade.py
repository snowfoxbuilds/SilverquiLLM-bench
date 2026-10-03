"""Re-grading retained runs on current grading inputs without touching their records."""

from __future__ import annotations

import hashlib
import json
import os
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
from silverquillm.karn.records import read_record, validate_scores
from silverquillm.karn.regrade import LiveContainers, recorded_grader, regrade
from silverquillm.results_repo import InvalidRunRecordError

from . import retained_runs
from .grader_fixtures import FIXTURE_IMAGE_ID, LocalDocker
from .retained_runs import building
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


def clone(template, directory: Path) -> SimpleNamespace:
    cloned = retained_runs.clone(template, directory)
    cloned.out = cloned.root / "regrade"
    return cloned


@pytest.fixture(scope="module")
def retained_template(tmp_path_factory):
    """Two graded runs of one candidate and one of another, recorded as a run would; built once."""
    root = tmp_path_factory.mktemp("retained")
    opts = options(root)
    second = make_candidate(root / "second", main=["python3", "-c", "pass  # second"])
    with building():
        records = [
            run_benchmark(**opts, run_id="run-a"),
            run_benchmark(**opts, run_id="run-b"),
            run_benchmark(**{**opts, "build_output": second.build_output}, run_id="run-c"),
        ]
    yield SimpleNamespace(root=root, opts=opts, records=records)
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def retained(retained_template, tmp_path):
    return clone(retained_template, tmp_path)


@pytest.fixture(scope="module")
def regraded_template(retained_template, tmp_path_factory):
    """The retained runs after one re-grade, so cache tests start from a filled cache."""
    directory = tmp_path_factory.mktemp("regraded")
    template = clone(retained_template, directory)
    with building():
        template.summary = invoke(template)
    yield template
    shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def regraded(regraded_template, tmp_path):
    cloned = clone(regraded_template, tmp_path)
    cloned.summary = regraded_template.summary
    return cloned


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
    assert [row["runs"] for row in summary["cohorts"]] in ([2, 1], [1, 2])
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


def test_graded_runs_are_reused_until_forced_or_the_grading_inputs_change(regraded):
    docker = LocalDocker()
    invoke(regraded, docker=docker)
    assert docker.runs == []

    invoke(regraded, docker=docker, force=True)
    assert len(docker.runs) == 3

    suite = regraded.opts["bench_root"] / "benchmarks/example/data/tests/audited/fdn/fdn_2/tests.py"
    suite.write_text(suite.read_text() + "def test_another(): assert value == 1\n")
    changed = LocalDocker()
    summary = invoke(regraded, docker=changed)
    assert len(changed.runs) == 3
    result = output(regraded, "run-a")
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


def test_an_output_graded_by_other_grading_code_is_graded_again(regraded, monkeypatch):
    monkeypatch.setattr(regrade_module, "grading_code_digest", lambda: "sha256:" + "9" * 64)
    docker = LocalDocker()
    invoke(regraded, docker=docker)
    assert len(docker.runs) == 3
    assert output(regraded, "run-a")["grading_code_digest"] == "sha256:" + "9" * 64


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


# --- Output containment: nothing reached through a link is ever read or written ----------


def protected(retained):
    return tree_digest(retained.opts["results_repo"]), tree_digest(retained.opts["results_dir"])


@pytest.mark.parametrize("target", ["results_repo", "results_dir"])
def test_a_candidate_output_directory_linked_into_retained_evidence_is_refused(retained, target):
    record = retained.records[0]
    inside = (
        retained.opts["results_dir"] / "run-a" / "workspace_final"
        if target == "results_dir"
        else next((retained.opts["results_repo"] / "results").glob("*/run-a"))
    )
    retained.out.mkdir()
    (retained.out / record.candidate.hash).symlink_to(inside, target_is_directory=True)
    before = protected(retained)

    summary = invoke(retained, runs=["run-a"])

    assert summary["errors"] == [
        {
            "run_id": "run-a",
            "reason": "regrade_output_unsafe:candidate_directory",
            "stderr_tail": "",
        }
    ]
    assert protected(retained) == before
    assert not (inside / "run-a.json").exists()


def test_an_existing_output_file_that_is_a_link_is_replaced_not_followed(retained, tmp_path):
    record = retained.records[0]
    target = tmp_path / "elsewhere.json"
    target.write_text("{}")
    directory = retained.out / record.candidate.hash
    directory.mkdir(parents=True)
    (directory / "run-a.json").symlink_to(target)

    invoke(retained, runs=["run-a"])

    assert target.read_text() == "{}"
    assert not (directory / "run-a.json").is_symlink()
    assert output(retained, "run-a")["scores"] == record.scores


@pytest.mark.parametrize("swap", ["link", "move"])
def test_a_candidate_directory_replaced_while_grading_is_not_written(
    retained, monkeypatch, swap, tmp_path
):
    record = retained.records[0]
    directory = retained.out / record.candidate.hash
    moved = tmp_path / "moved"
    original = regrade_module._scores

    def replace_directory(*args):
        directory.rename(moved)
        if swap == "link":
            directory.symlink_to(retained.opts["results_dir"] / "run-a" / "workspace_final")
        return original(*args)

    monkeypatch.setattr(regrade_module, "_scores", replace_directory)
    before = protected(retained)

    summary = invoke(retained, runs=["run-a"])

    assert [row["reason"] for row in summary["errors"]] == [
        "regrade_output_unsafe:candidate_replaced"
    ]
    assert list(moved.iterdir()) == []
    assert protected(retained) == before


def test_an_output_root_replaced_before_writing_is_refused(retained, monkeypatch, tmp_path):
    original = regrade_module._scores

    def replace_root(*args):
        retained.out.rename(tmp_path / "old-out")
        retained.out.symlink_to(retained.opts["results_dir"], target_is_directory=True)
        return original(*args)

    monkeypatch.setattr(regrade_module, "_scores", replace_root)
    before = protected(retained)

    with pytest.raises(regrade_module.UnsafeOutput, match="out_replaced"):
        invoke(retained, runs=["run-a"])
    assert protected(retained) == before


# --- Cache validation: a reused output must be a fully valid success ---------------------


def _drop_candidate_name(value):
    del value["candidate_name"]


def _null_dimension(value):
    value["scores"]["card_correctness"] = None


def _empty_dimension(value):
    value["scores"]["card_correctness"] = {}


def _missing_field(value):
    del value["scores"]["fdn_regression"]["tests_total"]


def _rate_out_of_range(value):
    value["scores"]["card_correctness"]["pass_rate"] = 500


def _rate_not_finite(value):
    value["scores"]["card_correctness"]["pass_rate"] = float("nan")


def _inconsistent_counts(value):
    score = value["scores"]["engine_regression"]
    score["tests_passed"] = score["tests_total"] + 1


def _rate_disagrees_with_counts(value):
    score = value["scores"]["fdn_regression"]
    score["pass_rate"] = 0.5 if score["pass_rate"] != 0.5 else 0.25


def _malformed_source_scores(value):
    value["source"]["scores"]["card_correctness"]["pass_rate"] = 0.123


def _wrong_source_digest(value):
    value["source"]["grading_inputs_digest"] = "sha256:" + "1" * 64


def _error_beside_scores(value):
    value["error"] = {"reason": "exit_1", "stderr_tail": ""}


def _bad_timestamp(value):
    value["graded_at"] = "yesterday"


@pytest.mark.parametrize(
    "damage",
    [
        _drop_candidate_name,
        _null_dimension,
        _empty_dimension,
        _missing_field,
        _rate_out_of_range,
        _rate_not_finite,
        _inconsistent_counts,
        _rate_disagrees_with_counts,
        _malformed_source_scores,
        _wrong_source_digest,
        _error_beside_scores,
        _bad_timestamp,
    ],
)
def test_a_damaged_cache_with_matching_digests_regrades_only_that_run(regraded, damage):
    path = output_file(regraded, "run-a")
    value = json.loads(path.read_text())
    damage(value)
    path.write_text(json.dumps(value))
    docker = LocalDocker()

    summary = invoke(regraded, docker=docker)

    assert len(docker.runs) == 1
    assert summary["errors"] == []
    repaired = output(regraded, "run-a")
    assert repaired["scores"] == regraded.records[0].scores
    assert repaired["candidate_name"] == output(regraded, "run-b")["candidate_name"]
    assert json.loads((regraded.out / "summary.json").read_text()) == summary


def test_a_valid_missing_observation_is_reused_and_left_out_of_that_dimensions_means(regraded):
    path = output_file(regraded, "run-a")
    value = json.loads(path.read_text())
    value["scores"]["card_correctness"] = {
        "evaluated": False,
        "complete": False,
        "tests_passed": None,
        "tests_total": None,
        "pass_rate": None,
        "missing_reasons": ["grading_did_not_execute"],
    }
    path.write_text(json.dumps(value))
    docker = LocalDocker()

    summary = invoke(regraded, docker=docker)

    assert docker.runs == []
    cohort = next(c for c in summary["cohorts"] if c["runs"] == 2)
    assert cohort["card_correctness"]["paired_runs"] == 1
    assert cohort["fdn_regression"]["paired_runs"] == 2


def test_scores_that_break_the_record_invariants_are_an_error_not_an_output(retained, monkeypatch):
    original = regrade_module._scores

    def impossible(evaluated, benchmark):
        scores = original(evaluated, benchmark)
        scores["card_correctness"]["pass_rate"] = 2.0
        return scores

    monkeypatch.setattr(regrade_module, "_scores", impossible)

    summary = invoke(retained, runs=["run-a"])

    assert [row["reason"] for row in summary["errors"]] == ["regrade_scores_invalid"]
    assert "scores" not in output(retained, "run-a")


# --- Cohorts: original scores from different grading inputs are never averaged ----------

DIGEST_A, DIGEST_B = "sha256:" + "a" * 64, "sha256:" + "b" * 64


def synthetic(run_id, source_digest, before, after, candidate="c" * 64):
    def dimension(rate):
        return {"tests_passed": None, "tests_total": None, "pass_rate": rate}

    return {
        "run_id": run_id,
        "candidate_hash": candidate,
        "candidate_name": "candidate",
        "source": {
            "grading_inputs_digest": source_digest,
            "scores": {
                "card_correctness": dimension(before),
                "fdn_regression": dimension(1.0),
                "engine_regression": dimension(1.0),
            },
        },
        "scores": {
            "card_correctness": dimension(after),
            "fdn_regression": dimension(1.0),
            "engine_regression": dimension(None),
        },
    }


def test_one_candidate_graded_on_two_input_digests_forms_two_cohorts():
    summary = regrade_module.summarize(
        [synthetic("r1", DIGEST_A, 0.0, 1.0), synthetic("r2", DIGEST_B, 1.0, 1.0)], {}, "example"
    )

    rows = {row["source_grading_inputs_digest"]: row for row in summary["cohorts"]}
    assert set(rows) == {DIGEST_A, DIGEST_B}
    assert rows[DIGEST_A]["card_correctness"]["before_mean_pass_rate"] == 0.0
    assert rows[DIGEST_B]["card_correctness"]["before_mean_pass_rate"] == 1.0
    assert all(row["runs"] == 1 for row in rows.values())


def test_runs_on_one_digest_aggregate_with_paired_counts_per_dimension():
    summary = regrade_module.summarize(
        [synthetic("r1", DIGEST_A, 0.5, 1.0), synthetic("r2", DIGEST_A, 1.0, None)], {}, "example"
    )

    (row,) = summary["cohorts"]
    assert row["runs"] == 2
    assert row["card_correctness"] == {
        "before_mean_pass_rate": 0.5,
        "after_mean_pass_rate": 1.0,
        "paired_runs": 1,
    }
    assert row["fdn_regression"]["paired_runs"] == 2
    assert row["engine_regression"] == {
        "before_mean_pass_rate": None,
        "after_mean_pass_rate": None,
        "paired_runs": 0,
    }


def test_runs_with_an_unknown_original_digest_stay_individual():
    summary = regrade_module.summarize(
        [
            synthetic("r1", None, 0.0, 1.0),
            synthetic("r2", None, 1.0, 1.0),
            synthetic("r3", DIGEST_A, 1.0, 1.0),
        ],
        {},
        "example",
    )

    unknown = [row for row in summary["cohorts"] if row["source_grading_inputs_digest"] is None]
    assert sorted(row["run_id"] for row in unknown) == ["r1", "r2"]
    assert all(row["runs"] == 1 for row in unknown)
    assert len(summary["cohorts"]) == 3


def test_reused_outputs_summarize_into_the_same_cohorts(regraded):
    first = regraded.summary
    second = invoke(regraded)
    assert first["cohorts"] == second["cohorts"]
    assert {row["source_grading_inputs_digest"] for row in second["cohorts"]} == {
        regraded.records[0].run_metadata["grading_inputs"]["digest"]
    }


def test_the_table_names_each_cohorts_original_grading_inputs(retained, monkeypatch):
    monkeypatch.setattr(regrade_module, "DockerRunner", LocalDocker)
    arguments = [
        "regrade", "--benchmark", "example", "--out", str(retained.out),
        "--bench-root", str(retained.opts["bench_root"]),
        "--results-repo", str(retained.opts["results_repo"]),
        "--results-dir", str(retained.opts["results_dir"]),
    ]  # fmt: skip

    result = CliRunner().invoke(main, arguments)

    assert result.exit_code == 0, result.output
    digest = retained.records[0].run_metadata["grading_inputs"]["digest"]
    assert "graded on" in result.output
    assert digest.removeprefix("sha256:")[:12] in result.output


def test_a_fifo_at_a_cache_path_is_a_miss_and_does_not_block(regraded):
    path = output_file(regraded, "run-a")
    path.unlink()
    os.mkfifo(path)
    docker = LocalDocker()
    finished = []
    worker = threading.Thread(target=lambda: finished.append(invoke(regraded, docker=docker)))
    worker.daemon = True
    worker.start()
    worker.join(timeout=60)

    assert finished, "a FIFO at the cache path blocked the re-grade"
    assert len(docker.runs) == 1
    assert path.is_file() and output(regraded, "run-a")["scores"] == regraded.records[0].scores


def test_a_huge_integer_rate_breaks_the_score_invariants_rather_than_overflowing(
    retained_template,
):
    scores = json.loads(json.dumps(retained_template.records[0].scores))
    scores["card_correctness"]["pass_rate"] = 10**400
    with pytest.raises(InvalidRunRecordError):
        validate_scores(scores)


def test_caches_that_cannot_be_decoded_or_checked_regrade_only_their_runs(regraded):
    huge = output_file(regraded, "run-a")
    value = json.loads(huge.read_text())
    value["scores"]["card_correctness"]["pass_rate"] = 10**400
    huge.write_text(json.dumps(value))
    output_file(regraded, "run-b").write_text("[" * 20000 + "]" * 20000)
    reused = output_file(regraded, "run-c").read_bytes()
    docker = LocalDocker()

    summary = invoke(regraded, docker=docker)

    assert len(docker.runs) == 2
    assert summary["errors"] == []
    assert output_file(regraded, "run-c").read_bytes() == reused
    for index, run_id in enumerate(["run-a", "run-b"]):
        assert output(regraded, run_id)["scores"] == regraded.records[index].scores
    assert json.loads((regraded.out / "summary.json").read_text()) == summary


def test_an_output_graded_by_another_image_is_graded_again(regraded):
    path = output_file(regraded, "run-a")
    value = json.loads(path.read_text())
    other = "sha256:" + "1" * 64
    assert other != FIXTURE_IMAGE_ID
    value["grading_isolation"]["grader_image_id"] = other
    path.write_text(json.dumps(value))
    docker = LocalDocker()

    invoke(regraded, docker=docker)

    assert len(docker.runs) == 1
    assert output(regraded, "run-a")["grading_isolation"]["grader_image_id"] == FIXTURE_IMAGE_ID


def _set_inputs(value):
    def change(manifest):
        manifest["run_metadata"]["grading_inputs"] = value(
            manifest["run_metadata"]["grading_inputs"]
        )

    return change


@pytest.mark.parametrize(
    "inputs",
    [
        lambda inputs: {**inputs, "digest": ["bad"]},
        lambda inputs: {**inputs, "digest": {"sha256": "x"}},
        lambda inputs: {**inputs, "digest": 7},
        lambda inputs: {**inputs, "digest": True},
        lambda inputs: {**inputs, "digest": "sha256:not-hex"},
        lambda inputs: "sha256:" + "0" * 64,
    ],
)
def test_a_malformed_historical_digest_skips_that_record_and_the_batch_finishes(retained, inputs):
    edit_manifest(retained, "run-a", _set_inputs(inputs))
    docker = LocalDocker()

    summary = invoke(retained, docker=docker)

    assert summary["skipped"] == [{"run_id": "run-a", "reason": "invalid_record"}]
    assert len(docker.runs) == 2
    assert json.loads((retained.out / "summary.json").read_text()) == summary
    assert invoke(retained)["skipped"] == summary["skipped"]


@pytest.mark.parametrize("inputs", [lambda inputs: None, lambda inputs: {**inputs, "digest": None}])
def test_an_absent_historical_digest_is_graded_in_the_unknown_cohort(retained, inputs):
    edit_manifest(retained, "run-a", _set_inputs(inputs))
    docker = LocalDocker()

    summary = invoke(retained, docker=docker)

    assert summary["skipped"] == []
    assert len(docker.runs) == 3
    assert output(retained, "run-a")["source"]["grading_inputs_digest"] is None


def test_stored_v4_and_v5_records_regrade_side_by_side(tmp_path):
    opts = options(tmp_path)
    v5 = make_candidate(tmp_path / "v5", definition_version=5)
    records = [
        run_benchmark(**opts, run_id="run-v4"),
        run_benchmark(**{**opts, "build_output": v5.build_output}, run_id="run-v5"),
    ]
    assert [r.candidate.scheme for r in records] == ["karn-v4", "karn-v5"]
    retained = SimpleNamespace(opts=opts, records=records, out=tmp_path / "regrade")
    records_before = tree_digest(opts["results_repo"])

    summary = invoke(retained)

    assert summary["skipped"] == summary["errors"] == []
    for record in records:
        assert output(retained, record.run_id)["scores"] == record.scores
    assert tree_digest(opts["results_repo"]) == records_before
