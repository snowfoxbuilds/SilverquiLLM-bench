"""The baseline reference grade and the baseline comparison, from the store to runs, recovery and regrade."""

from __future__ import annotations

import copy
import json
import shutil
import threading
import time
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.evaluator import CardResult, EngineResult, FullEvalResult
from silverquillm.karn import regrade as regrade_module
from silverquillm.karn.baseline import (
    Baseline,
    BaselineStore,
    baseline_comparison,
    baseline_key,
    baseline_reference_grade,
    stage_baseline,
)
from silverquillm.karn.benchmark import load_benchmark, stage_benchmark
from silverquillm.karn.definition import KarnError
from silverquillm.karn.execution import _scores, run_benchmark
from silverquillm.karn.grader import DockerRun, GraderError
from silverquillm.karn.grading_inputs import grading_inputs
from silverquillm.karn.records import read_record, validate_baseline_comparison, validate_scores
from silverquillm.karn.regrade import regrade
from silverquillm.results_repo import RETIRED_SUITE_KEYS, InvalidRunRecordError

from . import known_defect_fixture as fixture
from . import retained_runs
from .grader_fixtures import FIXTURE_IMAGE_ID, LocalDocker, local_grader
from .test_karn_execution import FixtureHost
from .test_karn_host import make_candidate
from .test_karn_lifecycle import ContainerDocker

DIGEST_A, DIGEST_B, DIGEST_C = ("sha256:" + digit * 64 for digit in "abc")


# --- The baseline comparison from scores, outcomes and a baseline ---------------------------


def nodes(pairs):
    return [{"test_node": node, "outcome": outcome} for node, outcome in pairs]


def evaluation(fdn: dict[str, str], engine: dict[str, str]) -> FullEvalResult:
    by_card: dict[str, list] = {}
    for node, outcome in fdn.items():
        card, test = node.split("/", 1)
        by_card.setdefault(card, []).append((test, outcome))
    return FullEvalResult(
        fdn_results={
            card: CardResult(card, test_nodes=nodes(pairs)) for card, pairs in by_card.items()
        },
        engine_result=EngineResult(test_nodes=nodes(engine.items())),
    )


def suite_grade(test_nodes: dict, *, reasons=(), evaluated=True):
    passed = sum(outcome == "pass" for outcome in test_nodes.values())
    return {
        "complete": evaluated and not reasons,
        "tests_passed": passed if evaluated else None,
        "tests_total": len(test_nodes) if evaluated else None,
        "missing_reasons": list(reasons) or ([] if evaluated else ["no_executed_tests"]),
        "test_nodes": test_nodes if evaluated else {},
    }


def baseline(fdn_nodes: dict, engine_nodes: dict, **changes) -> Baseline:
    suites = {"fdn": suite_grade(fdn_nodes), "engine": suite_grade(engine_nodes)}
    for name, value in changes.items():
        suites[name] = value
    key = {
        "benchmark": {"id": "kd"},
        "grading_inputs_digest": DIGEST_A,
        "grading_code_digest": DIGEST_B,
        "workspace_digest": DIGEST_C,
        "grader_image_id": FIXTURE_IMAGE_ID,
    }
    return Baseline(
        {"schema_version": 2, "key": key, "graded_at": "", "suites": suites}, None
    )


def scores_of(evaluated: FullEvalResult) -> dict:
    scores = {}
    for name, outcomes in (
        ("fdn", [n for r in evaluated.fdn_results.values() for n in r.test_nodes]),
        ("engine", evaluated.engine_result.test_nodes),
    ):
        passed = sum(node["outcome"] == "pass" for node in outcomes)
        total = len(outcomes)
        scores[name] = {
            "evaluated": total > 0,
            "complete": total > 0,
            "tests_passed": passed if total else None,
            "tests_total": total or None,
            "pass_rate": passed / total if total else None,
            "missing_reasons": [] if total else ["no_executed_tests"],
        }
    scores["target"] = copy.deepcopy(scores["fdn"])
    return scores


BASE_FDN = {"fdn_1/tests.py::a": "pass", "fdn_1/tests.py::b": "fail", "fdn_2/tests.py::c": "pass"}
BASE_ENGINE = {"test_x.py::d": "fail", "sub/test_y.py::e": "pass", "test_x.py::f": "pass"}


