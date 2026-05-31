"""Tests for TODO item 2: Record per-test-node pass/fail outcomes in result.json.

Tests verify:
- _run_pytest_with_pythonpath with capture_test_nodes=True returns per-node
  pass/fail data for a synthetic card with one passing and one failing test.
- Node IDs are normalized to tests.py::test_x form (no temp-dir path prefix).
- tests_passed/tests_failed/tests_total remain consistent with the per-node
  outcomes (back-compat preserved).
- Collection/setup errors produce at least one test_nodes row with outcome "fail"
  and do not crash the eval.
- test_nodes survives the asdict(cr) -> JSON round-trip into result.json.
- Non-SOS callers (4-tuple return) are unaffected by the additive change.
"""

from __future__ import annotations

import json
import shutil
import textwrap
from dataclasses import asdict, fields as dc_fields
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.evaluator import (
    CardResult,
    FullEvalResult,
    _normalize_nodeid,
    _parse_report_jsonl,
    _run_pytest_with_pythonpath,
    evaluate,
    run_tests,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_test_file(tmp_path: Path, content: str) -> Path:
    """Write a tests.py file in tmp_path and return its path."""
    p = tmp_path / "tests.py"
    p.write_text(content)
    return p


def _setup_run_dir(tmp_path: Path, completed_cards: list[str]) -> Path:
    """Build a minimal run_dir with status.json and card_impl.py stubs."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    status = {cn: "completed" for cn in completed_cards}
    (run_dir / "status.json").write_text(json.dumps(status))
    for cn in completed_cards:
        card_dir = run_dir / "cards" / cn
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "card_impl.py").write_text(f"# impl for {cn}\n")
    return run_dir


# ---------------------------------------------------------------------------
# Test data: synthetic tests.py with one pass and one fail
# ---------------------------------------------------------------------------

ONE_PASS_ONE_FAIL = textwrap.dedent("""\
    def test_passing():
        assert 1 + 1 == 2

    def test_failing():
        assert 1 + 1 == 3
""")

ALL_PASS = textwrap.dedent("""\
    def test_alpha():
        assert True

    def test_beta():
        assert True
""")

COLLECTION_ERROR = textwrap.dedent("""\
    raise RuntimeError("import-time explosion")

    def test_never_runs():
        assert True
""")

SETUP_ERROR = textwrap.dedent("""\
    import pytest

    @pytest.fixture
    def broken_fixture():
        raise RuntimeError("fixture setup error")

    def test_with_broken_fixture(broken_fixture):
        assert True
""")


# ---------------------------------------------------------------------------
# 1. Per-node outcomes captured via real pytest
# ---------------------------------------------------------------------------


class TestPerNodeCapture:
    """Verify _run_pytest_with_pythonpath with capture_test_nodes=True
    returns per-node pass/fail data from a real pytest invocation.
    """

    def test_one_pass_one_fail_returns_both_nodes(self, tmp_path):
        """A tests.py with one passing and one failing test should produce
        test_nodes with exactly two entries, one pass and one fail.
        """
        test_file = _write_test_file(tmp_path, ONE_PASS_ONE_FAIL)
        result = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        assert len(result) == 5, "capture_test_nodes=True should return a 5-tuple"
        passed, failed, total, errors, test_nodes = result

        assert len(test_nodes) == 2
        outcomes = {n["test_node"]: n["outcome"] for n in test_nodes}
        assert outcomes["tests.py::test_passing"] == "pass"
        assert outcomes["tests.py::test_failing"] == "fail"

    def test_all_pass_nodes(self, tmp_path):
        """When all tests pass, every node should have outcome 'pass'."""
        test_file = _write_test_file(tmp_path, ALL_PASS)
        _, _, _, _, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        assert len(test_nodes) == 2
        for node in test_nodes:
            assert node["outcome"] == "pass"

    def test_nodeids_are_normalized_no_path_prefix(self, tmp_path):
        """Node IDs should be in tests.py::test_x form with no tmp dir prefix."""
        test_file = _write_test_file(tmp_path, ONE_PASS_ONE_FAIL)
        _, _, _, _, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        for node in test_nodes:
            nodeid = node["test_node"]
            # Should not contain any temp-directory path components
            assert "/" not in nodeid, f"nodeid should not contain path separator: {nodeid}"
            # Should start with tests.py::
            assert nodeid.startswith("tests.py::"), f"nodeid should start with tests.py:: : {nodeid}"

    def test_each_node_has_required_keys(self, tmp_path):
        """Every item in test_nodes must have 'test_node' and 'outcome' keys."""
        test_file = _write_test_file(tmp_path, ONE_PASS_ONE_FAIL)
        _, _, _, _, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        for node in test_nodes:
            assert "test_node" in node
            assert "outcome" in node
            assert node["outcome"] in ("pass", "fail")


# ---------------------------------------------------------------------------
# 2. Back-compat: counts match node outcomes
# ---------------------------------------------------------------------------


class TestCountsMatchNodes:
    """Verify tests_passed/tests_failed/tests_total are consistent with
    the per-node pass/fail outcomes.
    """

    def test_counts_consistent_with_nodes_mixed(self, tmp_path):
        """For a mixed pass/fail test file, the counts from the parser should
        agree with the node-level outcomes.
        """
        test_file = _write_test_file(tmp_path, ONE_PASS_ONE_FAIL)
        passed, failed, total, errors, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        node_pass = sum(1 for n in test_nodes if n["outcome"] == "pass")
        node_fail = sum(1 for n in test_nodes if n["outcome"] == "fail")

        assert passed == node_pass
        assert failed == node_fail
        assert total == passed + failed

    def test_counts_consistent_with_nodes_all_pass(self, tmp_path):
        """When all tests pass, counts should match all-pass node outcomes."""
        test_file = _write_test_file(tmp_path, ALL_PASS)
        passed, failed, total, errors, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        node_pass = sum(1 for n in test_nodes if n["outcome"] == "pass")
        node_fail = sum(1 for n in test_nodes if n["outcome"] == "fail")

        assert passed == node_pass
        assert failed == 0
        assert node_fail == 0
        assert total == passed


# ---------------------------------------------------------------------------
# 3. Collection/setup errors produce fail nodes
# ---------------------------------------------------------------------------


class TestCollectionAndSetupErrors:
    """Verify that collection or setup errors produce at least one
    test_nodes entry with outcome 'fail' and do not crash the eval.
    """

    def test_collection_error_produces_fail_node(self, tmp_path):
        """A tests.py that raises at import/collection time should produce
        at least one test_nodes row with outcome 'fail'.
        """
        test_file = _write_test_file(tmp_path, COLLECTION_ERROR)
        result = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        assert len(result) == 5
        passed, failed, total, errors, test_nodes = result

        assert len(test_nodes) >= 1, "collection error should produce at least one node"
        fail_nodes = [n for n in test_nodes if n["outcome"] == "fail"]
        assert len(fail_nodes) >= 1, "at least one node should have outcome 'fail'"

    def test_collection_error_does_not_crash(self, tmp_path):
        """_run_pytest_with_pythonpath should not raise on collection errors."""
        test_file = _write_test_file(tmp_path, COLLECTION_ERROR)
        # This should not raise
        result = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        assert isinstance(result, tuple)

    def test_setup_error_produces_fail_node(self, tmp_path):
        """A test with a fixture that errors in setup should produce
        a test_nodes row with outcome 'fail'.
        """
        test_file = _write_test_file(tmp_path, SETUP_ERROR)
        passed, failed, total, errors, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        fail_nodes = [n for n in test_nodes if n["outcome"] == "fail"]
        assert len(fail_nodes) >= 1, "setup error should produce at least one fail node"
        # The failing node should reference the test function
        fail_nodeids = [n["test_node"] for n in fail_nodes]
        assert any("test_with_broken_fixture" in nid for nid in fail_nodeids), (
            f"Expected a fail node for test_with_broken_fixture, got: {fail_nodeids}"
        )


# ---------------------------------------------------------------------------
# 4. test_nodes persists through asdict -> JSON round-trip
# ---------------------------------------------------------------------------


class TestTestNodesPersistence:
    """Verify test_nodes survives asdict(cr) -> JSON write -> JSON load."""

    def test_asdict_includes_test_nodes(self):
        """asdict(CardResult) should include the test_nodes list."""
        cr = CardResult(
            collector_number="42",
            tests_passed=1,
            tests_failed=1,
            tests_total=2,
            test_nodes=[
                {"test_node": "tests.py::test_a", "outcome": "pass"},
                {"test_node": "tests.py::test_b", "outcome": "fail"},
            ],
        )
        d = asdict(cr)
        assert "test_nodes" in d
        assert len(d["test_nodes"]) == 2

    def test_json_roundtrip_preserves_test_nodes(self):
        """test_nodes should survive JSON serialization and deserialization."""
        nodes = [
            {"test_node": "tests.py::test_passing", "outcome": "pass"},
            {"test_node": "tests.py::test_failing", "outcome": "fail"},
        ]
        cr = CardResult(
            collector_number="99",
            tests_passed=1,
            tests_failed=1,
            tests_total=2,
            test_nodes=nodes,
        )
        json_str = json.dumps(asdict(cr))
        loaded = json.loads(json_str)
        assert loaded["test_nodes"] == nodes

    def test_result_json_on_disk_contains_test_nodes(self, tmp_path):
        """When _eval_sos_cards writes result.json, test_nodes must appear
        in the persisted file (not just on the in-memory CardResult).
        """
        # Set up the test content with one passing and one failing test
        test_content = ONE_PASS_ONE_FAIL
        cn = "42"

        run_dir = _setup_run_dir(tmp_path, [cn])

        # Create audited SOS test directory at the path _eval_sos_cards expects
        sos_dir = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / cn
        sos_dir.mkdir(parents=True, exist_ok=True)
        (sos_dir / "tests.py").write_text(test_content)

        # Create impl that doesn't break (tests don't import anything)
        card_dir = run_dir / "cards" / cn
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "card_impl.py").write_text("# empty impl\n")

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            result = evaluate(run_dir, cards_dir, engine_dir, timeout=30)

        # Check the on-disk result.json
        result_json_path = run_dir / "cards" / cn / "result.json"
        assert result_json_path.exists(), "result.json should be written"
        data = json.loads(result_json_path.read_text())
        assert "test_nodes" in data, "test_nodes should be in result.json"
        assert len(data["test_nodes"]) == 2, "Should have 2 test_node entries"

        # Verify the actual content
        node_map = {n["test_node"]: n["outcome"] for n in data["test_nodes"]}
        assert node_map.get("tests.py::test_passing") == "pass"
        assert node_map.get("tests.py::test_failing") == "fail"

    def test_result_json_on_disk_preserves_counts_alongside_nodes(self, tmp_path):
        """result.json should contain both test_nodes and the existing
        counts (tests_passed, tests_failed, tests_total).
        """
        test_content = ONE_PASS_ONE_FAIL
        cn = "50"

        run_dir = _setup_run_dir(tmp_path, [cn])

        sos_dir = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos" / cn
        sos_dir.mkdir(parents=True, exist_ok=True)
        (sos_dir / "tests.py").write_text(test_content)

        card_dir = run_dir / "cards" / cn
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "card_impl.py").write_text("# empty impl\n")

        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(exist_ok=True)
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(exist_ok=True)

        with patch("silverquillm.evaluator._REPO_ROOT", tmp_path):
            evaluate(run_dir, cards_dir, engine_dir, timeout=30)

        data = json.loads((run_dir / "cards" / cn / "result.json").read_text())
        assert data["tests_passed"] == 1
        assert data["tests_failed"] == 1
        assert data["tests_total"] == 2
        assert len(data["test_nodes"]) == 2


# ---------------------------------------------------------------------------
# 5. Back-compat: non-SOS callers unaffected (4-tuple return)
# ---------------------------------------------------------------------------


class TestBackCompat:
    """Verify the additive change did not break existing 4-tuple callers."""

    def test_run_tests_still_returns_four_tuple(self, tmp_path):
        """run_tests() (legacy API) should still return a 4-tuple."""
        impl_file = tmp_path / "impl.py"
        impl_file.write_text("def add(a, b): return a + b\n")
        test_file = tmp_path / "tests.py"
        test_file.write_text(
            "from card_impl import add\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n"
        )
        result = run_tests(impl_file, test_file)
        assert isinstance(result, tuple)
        assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple"

    def test_capture_false_returns_four_tuple(self, tmp_path):
        """_run_pytest_with_pythonpath with capture_test_nodes=False (default)
        should return a plain 4-tuple.
        """
        test_file = _write_test_file(tmp_path, ALL_PASS)
        result = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=False,
        )
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_capture_true_returns_five_tuple(self, tmp_path):
        """_run_pytest_with_pythonpath with capture_test_nodes=True
        should return a 5-tuple.
        """
        test_file = _write_test_file(tmp_path, ALL_PASS)
        result = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        assert isinstance(result, tuple)
        assert len(result) == 5

    def test_cardresult_test_nodes_default_is_empty_list(self):
        """CardResult().test_nodes should default to [] so existing code
        that doesn't populate it is unaffected.
        """
        cr = CardResult(collector_number="1")
        assert cr.test_nodes == []
        assert isinstance(cr.test_nodes, list)

    def test_cardresult_test_nodes_field_exists(self):
        """CardResult dataclass should have a test_nodes field."""
        field_names = {f.name for f in dc_fields(CardResult)}
        assert "test_nodes" in field_names


# ---------------------------------------------------------------------------
# 6. _normalize_nodeid unit tests
# ---------------------------------------------------------------------------


class TestNormalizeNodeid:
    """Verify node ID normalization strips directory prefixes."""

    def test_strips_temp_dir_prefix(self):
        assert _normalize_nodeid("/tmp/eval_sos_abc123/tests.py::test_foo") == "tests.py::test_foo"

    def test_already_normalized(self):
        assert _normalize_nodeid("tests.py::test_foo") == "tests.py::test_foo"

    def test_nested_path(self):
        assert _normalize_nodeid("/a/b/c/d/tests.py::test_bar") == "tests.py::test_bar"

    def test_no_separator(self):
        assert _normalize_nodeid("tests.py::test_x") == "tests.py::test_x"

    def test_collection_error_no_separator(self):
        result = _normalize_nodeid("<collection-error>")
        assert result == "<collection-error>"


# ---------------------------------------------------------------------------
# 7. _parse_report_jsonl unit tests
# ---------------------------------------------------------------------------


class TestParseReportJsonl:
    """Verify JSONL report parsing, deduplication, and normalization."""

    def test_parses_pass_and_fail(self, tmp_path):
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "tests.py::test_a", "when": "call", "outcome": "pass"}),
            json.dumps({"nodeid": "tests.py::test_b", "when": "call", "outcome": "fail"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert len(nodes) == 2
        node_map = {n["test_node"]: n["outcome"] for n in nodes}
        assert node_map["tests.py::test_a"] == "pass"
        assert node_map["tests.py::test_b"] == "fail"

    def test_deduplicates_by_nodeid(self, tmp_path):
        """First occurrence of a nodeid should win when there are duplicates."""
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "tests.py::test_a", "when": "setup", "outcome": "fail"}),
            json.dumps({"nodeid": "tests.py::test_a", "when": "call", "outcome": "pass"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert len(nodes) == 1
        assert nodes[0]["outcome"] == "fail"

    def test_normalizes_paths(self, tmp_path):
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "/tmp/foo/tests.py::test_x", "when": "call", "outcome": "pass"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert nodes[0]["test_node"] == "tests.py::test_x"

    def test_collection_error_gets_synthetic_nodeid(self, tmp_path):
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "<collection-error>", "when": "collect", "outcome": "fail"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert len(nodes) == 1
        assert nodes[0]["test_node"] == "tests.py::<collection-error>"
        assert nodes[0]["outcome"] == "fail"

    def test_empty_report(self, tmp_path):
        report_path = tmp_path / "report.jsonl"
        report_path.write_text("")
        nodes = _parse_report_jsonl(report_path)
        assert nodes == []

    def test_nonexistent_report(self, tmp_path):
        report_path = tmp_path / "does_not_exist.jsonl"
        nodes = _parse_report_jsonl(report_path)
        assert nodes == []
