"""Grades list every expected test function, say why one did not run, and keep failure messages (#221)."""

from __future__ import annotations

import json
import textwrap
from dataclasses import asdict
from pathlib import Path

import pytest

from silverquillm.evaluator import (
    FAILURE_MESSAGE_BUDGET,
    FAILURE_MESSAGE_LIMIT,
    CardResult,
    EngineResult,
    FullEvalResult,
    _apply_message_budget,
    _bounded_message,
    _failure_messages,
    _grade_audited_card,
    _not_run,
    _PytestRun,
    _python_files,
    _read_report,
    _Report,
    _run_pytest,
    expected_suite_functions,
    expected_test_functions,
    failure_message_cost,
)
from silverquillm.karn.grader import GraderError, evaluation_from_json


def _module(source: str) -> str:
    return textwrap.dedent(source)


# ---------------------------------------------------------------------------
# Static collection of expected test functions
# ---------------------------------------------------------------------------


def test_static_collection_mirrors_pytest_discovery():
    source = _module("""\
        import pytest

        def helper():
            pass

        def test_plain():
            pass

        async def test_async():
            pass

        @pytest.fixture
        def test_looks_like_a_test_but_is_a_fixture():
            pass

        @pytest.mark.parametrize("value", [1, 2, 3])
        def test_param(value):
            pass

        class Base:
            def test_inherited(self):
                pass

        class TestThing(Base):
            def test_method(self):
                pass

            def helper(self):
                pass

            class TestNested:
                def test_inner(self):
                    pass

        class TestWithInit:
            def __init__(self):
                pass

            def test_never_collected(self):
                pass

        class NotATest:
            def test_ignored(self):
                pass

        def test_plain():
            pass
    """)
    assert expected_test_functions(source, "tests.py") == [
        "tests.py::test_plain",
        "tests.py::test_async",
        "tests.py::test_param",
        "tests.py::TestThing::test_inherited",
        "tests.py::TestThing::test_method",
        "tests.py::TestThing::TestNested::test_inner",
    ]


def test_static_collection_of_an_unparseable_module_is_unknown():
    assert expected_test_functions("def test_x(:\n", "tests.py") is None


def test_suite_collection_is_suite_relative_and_follows_python_files(tmp_path):
    (tmp_path / "test_a.py").write_text("def test_one():\n    pass\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "test_b.py").write_text("class TestB:\n    def test_two(self):\n        pass\n")
    (tmp_path / "helpers.py").write_text("def test_not_a_test_file():\n    pass\n")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "test_c.py").write_text("def test_hidden():\n    pass\n")
    assert expected_suite_functions(tmp_path, ("test_*.py", "tests.py")) == [
        "sub/test_b.py::TestB::test_two",
        "test_a.py::test_one",
    ]


def test_python_files_come_from_the_support_ini(tmp_path):
    assert _python_files(tmp_path) == ("test_*.py", "tests.py")
    (tmp_path / "pytest.ini").write_text("[pytest]\npython_files = check_*.py\n")
    assert _python_files(tmp_path) == ("check_*.py",)
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -q\n")
    assert _python_files(tmp_path) == ("test_*.py", "*_test.py")


# ---------------------------------------------------------------------------
# Why an expected node did not run
# ---------------------------------------------------------------------------


def _run(tmp_path: Path, source: str, timeout: int = 60):
    test_file = tmp_path / "tests.py"
    test_file.write_text(_module(source))
    expected = expected_test_functions(test_file.read_text(), "tests.py")
    run = _run_pytest(test_file, [str(tmp_path)], timeout=timeout, capture_test_nodes=True)
    return expected, run


def test_an_import_error_marks_every_function_not_run(tmp_path):
    expected, run = _run(tmp_path, """\
        import module_that_does_not_exist

        def test_a():
            pass

        def test_b():
            pass
    """)
    assert _not_run(expected, run) == [
        {"test_node": "tests.py::test_a", "reason": "import_error"},
        {"test_node": "tests.py::test_b", "reason": "import_error"},
    ]
    assert "module_that_does_not_exist" in _failure_messages(run)["tests.py"]