def test_the_comparison_lists_fixed_and_broken_tests_per_suite():
    run = evaluation(
        # b fixed; c no longer executes, so it is broken; z is new and ignored.
        {"fdn_1/tests.py::a": "pass", "fdn_1/tests.py::b": "pass", "fdn_1/tests.py::z": "fail"},
        # d fixed; e broken.
        {"test_x.py::d": "pass", "sub/test_y.py::e": "fail", "test_x.py::f": "pass"},
    )
    scores = scores_of(run)
    before = copy.deepcopy(scores)
    block = baseline_comparison(scores, run, baseline(BASE_FDN, BASE_ENGINE))
    assert scores == before
    assert block == {
        "available": True,
        "fixed": {"fdn": ["fdn_1/tests.py::b"], "engine": ["test_x.py::d"]},
        "broken": {"fdn": ["fdn_2/tests.py::c"], "engine": ["sub/test_y.py::e"]},
        "baseline": {
            "grading_inputs_digest": DIGEST_A,
            "grading_code_digest": DIGEST_B,
            "workspace_digest": DIGEST_C,
            "grader_image_id": FIXTURE_IMAGE_ID,
        },
    }
    validate_baseline_comparison(block)


def test_without_a_manifest_there_is_no_block():
    run = evaluation(BASE_FDN, BASE_ENGINE)
    assert baseline_comparison(scores_of(run), run, None) is None


def test_a_coverage_gap_shared_with_the_run_keeps_the_block_available():
    run = evaluation(BASE_FDN, BASE_ENGINE)
    covered = suite_grade(BASE_FDN, reasons=["some_cards_have_no_executed_audited_tests"])
    block = baseline_comparison(
        scores_of(run), run, baseline(BASE_FDN, BASE_ENGINE, fdn=covered)
    )
    assert block["available"] is True


@pytest.mark.parametrize(
    ("arrange", "reason"),
    [
        (
            lambda s, b: {"inputs_changed": True, "unevaluated": True},
            "grading_inputs_changed_during_grading",
        ),
        (lambda s, b: {"unevaluated": True, "unavailable": True}, "suite_not_evaluated"),
        (lambda s, b: {"unavailable": True, "incomplete": True}, "baseline_grading_failed:timeout"),
        (lambda s, b: {"incomplete": True}, "baseline_incomplete"),
    ],
)
def test_unavailable_reasons_apply_in_order(arrange, reason):
    run = evaluation(BASE_FDN, BASE_ENGINE)
    scores = scores_of(run)
    reference = baseline(BASE_FDN, BASE_ENGINE)
    case = arrange(scores, reference)
    if case.get("unevaluated"):
        scores["engine"].update(evaluated=False, tests_passed=None, tests_total=None)
    if case.get("incomplete"):
        reference.grade["suites"]["engine"]["missing_reasons"] = ["ImportError"]
    if case.get("unavailable"):
        reference = Baseline(None, "baseline_grading_failed:timeout")
    block = baseline_comparison(
        scores, run, reference, inputs_changed=case.get("inputs_changed", False)
    )
    assert block == {"available": False, "reason": reason}
    validate_baseline_comparison(block)


def test_an_unevaluated_baseline_suite_is_incomplete():
    run = evaluation(BASE_FDN, BASE_ENGINE)
    reference = baseline(BASE_FDN, BASE_ENGINE, engine=suite_grade({}, evaluated=False))
    assert baseline_comparison(scores_of(run), run, reference)["reason"] == "baseline_incomplete"


# --- Validating the block -------------------------------------------------------------


def available_block():
    run = evaluation(
        {"fdn_1/tests.py::a": "pass", "fdn_1/tests.py::b": "pass", "fdn_2/tests.py::c": "fail"},
        BASE_ENGINE,
    )
    return baseline_comparison(scores_of(run), run, baseline(BASE_FDN, BASE_ENGINE))


def _set(path, value):
    def damage(block):
        *parents, last = path
        target = block
        for name in parents:
            target = target[name]
        target[last] = value

    return damage


def _drop(name):
    return lambda block: block.pop(name)


@pytest.mark.parametrize(
    "damage",
    [
        _set(("available",), 1),
        _set(("extra",), 1),
        _set(("tests_passed",), 4),
        _drop("fixed"),
        _set(("fixed", "fdn"), ["z", "a"]),
        _set(("fixed", "fdn"), ["a", "a"]),
        _set(("fixed", "fdn"), [""]),
        _set(("fixed",), {"fdn": []}),
        _set(("fixed",), {"fdn": [], "engine": [], "target": []}),
        _drop("broken"),
        _set(("broken", "engine"), "test_x.py::d"),
        _set(("broken", "fdn"), ["fdn_1/tests.py::b"]),
        _set(("baseline", "workspace_digest"), "sha256:short"),
        _set(("baseline", "grader_image_id"), ""),
        _set(("baseline", "extra"), DIGEST_A),
    ],
)
def test_a_malformed_available_block_is_rejected(damage):
    block = available_block()
    validate_baseline_comparison(block)
    damage(block)
    with pytest.raises(InvalidRunRecordError, match="invalid baseline comparison"):
        validate_baseline_comparison(block)


