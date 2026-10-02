"""Engine Regression records per-test node outcomes relative to the graded suite root."""

from __future__ import annotations

from pathlib import Path

import pytest

from silverquillm.evaluator import _eval_engine, _parse_report_jsonl

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
