from __future__ import annotations

import copy
import json
import os
import subprocess
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.evaluator import FullEvalResult
from silverquillm.karn.batching import KarnScheduler, queue_rows
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.host import HostResult
from silverquillm.karn.records import missing_scores, write_record
from silverquillm.results_repo import (
    CandidateIdentity,
    InvalidRunRecordError,
    RunRecord,
    RunRecordExistsError,
    iter_run_records,
    rebuild_index,
    write_run_record,
)

from .test_karn_host import FakeDocker, make_candidate


def benchmark_data(tmp_path):
    root = tmp_path / "benchmarks/example"
    workspace = root / "workspace"
    for name, content in {
        "engine/__init__.py": "",
        "engine/card.py": "value = 1\n",
        "engine/game_state.py": "",
        "engine/types.py": "",
        "test_utils.py": "",
        "cards/__init__.py": "",
        "cards/fdn/__init__.py": "",
        "cards/fdn/fdn_1/__init__.py": "",
        "cards/fdn/fdn_1/card_impl.py": "value = 1\n",
        "cards/fdn/fdn_1/card_spec.json": '{"collector_number":"1","name":"Example"}',
        "engine_tests/test_engine.py": "from engine.card import value\ndef test_value(): assert value == 1\n",
    }.items():
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (root / "config.json").write_text(
        '{"id":"example","cards":["1"],"draft_set":{"primary_set_code":"FDN"}}'
    )
    suite = root / "data/tests/audited/fdn/fdn_1/tests.py"
    suite.parent.mkdir(parents=True)
    suite.write_text("from engine.card import value\ndef test_value(): assert value == 1\n")
    return tmp_path


class FixtureHost:
    def __init__(self, *, status="completed", corrupt=False):
        self.docker = FakeDocker()
        self.status, self.corrupt = status, corrupt

    def run(self, candidate, workspace, evidence_dir, prompt, **kwargs):
        evidence_dir.mkdir(parents=True)
        assert "PR title" not in prompt and "proposal.json" not in prompt
        if self.corrupt:
            (workspace / "engine/card.py").write_text("this is not valid python !!!")
        result = HostResult(
            kwargs["run_id"],
            candidate.identity(),
            "fixture",
            str(workspace),
            str(evidence_dir),
            kwargs["budget_seconds"],
            status=self.status,
            workspace_stopped=True,
        )
        kwargs["after_stop"](result, None)
        return result

    def preflight(self, candidate, budget_seconds):
        pass


def options(tmp_path, **changes):
    candidate = make_candidate(tmp_path)
    bench_root = benchmark_data(tmp_path / "data")
    return {
        "build_output": candidate.build_output,
        "construct": "bare",
        "benchmark_id": "example",
        "bench_root": bench_root,
        "results_dir": tmp_path / "runs",
        "results_repo": tmp_path / "records",
        "state_root": tmp_path / "state",
        "host": FixtureHost(),
        **changes,
    }


def test_direct_run_records_three_dimensions_and_explicit_missing_measurements(tmp_path):
    opts = options(tmp_path)
    record = run_benchmark(**opts)
    assert record.manifest["schema_version"] == 2
    assert "mode" not in record.manifest and "leaderboard_valid" not in record.manifest
    assert all(
        score["tests_total"] == 1 and score["tests_passed"] == 1 for score in record.scores.values()
    )
    assert record.run_metadata["measurements"]["agent_turns"]["total"]["value"] is None
    assert record.run_metadata["measurements"]["estimated_cost"]["value"] is None
    directory = opts["results_dir"] / record.run_id
    assert (directory / "workspace_final/engine/card.py").is_file()
    assert (directory / "snapshots/00000/engine/card.py").is_file()
    assert record.run_metadata["grading_source"]["fallback"] is False
    assert record.run_metadata["benchmark_input"]["baseline_commit"]
    assert record.run_metadata["git_history"]["captured"]
    assert len(record.run_metadata["git_history"]["commits"]) == 1
    with pytest.raises(RunRecordExistsError):
        write_record(opts["results_repo"], record)


