"""Tests for TODO item 10: Postmortem JSONL logging.

After each agent invocation (adapter.run() call), a structured JSON line
is appended to ``<output_dir>/<card_name>/postmortem.jsonl``.

Each entry must contain:
- prompt: the prompt text sent to the agent
- response: the agent's response (truncated if very long)
- tokens: estimated token count (or null)
- timing_ms: duration in milliseconds
- round: round number (1 for blind, 1..N for test-informed)
- status: "success" or "error"
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from silverquillm.agent_session import (
    AgentSession,
    BlindResult,
    TestInformedResult,
    _append_postmortem,
)
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_config(output_dir: str = "", **overrides) -> BenchmarkConfig:
    defaults = dict(
        name="test-bench",
        set_code="FDN",
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
        output_dir=output_dir,
        agent=AgentConfig(
            timeout_per_card=300,
        ),
    )
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


_SAMPLE_SPEC = {
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "power": "2",
    "toughness": "2",
}


# ---------------------------------------------------------------------------
# Unit tests for _append_postmortem helper
# ---------------------------------------------------------------------------

class TestAppendPostmortem:
    """Direct tests for the _append_postmortem helper."""

    def test_creates_file_and_writes_jsonl(self, tmp_path):
        postmortem_path = tmp_path / "card" / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="hello",
            response="world",
            tokens=42,
            timing_ms=123.4,
            round_num=1,
            status="success",
        )
        assert postmortem_path.exists()
        lines = postmortem_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["prompt"] == "hello"
        assert entry["response"] == "world"
        assert entry["tokens"] == 42
        assert entry["timing_ms"] == 123.4
        assert entry["round"] == 1
        assert entry["status"] == "success"

    def test_appends_multiple_entries(self, tmp_path):
        postmortem_path = tmp_path / "postmortem.jsonl"
        for i in range(3):
            _append_postmortem(
                postmortem_path=postmortem_path,
                prompt=f"p{i}",
                response=f"r{i}",
                tokens=i * 10,
                timing_ms=float(i),
                round_num=i + 1,
                status="success",
            )
        lines = postmortem_path.read_text().strip().splitlines()
        assert len(lines) == 3
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert entry["round"] == i + 1

    def test_tokens_can_be_none(self, tmp_path):
        postmortem_path = tmp_path / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="p",
            response="r",
            tokens=None,
            timing_ms=1.0,
            round_num=1,
            status="success",
        )
        entry = json.loads(postmortem_path.read_text().strip())
        assert entry["tokens"] is None

    def test_error_status(self, tmp_path):
        postmortem_path = tmp_path / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="p",
            response="error msg",
            tokens=None,
            timing_ms=50.0,
            round_num=1,
            status="error",
        )
        entry = json.loads(postmortem_path.read_text().strip())
        assert entry["status"] == "error"

    def test_response_truncated_if_very_long(self, tmp_path):
        """Responses longer than 10_000 chars should be truncated."""
        postmortem_path = tmp_path / "postmortem.jsonl"
        long_response = "x" * 20_000
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="p",
            response=long_response,
            tokens=100,
            timing_ms=1.0,
            round_num=1,
            status="success",
        )
        entry = json.loads(postmortem_path.read_text().strip())
        assert len(entry["response"]) <= 10_100  # some slack for truncation marker

    def test_truncated_response_contains_marker(self, tmp_path):
        """Truncated responses should end with a truncation marker."""
        postmortem_path = tmp_path / "postmortem.jsonl"
        long_response = "a" * 20_000
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="p",
            response=long_response,
            tokens=100,
            timing_ms=1.0,
            round_num=1,
            status="success",
        )
        entry = json.loads(postmortem_path.read_text().strip())
        assert entry["response"].endswith("...[truncated]")

    def test_short_response_not_truncated(self, tmp_path):
        """Responses under the limit should be stored verbatim."""
        postmortem_path = tmp_path / "postmortem.jsonl"
        short_response = "b" * 5_000
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="p",
            response=short_response,
            tokens=50,
            timing_ms=2.0,
            round_num=1,
            status="success",
        )
        entry = json.loads(postmortem_path.read_text().strip())
        assert entry["response"] == short_response

    def test_required_fields_exactly(self, tmp_path):
        """Each entry must have exactly the required fields."""
        postmortem_path = tmp_path / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="p",
            response="r",
            tokens=10,
            timing_ms=5.0,
            round_num=1,
            status="success",
        )
        entry = json.loads(postmortem_path.read_text().strip())
        expected_keys = {"prompt", "response", "tokens", "timing_ms", "round", "status"}
        assert set(entry.keys()) == expected_keys

    def test_timing_ms_is_numeric(self, tmp_path):
        """timing_ms must be a number (int or float)."""
        postmortem_path = tmp_path / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="p",
            response="r",
            tokens=10,
            timing_ms=0.0,
            round_num=1,
            status="success",
        )
        entry = json.loads(postmortem_path.read_text().strip())
        assert isinstance(entry["timing_ms"], (int, float))
        assert entry["timing_ms"] >= 0

    def test_each_line_is_independent_valid_json(self, tmp_path):
        """Each line in the JSONL file must be independently parseable JSON."""
        postmortem_path = tmp_path / "postmortem.jsonl"
        for i in range(5):
            _append_postmortem(
                postmortem_path=postmortem_path,
                prompt=f"prompt-{i}",
                response=f"response-{i}",
                tokens=i,
                timing_ms=float(i * 10),
                round_num=i + 1,
                status="success" if i % 2 == 0 else "error",
            )
        lines = postmortem_path.read_text().strip().splitlines()
        assert len(lines) == 5
        for line in lines:
            entry = json.loads(line)  # Should not raise
            assert "prompt" in entry
            assert "status" in entry


# ---------------------------------------------------------------------------
# Integration: postmortem logged during blind implementation
# ---------------------------------------------------------------------------

class TestPostmortemDuringBlind:
    """Verify postmortem.jsonl is written during run_blind_implementation."""

    def test_blind_success_logs_postmortem(self, tmp_path, monkeypatch):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        config = _make_config(output_dir=str(output_dir))
        session = AgentSession(
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(tmp_path),
            run_dir=output_dir,
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        # Make _run_agent produce output and create blind_impl.py
        def fake_run(prompt, ws):
            (ws / "blind_impl.py").write_text("x = 1\n")
            return "agent output"

        monkeypatch.setattr(session, "_run_agent", fake_run)

        result = session.run_blind_implementation(workspace)
        assert result.status == "ok"

        postmortem = output_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
        assert postmortem.exists()
        entry = json.loads(postmortem.read_text().strip())
        assert entry["status"] == "success"
        assert entry["round"] == 1
        assert entry["timing_ms"] > 0

    def test_blind_timeout_logs_error(self, tmp_path, monkeypatch):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        config = _make_config(output_dir=str(output_dir))
        session = AgentSession(
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(tmp_path),
            run_dir=output_dir,
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        def fake_run(prompt, ws):
            raise subprocess.TimeoutExpired(cmd="agent", timeout=300)

        monkeypatch.setattr(session, "_run_agent", fake_run)

        result = session.run_blind_implementation(workspace)
        assert result.status == "timeout"

        postmortem = output_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
        assert postmortem.exists()
        entry = json.loads(postmortem.read_text().strip())
        assert entry["status"] == "error"
        assert entry["round"] == 1

    def test_no_postmortem_when_no_output_dir(self, tmp_path, monkeypatch):
        """When output_dir is empty, postmortem is silently skipped."""
        config = _make_config(output_dir="")
        session = AgentSession(
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(tmp_path),
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        def fake_run(prompt, ws):
            (ws / "blind_impl.py").write_text("x = 1\n")
            return "output"

        monkeypatch.setattr(session, "_run_agent", fake_run)

        result = session.run_blind_implementation(workspace)
        assert result.status == "ok"
        # No crash — postmortem just isn't written


# ---------------------------------------------------------------------------
# Integration: postmortem logged during test-informed rounds
# ---------------------------------------------------------------------------

class TestPostmortemDuringTestInformed:
    """Verify postmortem.jsonl entries for each test-informed round."""

    def test_test_informed_logs_per_round(self, tmp_path, monkeypatch):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        config = _make_config(
            output_dir=str(output_dir),
            agent=AgentConfig(timeout_per_card=300),
        )
        session = AgentSession(
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(tmp_path),
            run_dir=output_dir,
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        blind_impl = workspace / "blind_impl.py"
        blind_impl.write_text("x = 1\n")

        call_count = 0

        def fake_run(prompt, ws):
            nonlocal call_count
            call_count += 1
            # On round 1, produce tests that fail; on round 2, succeed
            (ws / "card_impl.py").write_text("x = 1\n")
            (ws / "tests.py").write_text("def test_ok(): pass\n")
            return f"round {call_count} output"

        monkeypatch.setattr(session, "_run_agent", fake_run)

        # Make _run_pytest return success on first call
        def fake_pytest(ws, tp):
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="passed", stderr=""
            )

        monkeypatch.setattr(session, "_run_pytest", fake_pytest)

        result = session.run_test_informed(workspace, blind_impl)
        assert result.status == "ok"

        postmortem = output_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
        assert postmortem.exists()
        lines = postmortem.read_text().strip().splitlines()
        # At least 1 entry logged
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["status"] == "success"
        assert entry["round"] == 1

    def test_test_informed_timeout_logs_error(self, tmp_path, monkeypatch):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        config = _make_config(
            output_dir=str(output_dir),
            agent=AgentConfig(timeout_per_card=300),
        )
        session = AgentSession(
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(tmp_path),
            run_dir=output_dir,
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        blind_impl = workspace / "blind_impl.py"
        blind_impl.write_text("x = 1\n")
        (workspace / "card_impl.py").write_text("x = 1\n")

        def fake_run(prompt, ws):
            raise subprocess.TimeoutExpired(cmd="agent", timeout=300)

        monkeypatch.setattr(session, "_run_agent", fake_run)

        result = session.run_test_informed(workspace, blind_impl)
        assert result.status == "timeout"

        postmortem = output_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
        assert postmortem.exists()
        entry = json.loads(postmortem.read_text().strip())
        assert entry["status"] == "error"
        assert entry["round"] == 1
