"""Tests for TODO item 14: Simplified postmortem schema.

Validates the new event types (file_written, eval_result, regression_check)
and the removal of round/phase from raw log events.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.agent_session import (
    _append_file_written,
    _append_eval_result,
    _append_regression_check,
    _append_postmortem,
    append_raw_log,
)


# ---------------------------------------------------------------------------
# file_written event
# ---------------------------------------------------------------------------

class TestFileWrittenEvent:
    """Tests for the _append_file_written helper."""

    def test_creates_file_written_event(self, tmp_path):
        """file_written event must contain event, path, and size_bytes."""
        pm = tmp_path / "postmortem.jsonl"
        _append_file_written(pm, "cards/Bear/card.py", 1234)
        entry = json.loads(pm.read_text().strip())
        assert entry["event"] == "file_written"
        assert entry["path"] == "cards/Bear/card.py"
        assert entry["size_bytes"] == 1234

    def test_file_written_has_exactly_expected_keys(self, tmp_path):
        """file_written events must have only event, path, size_bytes."""
        pm = tmp_path / "postmortem.jsonl"
        _append_file_written(pm, "foo.py", 42)
        entry = json.loads(pm.read_text().strip())
        assert set(entry.keys()) == {"event", "path", "size_bytes"}

    def test_file_written_no_round_or_phase(self, tmp_path):
        """file_written events must not contain round or phase keys."""
        pm = tmp_path / "postmortem.jsonl"
        _append_file_written(pm, "foo.py", 100)
        entry = json.loads(pm.read_text().strip())
        assert "round" not in entry
        assert "phase" not in entry

    def test_file_written_size_bytes_is_int(self, tmp_path):
        """size_bytes must be an integer."""
        pm = tmp_path / "postmortem.jsonl"
        _append_file_written(pm, "foo.py", 0)
        entry = json.loads(pm.read_text().strip())
        assert isinstance(entry["size_bytes"], int)

    def test_file_written_zero_size(self, tmp_path):
        """Empty files should have size_bytes=0."""
        pm = tmp_path / "postmortem.jsonl"
        _append_file_written(pm, "empty.py", 0)
        entry = json.loads(pm.read_text().strip())
        assert entry["size_bytes"] == 0

    def test_file_written_creates_parent_dirs(self, tmp_path):
        """_append_file_written should create parent directories."""
        pm = tmp_path / "deep" / "nested" / "postmortem.jsonl"
        _append_file_written(pm, "foo.py", 10)
        assert pm.exists()

    def test_file_written_appends_multiple(self, tmp_path):
        """Multiple file_written events should be appended as separate lines."""
        pm = tmp_path / "postmortem.jsonl"
        _append_file_written(pm, "a.py", 100)
        _append_file_written(pm, "b.py", 200)
        _append_file_written(pm, "c.py", 300)
        lines = pm.read_text().strip().splitlines()
        assert len(lines) == 3
        paths = [json.loads(l)["path"] for l in lines]
        assert paths == ["a.py", "b.py", "c.py"]


# ---------------------------------------------------------------------------
# No file_diff events
# ---------------------------------------------------------------------------

class TestNoFileDiffEvent:
    """Verify that file_diff is replaced by file_written."""

    def test_file_written_event_type_not_file_diff(self, tmp_path):
        """The new event type must be 'file_written', not 'file_diff'."""
        pm = tmp_path / "postmortem.jsonl"
        _append_file_written(pm, "card.py", 500)
        entry = json.loads(pm.read_text().strip())
        assert entry["event"] != "file_diff"
        assert entry["event"] == "file_written"


# ---------------------------------------------------------------------------
# eval_result event
# ---------------------------------------------------------------------------

class TestEvalResultEvent:
    """Tests for the _append_eval_result helper."""

    def test_creates_eval_result_event(self, tmp_path):
        """eval_result event must contain event, eval_type, passed, failed."""
        pm = tmp_path / "postmortem.jsonl"
        _append_eval_result(pm, "self", passed=5, failed=2)
        entry = json.loads(pm.read_text().strip())
        assert entry["event"] == "eval_result"
        assert entry["eval_type"] == "self"
        assert entry["passed"] == 5
        assert entry["failed"] == 2

    def test_eval_result_has_exactly_expected_keys(self, tmp_path):
        """eval_result events must have exactly event, eval_type, passed, failed."""
        pm = tmp_path / "postmortem.jsonl"
        _append_eval_result(pm, "audited", passed=3, failed=0)
        entry = json.loads(pm.read_text().strip())
        assert set(entry.keys()) == {"event", "eval_type", "passed", "failed"}

    def test_eval_result_no_round_or_phase(self, tmp_path):
        """eval_result events must not contain round or phase keys."""
        pm = tmp_path / "postmortem.jsonl"
        _append_eval_result(pm, "self", passed=1, failed=1)
        entry = json.loads(pm.read_text().strip())
        assert "round" not in entry
        assert "phase" not in entry

    def test_eval_result_self_type(self, tmp_path):
        """eval_type can be 'self'."""
        pm = tmp_path / "postmortem.jsonl"
        _append_eval_result(pm, "self", passed=10, failed=0)
        entry = json.loads(pm.read_text().strip())
        assert entry["eval_type"] == "self"

    def test_eval_result_audited_type(self, tmp_path):
        """eval_type can be 'audited'."""
        pm = tmp_path / "postmortem.jsonl"
        _append_eval_result(pm, "audited", passed=8, failed=2)
        entry = json.loads(pm.read_text().strip())
        assert entry["eval_type"] == "audited"

    def test_eval_result_passed_failed_are_ints(self, tmp_path):
        """passed and failed must be integers."""
        pm = tmp_path / "postmortem.jsonl"
        _append_eval_result(pm, "self", passed=0, failed=0)
        entry = json.loads(pm.read_text().strip())
        assert isinstance(entry["passed"], int)
        assert isinstance(entry["failed"], int)

    def test_eval_result_all_passing(self, tmp_path):
        """Should handle case where all tests pass (failed=0)."""
        pm = tmp_path / "postmortem.jsonl"
        _append_eval_result(pm, "self", passed=15, failed=0)
        entry = json.loads(pm.read_text().strip())
        assert entry["passed"] == 15
        assert entry["failed"] == 0

    def test_eval_result_all_failing(self, tmp_path):
        """Should handle case where all tests fail (passed=0)."""
        pm = tmp_path / "postmortem.jsonl"
        _append_eval_result(pm, "audited", passed=0, failed=7)
        entry = json.loads(pm.read_text().strip())
        assert entry["passed"] == 0
        assert entry["failed"] == 7


# ---------------------------------------------------------------------------
# regression_check event
# ---------------------------------------------------------------------------

class TestRegressionCheckEvent:
    """Tests for the _append_regression_check helper."""

    def test_creates_regression_check_event(self, tmp_path):
        """regression_check event must contain 'event' key."""
        pm = tmp_path / "postmortem.jsonl"
        _append_regression_check(pm)
        entry = json.loads(pm.read_text().strip())
        assert entry["event"] == "regression_check"

    def test_regression_check_no_round_or_phase(self, tmp_path):
        """regression_check events must not contain round or phase keys."""
        pm = tmp_path / "postmortem.jsonl"
        _append_regression_check(pm)
        entry = json.loads(pm.read_text().strip())
        assert "round" not in entry
        assert "phase" not in entry

    def test_regression_check_accepts_kwargs(self, tmp_path):
        """regression_check should accept extra keyword arguments."""
        pm = tmp_path / "postmortem.jsonl"
        _append_regression_check(pm, status="pending", detail="future use")
        entry = json.loads(pm.read_text().strip())
        assert entry["event"] == "regression_check"
        assert entry["status"] == "pending"
        assert entry["detail"] == "future use"

    def test_regression_check_minimal_event(self, tmp_path):
        """With no kwargs, regression_check has only 'event' key."""
        pm = tmp_path / "postmortem.jsonl"
        _append_regression_check(pm)
        entry = json.loads(pm.read_text().strip())
        assert set(entry.keys()) == {"event"}

    def test_regression_check_creates_parent_dirs(self, tmp_path):
        """_append_regression_check should create parent directories."""
        pm = tmp_path / "nested" / "dir" / "postmortem.jsonl"
        _append_regression_check(pm)
        assert pm.exists()


# ---------------------------------------------------------------------------
# raw_log: no round/phase
# ---------------------------------------------------------------------------

class TestRawLogNoRoundPhase:
    """append_raw_log should not include round or phase fields."""

    def test_raw_log_no_round(self, tmp_path):
        """Raw log entries must not have a 'round' key."""
        log_path = tmp_path / "raw_agent_log.jsonl"
        append_raw_log(log_path, "Bear", "blind", "prompt", "response")
        entry = json.loads(log_path.read_text().strip())
        assert "round" not in entry

    def test_raw_log_no_phase(self, tmp_path):
        """Raw log entries must not have a 'phase' key."""
        log_path = tmp_path / "raw_agent_log.jsonl"
        append_raw_log(log_path, "Bear", "blind", "prompt", "response")
        entry = json.loads(log_path.read_text().strip())
        assert "phase" not in entry

    def test_raw_log_has_expected_fields(self, tmp_path):
        """Raw log entries must have timestamp, card_name, mode, prompt, response."""
        log_path = tmp_path / "raw_agent_log.jsonl"
        append_raw_log(log_path, "Bear", "tested", "prompt text", "response text")
        entry = json.loads(log_path.read_text().strip())
        assert "timestamp" in entry
        assert entry["card_name"] == "Bear"
        assert entry["mode"] == "tested"
        assert entry["prompt"] == "prompt text"
        assert entry["response"] == "response text"


# ---------------------------------------------------------------------------
# JSONL format: mixed event types
# ---------------------------------------------------------------------------

class TestMixedEventJSONL:
    """Verify that mixed event types in one JSONL file are all valid JSON."""

    def test_mixed_events_valid_jsonl(self, tmp_path):
        """All event types can coexist in one JSONL file."""
        pm = tmp_path / "postmortem.jsonl"
        _append_postmortem(pm, "p", "r", 10, 5.0, "success")
        _append_file_written(pm, "card.py", 500)
        _append_eval_result(pm, "self", passed=3, failed=1)
        _append_regression_check(pm)

        lines = pm.read_text().strip().splitlines()
        assert len(lines) == 4
        for line in lines:
            entry = json.loads(line)  # must not raise
            assert isinstance(entry, dict)

    def test_event_types_in_mixed_file(self, tmp_path):
        """Each event type should be identifiable in a mixed JSONL file."""
        pm = tmp_path / "postmortem.jsonl"
        _append_file_written(pm, "card.py", 500)
        _append_eval_result(pm, "self", passed=3, failed=1)
        _append_regression_check(pm)

        lines = pm.read_text().strip().splitlines()
        events = [json.loads(l).get("event") for l in lines]
        assert "file_written" in events
        assert "eval_result" in events
        assert "regression_check" in events
        assert "file_diff" not in events


# ---------------------------------------------------------------------------
# Integration: harvest_results emits file_written events
# ---------------------------------------------------------------------------

class TestHarvestResultsEmitsFileWritten:
    """Verify harvest_results() calls _append_file_written for produced files."""

    def test_harvest_emits_file_written_for_card_impl(self, tmp_path):
        """harvest_results should emit a file_written event for card_impl.py."""
        from unittest.mock import patch, MagicMock
        from silverquillm.agent_session import AgentSession

        # Set up a fake workspace with card_impl.py
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        impl_file = workspace / "card_impl.py"
        impl_file.write_text("class Bear: pass\n")

        card_results_dir = tmp_path / "results" / "Bear"
        run_dir = tmp_path / "run"

        # Create a minimal AgentSession with necessary fields
        session = AgentSession.__new__(AgentSession)
        session._workspace = workspace
        session.run_dir = run_dir
        session.card_spec = {"name": "Bear"}
        session.card_dir = str(tmp_path / "cards" / "Bear")

        with patch(
            "silverquillm.agent_session._append_file_written"
        ) as mock_fw:
            session.harvest_results(card_results_dir)

        # At least one call should be for card_impl.py
        calls = mock_fw.call_args_list
        paths_written = [c.kwargs.get("path", c.args[1] if len(c.args) > 1 else None) for c in calls]
        assert any("card_impl.py" in str(p) for p in paths_written), (
            f"Expected file_written for card_impl.py, got: {paths_written}"
        )

    def test_harvest_emits_file_written_for_tests(self, tmp_path):
        """harvest_results should emit a file_written event for tests.py."""
        from unittest.mock import patch
        from silverquillm.agent_session import AgentSession

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "tests.py").write_text("def test_it(): pass\n")

        card_results_dir = tmp_path / "results" / "Bear"
        run_dir = tmp_path / "run"

        session = AgentSession.__new__(AgentSession)
        session._workspace = workspace
        session.run_dir = run_dir
        session.card_spec = {"name": "Bear"}
        session.card_dir = str(tmp_path / "cards" / "Bear")

        with patch(
            "silverquillm.agent_session._append_file_written"
        ) as mock_fw:
            session.harvest_results(card_results_dir)

        calls = mock_fw.call_args_list
        paths_written = [c.kwargs.get("path", c.args[1] if len(c.args) > 1 else None) for c in calls]
        assert any("tests.py" in str(p) for p in paths_written), (
            f"Expected file_written for tests.py, got: {paths_written}"
        )

    def test_harvest_writes_actual_postmortem_file(self, tmp_path):
        """harvest_results should create real file_written entries in postmortem.jsonl."""
        from silverquillm.agent_session import AgentSession

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        impl_file = workspace / "card_impl.py"
        impl_file.write_text("class Bear: pass\n")

        run_dir = tmp_path / "run"
        card_results_dir = run_dir / "cards" / "Bear"

        session = AgentSession.__new__(AgentSession)
        session._workspace = workspace
        session.run_dir = run_dir
        session.card_spec = {"name": "Bear"}
        session.card_dir = str(tmp_path / "cards" / "Bear")

        session.harvest_results(card_results_dir)

        pm_path = run_dir / "cards" / "Bear" / "postmortem.jsonl"
        assert pm_path.exists(), "postmortem.jsonl should be created by harvest_results"
        lines = pm_path.read_text().strip().splitlines()
        events = [json.loads(l) for l in lines]
        file_written_events = [e for e in events if e.get("event") == "file_written"]
        assert len(file_written_events) >= 1, (
            f"Expected at least one file_written event, got: {events}"
        )
        assert file_written_events[0]["size_bytes"] == len(impl_file.read_bytes())

    def test_harvest_no_file_written_when_no_files(self, tmp_path):
        """harvest_results should not emit file_written when workspace has no files."""
        from unittest.mock import patch
        from silverquillm.agent_session import AgentSession

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # No card_impl.py or tests.py

        card_results_dir = tmp_path / "results" / "Bear"
        run_dir = tmp_path / "run"

        session = AgentSession.__new__(AgentSession)
        session._workspace = workspace
        session.run_dir = run_dir
        session.card_spec = {"name": "Bear"}
        session.card_dir = str(tmp_path / "cards" / "Bear")

        with patch(
            "silverquillm.agent_session._append_file_written"
        ) as mock_fw:
            session.harvest_results(card_results_dir)

        mock_fw.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: run_post_eval emits eval_result events
# ---------------------------------------------------------------------------

class TestPostEvalEmitsEvalResult:
    """Verify run_post_eval() calls _append_eval_result for completed evals."""

    def test_self_eval_emits_eval_result(self, tmp_path):
        """run_post_eval in impl_test mode should emit eval_result for self-eval."""
        from unittest.mock import patch

        run_dir = tmp_path / "run"
        card_dir = run_dir / "cards" / "Bear"
        card_dir.mkdir(parents=True)
        (card_dir / "card_impl.py").write_text("class Bear: pass\n")
        (card_dir / "tests.py").write_text("def test_it(): pass\n")

        with patch(
            "silverquillm.post_eval.run_tests", return_value=(3, 1, 4, [])
        ), patch(
            "silverquillm.post_eval._append_eval_result"
        ) as mock_er:
            from silverquillm.post_eval import run_post_eval
            run_post_eval(run_dir, mode="impl_test")

        mock_er.assert_called()
        # Find the self-eval call
        self_calls = [
            c for c in mock_er.call_args_list
            if c.args[1] == "self" or c.kwargs.get("eval_type") == "self"
        ]
        assert len(self_calls) >= 1, (
            f"Expected eval_result call with eval_type='self', got: {mock_er.call_args_list}"
        )

    def test_self_eval_result_has_correct_counts(self, tmp_path):
        """eval_result from self-eval should have correct passed/failed counts."""
        from unittest.mock import patch

        run_dir = tmp_path / "run"
        card_dir = run_dir / "cards" / "Bear"
        card_dir.mkdir(parents=True)
        (card_dir / "card_impl.py").write_text("class Bear: pass\n")
        (card_dir / "tests.py").write_text("def test_it(): pass\n")

        with patch(
            "silverquillm.post_eval.run_tests", return_value=(5, 2, 7, [])
        ), patch(
            "silverquillm.post_eval._append_eval_result"
        ) as mock_er:
            from silverquillm.post_eval import run_post_eval
            run_post_eval(run_dir, mode="impl_test")

        self_calls = [
            c for c in mock_er.call_args_list
            if (len(c.args) > 1 and c.args[1] == "self") or c.kwargs.get("eval_type") == "self"
        ]
        assert len(self_calls) == 1
        call = self_calls[0]
        # Check passed=5, failed=2
        kwargs = call.kwargs if call.kwargs else {}
        if "passed" in kwargs:
            assert kwargs["passed"] == 5
            assert kwargs["failed"] == 2
        else:
            # positional: (pm_path, "self", passed=5, failed=2)
            assert call.kwargs.get("passed", call[1].get("passed")) == 5

    def test_blind_mode_no_self_eval_result(self, tmp_path):
        """run_post_eval in blind mode should NOT emit self-eval eval_result."""
        from unittest.mock import patch

        run_dir = tmp_path / "run"
        card_dir = run_dir / "cards" / "Bear"
        card_dir.mkdir(parents=True)
        (card_dir / "card_impl.py").write_text("class Bear: pass\n")
        (card_dir / "tests.py").write_text("def test_it(): pass\n")

        with patch(
            "silverquillm.post_eval.run_tests", return_value=(3, 1, 4, [])
        ), patch(
            "silverquillm.post_eval._append_eval_result"
        ) as mock_er:
            from silverquillm.post_eval import run_post_eval
            run_post_eval(run_dir, mode="blind")

        # In blind mode, self-eval should not be run
        self_calls = [
            c for c in mock_er.call_args_list
            if (len(c.args) > 1 and c.args[1] == "self")
        ]
        assert len(self_calls) == 0, (
            "blind mode should not produce self-eval eval_result events"
        )

    def test_eval_result_writes_to_postmortem_file(self, tmp_path):
        """run_post_eval should write actual eval_result entries to postmortem.jsonl."""
        from unittest.mock import patch

        run_dir = tmp_path / "run"
        card_dir = run_dir / "cards" / "Bear"
        card_dir.mkdir(parents=True)
        (card_dir / "card_impl.py").write_text("class Bear: pass\n")
        (card_dir / "tests.py").write_text("def test_it(): pass\n")

        with patch(
            "silverquillm.post_eval.run_tests", return_value=(3, 1, 4, [])
        ):
            from silverquillm.post_eval import run_post_eval
            run_post_eval(run_dir, mode="impl_test")

        pm_path = card_dir / "postmortem.jsonl"
        assert pm_path.exists(), "postmortem.jsonl should be created by run_post_eval"
        lines = pm_path.read_text().strip().splitlines()
        events = [json.loads(l) for l in lines]
        eval_events = [e for e in events if e.get("event") == "eval_result"]
        assert len(eval_events) >= 1, (
            f"Expected eval_result event in postmortem.jsonl, got: {events}"
        )
        self_eval = [e for e in eval_events if e.get("eval_type") == "self"]
        assert len(self_eval) == 1
        assert self_eval[0]["passed"] == 3
        assert self_eval[0]["failed"] == 1


# ---------------------------------------------------------------------------
# Integration: CLI regression loop emits regression_check events
# ---------------------------------------------------------------------------

class TestRegressionLoopEmitsRegressionCheck:
    """Verify CLI regression loop calls _append_regression_check."""

    def test_regression_check_called_in_cli(self):
        """cli.py should import _append_regression_check from agent_session."""
        import silverquillm.cli as cli_mod
        import inspect
        source = inspect.getsource(cli_mod)
        assert "_append_regression_check" in source, (
            "cli.py should use _append_regression_check"
        )

    def test_regression_check_event_structure(self, tmp_path):
        """_append_regression_check called from CLI should produce correct event."""
        # Simulate what the CLI does: call _append_regression_check with
        # the same arguments the CLI uses
        pm_path = tmp_path / "cards" / "Bear" / "postmortem.jsonl"
        _append_regression_check(
            pm_path,
            status="pass",
            cards_failed=0,
            total_cards=3,
        )
        entry = json.loads(pm_path.read_text().strip())
        assert entry["event"] == "regression_check"
        assert entry["status"] == "pass"
        assert entry["cards_failed"] == 0
        assert entry["total_cards"] == 3

    def test_regression_check_fail_status(self, tmp_path):
        """regression_check with failures should record fail status."""
        pm_path = tmp_path / "cards" / "Bear" / "postmortem.jsonl"
        _append_regression_check(
            pm_path,
            status="fail",
            cards_failed=2,
            total_cards=5,
        )
        entry = json.loads(pm_path.read_text().strip())
        assert entry["event"] == "regression_check"
        assert entry["status"] == "fail"
        assert entry["cards_failed"] == 2
        assert entry["total_cards"] == 5
