"""Additional tests for TODO item 2 gaps not covered by test_test_nodes.py.

Covers:
- Skipped/xfail tests are NOT enumerated in test_nodes (pass/fail-only contract).
- _parse_report_jsonl ignores rows with unknown/non-pass-fail outcome values.
- _normalize_nodeid unit behavior: path with '/' but no '::' separator.
- Guaranteed cleanup: no leftover conftest.py or report dir after capture.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from silverquillm.evaluator import (
    _normalize_nodeid,
    _parse_report_jsonl,
    _run_pytest_with_pythonpath,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_test_file(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "tests.py"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Test data: files with skipped / xfail tests
# ---------------------------------------------------------------------------

WITH_SKIPPED = textwrap.dedent("""\
    import pytest

    def test_pass():
        assert True

    @pytest.mark.skip(reason="intentionally skipped")
    def test_skipped():
        assert False
""")

WITH_XFAIL = textwrap.dedent("""\
    import pytest

    def test_pass():
        assert True

    @pytest.mark.xfail
    def test_expected_fail():
        assert False
""")

WITH_XPASS = textwrap.dedent("""\
    import pytest

    def test_pass():
        assert True

    @pytest.mark.xfail
    def test_unexpectedly_passes():
        assert True
""")


# ---------------------------------------------------------------------------
# 1. Skipped/xfail tests are NOT enumerated in test_nodes
# ---------------------------------------------------------------------------


class TestSkippedXfailNotEnumerated:
    """The pass/fail-only contract: skipped and xfail tests must NOT appear
    in test_nodes, and must not be miscounted as failures.
    """

    def test_skipped_test_absent_from_test_nodes(self, tmp_path):
        """A @pytest.mark.skip test should not appear in test_nodes at all."""
        test_file = _write_test_file(tmp_path, WITH_SKIPPED)
        _, _, _, _, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        node_ids = [n["test_node"] for n in test_nodes]
        assert not any("test_skipped" in nid for nid in node_ids), (
            f"Skipped test should not appear in test_nodes, got: {node_ids}"
        )

    def test_skipped_test_does_not_inflate_fail_count(self, tmp_path):
        """A skipped test must not be counted as a failure."""
        test_file = _write_test_file(tmp_path, WITH_SKIPPED)
        passed, failed, total, errors, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        fail_nodes = [n for n in test_nodes if n["outcome"] == "fail"]
        assert len(fail_nodes) == 0, (
            f"Skipped test should not produce fail nodes, got: {fail_nodes}"
        )

    def test_xfail_test_absent_from_test_nodes(self, tmp_path):
        """An xfail test (that actually fails as expected) should not appear
        in test_nodes.
        """
        test_file = _write_test_file(tmp_path, WITH_XFAIL)
        _, _, _, _, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        node_ids = [n["test_node"] for n in test_nodes]
        assert not any("test_expected_fail" in nid for nid in node_ids), (
            f"xfail test should not appear in test_nodes, got: {node_ids}"
        )

    def test_xfail_test_does_not_inflate_fail_count(self, tmp_path):
        """An xfail test must not be counted as a failure."""
        test_file = _write_test_file(tmp_path, WITH_XFAIL)
        passed, failed, total, errors, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        fail_nodes = [n for n in test_nodes if n["outcome"] == "fail"]
        assert len(fail_nodes) == 0, (
            f"xfail test should not produce fail nodes, got: {fail_nodes}"
        )

    def test_only_passing_test_in_test_nodes_when_skip_present(self, tmp_path):
        """When a file has one passing test and one skipped test, only the
        passing test should appear in test_nodes.
        """
        test_file = _write_test_file(tmp_path, WITH_SKIPPED)
        _, _, _, _, test_nodes = _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )
        assert len(test_nodes) == 1
        assert test_nodes[0]["outcome"] == "pass"
        assert "test_pass" in test_nodes[0]["test_node"]


# ---------------------------------------------------------------------------
# 2. _parse_report_jsonl ignores unknown/non-pass-fail outcome values
# ---------------------------------------------------------------------------


class TestParseReportJsonlUnknownOutcomes:
    """_parse_report_jsonl must silently ignore rows with outcome values
    that are neither 'pass' nor 'fail' — they must not be coerced to 'fail'.
    """

    def test_skipped_outcome_ignored(self, tmp_path):
        """A row with outcome='skipped' must be ignored entirely."""
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "tests.py::test_a", "when": "call", "outcome": "pass"}),
            json.dumps({"nodeid": "tests.py::test_b", "when": "call", "outcome": "skipped"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert len(nodes) == 1
        assert nodes[0]["test_node"] == "tests.py::test_a"
        assert nodes[0]["outcome"] == "pass"

    def test_xfail_outcome_ignored(self, tmp_path):
        """A row with outcome='xfail' must be ignored entirely."""
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "tests.py::test_x", "when": "call", "outcome": "xfail"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert nodes == []

    def test_xpass_outcome_ignored(self, tmp_path):
        """A row with outcome='xpass' must be ignored entirely."""
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "tests.py::test_y", "when": "call", "outcome": "xpass"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert nodes == []

    def test_missing_outcome_field_ignored(self, tmp_path):
        """A row with no 'outcome' key must be ignored."""
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "tests.py::test_z", "when": "call"}),
            json.dumps({"nodeid": "tests.py::test_ok", "when": "call", "outcome": "pass"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert len(nodes) == 1
        assert nodes[0]["outcome"] == "pass"

    def test_malformed_json_line_ignored(self, tmp_path):
        """A malformed (non-JSON) line must be silently skipped."""
        report_path = tmp_path / "report.jsonl"
        lines = [
            "this is not valid json {{{",
            json.dumps({"nodeid": "tests.py::test_good", "when": "call", "outcome": "pass"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert len(nodes) == 1
        assert nodes[0]["outcome"] == "pass"

    def test_unknown_string_outcome_ignored(self, tmp_path):
        """An arbitrary unknown outcome string must be ignored."""
        report_path = tmp_path / "report.jsonl"
        lines = [
            json.dumps({"nodeid": "tests.py::test_a", "when": "call", "outcome": "error"}),
            json.dumps({"nodeid": "tests.py::test_b", "when": "call", "outcome": "unknown"}),
            json.dumps({"nodeid": "tests.py::test_c", "when": "call", "outcome": "fail"}),
        ]
        report_path.write_text("\n".join(lines) + "\n")
        nodes = _parse_report_jsonl(report_path)
        assert len(nodes) == 1
        assert nodes[0]["test_node"] == "tests.py::test_c"
        assert nodes[0]["outcome"] == "fail"


# ---------------------------------------------------------------------------
# 3. _normalize_nodeid: path-with-slash but no '::' separator
# ---------------------------------------------------------------------------


class TestNormalizeNodeidEdgeCases:
    """Unit tests for the _normalize_nodeid path-only (no '::') branch."""

    def test_path_without_separator_returns_basename(self):
        """A bare filesystem path (no '::') should return just the filename."""
        result = _normalize_nodeid("/tmp/some_dir/tests.py")
        assert result == "tests.py"

    def test_path_without_separator_single_component(self):
        """A multi-component path with no '::' returns the last component."""
        result = _normalize_nodeid("/a/b/c/d/myfile.py")
        assert result == "myfile.py"

    def test_already_normalized_with_separator(self):
        """An already-normalized 'filename::test' is returned unchanged."""
        result = _normalize_nodeid("tests.py::test_foo")
        assert result == "tests.py::test_foo"

    def test_deep_nested_path_with_separator(self):
        """A deeply nested path::test_name is stripped to 'filename::test_name'."""
        result = _normalize_nodeid("/very/deeply/nested/dir/tests.py::test_bar")
        assert result == "tests.py::test_bar"


# ---------------------------------------------------------------------------
# 4. Cleanup: no leftover conftest or report dir after capture
# ---------------------------------------------------------------------------


class TestCleanupAfterCapture:
    """Verify that the temp conftest.py and report directory are removed
    after _run_pytest_with_pythonpath with capture_test_nodes=True completes.
    """

    def test_no_leftover_conftest_after_success(self, tmp_path):
        """No conftest.py should remain in the test dir after a successful run."""
        test_content = textwrap.dedent("""\
            def test_ok():
                assert True
        """)
        test_file = _write_test_file(tmp_path, test_content)
        conftest_path = tmp_path / "conftest.py"

        # No conftest before the call
        assert not conftest_path.exists()

        _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )

        assert not conftest_path.exists(), (
            "conftest.py injected for capture should be removed after eval"
        )

    def test_no_leftover_conftest_after_failure(self, tmp_path):
        """No conftest.py should remain even when the tested file has failures."""
        test_content = textwrap.dedent("""\
            def test_fail():
                assert False
        """)
        test_file = _write_test_file(tmp_path, test_content)
        conftest_path = tmp_path / "conftest.py"

        assert not conftest_path.exists()

        _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )

        assert not conftest_path.exists(), (
            "conftest.py should be cleaned up even when tests fail"
        )

    def test_existing_conftest_restored_after_capture(self, tmp_path):
        """If a conftest.py already exists before capture, it must be
        restored to its original content after the run.
        """
        test_content = textwrap.dedent("""\
            def test_ok():
                assert True
        """)
        test_file = _write_test_file(tmp_path, test_content)
        conftest_path = tmp_path / "conftest.py"
        original_conftest = "# original conftest\nimport pytest\n"
        conftest_path.write_text(original_conftest)

        _run_pytest_with_pythonpath(
            test_file, [str(tmp_path)],
            capture_test_nodes=True,
        )

        assert conftest_path.exists(), "Original conftest.py should still exist"
        assert conftest_path.read_text() == original_conftest, (
            "conftest.py should be restored to its original content"
        )