def test_failed_run_uses_proven_snapshot_only_when_final_engine_is_unusable(tmp_path):
    opts = options(tmp_path, host=FixtureHost(status="failed", corrupt=True))
    record = run_benchmark(**opts)
    source = record.run_metadata["grading_source"]
    assert record.run_metadata["execution"]["status"] == "failed"
    assert source["fallback"] is True
    assert source["reason"] == "engine_source_invalid"
    assert source["selected"] == "snapshots/00000"
    assert (
        "not valid"
        in (opts["results_dir"] / record.run_id / "workspace_final/engine/card.py").read_text()
    )
    assert all(score["pass_rate"] == 1.0 for score in record.scores.values())


class LeftoversHost(FixtureHost):
    """Leaves what an agent plausibly leaves: a venv symlink, a large data file, a FIFO."""

    def __init__(self, *, unreadable_engine=False):
        super().__init__()
        self.unreadable_engine = unreadable_engine

    def run(self, candidate, workspace, evidence_dir, prompt, **kwargs):
        (workspace / "cards/fdn/fdn_1/card_impl.py").write_text("value = 1\nedited = True\n")
        (workspace / ".venv/bin").mkdir(parents=True)
        (workspace / ".venv/bin/python").symlink_to("/usr/bin/python3")
        (workspace / "data").mkdir()
        with open(workspace / "data/big.bin", "wb") as large:
            large.truncate(33 * 1024 * 1024)
        os.mkfifo(workspace / "pipe")
        if self.unreadable_engine:
            secret = workspace / "engine/extra.py"
            secret.write_text("")
            secret.chmod(0)
        return super().run(candidate, workspace, evidence_dir, prompt, **kwargs)


def test_symlinks_large_files_and_fifos_are_omitted_without_demoting_final_work(tmp_path):
    opts = options(tmp_path, host=LeftoversHost())
    record = run_benchmark(**opts)
    source = record.run_metadata["grading_source"]
    assert source["selected"] == "workspace_final" and source["fallback"] is False
    assert source["final"]["errors"] == []
    assert {(row["path"], row["reason"]) for row in source["final"]["omissions"]} == {
        (".venv/bin/python", "symlink_excluded"),
        ("data/big.bin", "file_too_large"),
        ("pipe", "not_regular_file"),
    }
    final = opts["results_dir"] / record.run_id / "workspace_final"
    assert "edited" in (final / "cards/fdn/fdn_1/card_impl.py").read_text()
    assert not (final / "data/big.bin").exists() and not (final / "pipe").exists()


def test_unreadable_engine_source_still_falls_back_to_a_complete_snapshot(tmp_path):
    opts = options(tmp_path, host=LeftoversHost(unreadable_engine=True))
    record = run_benchmark(**opts)
    source = record.run_metadata["grading_source"]
    assert source["fallback"] is True and source["selected"] == "snapshots/00000"
    assert source["reason"] == "final_workspace_copy_incomplete"
    assert source["final"]["errors"] == [
        {"path": "engine/extra.py", "reason": "file_unavailable_during_copy"}
    ]


def test_grader_failure_is_absent_not_zero_and_does_not_erase_execution(tmp_path):
    def unavailable(*args, **kwargs):
        raise RuntimeError("grader failed")

    record = run_benchmark(**options(tmp_path), evaluator=unavailable)
    assert record.run_metadata["execution"]["status"] == "completed"
    assert all(
        not score["evaluated"] and score["pass_rate"] is None for score in record.scores.values()
    )


def test_mixed_history_reader_and_index_preserve_original_schema(tmp_path):
    opts = options(tmp_path)
    new = run_benchmark(**opts, evaluator=lambda *a, **k: FullEvalResult())
    legacy = RunRecord(
        run_id="old-run",
        candidate=CandidateIdentity.legacy("old-image"),
        mode="basic",
        benchmark="sos",
        budget_seconds=60,
        leaderboard_valid=False,
        resumed_from=None,
        run_metadata={"run_date": "old-date"},
        proposal_status=None,
        scores={key: {} for key in missing_scores("unused")},
    )
    write_run_record(opts["results_repo"], legacy)
    records = list(iter_run_records(opts["results_repo"]))
    assert {record.candidate.scheme for _, record in records} == {"legacy", "karn-v4"}
    index = rebuild_index(opts["results_repo"])
    previous = next(row for row in index if row["run_id"] == "old-run")
    assert previous["mode"] == "basic" and previous["leaderboard_valid"] is False
    current = next(row for row in index if row["run_id"] == new.run_id)
    assert (
        current["schema_version"] == 2
        and "mode" not in current
        and "leaderboard_valid" not in current
    )