def test_a_test_both_fixed_and_broken_is_rejected():
    block = available_block()
    block["broken"]["fdn"] = list(block["fixed"]["fdn"])
    with pytest.raises(InvalidRunRecordError):
        validate_baseline_comparison(block)


@pytest.mark.parametrize(
    "block",
    [
        {"available": False},
        {"available": False, "reason": ""},
        {"available": False, "reason": "x", "tests_total": 1},
        {"available": "no", "reason": "x"},
        None,
    ],
)
def test_a_malformed_unavailable_block_is_rejected(block):
    with pytest.raises(InvalidRunRecordError):
        validate_baseline_comparison(block)


# --- The store ------------------------------------------------------------------------


def grade_for(key):
    return {
        "schema_version": 2,
        "key": key,
        "graded_at": "2026-10-02T12:00:00+00:00",
        "suites": {
            "fdn": suite_grade({"fdn_1/tests.py::a": "pass"}),
            "engine": suite_grade({"test_x.py::d": "fail"}),
        },
    }


def store_key(**changes):
    return {
        "benchmark": {
            "id": "kd",
            "configuration_digest": DIGEST_A,
            "target_set": "hob",
            "cards": ["1"],
        },
        "grading_inputs_digest": DIGEST_A,
        "grading_code_digest": DIGEST_B,
        "workspace_digest": DIGEST_C,
        "grader_image_id": FIXTURE_IMAGE_ID,
        **changes,
    }


class Grades:
    def __init__(self, delay=0.0):
        self.calls, self.delay = 0, delay

    def __call__(self, key):
        def grade():
            self.calls += 1
            time.sleep(self.delay)
            return grade_for(key)

        return grade


def test_an_equal_key_is_graded_once(tmp_path):
    store, grades = BaselineStore(tmp_path / "baseline-grades"), Grades()
    first = store.get_or_grade(store_key(), grades(store_key()))
    assert store.get_or_grade(store_key(), grades(store_key())) == first
    assert grades.calls == 1
    directory = tmp_path / "baseline-grades" / "kd"
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "baseline-grades").stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "change",
    [
        {
            "benchmark": {
                "id": "kd",
                "configuration_digest": DIGEST_B,
                "target_set": "hob",
                "cards": ["1"],
            }
        },
        {"grading_inputs_digest": DIGEST_C},
        {"grading_code_digest": DIGEST_A},
        {"workspace_digest": DIGEST_A},
        {"grader_image_id": "sha256:" + "1" * 64},
    ],
)
def test_any_key_field_change_grades_again(tmp_path, change):
    store, grades = BaselineStore(tmp_path), Grades()
    store.get_or_grade(store_key(), grades(store_key()))
    store.get_or_grade(store_key(**change), grades(store_key(**change)))
    assert grades.calls == 2


@pytest.mark.parametrize(
    "damage",
    [
        lambda path, key: path.write_text("{not json"),
        lambda path, key: path.write_text(json.dumps({**grade_for(key), "schema_version": 1})),
        lambda path, key: path.write_text(
            json.dumps({**grade_for(key), "key": store_key(grader_image_id="x")})
        ),
        lambda path, key: path.write_text(json.dumps({**grade_for(key), "extra": 1})),
        lambda path, key: path.write_text(
            json.dumps({**grade_for(key), "suites": {"fdn": {}}})
        ),
        lambda path, key: path.write_text(
            json.dumps(
                {
                    **grade_for(key),
                    "suites": {
                        **grade_for(key)["suites"],
                        "engine": {
                            **suite_grade({"t.py::x": "fail"}),
                            "test_nodes": {"t.py::x": "skipped"},
                        },
                    },
                }
            )
        ),
    ],
)
def test_a_corrupt_or_mismatched_grade_is_graded_again_and_overwritten(tmp_path, damage):
    store, grades = BaselineStore(tmp_path), Grades()
    store.get_or_grade(store_key(), grades(store_key()))
    path = store.path(store_key())
    damage(path, store_key())
    store.get_or_grade(store_key(), grades(store_key()))
    assert grades.calls == 2
    assert json.loads(path.read_text())["key"] == store_key()
    store.get_or_grade(store_key(), grades(store_key()))
    assert grades.calls == 2