def test_a_collection_error_that_is_not_an_import_error(tmp_path):
    expected, run = _run(tmp_path, """\
        raise RuntimeError("broken at import")

        def test_a():
            pass
    """)
    assert _not_run(expected, run) == [{"test_node": "tests.py::test_a", "reason": "collection_error"}]


def test_a_runtime_skip_is_not_run_and_a_failure_keeps_its_message(tmp_path):
    expected, run = _run(tmp_path, """\
        import pytest

        def test_skips():
            pytest.skip("the candidate skipped this")

        def test_fails():
            assert 1 == 2, "one is not two"

        @pytest.mark.parametrize("value", [1, 2])
        def test_param(value):
            pass
    """)
    assert _not_run(expected, run) == [{"test_node": "tests.py::test_skips", "reason": "skipped"}]
    messages = _failure_messages(run)
    assert set(messages) == {"tests.py::test_fails"}
    assert "one is not two" in messages["tests.py::test_fails"]


def test_nodes_after_an_abrupt_exit_did_not_run(tmp_path):
    expected, run = _run(tmp_path, """\
        import os

        def test_first():
            pass

        def test_exits():
            os._exit(3)

        def test_after():
            pass
    """)
    assert run.returncode == 3
    assert _not_run(expected, run) == [
        {"test_node": "tests.py::test_exits", "reason": "pytest_exited"},
        {"test_node": "tests.py::test_after", "reason": "pytest_exited"},
    ]


def test_a_timed_out_suite_runs_nothing(tmp_path):
    expected, run = _run(tmp_path, """\
        import time

        def test_slow():
            time.sleep(30)

        def test_quick():
            pass
    """, timeout=3)
    assert run.timed_out and run.report.nodes == []
    assert {row["reason"] for row in _not_run(expected, run)} == {"timeout"}


def test_one_bad_module_interrupts_the_rest_of_a_suite(tmp_path):
    suite = tmp_path / "engine_tests"
    suite.mkdir()
    (suite / "test_good.py").write_text("def test_good():\n    pass\n")
    (suite / "test_bad.py").write_text("import nowhere\n\ndef test_bad():\n    pass\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = --import-mode=importlib\n")
    expected = expected_suite_functions(suite, ("test_*.py",))
    run = _run_pytest(
        suite, [str(tmp_path)], capture_test_nodes=True, isolated_workspace=tmp_path,
        suite_dir="engine_tests",
    )
    assert _not_run(expected, run) == [
        {"test_node": "test_bad.py::test_bad", "reason": "import_error"},
        {"test_node": "test_good.py::test_good", "reason": "collection_interrupted"},
    ]


def test_grading_a_card_counts_expected_functions_from_the_authoritative_file(tmp_path):
    """The candidate's card cannot change what is expected, only what ran."""
    audited = tmp_path / "audited" / "hob" / "hob_1"
    audited.mkdir(parents=True)
    test_file = audited / "tests.py"
    test_file.write_text(_module("""\
        from card_impl import Card

        def test_one():
            assert Card

        def test_two():
            assert Card

        def test_three():
            assert Card
    """))
    support = tmp_path / "test_utils.py"
    support.write_text("")
    overlay = tmp_path / "workspace"
    card = overlay / "cards" / "hob" / "hob_1"
    card.mkdir(parents=True)
    (overlay / "engine").mkdir()
    (overlay / "engine" / "__init__.py").write_text("")
    (card / "card_impl.py").write_text("raise ImportError('the candidate broke its card')\n")
    result = _grade_audited_card("hob_1", test_file, overlay, 60, test_utils=support)
    assert result.expected_test_functions == 3
    assert [row["test_node"] for row in result.not_run] == [
        "tests.py::test_one", "tests.py::test_two", "tests.py::test_three",
    ]
    assert {row["reason"] for row in result.not_run} == {"import_error"}
    # The score is unchanged: functions that did not run are not added to tests_total.
    assert all("::" not in node["test_node"] or "<collection-error>" in node["test_node"]
               for node in result.test_nodes)