def test_batch_uses_shared_runner_and_does_not_replay_completed_entries(tmp_path):
    opts = options(tmp_path)
    directory = tmp_path / "batches"
    directory.mkdir()
    (directory / "trial.toml").write_text(
        'format = "karn-v4"\n[[runs]]\nbuild_output = '
        + json.dumps(str(opts["build_output"]))
        + '\nconstruct = "bare"\nbenchmark = "example"\nbudget_seconds = 60\n'
    )
    calls = []

    def execute(**kwargs):
        calls.append(kwargs["run_id"])
        return run_benchmark(
            **kwargs, host=FixtureHost(), evaluator=lambda *a, **k: FullEvalResult()
        )

    scheduler = KarnScheduler(
        directory,
        **{key: opts[key] for key in ("bench_root", "results_dir", "results_repo", "state_root")},
        replay_without_state=["trial"],
        executor=execute,
    )
    assert scheduler.run_until_idle() == 1
    assert scheduler.run_until_idle() == 0
    assert len(calls) == 1
    assert queue_rows(directory)[0]["status"] == "done"
    outcome = CliRunner().invoke(main, ["queue", "ls", "--batches-dir", str(directory)])
    assert outcome.exit_code == 0, outcome.output
    assert "[karn-v4]: done" in outcome.output


def test_legacy_batches_and_state_are_reported_once_and_never_rewritten(tmp_path, caplog):
    directory = tmp_path / "batches"
    (directory / "state").mkdir(parents=True)
    batch = directory / "old.toml"
    batch.write_text('[[runs]]\ncandidate = "candidates/x"\nbenchmark = "smoke"\n')
    state = directory / "state" / "old.json"
    state.write_text('{"schema_version": 1, "batch": "old", "runs": [{"status": "running"}]}\n')
    before = {path: path.read_bytes() for path in (batch, state)}
    scheduler = KarnScheduler(
        directory,
        bench_root=tmp_path,
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "results",
        state_root=tmp_path / "state-root",
        executor=lambda **kwargs: pytest.fail("a legacy batch must never run"),
        recoverer=lambda **kwargs: pytest.fail("legacy state must never be recovered"),
    )
    with caplog.at_level("WARNING"):
        assert scheduler.run_until_idle() == 0
        assert scheduler.run_until_idle() == 0
    assert scheduler.warnings == [
        "unsupported_legacy_state:old.json",
        "unsupported_legacy_batch:old.toml",
    ]
    assert len(caplog.records) == 2
    assert {path: path.read_bytes() for path in (batch, state)} == before
    assert queue_rows(directory) == [
        {"batch": "old", "format": "legacy", "status": "unsupported_legacy_batch"}
    ]


def test_new_run_command_has_no_mode_or_proposal_options():
    result = CliRunner().invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    assert "--build-output" in result.output and "--benchmark" in result.output
    assert "--mode" not in result.output and "--proposal" not in result.output


def test_measurement_finalization_failure_does_not_suppress_grading(tmp_path):
    from silverquillm.karn.observations import CodexTelemetryCollector

    class BrokenFinalizer(CodexTelemetryCollector):
        def finalize(self, **kwargs):
            raise RuntimeError("collector failed")

    record = run_benchmark(**options(tmp_path), collector_factory=BrokenFinalizer)
    assert record.run_metadata["execution"]["status"] == "completed"
    assert all(score["pass_rate"] == 1.0 for score in record.scores.values())
    assert (
        "measurement_finalization_failed"
        in record.run_metadata["measurements"]["agent_turns"]["total"]["reasons"]
    )