def test_a_failed_grade_writes_nothing(tmp_path):
    store = BaselineStore(tmp_path)

    def fail():
        raise GraderError("timeout")

    with pytest.raises(GraderError):
        store.get_or_grade(store_key(), fail)
    assert [path.name for path in (tmp_path / "kd").iterdir()] == [".lock"]


def test_concurrent_requests_for_one_key_grade_once(tmp_path):
    store, grades = BaselineStore(tmp_path), Grades(delay=0.3)
    results = []
    threads = [
        threading.Thread(
            target=lambda: results.append(store.get_or_grade(store_key(), grades(store_key())))
        )
        for _ in range(3)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert grades.calls == 1
    assert len(results) == 3 and all(result == results[0] for result in results)


# --- Staging and producing the baseline reference grade -------------------------------


@pytest.fixture
def kd(tmp_path):
    return load_benchmark(fixture.build(tmp_path / "data"), fixture.BENCHMARK)


def test_the_staged_baseline_has_the_digest_a_run_records(kd, tmp_path):
    staged = stage_baseline(kd, tmp_path / "scratch")
    _, recorded = stage_benchmark(kd, tmp_path / "run")
    assert staged.digest == recorded["workspace_digest"]
    assert staged.path == tmp_path / "scratch/workspace"


def test_an_incomplete_workspace_copy_makes_the_baseline_unavailable(kd, tmp_path):
    (kd.root / "workspace/linked").symlink_to(kd.root / "config.json")
    reference = baseline_reference_grade(
        kd,
        evaluate=lambda *a, **k: pytest.fail("graded an incomplete copy"),
        score=_scores,
        grading_inputs_digest=DIGEST_A,
        grader_image_id=FIXTURE_IMAGE_ID,
        store=BaselineStore(tmp_path / "store"),
    )
    assert reference == Baseline(None, "baseline_workspace_incomplete")


def test_no_manifest_means_no_baseline(tmp_path):
    benchmark = load_benchmark(fixture.build(tmp_path, manifest=False), fixture.BENCHMARK)
    assert (
        baseline_reference_grade(
            benchmark,
            evaluate=lambda *a, **k: pytest.fail("graded without a manifest"),
            score=_scores,
            grading_inputs_digest=DIGEST_A,
            grader_image_id=FIXTURE_IMAGE_ID,
            store=BaselineStore(tmp_path / "store"),
        )
        is None
    )


def test_an_unexpected_failure_is_reported_by_type(kd, tmp_path):
    def evaluate(*args, **kwargs):
        raise RuntimeError("boom")

    reference = request(kd, BaselineStore(tmp_path / "store"), evaluate)
    assert reference == Baseline(None, "baseline_grading_failed:RuntimeError")


def request(benchmark, store, evaluate, digest=None):
    return baseline_reference_grade(
        benchmark,
        evaluate=evaluate,
        score=_scores,
        grading_inputs_digest=digest or grading_inputs(benchmark)["digest"],
        grader_image_id=FIXTURE_IMAGE_ID,
        store=store,
    )


class Scripted:
    """Real grading; each queued change is applied before (or to) one evaluation in turn."""

    def __init__(self, *before, after=()):
        self.grader, self.calls = local_grader(), 0
        self.before, self.after = list(before), list(after)

    def __call__(self, run_dir, benchmark, *, workspace_source):
        self.calls += 1
        if self.before:
            self.before.pop(0)()
        evaluated = self.grader.evaluate_run(run_dir, benchmark, workspace_source=workspace_source)
        if self.after:
            self.after.pop(0)(evaluated)
        return evaluated


def timed_out(evaluated):
    evaluated.engine_result = EngineResult(errors=["Timeout after 120s"])


def stored_grades(store, benchmark):
    return sorted((store.root / benchmark.id).glob("*.json"))


def test_a_timed_out_baseline_is_reported_but_graded_again_next_time(kd, tmp_path):
    store, evaluate = BaselineStore(tmp_path / "store"), Scripted(after=[timed_out])
    first = request(kd, store, evaluate)
    assert first.grade["suites"]["engine"]["tests_total"] is None
    run = evaluation(BASE_FDN, BASE_ENGINE)
    assert baseline_comparison(scores_of(run), run, first)["reason"] == "baseline_incomplete"
    assert stored_grades(store, kd) == []

    healthy = request(kd, store, evaluate)
    assert evaluate.calls == 2
    assert healthy.grade["suites"]["engine"]["test_nodes"] == {
        fixture.ENGINE_NODES[0]: "pass",
        fixture.ENGINE_DEFECT: "fail",
    }
    # Failing Known Defect tests and the shared FDN coverage gap are reference data.
    assert healthy.grade["suites"]["fdn"]["missing_reasons"] == [
        "some_cards_have_no_executed_audited_tests"
    ]
    assert request(kd, store, evaluate) == healthy
    assert evaluate.calls == 2
    assert len(stored_grades(store, kd)) == 1


def test_an_incomplete_stored_grade_is_graded_again(kd, tmp_path):
    store, evaluate = BaselineStore(tmp_path / "store"), Scripted()
    healthy = request(kd, store, evaluate)
    [path] = stored_grades(store, kd)
    damaged = copy.deepcopy(healthy.grade)
    damaged["suites"]["engine"].update(
        complete=False,
        tests_passed=None,
        tests_total=None,
        missing_reasons=["Timeout after 120s"],
        test_nodes={},
    )
    path.write_text(json.dumps(damaged))
    assert request(kd, store, evaluate).grade["suites"] == healthy.grade["suites"]
    assert evaluate.calls == 2
    assert json.loads(path.read_text())["suites"] == healthy.grade["suites"]


def engine_suite_edit(benchmark):
    """Make the lifegain Audited Test expect the defect, and a way to restore it."""
    suite = benchmark.root / "data/tests/audited/engine/test_rules.py"
    original = suite.read_text()
    edited = original.replace("lifegain(3) == 3", "lifegain(3) == 2")
    assert edited != original
    return (lambda: suite.write_text(edited)), (lambda: suite.write_text(original))


def test_inputs_changed_before_baseline_grading_are_reported_and_not_graded(kd, tmp_path):
    store, evaluate = BaselineStore(tmp_path / "store"), Scripted()
    requested = grading_inputs(kd)["digest"]
    edit, _ = engine_suite_edit(kd)
    edit()
    assert request(kd, store, evaluate, requested) == Baseline(
        None, "grading_inputs_changed_during_grading"
    )
    assert evaluate.calls == 0
    assert stored_grades(store, kd) == []


def test_inputs_changed_during_baseline_grading_store_nothing(kd, tmp_path):
    store = BaselineStore(tmp_path / "store")
    requested = grading_inputs(kd)["digest"]
    edit, restore = engine_suite_edit(kd)
    evaluate = Scripted(edit)
    assert request(kd, store, evaluate, requested) == Baseline(
        None, "grading_inputs_changed_during_grading"
    )
    assert stored_grades(store, kd) == []

    restore()
    assert grading_inputs(kd)["digest"] == requested
    restored = request(kd, store, evaluate, requested)
    assert restored.grade["suites"]["engine"]["tests_passed"] == 1
    assert len(stored_grades(store, kd)) == 1


# --- Runs and recovery ----------------------------------------------------------------


class EditingHost(FixtureHost):
    def run(self, candidate, workspace, evidence_dir, prompt, **kwargs):
        fixture.candidate_edits(workspace)
        return super().run(candidate, workspace, evidence_dir, prompt, **kwargs)


class Counting:
    def __init__(self, grader):
        self.grader, self.calls = grader, 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.grader.evaluate_run(*args, **kwargs)


def run_options(tmp_path, *, manifest=True, **changes):
    candidate = make_candidate(tmp_path)
    grader = local_grader()
    return {
        "build_output": candidate.build_output,
        "construct": "bare",
        "benchmark_id": fixture.BENCHMARK,
        "bench_root": fixture.build(tmp_path / "data", manifest=manifest),
        "results_dir": tmp_path / "runs",
        "results_repo": tmp_path / "records",
        "state_root": tmp_path / "state",
        "host": EditingHost(),
        "grader": grader,
        "evaluator": Counting(grader),
        **changes,
    }


EXPECTED_FIXED = {"fdn": [], "engine": [fixture.ENGINE_DEFECT]}
EXPECTED_BROKEN = {"fdn": [fixture.FDN_NODES[0]], "engine": []}


def test_runs_and_recovery_report_the_baseline_comparison_against_one_cached_baseline(
    tmp_path, monkeypatch
):
    """End to end: a run, a second run reusing its cached baseline, a recovered run, and the
    published record's validation of the block."""
    from silverquillm.karn import recovery

    opts = run_options(tmp_path)
    record = run_benchmark(**opts, run_id="first")
    comparison = record.run_metadata["baseline_comparison"]
    assert comparison["available"] is True, comparison
    assert set(comparison) == {"available", "fixed", "broken", "baseline"}
    assert comparison["fixed"] == EXPECTED_FIXED
    assert comparison["broken"] == EXPECTED_BROKEN
    assert comparison["baseline"]["grader_image_id"] == FIXTURE_IMAGE_ID
    assert (
        comparison["baseline"]["grading_inputs_digest"]
        == record.run_metadata["grading_inputs"]["digest"]
    )
    assert (
        comparison["baseline"]["workspace_digest"]
        == record.run_metadata["benchmark_input"]["workspace_digest"]
    )
    counts = {
        "evaluated",
        "complete",
        "pass_rate",
        "tests_passed",
        "tests_total",
        "missing_reasons",
    }
    assert set(record.scores["fdn"]) == counts | {"coverage", "cards"}
    assert set(record.scores["engine"]) == counts | {
        "diagnostics",
        "test_nodes",
        "expected_test_functions",
        "not_run",
        "failure_messages",
    }
    assert record.scores["target"]["tests_passed"] == 1
    assert opts["evaluator"].calls == 2
    published = opts["results_repo"] / "results" / record.candidate.hash / record.run_id
    assert read_record(published).run_metadata["baseline_comparison"] == comparison

    again = run_benchmark(**opts, run_id="second")
    assert opts["evaluator"].calls == 3
    assert again.run_metadata["baseline_comparison"] == comparison

    # Recovery reports the same block as the run path.
    class Killed(EditingHost):
        def run(self, candidate, workspace, evidence_dir, prompt, **kwargs):
            fixture.candidate_edits(workspace)
            raise SystemExit(137)

    with pytest.raises(SystemExit):
        run_benchmark(**{**opts, "host": Killed()}, run_id="killed")
    docker = ContainerDocker(running=False)
    monkeypatch.setattr(
        recovery, "DockerHost", lambda **kwargs: SimpleNamespace(docker=docker, plugin_cache=None)
    )
    recovered = recovery.recover_benchmark(
        run_id="killed",
        spec={},
        **{
            key: opts[key]
            for key in ("bench_root", "results_dir", "results_repo", "state_root", "grader")
        },
    )
    assert recovered.run_metadata["baseline_comparison"] == comparison
    recovered.validate()

    # A published record whose block is malformed does not read.
    manifest = json.loads((published / "manifest.json").read_text())
    manifest["run_metadata"]["baseline_comparison"]["fixed"]["fdn"] = ["b", "a"]
    (published / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(InvalidRunRecordError):
        read_record(published)


def schema_2(record):
    """The record as a bench before the rename wrote it, retired keys and all (ADR-021)."""
    old = copy.deepcopy(record)
    old.manifest["schema_version"] = 2
    old.scores = {RETIRED_SUITE_KEYS[suite]: score for suite, score in old.scores.items()}
    comparison = old.run_metadata.pop("baseline_comparison")
    old.run_metadata["combined_regression"] = {
        "available": True,
        "tests_passed": 4,
        "tests_total": 6,
        "pass_rate": 4 / 6,
        "baseline_score": {"tests_passed": 4, "tests_total": 6},
        "known_best_score": {"tests_passed": 6, "tests_total": 6},
        "fixed": {
            "count": 1,
            "test_nodes": {"fdn_regression": [], "engine_regression": ["test_x.py::d"]},
        },
        "regressed": {
            "count": 1,
            "test_nodes": {"fdn_regression": ["fdn_2/tests.py::c"], "engine_regression": []},
        },
        "baseline": comparison["baseline"],
    }
    return old


def test_a_schema_2_record_reads_by_its_version_and_never_mixes_names(tmp_path):
    record = run_benchmark(**run_options(tmp_path), run_id="first")
    assert record.manifest["schema_version"] == 3
    old = schema_2(record)
    old.validate()
    assert old.suites == record.suites
    for damage in (
        lambda r: r.manifest.update(schema_version=3),
        lambda r: r.run_metadata.update(baseline_comparison=record.run_metadata["baseline_comparison"]),
        lambda r: r.run_metadata["combined_regression"]["regressed"].update(count=0),
    ):
        damaged = copy.deepcopy(old)
        damage(damaged)
        with pytest.raises(InvalidRunRecordError):
            damaged.validate()
    current = copy.deepcopy(record)
    current.run_metadata["combined_regression"] = old.run_metadata["combined_regression"]
    with pytest.raises(InvalidRunRecordError):
        current.validate()
    current = copy.deepcopy(record)
    current.scores = copy.deepcopy(old.scores)
    with pytest.raises(InvalidRunRecordError):
        current.validate()


def test_a_failed_baseline_grade_leaves_the_runs_scores_alone(tmp_path):
    opts = run_options(tmp_path)
    grader = opts["grader"]
    calls = []

    def evaluator(run_dir, benchmark, *, workspace_source):
        calls.append(workspace_source)
        if len(calls) == 1:
            raise GraderError("timeout")
        return grader.evaluate_run(run_dir, benchmark, workspace_source=workspace_source)

    failed = run_benchmark(**{**opts, "evaluator": evaluator}, run_id="failed")
    graded = run_benchmark(**{**opts, "evaluator": Counting(grader)}, run_id="graded")
    assert failed.run_metadata["baseline_comparison"] == {
        "available": False,
        "reason": "baseline_grading_failed:timeout",
    }
    assert {name: (s["tests_passed"], s["tests_total"]) for name, s in failed.scores.items()} == {
        name: (s["tests_passed"], s["tests_total"]) for name, s in graded.scores.items()
    }
    assert "grading_failure" not in failed.run_metadata


# --- Regrade --------------------------------------------------------------------------


def clone(template, directory):
    cloned = retained_runs.clone(template, directory)
    cloned.out = cloned.root / "regrade"
    return cloned


@pytest.fixture(scope="module")
def retained_template(tmp_path_factory):
    """Two runs of the Known Defect benchmark, built once."""
    root = tmp_path_factory.mktemp("retained")
    opts = run_options(root, evaluator=None)
    with retained_runs.building():
        records = [run_benchmark(**opts, run_id=run_id) for run_id in ("run-a", "run-b")]
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
    with retained_runs.building():
        template.summary = invoke(template)
    yield template
    shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def regraded(regraded_template, tmp_path):
    return clone(regraded_template, tmp_path)


def invoke(retained, docker=None, **changes):
    return regrade(
        **{
            "bench_root": retained.opts["bench_root"],
            "benchmark_id": fixture.BENCHMARK,
            "results_repo": retained.opts["results_repo"],
            "results_dir": retained.opts["results_dir"],
            "out": retained.out,
            "docker": docker or LocalDocker(),
            "state_root": retained.opts["state_root"],
            **changes,
        }
    )


def output(retained, run_id):
    return json.loads(next(retained.out.glob(f"*/{run_id}.json")).read_text())


def test_regrade_outputs_carry_the_block_beside_scores_and_reuse_it(regraded):
    summary = regraded.summary
    staged = regraded.records[0].run_metadata["benchmark_input"]["workspace_digest"]
    assert summary["baseline_workspace_digest"] == staged
    assert json.loads((regraded.out / "summary.json").read_text()) == summary
    for record in regraded.records:
        result = output(regraded, record.run_id)
        assert result["baseline_workspace_digest"] == staged
        assert result["baseline_comparison"] == record.run_metadata["baseline_comparison"]
        validate_scores(result["scores"])
        assert "baseline_comparison" not in result["scores"]
    docker = LocalDocker()
    invoke(regraded, docker=docker)
    assert docker.runs == []


class BaselineDown(LocalDocker):
    """The grader fails every baseline grading and grades runs normally."""

    def run(self, arguments, *, timeout, stdout_limit=0):
        if any("sq-regrade-baseline-" in argument for argument in arguments):
            return DockerRun(125, "grader start failed")
        return super().run(arguments, timeout=timeout, stdout_limit=stdout_limit)


def test_a_failed_regrade_baseline_is_retried_on_the_next_invocation(retained):
    store = retained.opts["state_root"] / "baseline-grades"
    for path in store.rglob("*.json"):
        path.unlink()
    invoke(retained, docker=BaselineDown())
    failed = output(retained, "run-a")
    assert failed["baseline_comparison"] == {
        "available": False,
        "reason": "baseline_grading_failed:exit_125",
    }
    validate_scores(failed["scores"])
    assert not list(store.rglob("*.json"))

    docker = LocalDocker()
    invoke(retained, docker=docker)
    # One baseline grade, then both runs again.
    assert len(docker.runs) == 3
    assert (
        output(retained, "run-a")["baseline_comparison"]
        == (retained.records[0].run_metadata["baseline_comparison"])
    )
    docker = LocalDocker()
    invoke(retained, docker=docker)
    assert docker.runs == []


class SuiteEditing(LocalDocker):
    """Changes an Audited Test while the first run is graded."""

    def __init__(self, edit):
        super().__init__()
        self.edit = edit

    def run(self, arguments, *, timeout, stdout_limit=0):
        if self.edit is not None:
            self.edit, edit = None, self.edit
            edit()
        return super().run(arguments, timeout=timeout, stdout_limit=stdout_limit)


def test_inputs_changed_during_a_regrade_make_the_comparison_unavailable_and_retried(retained):
    benchmark = load_benchmark(retained.opts["bench_root"], fixture.BENCHMARK)
    store = retained.opts["state_root"] / "baseline-grades"
    stored = sorted(store.rglob("*.json"))
    edit, restore = engine_suite_edit(benchmark)
    invoke(retained, docker=SuiteEditing(edit), workers=1)
    for record in retained.records:
        assert output(retained, record.run_id)["baseline_comparison"] == {
            "available": False,
            "reason": "grading_inputs_changed_during_grading",
        }
    assert sorted(store.rglob("*.json")) == stored

    restore()
    docker = LocalDocker()
    invoke(retained, docker=docker)
    assert len(docker.runs) == 2
    for record in retained.records:
        assert (
            output(retained, record.run_id)["baseline_comparison"]
            == (record.run_metadata["baseline_comparison"])
        )


def test_a_changed_workspace_misses_the_regrade_cache_and_regrades_the_baseline(regraded):
    (regraded.opts["bench_root"] / "benchmarks/kd/workspace/engine/card.py").write_text(
        "value = 2\n"
    )
    docker = LocalDocker()
    summary = invoke(regraded, docker=docker)
    # One baseline grade for the new Workspace, then each run.
    assert len(docker.runs) == 3
    result = output(regraded, "run-a")
    assert result["baseline_workspace_digest"] == summary["baseline_workspace_digest"]
    assert (
        result["baseline_comparison"]["baseline"]["workspace_digest"]
        != result["source"]["workspace_digest"]
    )


@pytest.mark.parametrize("damage", ["missing", "malformed"])
def test_a_cached_output_with_a_missing_or_malformed_block_is_a_miss(regraded, damage):
    path = next(regraded.out.glob("*/run-a.json"))
    value = json.loads(path.read_text())
    if damage == "missing":
        del value["baseline_comparison"]
    else:
        value["baseline_comparison"]["broken"] = {"fdn": []}
    path.write_text(json.dumps(value))
    docker = LocalDocker()
    invoke(regraded, docker=docker)
    assert len(docker.runs) == 1
    assert output(regraded, "run-a")["baseline_comparison"]["available"] is True


def test_without_a_manifest_a_run_grades_once_and_adding_one_makes_its_outputs_misses(
    tmp_path,
):
    opts = run_options(tmp_path, manifest=False)
    record = run_benchmark(**opts, run_id="run-a")
    assert "baseline_comparison" not in record.run_metadata
    assert opts["evaluator"].calls == 1
    assert not (tmp_path / "state/baseline-grades").exists()
    retained = SimpleNamespace(opts=opts, records=[record], out=tmp_path / "regrade")
    summary = invoke(retained)
    assert summary["baseline_workspace_digest"] is None
    assert output(retained, "run-a")["baseline_workspace_digest"] is None
    assert "baseline_comparison" not in output(retained, "run-a")
    fixture.write_manifest(opts["bench_root"] / "benchmarks/kd", fixture.MANIFEST)
    docker = LocalDocker()
    invoke(retained, docker=docker)
    assert len(docker.runs) == 2
    assert output(retained, "run-a")["baseline_comparison"]["available"] is True


def test_regrade_accepts_a_state_root_and_keeps_the_digest_helper_importable(tmp_path, monkeypatch):
    seen = {}

    def fake(**options):
        seen.update(options)
        raise KarnError("stopped_after_parsing")

    monkeypatch.setattr(regrade_module, "regrade", fake)
    result = CliRunner().invoke(
        main,
        [
            "regrade",
            "--benchmark",
            "kd",
            "--out",
            str(tmp_path / "out"),
            "--state-root",
            str(tmp_path / "s"),
            "--results-dir",
            str(tmp_path / "runs"),
            "--results-repo",
            str(tmp_path / "results"),
        ],
    )
    assert "stopped_after_parsing" in result.output
    assert seen["state_root"] == tmp_path / "s"
    assert regrade_module.grading_code_digest().startswith("sha256:")


def test_the_baseline_key_covers_grading_code_and_image(kd):
    key = baseline_key(
        kd, grading_inputs_digest=DIGEST_A, workspace_digest=DIGEST_C, grader_image_id="img"
    )
    assert key["benchmark"] == kd.identity
    assert set(key) == {
        "benchmark",
        "grading_inputs_digest",
        "grading_code_digest",
        "workspace_digest",
        "grader_image_id",
    }