def test_missing_grading_support_marks_everything_not_run(tmp_path):
    test_file = tmp_path / "tests.py"
    test_file.write_text("def test_a():\n    pass\n")
    result = _grade_audited_card("hob_1", test_file, tmp_path, 60, test_utils=tmp_path / "missing.py")
    assert result.skipped and result.expected_test_functions == 1
    assert result.not_run == [{"test_node": "tests.py::test_a", "reason": "grading_support_missing"}]


# ---------------------------------------------------------------------------
# Failure messages stay bounded
# ---------------------------------------------------------------------------


def test_a_message_is_one_bounded_printable_line():
    message = _bounded_message("first\nsecond\x00\ud800" + "x" * 10_000)
    assert len(message) == FAILURE_MESSAGE_LIMIT
    assert message.startswith("first second ?")
    message.encode("utf-8")
    assert _bounded_message(None) == ""
    assert _bounded_message("<Card object at 0x7f2f9d4aa6c0>") == "<Card object at 0x…>"


def test_messages_past_the_evaluation_budget_are_dropped():
    per_card = FAILURE_MESSAGE_BUDGET // FAILURE_MESSAGE_LIMIT
    cards = {
        f"c{index}": CardResult(
            collector_number=f"c{index}",
            failure_messages={f"tests.py::t{n}": "m" * FAILURE_MESSAGE_LIMIT for n in range(per_card)},
        )
        for index in range(3)
    }
    result = FullEvalResult(sos_results=cards)
    _apply_message_budget(result)
    kept = sum(
        failure_message_cost(*entry) for card in cards.values() for entry in card.failure_messages.items()
    )
    assert kept <= FAILURE_MESSAGE_BUDGET
    assert cards["c0"].failure_messages and not cards["c2"].failure_messages