def test_schema2_rejects_impossible_or_absent_score_numbers(tmp_path):
    result = run_benchmark(**options(tmp_path), evaluator=lambda *a, **k: FullEvalResult())
    for change in (
        {"tests_passed": 0},
        {"missing_reasons": []},
        {"evaluated": True, "tests_passed": 2, "tests_total": 1, "pass_rate": 2},
        {"evaluated": True, "tests_passed": 1, "tests_total": 2, "pass_rate": 1},
    ):
        damaged = copy.deepcopy(result)
        damaged.scores["card_correctness"].update(change)
        with pytest.raises(InvalidRunRecordError):
            damaged.validate()
    result.manifest["run_metadata"]["run_date"] = 7
    with pytest.raises(InvalidRunRecordError, match="run_date"):
        result.validate()


def test_git_history_preserves_commits_without_loading_workload_hooks_or_config(tmp_path):
    from silverquillm.karn.snapshots import retain_git_history

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "implementation.py").write_text("answer=42")
    for args in (
        ["init", "--quiet"],
        ["add", "implementation.py"],
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "Implement fixture",
        ],
    ):
        subprocess.run(["git", "-C", str(workspace), *args], check=True, capture_output=True)
    marker = tmp_path / "must-not-exist"
    (workspace / ".git/config").write_text(
        f'[core]\nrepositoryformatversion = 0\nfsmonitor = touch {marker}\n[remote "origin"]\nurl = https://secret-user:secret-password@example.invalid/repo\n'
    )
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    result = retain_git_history(workspace, evidence)
    assert result["captured"], result
    assert len(result["commits"]) == 1
    assert not marker.exists()
    assert not any(b"secret-password" in path.read_bytes() for path in evidence.iterdir())
    listed = subprocess.run(
        ["git", "bundle", "list-heads", str(evidence / "git-history.bundle")],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result["commits"][0] in listed.stdout


def test_batch_recovers_finalized_local_record_even_when_batch_file_was_removed(
    tmp_path, monkeypatch
):
    opts = options(tmp_path)
    directory = tmp_path / "batches"
    directory.mkdir()
    batch_file = directory / "trial.toml"
    batch_file.write_text(
        'format="karn-v4"\n[[runs]]\nbuild_output='
        + json.dumps(str(opts["build_output"]))
        + '\nconstruct="bare"\nbenchmark="example"\nbudget_seconds=60\n'
    )
    calls = []

    def execute(**kwargs):
        calls.append(kwargs["run_id"])
        return run_benchmark(
            **kwargs, host=FixtureHost(), evaluator=lambda *a, **k: FullEvalResult()
        )

    scheduler = KarnScheduler(
        directory,
        **{key: opts[key] for key in ("bench_root", "results_dir", "results_repo", "state_root")},
        replay_without_state=["trial"],
        executor=execute,
    )
    with monkeypatch.context() as patch:

        def interrupted(*args):
            raise SystemExit(91)

        patch.setattr("silverquillm.karn.execution.write_record", interrupted)
        with pytest.raises(SystemExit):
            scheduler.run_until_idle()
    batch_file.unlink()
    assert scheduler.run_until_idle() == 0
    assert len(calls) == 1
    state = json.loads((directory / "state/trial.json").read_text())
    assert state["runs"][0]["status"] == "done"
    assert len(list(iter_run_records(opts["results_repo"]))) == 1


@pytest.mark.parametrize("edit", ["remove", "malform"])
def test_mid_run_batch_edit_keeps_completed_state_and_continues_other_batches(tmp_path, edit):
    directory = tmp_path / "batches"
    directory.mkdir()
    content = 'format="karn-v4"\n[[runs]]\nbuild_output="fixture"\nconstruct="bare"\nbenchmark="example"\n'
    for name in ("a", "b"):
        (directory / (name + ".toml")).write_text(content)
    calls = []

    def execute(**kwargs):
        calls.append(kwargs["run_id"])
        if len(calls) == 1:
            if edit == "remove":
                (directory / "a.toml").unlink()
            else:
                (directory / "a.toml").write_text("format = [")
        return SimpleNamespace(
            run_metadata={"execution": {"status": "completed"}},
            candidate=SimpleNamespace(to_dict=dict),
        )

    scheduler = KarnScheduler(
        directory,
        bench_root=tmp_path,
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=tmp_path / "state",
        replay_without_state=["a", "b"],
        executor=execute,
    )
    assert scheduler.run_until_idle() == 2
    assert len(calls) == 2
    assert scheduler.warnings == ["batch_unreadable:a.toml"]
    for name in ("a", "b"):
        assert (
            json.loads((directory / ("state/" + name + ".json")).read_text())["runs"][0]["status"]
            == "done"
        )


def test_failed_assertions_are_observed_zero_scores_not_missing_grading(tmp_path):
    from silverquillm.evaluator import EngineResult

    def failed_engine(*args, **kwargs):
        return FullEvalResult(
            engine_result=EngineResult(
                tests_failed=1, tests_total=1, errors=["FAILED test_engine.py::test_behavior"]
            )
        )

    result = run_benchmark(**options(tmp_path), evaluator=failed_engine)
    score = result.scores["engine_regression"]
    assert score["evaluated"] and score["complete"]
    assert score["pass_rate"] == 0 and score["tests_passed"] == 0
    assert score["missing_reasons"] == []
    assert score["diagnostics"] == ["FAILED test_engine.py::test_behavior"]


def test_audited_card_impl_import_resolves_selected_candidate_after_trusted_support(tmp_path):
    opts = options(tmp_path)
    suite = opts["bench_root"] / "benchmarks/example/data/tests/audited/fdn/fdn_1/tests.py"
    suite.write_text("from card_impl import value\ndef test_candidate_card(): assert value == 1\n")
    result = run_benchmark(**opts)
    assert result.scores["card_correctness"]["tests_passed"] == 1
    assert result.scores["fdn_regression"]["tests_passed"] == 1


def test_selected_benchmark_data_root_reaches_grader_without_source_package_import(tmp_path):
    opts = options(tmp_path)
    suite = opts["bench_root"] / "benchmarks/example/workspace/engine_tests/test_engine.py"
    suite.write_text(
        "import os\nfrom pathlib import Path\ndef test_data_root():\n    assert Path(os.environ['SILVERQUILLM_BENCH_ROOT']) == Path("
        + repr(str(opts["bench_root"].resolve()))
        + ")\n"
    )
    result = run_benchmark(**opts)
    assert result.scores["engine_regression"]["tests_passed"] == 1


def test_operator_interruption_records_state_and_stops_before_next_run(tmp_path):
    directory = tmp_path / "batches"
    directory.mkdir()
    spec = '[[runs]]\nbuild_output="fixture"\nconstruct="bare"\nbenchmark="example"\n'
    (directory / "trial.toml").write_text('format="karn-v4"\n' + spec + spec)
    calls = []

    def execute(**kwargs):
        calls.append(kwargs["run_id"])
        return SimpleNamespace(
            run_metadata={"execution": {"status": "interrupted"}},
            candidate=SimpleNamespace(to_dict=dict),
        )

    scheduler = KarnScheduler(
        directory,
        bench_root=tmp_path,
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=tmp_path / "state",
        replay_without_state=["trial"],
        executor=execute,
    )
    with pytest.raises(KeyboardInterrupt):
        scheduler.run_until_idle()
    assert len(calls) == 1
    state = json.loads((directory / "state/trial.json").read_text())
    assert len(state["runs"]) == 1 and state["runs"][0]["status"] == "failed"


def test_collector_teardown_error_keeps_completed_execution_and_grading(tmp_path):
    from silverquillm.karn.observations import CodexTelemetryCollector

    class BrokenExit(CodexTelemetryCollector):
        def __exit__(self, *args):
            super().__exit__(*args)
            raise RuntimeError("collector cleanup failed")

    opts = options(tmp_path)
    result = run_benchmark(**opts, collector_factory=BrokenExit)
    assert result.run_metadata["execution"]["status"] == "completed"
    assert all(score["tests_passed"] == 1 for score in result.scores.values())
    assert (opts["results_dir"] / result.run_id / "workspace_final").is_dir()
    assert "collector_teardown_failed" in result.run_metadata["execution"]["observation_errors"]


def test_recovery_refuses_a_changed_retained_definition_and_preserves_original_input(
    tmp_path, monkeypatch
):
    from silverquillm.karn import definition, recovery

    opts = options(tmp_path)

    def interrupted(*args, **kwargs):
        raise SystemExit(91)

    with pytest.raises(SystemExit):
        run_benchmark(**opts, run_id="interrupted", evaluator=interrupted)
    directory = opts["results_dir"] / "interrupted"
    inputs = json.loads((directory / "run-input.json").read_text())
    assert {"workspace_digest", "baseline_commit", "prompt_digest"} <= inputs["staged_input"].keys()
    selected = directory / "candidate/constructs/bare/definition.json"
    document = json.loads(selected.read_text())
    document["runtime"]["environment"]["ALTERED"] = "after execution"
    selected.write_bytes(definition.canonical(document))
    with pytest.raises(definition.KarnError, match="retained_definition_identity_mismatch"):
        recovery.recover_benchmark(
            run_id="interrupted",
            spec={},
            **{
                key: opts[key]
                for key in ("bench_root", "results_dir", "results_repo", "state_root")
            },
        )
    assert not list(iter_run_records(opts["results_repo"]))


def test_recovery_of_uncertain_record_stops_writers_and_appends_linked_evidence(
    tmp_path, monkeypatch
):
    from silverquillm.karn import recovery

    class UncertainHost(FixtureHost):
        def run(self, candidate, workspace, evidence_dir, prompt, **kwargs):
            evidence_dir.mkdir(parents=True)
            return HostResult(
                kwargs["run_id"],
                candidate.identity(),
                "sq-run-" + kwargs["run_id"],
                str(workspace),
                str(evidence_dir),
                kwargs["budget_seconds"],
                status="host_failed",
                workspace_stopped=False,
                error="stop_unconfirmed",
            )

    opts = options(tmp_path, host=UncertainHost())
    original = run_benchmark(**opts)
    old_path = opts["results_repo"] / "results" / original.candidate.hash / original.run_id
    before = {name: (old_path / name).read_bytes() for name in ("manifest.json", "scores.json")}
    from silverquillm.karn.snapshots import copy_workspace

    run_dir = opts["results_dir"] / original.run_id
    copy_workspace(run_dir / "workspace", run_dir / "workspace_final")
    (run_dir / "workspace/engine/card.py").write_text("value = 2\n")
    stopped = []
    docker = SimpleNamespace(
        stop_and_confirm=lambda *args: stopped.append(args),
        cleanup_run=lambda *args: stopped.append(("cleanup", *args)),
    )
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: SimpleNamespace(docker=docker, plugin_cache=tmp_path / "cache"),
    )
    recovered = recovery.recover_benchmark(
        run_id=original.run_id,
        spec={},
        **{key: opts[key] for key in ("bench_root", "results_dir", "results_repo", "state_root")},
    )
    assert stopped and recovered.run_metadata["execution"]["workspace_stopped"]
    assert recovered.run_id != original.run_id
    assert recovered.run_metadata["recovery_of"] == original.run_id
    assert recovered.run_metadata["benchmark_input"] == original.run_metadata["benchmark_input"]
    assert recovered.candidate == original.candidate
    assert all(score["tests_passed"] == 0 for score in recovered.scores.values())
    assert (run_dir / "workspace_final/engine/card.py").read_text() == "value = 1\n"
    assert recovered.run_metadata["grading_source"]["selected"] != "workspace_final"
    assert recovered.run_metadata["grading_source"]["fallback"] is False
    assert before == {name: (old_path / name).read_bytes() for name in before}
    assert len(list(iter_run_records(opts["results_repo"]))) == 2
    again = recovery.recover_benchmark(
        run_id=original.run_id,
        spec={},
        **{key: opts[key] for key in ("bench_root", "results_dir", "results_repo", "state_root")},
    )
    assert again.run_id == recovered.run_id and len(stopped) == 2


