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
        (suite / name).parent.mkdir(parents=True, exist_ok=True)
        (suite / name).write_text(_module(source))
    return _eval_engine(
        workspace / "engine", suite, timeout,
        support_dir=workspace, test_utils=workspace / "test_utils.py",
    )


def _suite_scores(engine: EngineResult, tmp_path: Path, fdn: dict | None = None) -> dict:
    from types import SimpleNamespace

    from silverquillm.karn.execution import _scores

    benchmark = SimpleNamespace(target_set="hob", cards=[], root=tmp_path)
    return _scores(FullEvalResult(fdn_results=fdn or {}, engine_result=engine), benchmark)


def _engine_score(engine: EngineResult, tmp_path: Path) -> tuple:
    score = _suite_scores(engine, tmp_path)["engine"]
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


def test_missing_engine_support_leaves_the_suite_unevaluated(tmp_path):
    engine = _engine(tmp_path, {"test_e.py": "def test_a():\n    pass\n"}, support=False)
    score = _suite_scores(engine, tmp_path)["engine"]
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


def test_the_suite_totals_reach_the_baseline_comparison_and_regrade(tmp_path):
    from silverquillm.karn import regrade as regrade_module
    from silverquillm.karn.baseline import baseline_comparison
    from silverquillm.karn.execution import _scores
    from silverquillm.karn.records import validate_scores

    from .test_karn_baseline_comparison import baseline

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
    scores = _suite_scores(engine, tmp_path, fdn)
    validate_scores(scores)
    reference = baseline(
        {"fdn_1/tests.py::a": "pass"},
        {"test_e.py::test_first": "pass", "test_e.py::test_exits": "pass", "test_e.py::test_after": "pass"},
    )
    block = baseline_comparison(scores, FullEvalResult(fdn_results=fdn, engine_result=engine), reference)
    assert (scores["engine"]["tests_passed"], scores["engine"]["tests_total"]) == (1, 3)
    assert block["broken"]["engine"] == [
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


def _card(tmp_path: Path, source: str) -> CardResult:
    """Grade one hob card whose authoritative tests are *source*, with a working card."""
    audited = tmp_path / "audited" / "hob" / "hob_1"
    audited.mkdir(parents=True)
    test_file = audited / "tests.py"
    test_file.write_text(_module(source))
    support = tmp_path / "test_utils.py"
    support.write_text("")
    overlay = tmp_path / "workspace"
    card = overlay / "cards" / "hob" / "hob_1"
    card.mkdir(parents=True)
    (overlay / "engine").mkdir()
    (overlay / "engine" / "__init__.py").write_text("")
    (card / "card_impl.py").write_text("class Card:\n    pass\n")
    return _grade_audited_card("hob_1", test_file, overlay, 60, test_utils=support)


def _host_round_trip(engine: EngineResult | None = None, card: CardResult | None = None) -> FullEvalResult:
    value = FullEvalResult(
        sos_results={"hob_1": card} if card is not None else {},
        engine_result=engine or EngineResult(),
    )
    return evaluation_from_json(json.dumps(asdict(value)).encode())


_CLASS_COLLECTION_ERROR = """\
    import pytest

    class TestBad:
        @pytest.mark.parametrize("x,y", [(1,)])
        def test_bad(self, x, y):
            pass

    def test_good():
        pass
"""

_NESTED_CLASS_COLLECTION_ERROR = """\
    import pytest

    class TestOuter:
        class TestInner:
            @pytest.mark.parametrize("x,y", [(1,)])
            def test_bad(self, x, y):
                pass

        def test_outer(self):
            pass
"""


@pytest.mark.parametrize(
    ("source", "collector", "missing"),
    [
        (_CLASS_COLLECTION_ERROR, "test_e.py::TestBad", ["test_e.py::TestBad::test_bad", "test_e.py::test_good"]),
        (
            _NESTED_CLASS_COLLECTION_ERROR,
            "test_e.py::TestOuter::TestInner",
            ["test_e.py::TestOuter::TestInner::test_bad", "test_e.py::TestOuter::test_outer"],
        ),
    ],
    ids=["class", "nested_class"],
)
def test_an_engine_class_collection_error_is_not_a_scored_test(tmp_path, source, collector, missing):
    from silverquillm.karn.execution import _suite_counts

    engine = _engine(tmp_path, {"test_e.py": source})
    row = f"{collector}::<collection-error>"
    assert {"test_node": row, "outcome": "fail"} in engine.test_nodes
    assert sorted(item["test_node"] for item in engine.not_run) == sorted(missing)
    assert _suite_counts(engine) == (0, 2)
    decoded = _host_round_trip(engine=engine).engine_result
    assert decoded.test_nodes == engine.test_nodes and decoded.not_run == engine.not_run
    assert _suite_counts(decoded) == (0, 2)
    assert _engine_score(decoded, tmp_path)[:2] == (0, 2)


def test_a_card_class_collection_error_is_not_a_scored_test(tmp_path):
    from silverquillm.karn.execution import _suite_counts

    card = _card(tmp_path, _CLASS_COLLECTION_ERROR)
    assert {"test_node": "tests.py::TestBad::<collection-error>", "outcome": "fail"} in card.test_nodes
    assert {row["test_node"]: row["reason"] for row in card.not_run} == {
        "tests.py::TestBad::test_bad": "collection_error",
        "tests.py::test_good": "collection_interrupted",
    }
    assert "tests.py::TestBad::<collection-error>" in card.failure_messages
    assert _suite_counts(card) == (0, 2)
    assert _suite_counts(_host_round_trip(card=card).sos_results["hob_1"]) == (0, 2)


def test_a_suite_that_keeps_collecting_scores_its_unaffected_tests(tmp_path):
    from silverquillm.evaluator import _eval_engine
    from silverquillm.karn.execution import _suite_counts

    workspace = tmp_path / "workspace"
    (workspace / "engine").mkdir(parents=True)
    (workspace / "cards").mkdir()
    (workspace / "pytest.ini").write_text(
        "[pytest]\npython_files = test_*.py\n"
        "addopts = --import-mode=importlib --continue-on-collection-errors\n"
    )
    (workspace / "test_utils.py").write_text("")
    suite = tmp_path / "engine_tests"
    suite.mkdir()
    (suite / "test_e.py").write_text(_module(_CLASS_COLLECTION_ERROR))
    engine = _eval_engine(
        workspace / "engine", suite, 60, support_dir=workspace, test_utils=workspace / "test_utils.py",
    )
    assert [row["test_node"] for row in engine.not_run] == ["test_e.py::TestBad::test_bad"]
    assert _suite_counts(engine) == (1, 2)
    block = _class_collection_comparison(engine, tmp_path)
    assert block["broken"]["engine"] == ["test_e.py::TestBad::test_bad"]


def _class_collection_comparison(engine: EngineResult, tmp_path: Path) -> dict:
    from silverquillm.karn.baseline import baseline_comparison

    from .test_karn_baseline_comparison import baseline

    fdn = {"fdn_1": CardResult("fdn_1", test_nodes=[{"test_node": "tests.py::a", "outcome": "pass"}])}
    scores = _suite_scores(engine, tmp_path, fdn)
    reference = baseline(
        {"fdn_1/tests.py::a": "pass"},
        {"test_e.py::TestBad::test_bad": "pass", "test_e.py::test_good": "pass"},
    )
    return baseline_comparison(scores, FullEvalResult(fdn_results=fdn, engine_result=engine), reference)


def test_a_class_collection_error_reaches_the_baseline_comparison_once(tmp_path):
    engine = _engine(tmp_path, {"test_e.py": _CLASS_COLLECTION_ERROR})
    block = _class_collection_comparison(engine, tmp_path)
    assert block["broken"]["engine"] == ["test_e.py::TestBad::test_bad", "test_e.py::test_good"]


def _exiting(status: int, after_a_pass: bool) -> str:
    if after_a_pass:
        return f"""\
            import os

            def test_first():
                pass

            def test_exits():
                os._exit({status})

            def test_after():
                pass
        """
    return f"""\
        import os

        os._exit({status})

        def test_first():
            pass

        def test_exits():
            pass

        def test_after():
            pass
    """


@pytest.mark.parametrize("after_a_pass", [False, True], ids=["before_any_test", "after_a_pass"])
@pytest.mark.parametrize("status", [0, 1, 5])
def test_an_engine_suite_cut_short_with_an_orderly_status_is_incomplete(tmp_path, status, after_a_pass):
    engine = _engine(tmp_path, {"test_e.py": _exiting(status, after_a_pass)})
    assert f"pytest_exited: exit status {status}" in engine.errors
    passed = 1 if after_a_pass else 0
    assert _engine_score(engine, tmp_path) == (passed, 3, False)
    assert {row["reason"] for row in engine.not_run} == {"pytest_exited"}
    decoded = _host_round_trip(engine=engine).engine_result
    assert _engine_score(decoded, tmp_path) == (passed, 3, False)


@pytest.mark.parametrize("after_a_pass", [False, True], ids=["before_any_test", "after_a_pass"])
@pytest.mark.parametrize("status", [0, 1, 5])
def test_a_card_suite_cut_short_with_an_orderly_status_is_incomplete(tmp_path, status, after_a_pass):
    from silverquillm.karn.execution import _suite_counts

    card = _card(tmp_path, _exiting(status, after_a_pass))
    assert f"pytest_exited: exit status {status}" in card.errors
    assert _suite_counts(card) == (1 if after_a_pass else 0, 3)
    assert {row["reason"] for row in card.not_run} == {"pytest_exited"}
    decoded = _host_round_trip(card=card).sos_results["hob_1"]
    assert f"pytest_exited: exit status {status}" in decoded.errors


_INTERRUPTIONS = {
    "keyboard_interrupt": "raise KeyboardInterrupt",
    "pytest_exit_default": "pytest.exit('stop')",
    "pytest_exit_0": "pytest.exit('stop', returncode=0)",
    "pytest_exit_1": "pytest.exit('stop', returncode=1)",
    "pytest_exit_5": "pytest.exit('stop', returncode=5)",
    "system_exit_0": "raise SystemExit(0)",
}


def _interrupting(statement: str, after_a_pass: bool) -> str:
    if after_a_pass:
        return f"""\
            import pytest

            def test_first():
                pass

            def test_stops():
                {statement}

            def test_after():
                pass
        """
    return f"""\
        import pytest

        {statement}

        def test_first():
            pass

        def test_stops():
            pass

        def test_after():
            pass
    """


# Inside a test, SystemExit is an ordinary test failure; only at import does it stop pytest.
_INTERRUPTION_CASES = [
    pytest.param(statement, after, id=f"{name}-{'after_a_pass' if after else 'before_any_test'}")
    for name, statement in _INTERRUPTIONS.items()
    for after in (False, True)
    if not (name == "system_exit_0" and after)
]
# pytest.exit at import is reported as that module's collection error, a more specific diagnosis.
_STOPPED_REASONS = {"pytest_exited", "collection_error", "collection_interrupted"}


def _stopped(errors: list[str]) -> bool:
    return any(error.startswith(("pytest_exited: exit status ", "ERROR ")) for error in errors)


@pytest.mark.parametrize("statement", ["raise KeyboardInterrupt", "pytest.exit('stop', returncode=0)"])
def test_an_interruption_after_a_pass_reports_pytest_exited(tmp_path, statement):
    expected, run = _run(tmp_path, _interrupting(statement, after_a_pass=True))
    assert not run.report.completed and run.ended_early
    assert f"pytest_exited: exit status {run.returncode}" in run.errors
    assert {row["reason"] for row in _not_run(expected, run)} == {"pytest_exited"}


@pytest.mark.parametrize(("statement", "after_a_pass"), _INTERRUPTION_CASES)
def test_an_interrupted_engine_suite_is_incomplete(tmp_path, statement, after_a_pass):
    engine = _engine(tmp_path, {"test_e.py": _interrupting(statement, after_a_pass)})
    assert _stopped(engine.errors), engine.errors
    passed, total, complete = _engine_score(engine, tmp_path)
    assert (passed, total, complete) == (1 if after_a_pass else 0, 3, False)
    assert {row["reason"] for row in engine.not_run} <= _STOPPED_REASONS
    decoded = _host_round_trip(engine=engine).engine_result
    assert _engine_score(decoded, tmp_path) == (passed, 3, False)


@pytest.mark.parametrize(("statement", "after_a_pass"), _INTERRUPTION_CASES)
def test_an_interrupted_card_suite_is_incomplete(tmp_path, statement, after_a_pass):
    from silverquillm.karn.execution import _suite_counts

    card = _card(tmp_path, _interrupting(statement, after_a_pass))
    assert _stopped(card.errors), card.errors
    assert _suite_counts(card) == (1 if after_a_pass else 0, 3)
    assert {row["reason"] for row in card.not_run} <= _STOPPED_REASONS
    decoded = _host_round_trip(card=card).sos_results["hob_1"]
    assert _stopped(decoded.errors)


def test_an_internal_error_is_incomplete(tmp_path):
    _, run = _run(tmp_path, _interrupting("raise SystemExit(0)", after_a_pass=False))
    assert not run.report.completed and run.ended_early
    assert f"pytest_exited: exit status {run.returncode}" in run.errors


def test_a_completion_row_never_overrides_an_abnormal_exit(tmp_path):
    """A completion row written before an abnormal exit status does not make the suite complete."""
    _, run = _run(tmp_path, """\
        import os
        import sys

        def test_first():
            pass

        def test_forges_completion_then_exits():
            reporter = next(
                module for name, module in sys.modules.items()
                if name.startswith("_silverquillm_node_report_")
            )
            reporter._write({"when": "session", "outcome": "complete", "token": reporter._SESSION_TOKEN})
            os._exit(2)
    """)
    assert run.report.completed and run.returncode == 2
    assert run.ended_early
    assert "pytest_exited: exit status 2" in run.errors


def test_a_regrade_keeps_an_interrupted_suite_incomplete(tmp_path):
    from silverquillm.karn.records import validate_scores

    engine = _engine(tmp_path, {"test_e.py": _interrupting("pytest.exit('stop', returncode=0)", True)})
    scores = _suite_scores(engine, tmp_path)
    validate_scores(scores)
    assert scores["engine"]["complete"] is False


def test_pytests_own_stop_after_collection_errors_keeps_its_diagnosis(tmp_path):
    expected, run = _run(tmp_path, "import missing_module_for_the_test\n\ndef test_a():\n    pass\n")
    assert run.report.collection_errors
    assert run.report.completed and not run.ended_early
    assert not any(error.startswith("pytest_exited") for error in run.errors)
    assert {row["reason"] for row in _not_run(expected, run)} == {"import_error"}


def test_a_regrade_keeps_a_cut_short_suite_incomplete(tmp_path):
    from silverquillm.karn import regrade as regrade_module
    from silverquillm.karn.execution import _scores
    from silverquillm.karn.records import validate_scores

    engine = _engine(tmp_path, {"test_e.py": _exiting(0, after_a_pass=True)})
    scores = _suite_scores(engine, tmp_path)
    validate_scores(scores)
    assert scores["engine"]["complete"] is False
    assert "pytest_exited: exit status 0" in scores["engine"]["missing_reasons"]
    assert regrade_module._scores is _scores


@pytest.mark.parametrize(
    ("source", "reasons"),
    [
        ("def test_passes():\n    pass\n", set()),
        ("def test_fails():\n    assert False\n", set()),
        ("import pytest\n\n@pytest.mark.skip\ndef test_skipped():\n    pass\n", {"skipped"}),
        ("import pytest\n\n@pytest.mark.xfail\ndef test_xfails():\n    assert False\n", {"skipped"}),
        ("def helper():\n    pass\n", set()),
    ],
    ids=["passing", "failing", "all_skipped", "xfail", "no_tests"],
)
def test_an_orderly_session_is_not_cut_short(tmp_path, source, reasons):
    expected, run = _run(tmp_path, source)
    assert run.report.completed and not run.ended_early
    assert not any(error.startswith("pytest_exited") for error in run.errors)
    assert {row["reason"] for row in _not_run(expected, run)} == reasons


@pytest.mark.parametrize("token", [None, "other"])
def test_a_completion_row_without_this_runs_token_does_not_complete(tmp_path, token):
    report = tmp_path / "report.jsonl"
    report.write_text(json.dumps({"when": "session", "outcome": "complete", "token": "forged"}) + "\n")
    assert not _read_report(report, None, token).completed
    assert _read_report(report, None, "forged").completed
    assert _read_report(report, None, "forged").nodes == []


# ---------------------------------------------------------------------------
# Adversarial review of 24357066
# ---------------------------------------------------------------------------

# Candidate code that closes the process's stdout: pytest's terminal reporter then fails
# inside its own internal-error handler, before a later hook could see the error.
_CLOSED_STDOUT = {
    "garbage_collected_wrapper": """\
        import io
        import sys

        def test_first():
            pass

        def test_stops():
            io.TextIOWrapper(sys.__stdout__.buffer, encoding="utf-8").write("")

        def test_after():
            pass
    """,
    "plain_close": """\
        import sys

        def test_first():
            pass

        def test_stops():
            sys.__stdout__.close()

        def test_after():
            pass
    """,
}


@pytest.mark.parametrize("source", list(_CLOSED_STDOUT.values()), ids=list(_CLOSED_STDOUT))
def test_an_engine_suite_whose_stdout_is_closed_is_incomplete(tmp_path, source):
    engine = _engine(tmp_path, {"test_e.py": source})
    assert any(error.startswith("pytest_exited: exit status ") for error in engine.errors), engine.errors
    passed, total, complete = _engine_score(engine, tmp_path)
    assert (total, complete) == (3, False)
    assert {row["reason"] for row in engine.not_run} == {"pytest_exited"}
    decoded = _host_round_trip(engine=engine).engine_result
    assert _engine_score(decoded, tmp_path) == (passed, 3, False)


@pytest.mark.parametrize("source", list(_CLOSED_STDOUT.values()), ids=list(_CLOSED_STDOUT))
def test_a_card_suite_whose_stdout_is_closed_is_incomplete(tmp_path, source):
    from silverquillm.karn.execution import _suite_counts

    card = _card(tmp_path, source)
    assert any(error.startswith("pytest_exited: exit status ") for error in card.errors), card.errors
    assert _suite_counts(card)[1] == 3
    assert {row["reason"] for row in card.not_run} == {"pytest_exited"}
    decoded = _host_round_trip(card=card).sos_results["hob_1"]
    assert any(error.startswith("pytest_exited: exit status ") for error in decoded.errors)


_LOGS_AN_ERROR = """\
    import logging

    def test_passes():
        pass

    def test_fails():
        logging.getLogger("engine.game").error("illegal target")
        assert False
"""


def test_an_engine_failure_that_logs_an_error_stays_complete(tmp_path):
    engine = _engine(tmp_path, {"test_e.py": _LOGS_AN_ERROR})
    assert not any("illegal target" in error for error in engine.errors), engine.errors
    assert _engine_score(engine, tmp_path) == (1, 2, True)
    assert _engine_score(_host_round_trip(engine=engine).engine_result, tmp_path) == (1, 2, True)


def test_a_card_failure_that_logs_an_error_stays_complete(tmp_path):
    from silverquillm.karn.execution import _suite_counts

    card = _card(tmp_path, _LOGS_AN_ERROR)
    assert _suite_counts(card) == (1, 2)
    assert all(error.startswith("FAILED ") for error in card.errors), card.errors


def test_only_the_short_summary_holds_errors():
    from silverquillm.evaluator import _parse_pytest_output

    output = textwrap.dedent("""\
        ---------------------------- Captured log call -----------------------------
        ERROR    engine.game:test_e.py:4 illegal target
        =========================== short test summary info ============================
        FAILED test_e.py::test_fails - assert False
        ERROR test_e.py::test_setup - RuntimeError
        1 failed, 1 passed, 1 error in 0.05s
    """)
    assert _parse_pytest_output(output)[3] == [
        "FAILED test_e.py::test_fails - assert False",
        "ERROR test_e.py::test_setup - RuntimeError",
    ]


@pytest.mark.parametrize(
    "statement",
    ["pytest.skip('not here', allow_module_level=True)", "pytest.importorskip('no_such_module_xyz')"],
    ids=["skip", "importorskip"],
)
def test_a_module_level_skip_labels_its_functions_skipped(tmp_path, statement):
    expected, run = _run(tmp_path, f"""\
        import pytest

        {statement}

        def test_one():
            pass

        def test_two():
            pass
    """)
    assert run.report.completed and not run.ended_early
    assert {row["reason"] for row in _not_run(expected, run)} == {"skipped"}


def test_test_false_turns_off_what_pytest_does_not_collect():
    source = _module("""\
        def test_off():
            pass
        test_off.__test__ = False

        def test_on():
            pass

        class TestOff:
            __test__ = False

            def test_m(self):
                pass

        class TestInherits(TestOff):
            def test_n(self):
                pass

        class TestBack(TestOff):
            __test__ = True

            def test_k(self):
                pass

        class TestMethodOff:
            def test_a(self):
                pass
            test_a.__test__ = False

            def test_b(self):
                pass
    """)
    assert expected_test_functions(source, "t.py") == [
        "t.py::test_on",
        "t.py::TestBack::test_m",
        "t.py::TestBack::test_k",
        "t.py::TestMethodOff::test_b",
    ]
    assert expected_test_functions("__test__ = False\n\ndef test_x():\n    pass\n", "t.py") == []


def test_test_false_matches_pytest_collection(tmp_path):
    source = """\
        def test_off():
            pass
        test_off.__test__ = False

        def test_on():
            pass

        class TestOff:
            __test__ = False

            def test_m(self):
                pass

        class TestInherits(TestOff):
            def test_n(self):
                pass
    """
    expected, run = _run(tmp_path, source)
    assert expected == ["tests.py::test_on"]
    assert _not_run(expected, run) == []


def _collect_only(tmp_path: Path, source: str) -> list[str]:
    """The function node ids real pytest collects from *source*, without parametrize ids."""
    import subprocess
    import sys

    (tmp_path / "tests.py").write_text(_module(source))
    (tmp_path / "pytest.ini").write_text("[pytest]\npython_files = tests.py\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "-c", str(tmp_path / "pytest.ini"), "--rootdir", str(tmp_path), "tests.py"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False,
    )
    return list(dict.fromkeys(line.split("[")[0] for line in result.stdout.splitlines() if "::" in line))


def test_test_true_and_later_assignments_match_pytest_collection(tmp_path):
    source = """\
        def test_redefined():
            pass
        test_redefined.__test__ = False

        def test_redefined():
            pass

        def test_off_then_on():
            pass
        test_off_then_on.__test__ = False
        test_off_then_on.__test__ = True

        def check_nose():
            pass
        check_nose.__test__ = True

        def check_truthy():
            pass
        check_truthy.__test__ = 1

        class TestOff:
            __test__ = False

            def test_m(self):
                pass

        class TestSub(TestOff):
            def test_n(self):
                pass
        TestSub.__test__ = True

        class Helper:
            __test__ = True

            def test_h(self):
                pass

            def check_x(self):
                pass
            check_x.__test__ = True

        class Plain:
            def test_p(self):
                pass
        Plain.__test__ = True

        class Inherited(Helper):
            def test_i(self):
                pass

        class TestAfterOff:
            def test_q(self):
                pass
        TestAfterOff.__test__ = False
    """
    expected = expected_test_functions(_module(source), "tests.py")
    assert expected == [
        "tests.py::test_redefined",
        "tests.py::test_off_then_on",
        "tests.py::check_nose",
        "tests.py::TestSub::test_m",
        "tests.py::TestSub::test_n",
        "tests.py::Helper::test_h",
        "tests.py::Helper::check_x",
        "tests.py::Plain::test_p",
        "tests.py::Inherited::test_h",
        "tests.py::Inherited::check_x",
        "tests.py::Inherited::test_i",
    ]
    assert expected == _collect_only(tmp_path, source)


def test_a_skip_in_a_subdirectory_conftest_labels_its_functions_skipped(tmp_path):
    engine = _engine(tmp_path, {
        "test_top.py": "def test_top():\n    pass\n",
        "sub/conftest.py": "import pytest\n\npytest.skip('not here', allow_module_level=True)\n",
        "sub/test_inner.py": "def test_a():\n    pass\n\ndef test_b():\n    pass\n",
    })
    assert engine.not_run == [
        {"test_node": "sub/test_inner.py::test_a", "reason": "skipped"},
        {"test_node": "sub/test_inner.py::test_b", "reason": "skipped"},
    ]


@pytest.mark.parametrize("schema_version", [2, 3])
def test_a_regrade_source_keeps_the_record_completeness(schema_version):
    from silverquillm.karn.records import KarnRunRecord
    from silverquillm.karn.regrade import _suite_counts
    from silverquillm.results_repo import suite_keys

    scores = {
        key: {"tests_passed": 1, "tests_total": 3, "pass_rate": 1 / 3, "complete": False}
        for key in suite_keys(schema_version).values()
    }
    record = KarnRunRecord({"schema_version": schema_version}, scores)
    assert set(_suite_counts(record)) == {"target", "fdn", "engine"}
    for value in _suite_counts(record).values():
        assert value["complete"] is False