def test_the_budget_counts_escaped_bytes_not_characters():
    wide = "\u00e9" * FAILURE_MESSAGE_LIMIT
    card = CardResult(
        collector_number="c",
        failure_messages={f"tests.py::t{n}": wide for n in range(FAILURE_MESSAGE_BUDGET // FAILURE_MESSAGE_LIMIT)},
    )
    result = FullEvalResult(sos_results={"c": card})
    _apply_message_budget(result)
    assert len(json.dumps(card.failure_messages)) <= FAILURE_MESSAGE_BUDGET + 64 * len(card.failure_messages)
    assert sum(failure_message_cost(*e) for e in card.failure_messages.items()) <= FAILURE_MESSAGE_BUDGET


# ---------------------------------------------------------------------------
# The host accepts only bounded, consistent gap fields
# ---------------------------------------------------------------------------


def _evaluation(**card_fields) -> bytes:
    card = CardResult(
        collector_number="hob_1",
        tests_passed=1,
        tests_failed=1,
        tests_total=2,
        pass_rate=0.5,
        test_nodes=[
            {"test_node": "tests.py::test_a", "outcome": "pass"},
            {"test_node": "tests.py::test_b[1]", "outcome": "fail"},
        ],
        expected_test_functions=3,
        not_run=[{"test_node": "tests.py::test_c", "reason": "skipped"}],
        failure_messages={"tests.py::test_b[1]": "AssertionError: no"},
    )
    value = asdict(FullEvalResult(sos_results={"hob_1": card}, engine_result=EngineResult()))
    value["sos_results"]["hob_1"].update(card_fields)
    return json.dumps(value).encode()


def test_the_host_reads_back_the_gap_fields():
    card = evaluation_from_json(_evaluation()).sos_results["hob_1"]
    assert card.expected_test_functions == 3
    assert card.not_run == [{"test_node": "tests.py::test_c", "reason": "skipped"}]
    assert card.failure_messages == {"tests.py::test_b[1]": "AssertionError: no"}


@pytest.mark.parametrize(
    "fields",
    [
        {"failure_messages": {"tests.py::test_b[1]": "x" * (FAILURE_MESSAGE_LIMIT + 1)}},
        {"failure_messages": {"tests.py::test_a": "a passing node has no message"}},
        {"failure_messages": {"tests.py::test_b[1]": ""}},
        {"not_run": [{"test_node": "tests.py::test_c", "reason": "made_up"}]},
        {"not_run": [{"test_node": "tests.py::test_c", "reason": "skipped", "extra": 1}]},
        {"not_run": [{"test_node": "tests.py::test_b", "reason": "skipped"}]},
        {"not_run": [{"test_node": "tests.py::test_c", "reason": "skipped"}] * 2},
        {"expected_test_functions": 0},
        {"expected_test_functions": None},
        {"expected_test_functions": -1},
        {"expected_test_functions": True},
    ],
)
def test_the_host_refuses_inconsistent_gap_fields(fields):
    with pytest.raises(GraderError):
        evaluation_from_json(_evaluation(**fields))


def test_the_host_refuses_messages_over_the_evaluation_budget():
    value = json.loads(_evaluation())
    per_card = FAILURE_MESSAGE_BUDGET // FAILURE_MESSAGE_LIMIT + 1
    for index in range(2):
        nodes = [{"test_node": f"tests.py::t{n}", "outcome": "fail"} for n in range(per_card)]
        value["fdn_results"][f"fdn_{index}"] = asdict(CardResult(
            collector_number=f"fdn_{index}", tests_failed=per_card, tests_total=per_card,
            test_nodes=nodes,
            failure_messages={node["test_node"]: "m" * FAILURE_MESSAGE_LIMIT for node in nodes},
        ))  # fmt: skip
    with pytest.raises(GraderError):
        evaluation_from_json(json.dumps(value).encode())


def test_an_older_style_result_without_expected_functions_has_no_not_run():
    card = evaluation_from_json(
        _evaluation(expected_test_functions=None, not_run=[])
    ).sos_results["hob_1"]
    assert card.expected_test_functions is None and card.not_run == []


def test_a_forged_collect_row_without_a_failure_does_not_crash_grading(tmp_path):
    report = tmp_path / "report.jsonl"
    report.write_text(json.dumps({"nodeid": "x", "when": "collect", "outcome": "pass"}) + "\n")
    assert _read_report(report).collection_errors == {"x": ""}


def test_a_class_collection_error_is_that_class_functions_own_error():
    report = _Report(collection_errors={"tests.py::TestA": "ImportError: no"})
    run = _PytestRun(0, 1, 1, [], report, returncode=2)
    assert _not_run(["tests.py::TestA::test_x", "tests.py::TestAB::test_y"], run) == [
        {"test_node": "tests.py::TestA::test_x", "reason": "import_error"},
        {"test_node": "tests.py::TestAB::test_y", "reason": "collection_interrupted"},
    ]


def test_worker_and_host_agree_on_which_functions_ran():
    nodes = [{"test_node": "tests.py::test_a[<collection-error>]", "outcome": "pass"}]
    run = _PytestRun(1, 0, 1, [], _Report(nodes=nodes), returncode=0)
    not_run = _not_run(["tests.py::test_a"], run)
    card = CardResult(
        collector_number="hob_1", tests_passed=1, tests_total=1, pass_rate=1.0,
        test_nodes=nodes, expected_test_functions=1, not_run=not_run,
    )
    value = asdict(FullEvalResult(sos_results={"hob_1": card}, engine_result=EngineResult()))
    assert evaluation_from_json(json.dumps(value).encode()).sos_results["hob_1"].not_run == not_run


def test_engine_messages_within_budget_are_accepted_by_the_host():
    nodes = [{"test_node": f"test_e.py::test_{n}", "outcome": "fail"} for n in range(2000)]
    engine = EngineResult(
        tests_failed=2000, tests_total=2000, test_nodes=nodes, expected_test_functions=2000,
        failure_messages={node["test_node"]: "m" * FAILURE_MESSAGE_LIMIT for node in nodes},
    )
    result = FullEvalResult(engine_result=engine)
    _apply_message_budget(result)
    assert engine.failure_messages
    assert evaluation_from_json(json.dumps(asdict(result)).encode()).engine_result.failure_messages


# ---------------------------------------------------------------------------
# Dimension totals: nodes that ran plus each scored function that did not (SCORING.md)
# ---------------------------------------------------------------------------


def _engine(tmp_path: Path, files: dict[str, str], timeout: int = 60, *, support: bool = True):
    from silverquillm.evaluator import _eval_engine

    workspace = tmp_path / "workspace"
    (workspace / "engine").mkdir(parents=True)
    (workspace / "cards").mkdir()
    (workspace / "pytest.ini").write_text(
        "[pytest]\npython_files = test_*.py\naddopts = --import-mode=importlib\n"
    )
    if support:
        (workspace / "test_utils.py").write_text("")
    suite = tmp_path / "engine_tests"
    suite.mkdir()
    for name, source in files.items():
        (suite / name).write_text(_module(source))
    return _eval_engine(
        workspace / "engine", suite, timeout,
        support_dir=workspace, test_utils=workspace / "test_utils.py",
    )


def _dimensions(engine: EngineResult, tmp_path: Path, fdn: dict | None = None) -> dict:
    from types import SimpleNamespace

    from silverquillm.karn.execution import _scores

    benchmark = SimpleNamespace(target_set="hob", cards=[], root=tmp_path)
    return _scores(FullEvalResult(fdn_results=fdn or {}, engine_result=engine), benchmark)


def _engine_score(engine: EngineResult, tmp_path: Path) -> tuple:
    score = _dimensions(engine, tmp_path)["engine_regression"]
    return score["tests_passed"], score["tests_total"], score["complete"]


def test_a_collection_error_is_not_a_scored_test(tmp_path):
    engine = _engine(tmp_path, {
        "test_good.py": "def test_good():\n    pass\n",
        "test_bad.py": "import nowhere\n\ndef test_bad():\n    pass\n",
    })
    assert engine.tests_total == 1  # pytest's raw summary counts the collection error
    assert _engine_score(engine, tmp_path) == (0, 2, False)


def test_a_pass_then_an_abrupt_exit_keeps_the_pass_and_is_incomplete(tmp_path):
    engine = _engine(tmp_path, {"test_e.py": """\
        import os

        def test_first():
            pass

        def test_exits():
            os._exit(3)

        def test_after():
            pass
    """})
    assert engine.tests_total == 0  # no summary was printed
    assert _engine_score(engine, tmp_path) == (1, 3, False)
    assert any(error.startswith("pytest_exited") for error in engine.errors)


def test_setup_and_teardown_failures_fail_their_nodes(tmp_path):
    engine = _engine(tmp_path, {"test_e.py": """\
        import pytest

        @pytest.fixture
        def broken_setup():
            raise RuntimeError("setup broke")

        @pytest.fixture
        def broken_teardown():
            yield
            raise RuntimeError("teardown broke")

        def test_setup(broken_setup):
            pass

        def test_teardown(broken_teardown):
            pass

        def test_ok():
            pass
    """})
    outcomes = {node["test_node"]: node["outcome"] for node in engine.test_nodes}
    assert outcomes == {
        "test_e.py::test_setup": "fail",
        "test_e.py::test_teardown": "fail",
        "test_e.py::test_ok": "pass",
    }
    assert "teardown broke" in engine.failure_messages["test_e.py::test_teardown"]
    assert _engine_score(engine, tmp_path) == (1, 3, False)


def test_a_skipped_function_counts_as_failed_without_making_the_grade_incomplete(tmp_path):
    engine = _engine(tmp_path, {"test_e.py": """\
        import pytest

        def test_skips():
            pytest.skip("not today")

        def test_ok():
            pass
    """})
    assert _engine_score(engine, tmp_path) == (1, 2, True)


def test_a_timed_out_engine_suite_scores_every_function_failed(tmp_path):
    engine = _engine(tmp_path, {"test_e.py": """\
        import time

        def test_slow():
            time.sleep(30)

        def test_quick():
            pass
    """}, timeout=3)
    assert _engine_score(engine, tmp_path) == (0, 2, False)


def test_missing_engine_support_leaves_the_dimension_unevaluated(tmp_path):
    engine = _engine(tmp_path, {"test_e.py": "def test_a():\n    pass\n"}, support=False)
    score = _dimensions(engine, tmp_path)["engine_regression"]
    assert not score["evaluated"] and score["tests_total"] is None


def test_a_result_without_node_reporting_falls_back_to_the_summary():
    from silverquillm.karn.execution import _suite_counts

    assert _suite_counts(EngineResult(tests_passed=2, tests_failed=1, tests_total=3)) == (2, 3)
    card = CardResult(
        collector_number="c",
        tests_failed=1,
        tests_total=1,
        test_nodes=[
            {"test_node": "tests.py", "outcome": "fail"},
            {"test_node": "tests.py::<collection-error>", "outcome": "fail"},
        ],
        expected_test_functions=1,
        not_run=[{"test_node": "tests.py::test_a", "reason": "import_error"}],
    )
    assert _suite_counts(card) == (0, 1)


def test_the_dimension_totals_reach_the_combined_regression_and_regrade(tmp_path):
    from silverquillm.karn import regrade as regrade_module
    from silverquillm.karn.baseline import combined_regression
    from silverquillm.karn.execution import _scores
    from silverquillm.karn.records import validate_scores

    from .test_karn_combined_regression import baseline

    engine = _engine(tmp_path, {"test_e.py": """\
        import os

        def test_first():
            pass

        def test_exits():
            os._exit(3)

        def test_after():
            pass
    """})
    fdn = {"fdn_1": CardResult("fdn_1", test_nodes=[{"test_node": "tests.py::a", "outcome": "pass"}])}
    scores = _dimensions(engine, tmp_path, fdn)
    validate_scores(scores)
    reference = baseline(
        {"fdn_1/tests.py::a": "pass"},
        {"test_e.py::test_first": "pass", "test_e.py::test_exits": "pass", "test_e.py::test_after": "pass"},
    )
    block = combined_regression(scores, FullEvalResult(fdn_results=fdn, engine_result=engine), reference)
    assert (block["tests_passed"], block["tests_total"]) == (2, 4)
    assert block["regressed"]["test_nodes"]["engine_regression"] == [
        "test_e.py::test_after", "test_e.py::test_exits",
    ]
    # A regrade scores its evaluation with the same function a run does.
    assert regrade_module._scores is _scores


@pytest.mark.parametrize("reason", [["skipped"], {"skipped": 1}, None])
def test_the_host_refuses_a_not_run_reason_that_is_not_a_string(reason):
    with pytest.raises(GraderError, match="evaluation_invalid_not_run"):
        evaluation_from_json(_evaluation(not_run=[{"test_node": "tests.py::test_c", "reason": reason}]))


def test_the_kept_messages_encode_within_the_budget():
    holders = [
        CardResult(
            collector_number=f"c{index}",
            failure_messages={f"tests.py::t{n}": "m" * FAILURE_MESSAGE_LIMIT for n in range(250)},
        )
        for index in range(4)
    ]
    result = FullEvalResult(sos_results={card.collector_number: card for card in holders})
    _apply_message_budget(result)
    kept = [card.failure_messages for card in holders if card.failure_messages]
    assert sum(len(json.dumps(mapping).encode()) for mapping in kept) <= FAILURE_MESSAGE_BUDGET
    for mapping in kept:
        assert len(json.dumps(mapping)) == sum(failure_message_cost(*entry) for entry in mapping.items())
