"""Engine Regression records per-test node outcomes relative to the graded suite root."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from silverquillm import evaluator
from silverquillm.evaluator import (
    _eval_engine,
    _parse_report_jsonl,
    _run_pytest_with_pythonpath,
)

PASSING_SUITE = {
    "__init__.py": "",
    "test_a.py": """
import pytest


def test_pass():
    pass


def test_fail():
    assert False


def test_skip():
    pytest.skip("not today")


@pytest.mark.xfail(reason="known")
def test_xfail():
    assert False


@pytest.mark.parametrize("value", [1, 2], ids=["one", "two"])
def test_param(value):
    assert value == 1
""",
    "sub/__init__.py": "",
    "sub/test_b.py": """
import pytest


@pytest.fixture
def broken():
    raise RuntimeError("setup")


def test_y():
    pass


def test_setup_error(broken):
    pass
""",
}


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


def _benchmark(tmp_path: Path, suite: dict[str, str]) -> tuple[Path, Path]:
    workspace = tmp_path / "bench/workspace"
    _write(workspace / "engine/__init__.py", "")
    _write(workspace / "cards/__init__.py", "")
    _write(workspace / "test_utils.py", "")
    _write(workspace / "pytest.ini", "[pytest]\naddopts = --import-mode=importlib\n")
    audited = tmp_path / "bench/data/tests/audited/engine"
    for relative, source in suite.items():
        _write(audited / relative, source)
    return workspace, audited


def test_engine_nodes_follow_the_suite_relative_contract(tmp_path):
    workspace, audited = _benchmark(tmp_path, PASSING_SUITE)

    result = _eval_engine(workspace / "engine", audited, 120, support_dir=workspace)

    assert result.test_nodes == [
        {"test_node": "sub/test_b.py::test_y", "outcome": "pass"},
        {"test_node": "sub/test_b.py::test_setup_error", "outcome": "fail"},
        {"test_node": "test_a.py::test_pass", "outcome": "pass"},
        {"test_node": "test_a.py::test_fail", "outcome": "fail"},
        {"test_node": "test_a.py::test_param[one]", "outcome": "pass"},
        {"test_node": "test_a.py::test_param[two]", "outcome": "fail"},
    ]


def test_module_collection_error_is_a_failing_module_node(tmp_path):
    suite = {**PASSING_SUITE, "test_broken.py": "import does_not_exist\n"}
    workspace, audited = _benchmark(tmp_path, suite)

    result = _eval_engine(workspace / "engine", audited, 120, support_dir=workspace)

    # A collection error interrupts the session, so no test runs after it.
    assert result.test_nodes == [{"test_node": "test_broken.py", "outcome": "fail"}]


def test_engine_timeout_records_no_nodes(tmp_path):
    suite = {"__init__.py": "", "test_slow.py": "import time\n\n\ndef test_slow():\n    time.sleep(30)\n"}
    workspace, audited = _benchmark(tmp_path, suite)

    result = _eval_engine(workspace / "engine", audited, 3, support_dir=workspace)

    assert result.test_nodes == []
    assert result.errors == ["Timeout after 3s"]


@pytest.mark.parametrize(
    ("nodeid", "expected"),
    [
        ("engine_tests/test_zones.py::TestMove::test_moves", "test_zones.py::TestMove::test_moves"),
        ("engine_tests/zone_change/test_lki.py::test_y", "zone_change/test_lki.py::test_y"),
        ("engine_tests/test_casting.py::test_x[two]", "test_casting.py::test_x[two]"),
        ("engine_tests/test_combat.py", "test_combat.py"),
        ("engine_tests", "<collection-error>"),
        ("", "<collection-error>"),
        ("<collection-error>", "<collection-error>"),
        ("elsewhere/test_q.py::test_q", "elsewhere/test_q.py::test_q"),
    ],
)
def test_suite_relative_normalization(tmp_path, nodeid, expected):
    report = tmp_path / "report.jsonl"
    report.write_text(
        f'{{"nodeid": "{nodeid}", "outcome": "fail"}}\n'
        f'{{"nodeid": "{nodeid}", "outcome": "pass"}}\n'
    )
    assert _parse_report_jsonl(report, "engine_tests") == [
        {"test_node": expected, "outcome": "fail"}
    ]


FUTURE_CONFTEST = '''"""Authoritative fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def authoritative():
    return "authoritative"
'''

AUTHORITATIVE_FIXTURE = '''

import pytest


@pytest.fixture
def authoritative():
    return "authoritative"
'''

HOOKED_CONFTEST = '''from __future__ import annotations

from pathlib import Path

MARKERS = Path({markers!r})


def pytest_runtest_logreport(report):
    with MARKERS.open("a") as handle:
        handle.write(f"runtest {{report.when}} {{report.nodeid}}\\n")


def pytest_collectreport(report):
    if report.failed:
        with MARKERS.open("a") as handle:
            handle.write(f"collect {{report.nodeid}}\\n")
