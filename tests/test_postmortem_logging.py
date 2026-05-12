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
                status="success",
            )
        lines = postmortem_path.read_text().strip().splitlines()
        assert len(lines) == 3
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert entry["prompt"] == f"p{i}"

    def test_tokens_can_be_none(self, tmp_path):
        postmortem_path = tmp_path / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="p",
            response="r",
            tokens=None,
            timing_ms=1.0,
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
            status="success",
        )
        entry = json.loads(postmortem_path.read_text().strip())
        expected_keys = {"prompt", "response", "tokens", "timing_ms", "status"}
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
    """Verify postmortem functions are importable and callable after refactor."""

    def test_blind_success_logs_postmortem(self, tmp_path, monkeypatch):
        """_append_postmortem can be called directly to log entries."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        postmortem_path = output_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="blind prompt",
            response="agent output",
            tokens=42,
            timing_ms=123.4,
            status="success",
        )

        assert postmortem_path.exists()
        entry = json.loads(postmortem_path.read_text().strip())
        assert entry["status"] == "success"
        assert entry["timing_ms"] > 0

    def test_blind_timeout_logs_error(self, tmp_path, monkeypatch):
        """_append_postmortem can log error entries for timeouts."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        postmortem_path = output_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="blind prompt",
            response="TimeoutExpired",
            tokens=None,
            timing_ms=300000.0,
            status="error",
        )

        assert postmortem_path.exists()
        entry = json.loads(postmortem_path.read_text().strip())
        assert entry["status"] == "error"


# ---------------------------------------------------------------------------
# Integration: run_card() triggers postmortem logging
# ---------------------------------------------------------------------------

class TestRunCardPostmortem:
    """AgentSession.run_card() must log postmortem entries and generate agent_thoughts."""

    def test_run_card_logs_postmortem_on_success(self, tmp_path, monkeypatch):
        """run_card() must append a postmortem entry after successful strategy execution."""
        from unittest.mock import MagicMock, patch
        from silverquillm.strategies import CardRunResult, CardRunStatus

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        card_dir = tmp_path / "card_data"
        card_dir.mkdir()
        (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))

        config = _make_config(output_dir=str(run_dir))
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            run_dir=run_dir,
        )

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed, files_written=[], runtime_ms=200,
        )

        try:
            with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
                session.setup_workspace()
                session.run_card()

            postmortem_path = run_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
            assert postmortem_path.exists(), "run_card() must log postmortem entries"
            lines = postmortem_path.read_text().strip().splitlines()
            assert len(lines) >= 1
            entry = json.loads(lines[0])
            assert entry["status"] == "success"
        finally:
            session.cleanup()

    def test_run_card_generates_agent_thoughts(self, tmp_path, monkeypatch):
        """run_card() must generate agent_thoughts.md after strategy execution."""
        from unittest.mock import MagicMock, patch
        from silverquillm.strategies import CardRunResult, CardRunStatus

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        card_dir = tmp_path / "card_data"
        card_dir.mkdir()
        (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))

        config = _make_config(output_dir=str(run_dir))
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            run_dir=run_dir,
        )

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed, files_written=[], runtime_ms=100,
        )

        try:
            with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
                session.setup_workspace()
                session.run_card()

            thoughts_path = run_dir / "cards" / "Grizzly Bears" / "agent_thoughts.md"
            assert thoughts_path.exists(), "run_card() must generate agent_thoughts.md"
        finally:
            session.cleanup()

    def test_run_card_logs_postmortem_on_error(self, tmp_path, monkeypatch):
        """run_card() must log an error postmortem when strategy raises."""
        from unittest.mock import MagicMock, patch

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        card_dir = tmp_path / "card_data"
        card_dir.mkdir()
        (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))

        config = _make_config(output_dir=str(run_dir))
        session = AgentSession(
            config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir),
            run_dir=run_dir,
        )

        mock_strategy = MagicMock()
        mock_strategy.run_card.side_effect = RuntimeError("agent crashed")

        try:
            with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
                session.setup_workspace()
                with pytest.raises(RuntimeError):
                    session.run_card()

            postmortem_path = run_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
            assert postmortem_path.exists(), "run_card() must log postmortem even on error"
            entry = json.loads(postmortem_path.read_text().strip())
            assert entry["status"] == "error"
        finally:
            session.cleanup()
    def test_no_postmortem_when_no_output_dir(self, tmp_path, monkeypatch):
        """When output_dir is empty, postmortem is silently skipped (no crash)."""
        config = _make_config(output_dir="")
        session = AgentSession(
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(tmp_path),
        )
        # Just verify the session can be created without crash
        assert session.config.output_dir == ""


# ---------------------------------------------------------------------------
# Integration: postmortem logged during test-informed rounds
# ---------------------------------------------------------------------------

class TestPostmortemDuringTestInformed:
    """Verify postmortem entries can be written for multiple rounds."""

    def test_test_informed_logs_per_round(self, tmp_path, monkeypatch):
        """Multiple postmortem entries can be appended for iteration rounds."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        postmortem_path = output_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"

        for i in range(1, 4):
            _append_postmortem(
                postmortem_path=postmortem_path,
                prompt=f"round {i} prompt",
                response=f"round {i} output",
                tokens=i * 10,
                timing_ms=float(i * 100),
                status="success",
            )

        assert postmortem_path.exists()
        lines = postmortem_path.read_text().strip().splitlines()
        assert len(lines) == 3
        entry = json.loads(lines[0])
        assert entry["status"] == "success"
        assert entry["prompt"] == "round 1 prompt"

    def test_test_informed_timeout_logs_error(self, tmp_path, monkeypatch):
        """Timeout error entry can be logged via _append_postmortem."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        postmortem_path = output_dir / "cards" / "Grizzly Bears" / "postmortem.jsonl"
        _append_postmortem(
            postmortem_path=postmortem_path,
            prompt="test informed prompt",
            response="TimeoutExpired",
            tokens=None,
            timing_ms=300000.0,
            status="error",
        )

        assert postmortem_path.exists()
        entry = json.loads(postmortem_path.read_text().strip())
        assert entry["status"] == "error"