def test_selected_card_binding_resists_shadow_modules_and_keeps_local_helpers(tmp_path):
    opts = options(tmp_path)
    source = opts["bench_root"] / "benchmarks/example/workspace"
    card = source / "cards/fdn/fdn_1"
    (source / "card_impl.py").write_text(
        "raise AssertionError('root implementation must not load')"
    )
    (card / "engine.py").write_text("raise AssertionError('card-local engine must not load')")
    (card / "helpers.py").write_text("value = 7")
    (card / "relative.py").write_text("value = 11")
    (card / "card_impl.py").write_text(
        "from helpers import value as local\nfrom .relative import value as relative\nfrom engine.card import value as engine_value\nvalue = local + relative + engine_value\n"
    )
    suite = opts["bench_root"] / "benchmarks/example/data/tests/audited/fdn/fdn_1/tests.py"
    suite.write_text(
        "from card_impl import value\nfrom engine.card import value as engine_value\ndef test_selected():\n    assert value == 19\n    assert engine_value == 1\n"
    )
    result = run_benchmark(**opts)
    assert result.scores["card_correctness"]["tests_passed"] == 1
    assert result.scores["fdn_regression"]["tests_passed"] == 1
    assert result.scores["engine_regression"]["tests_passed"] == 1


def test_host_grading_inputs_are_fingerprinted_without_entering_workspace(tmp_path):
    opts = options(tmp_path)
    result = run_benchmark(**opts)
    inputs = result.run_metadata["grading_inputs"]
    kinds = {row["kind"] for row in inputs["files"]}
    assert kinds == {"target", "fdn", "engine", "test_utils", "replay_token_map", "replay_card_map"}
    assert all(
        row["sha256"]
        for row in inputs["files"]
        if row["kind"] not in {"replay_token_map", "replay_card_map"}
    )
    assert {item["kind"] for item in inputs["problems"]} == {"replay_token_map", "replay_card_map"}
    assert all(item["reason"] == "grading_input_unavailable" for item in inputs["problems"])

    assert not (opts["results_dir"] / result.run_id / "workspace_final/data/tests/audited").exists()


