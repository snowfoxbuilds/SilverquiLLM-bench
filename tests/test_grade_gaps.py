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
    _python_files,
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
        failure_message_cost(m) for card in cards.values() for m in card.failure_messages.values()
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
    assert sum(map(failure_message_cost, card.failure_messages.values())) <= FAILURE_MESSAGE_BUDGET


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