'''

FIXTURE_SUITE = {
    "__init__.py": "",
    "test_one.py": "def test_ok(authoritative):\n    assert authoritative == 'authoritative'\n\n\n"
    "def test_bad():\n    assert False\n",
}


def _support_snapshot(workspace: Path) -> dict[Path, bytes]:
    return {
        path: path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def test_authoritative_conftest_with_future_import_is_left_intact(tmp_path):
    workspace, audited = _benchmark(tmp_path, FIXTURE_SUITE)
    _write(workspace / "conftest.py", FUTURE_CONFTEST)
    before = _support_snapshot(tmp_path / "bench")

    result = _eval_engine(workspace / "engine", audited, 120, support_dir=workspace)

    assert (result.tests_passed, result.tests_failed, result.tests_total) == (1, 1, 2), result.errors
    assert result.test_nodes == [
        {"test_node": "test_one.py::test_ok", "outcome": "pass"},
        {"test_node": "test_one.py::test_bad", "outcome": "fail"},
    ]
    assert _support_snapshot(tmp_path / "bench") == before


def test_authoritative_report_hooks_run_beside_node_capture(tmp_path):
    markers = tmp_path / "markers.txt"
    workspace, audited = _benchmark(tmp_path, FIXTURE_SUITE)
    _write(
        workspace / "conftest.py",
        HOOKED_CONFTEST.format(markers=str(markers)) + AUTHORITATIVE_FIXTURE,
    )
    before = _support_snapshot(tmp_path / "bench")

    result = _eval_engine(workspace / "engine", audited, 120, support_dir=workspace)

    assert (result.tests_passed, result.tests_failed, result.tests_total) == (1, 1, 2), result.errors
    assert result.test_nodes == [
        {"test_node": "test_one.py::test_ok", "outcome": "pass"},
        {"test_node": "test_one.py::test_bad", "outcome": "fail"},
    ]
    assert "runtest call engine_tests/test_one.py::test_ok" in markers.read_text()
    assert "runtest call engine_tests/test_one.py::test_bad" in markers.read_text()
    assert _support_snapshot(tmp_path / "bench") == before

    markers.unlink()
    _write(audited / "test_broken.py", "import does_not_exist\n")
    result = _eval_engine(workspace / "engine", audited, 120, support_dir=workspace)
    assert result.test_nodes == [{"test_node": "test_broken.py", "outcome": "fail"}]
    assert "collect engine_tests/test_broken.py" in markers.read_text()


def test_card_conftest_with_future_import_and_hooks_keeps_card_nodes(tmp_path):
    markers = tmp_path / "markers.txt"
    suite = tmp_path / "card"
    _write(suite / "conftest.py", HOOKED_CONFTEST.format(markers=str(markers)))
    _write(suite / "tests.py", "def test_a():\n    pass\n\n\ndef test_b():\n    assert False\n")
    before = _support_snapshot(suite)

    passed, failed, total, _errors, nodes = _run_pytest_with_pythonpath(
        suite / "tests.py", [str(suite)], 60, capture_test_nodes=True
    )

    assert (passed, failed, total) == (1, 1, 2)
    assert nodes == [
        {"test_node": "tests.py::test_a", "outcome": "pass"},
        {"test_node": "tests.py::test_b", "outcome": "fail"},
    ]
    assert "runtest call" in markers.read_text()
    assert _support_snapshot(suite) == before


@pytest.fixture
def report_tmp(tmp_path, monkeypatch):
    directory = tmp_path / "system-tmp"
    directory.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(directory))
    return directory


def _leftovers(directory: Path) -> list[Path]:
    return list(directory.iterdir())


def test_reporter_is_removed_after_success_and_does_not_leak(tmp_path, report_tmp):
    workspace, audited = _benchmark(tmp_path / "first", PASSING_SUITE)
    first = _eval_engine(workspace / "engine", audited, 120, support_dir=workspace)
    assert first.test_nodes and _leftovers(report_tmp) == []

    workspace, audited = _benchmark(tmp_path / "second", FIXTURE_SUITE)
    _write(workspace / "conftest.py", FUTURE_CONFTEST)
    second = _eval_engine(workspace / "engine", audited, 120, support_dir=workspace)
    assert [node["test_node"] for node in second.test_nodes] == [
        "test_one.py::test_ok", "test_one.py::test_bad",
    ]
    assert _leftovers(report_tmp) == []


def test_reporter_is_removed_after_timeout(tmp_path, report_tmp):
    suite = {"__init__.py": "", "test_slow.py": "import time\n\n\ndef test_slow():\n    time.sleep(30)\n"}
    workspace, audited = _benchmark(tmp_path, suite)
    result = _eval_engine(workspace / "engine", audited, 3, support_dir=workspace)
    assert result.errors == ["Timeout after 3s"]
    assert _leftovers(report_tmp) == []


def test_reporter_is_removed_when_the_subprocess_fails(tmp_path, report_tmp, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise OSError("cannot start pytest")

    monkeypatch.setattr(evaluator.subprocess, "run", refuse)
    _write(tmp_path / "tests.py", "def test_a():\n    pass\n")
    with pytest.raises(OSError):
        _run_pytest_with_pythonpath(tmp_path / "tests.py", [], 10, capture_test_nodes=True)
    assert _leftovers(report_tmp) == []