def test_reference_extra_set_card_loads_from_its_declared_fdn_population(tmp_path):
    opts = options(tmp_path)
    root = opts["bench_root"] / "benchmarks/example"
    card = root / "workspace/cards/fdn/spg_74"
    card.mkdir()
    (card / "__init__.py").write_text("")
    (card / "card_spec.json").write_text('{"collector_number":"74","name":"Extra reference"}')
    (card / "card_impl.py").write_text("value = 9")
    suite = root / "data/tests/audited/fdn/spg_74/tests.py"
    suite.parent.mkdir()
    suite.write_text("from card_impl import value\ndef test_extra_reference(): assert value == 9\n")
    result = run_benchmark(**opts)
    assert result.scores["fdn_regression"]["tests_passed"] == 2
    assert result.scores["fdn_regression"]["coverage"]["evaluated_cards"] == ["fdn_1", "spg_74"]


def test_replay_card_map_uses_selected_benchmark_data_root(tmp_path, monkeypatch):
    from silverquillm.replay.parser import load_card_id_map

    directory = tmp_path / "data/replays"
    directory.mkdir(parents=True)
    (directory / "card_id_map.json").write_text(
        '{"grpId_to_card":{"42":{"card_name":"Selected fixture"}}}'
    )
    monkeypatch.setenv("SILVERQUILLM_BENCH_ROOT", str(tmp_path))
    assert load_card_id_map() == {42: "Selected fixture"}


def test_fingerprint_includes_authoritative_engine_configuration_and_replay_support(tmp_path):
    from silverquillm.karn.benchmark import load_benchmark
    from silverquillm.karn.grading_inputs import grading_inputs

    root = benchmark_data(tmp_path / "data")
    support = {
        "benchmarks/example/workspace/conftest.py": "# authoritative fixtures\n",
        "benchmarks/example/workspace/pytest.ini": "[pytest]\n",
        "data/replays/golden/example.json": "{}",
        "scripts/triage_divergences.py": "# authoritative replay support\n",
    }
    for relative, contents in support.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    observed = grading_inputs(load_benchmark(root, "example"))
    by_path = {row["path"]: row for row in observed["files"]}
    assert all(by_path[path]["sha256"] for path in support)
    assert {by_path[path]["kind"] for path in support} == {
        "engine_support",
        "replay_fixture",
        "replay_support",
    }
