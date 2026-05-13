"""Tests for TODO item 5: Wire agent output through strategy → CardRunResult → postmortem.

Tests verify:
- CardRunResult has agent_output and prompt_used fields defaulting to empty strings.
- BlindStrategy.run_card() captures adapter return value into CardRunResult.agent_output.
- ImplTestStrategy.run_card() captures adapter return value into CardRunResult.agent_output.
- CardRunResult.prompt_used contains the prompt that was sent to the adapter.
- On timeout, agent_output is empty string.
- Postmortem logging in run_card() uses result.agent_output and result.prompt_used.
- Raw log uses result.agent_output.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.adapters.base import AgentAdapter
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.strategies import (
    BlindStrategy,
    CardRunResult,
    CardRunStatus,
    ImplTestStrategy,
)


# ---------------------------------------------------------------------------
# Sample card spec
# ---------------------------------------------------------------------------

_SAMPLE_CARD_SPEC: dict = {
    "name": "Lightning Bolt",
    "mana_cost": "{R}",
    "type_line": "Instant",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
}


def _default_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        name="test-bench",
        set_code="TST",
        model_name="test-model",
        model_provider="test",
        max_context=200_000,
        temperature=0.0,
        agent=AgentConfig(timeout_per_card=300),
    )


# ---------------------------------------------------------------------------
# Mock adapters
# ---------------------------------------------------------------------------


class _OutputAdapter(AgentAdapter):
    """Adapter that returns a configurable output string."""

    def __init__(
        self,
        output: str = "agent response text",
        *,
        write_impl: bool = False,
        write_tests: bool = False,
        raise_timeout: bool = False,
    ) -> None:
        super().__init__(_default_config())
        self._output = output
        self._write_impl = write_impl
        self._write_tests = write_tests
        self._raise_timeout = raise_timeout

    def setup(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def run(self, prompt: str, workspace: Path) -> str:
        if self._raise_timeout:
            raise TimeoutError("adapter timed out")
        if self._write_impl:
            (workspace / "card_impl.py").write_text("# impl\n")
        if self._write_tests:
            (workspace / "tests.py").write_text("# tests\n")
        return self._output


# =========================================================================
# CardRunResult defaults for new fields
# =========================================================================


class TestCardRunResultNewFields:
    """CardRunResult.agent_output and prompt_used must exist and default to ''."""

    def test_agent_output_defaults_to_empty_string(self) -> None:
        result = CardRunResult(status=CardRunStatus.completed)
        assert result.agent_output == ""

    def test_prompt_used_defaults_to_empty_string(self) -> None:
        result = CardRunResult(status=CardRunStatus.completed)
        assert result.prompt_used == ""

    def test_agent_output_accepts_custom_value(self) -> None:
        result = CardRunResult(status=CardRunStatus.completed, agent_output="hello")
        assert result.agent_output == "hello"

    def test_prompt_used_accepts_custom_value(self) -> None:
        result = CardRunResult(status=CardRunStatus.completed, prompt_used="do stuff")
        assert result.prompt_used == "do stuff"


# =========================================================================
# BlindStrategy — agent_output and prompt_used capture
# =========================================================================


class TestBlindStrategyOutputCapture:
    """BlindStrategy.run_card() must capture adapter output and prompt."""

    def test_agent_output_contains_adapter_return_value(self, tmp_path: Path) -> None:
        """agent_output should be the string returned by adapter.run()."""
        strategy = BlindStrategy()
        adapter = _OutputAdapter("blind adapter response", write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.agent_output == "blind adapter response"

    def test_prompt_used_is_non_empty(self, tmp_path: Path) -> None:
        """prompt_used should contain the actual prompt sent to the adapter."""
        strategy = BlindStrategy()
        adapter = _OutputAdapter("output", write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.prompt_used != ""

    def test_prompt_used_contains_card_name(self, tmp_path: Path) -> None:
        """prompt_used should contain the card name from the spec."""
        strategy = BlindStrategy()
        adapter = _OutputAdapter("output", write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert "Lightning Bolt" in result.prompt_used

    def test_agent_output_empty_on_timeout(self, tmp_path: Path) -> None:
        """On timeout, agent_output must be empty string."""
        strategy = BlindStrategy()
        adapter = _OutputAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.agent_output == ""

    def test_prompt_used_set_even_on_timeout(self, tmp_path: Path) -> None:
        """Even when timeout occurs, prompt_used should still contain the prompt."""
        strategy = BlindStrategy()
        adapter = _OutputAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.prompt_used != ""
        assert "Lightning Bolt" in result.prompt_used

    def test_agent_output_on_no_output_status(self, tmp_path: Path) -> None:
        """When no card_impl.py is produced, agent_output still has the adapter return."""
        strategy = BlindStrategy()
        adapter = _OutputAdapter("no file written response", write_impl=False)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.no_output
        assert result.agent_output == "no file written response"

    def test_agent_output_converts_non_string_to_str(self, tmp_path: Path) -> None:
        """If adapter returns a non-string, it should be converted to string."""
        strategy = BlindStrategy()

        class _IntAdapter(AgentAdapter):
            def __init__(self):
                super().__init__(_default_config())
            def setup(self): pass
            def teardown(self): pass
            def run(self, prompt: str, workspace: Path) -> str:
                (workspace / "card_impl.py").write_text("# impl\n")
                return 42  # type: ignore[return-value]

        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, _IntAdapter(), timeout=60)
        assert result.agent_output == "42"


# =========================================================================
# ImplTestStrategy — agent_output and prompt_used capture
# =========================================================================


class TestImplTestStrategyOutputCapture:
    """ImplTestStrategy.run_card() must capture adapter output and prompt."""

    def test_agent_output_contains_adapter_return_value(self, tmp_path: Path) -> None:
        """agent_output should be the string returned by adapter.run()."""
        strategy = ImplTestStrategy()
        adapter = _OutputAdapter("impl_test adapter response", write_impl=True, write_tests=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.agent_output == "impl_test adapter response"

    def test_prompt_used_is_non_empty(self, tmp_path: Path) -> None:
        strategy = ImplTestStrategy()
        adapter = _OutputAdapter("output", write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.prompt_used != ""

    def test_prompt_used_contains_card_name(self, tmp_path: Path) -> None:
        strategy = ImplTestStrategy()
        adapter = _OutputAdapter("output", write_impl=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert "Lightning Bolt" in result.prompt_used

    def test_agent_output_empty_on_timeout(self, tmp_path: Path) -> None:
        strategy = ImplTestStrategy()
        adapter = _OutputAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.agent_output == ""

    def test_prompt_used_set_even_on_timeout(self, tmp_path: Path) -> None:
        strategy = ImplTestStrategy()
        adapter = _OutputAdapter(raise_timeout=True)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.prompt_used != ""

    def test_agent_output_on_no_output_status(self, tmp_path: Path) -> None:
        strategy = ImplTestStrategy()
        adapter = _OutputAdapter("nothing written", write_impl=False)
        result = strategy.run_card(_SAMPLE_CARD_SPEC, tmp_path, adapter, timeout=60)
        assert result.status == CardRunStatus.no_output
        assert result.agent_output == "nothing written"


# =========================================================================
# Postmortem / raw-log wiring in AgentSession.run_card()
# =========================================================================


class TestPostmortemUsesResultFields:
    """AgentSession.run_card() should pass result.agent_output and result.prompt_used
    to _append_postmortem() and append_raw_log(), not placeholders."""

    @pytest.fixture()
    def _session_env(self, tmp_path):
        """Set up an AgentSession with mocked adapter and strategy."""
        from silverquillm.agent_session import AgentSession
        from silverquillm.config import AgentConfig, BenchmarkConfig

        card_dir = tmp_path / "card_data"
        card_dir.mkdir()
        (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_CARD_SPEC))

        run_dir = tmp_path / "run_output"
        run_dir.mkdir()

        config = BenchmarkConfig(
            name="test-bench",
            set_code="FDN",
            model_name="test-model",
            model_provider="test-provider",
            max_context=200_000,
            temperature=0.0,
            agent=AgentConfig(timeout_per_card=300),
            output_dir=str(run_dir),
        )
        sess = AgentSession(
            config=config,
            card_spec=_SAMPLE_CARD_SPEC,
            card_dir=str(card_dir),
        )
        sess.setup_workspace()
        # Set run_dir so postmortem paths resolve
        sess.run_dir = run_dir
        return sess

    def test_postmortem_receives_agent_output(self, _session_env) -> None:
        """_append_postmortem should be called with the agent_output from the result."""
        sess = _session_env
        fake_result = CardRunResult(
            status=CardRunStatus.completed,
            runtime_ms=100,
            agent_output="the real agent output",
            prompt_used="the real prompt",
        )
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = fake_result

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._append_postmortem") as mock_pm,
            patch("silverquillm.agent_session.append_raw_log") as mock_raw,
            patch("silverquillm.agent_session._get_postmortem_path", return_value=Path("/fake/postmortem.jsonl")),
            patch("silverquillm.agent_session._get_raw_log_path", return_value=Path("/fake/raw.jsonl")),
        ):
            sess.run_card()

            # Postmortem should receive the actual agent output, not a placeholder
            assert mock_pm.called
            pm_kwargs = mock_pm.call_args
            # response kwarg or positional arg should contain the agent output
            call_args = pm_kwargs.kwargs if pm_kwargs.kwargs else {}
            call_positional = pm_kwargs.args if pm_kwargs.args else ()
            # _append_postmortem(postmortem_path, prompt, response, tokens, timing_ms, status)
            # Check that "the real agent output" appears in the response argument
            all_args_str = str(call_positional) + str(call_args)
            assert "the real agent output" in all_args_str

    def test_postmortem_receives_prompt_used(self, _session_env) -> None:
        """_append_postmortem should be called with the prompt_used from the result."""
        sess = _session_env
        fake_result = CardRunResult(
            status=CardRunStatus.completed,
            runtime_ms=100,
            agent_output="output text",
            prompt_used="the real prompt",
        )
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = fake_result

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._append_postmortem") as mock_pm,
            patch("silverquillm.agent_session.append_raw_log") as mock_raw,
            patch("silverquillm.agent_session._get_postmortem_path", return_value=Path("/fake/postmortem.jsonl")),
            patch("silverquillm.agent_session._get_raw_log_path", return_value=Path("/fake/raw.jsonl")),
        ):
            sess.run_card()

            assert mock_pm.called
            all_args_str = str(mock_pm.call_args.args) + str(mock_pm.call_args.kwargs)
            assert "the real prompt" in all_args_str

    def test_raw_log_receives_agent_output(self, _session_env) -> None:
        """append_raw_log should be called with the agent_output from the result."""
        sess = _session_env
        fake_result = CardRunResult(
            status=CardRunStatus.completed,
            runtime_ms=100,
            agent_output="raw log output text",
            prompt_used="prompt for raw",
        )
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = fake_result

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._append_postmortem") as mock_pm,
            patch("silverquillm.agent_session.append_raw_log") as mock_raw,
            patch("silverquillm.agent_session._get_postmortem_path", return_value=Path("/fake/postmortem.jsonl")),
            patch("silverquillm.agent_session._get_raw_log_path", return_value=Path("/fake/raw.jsonl")),
        ):
            sess.run_card()

            assert mock_raw.called
            all_args_str = str(mock_raw.call_args.args) + str(mock_raw.call_args.kwargs)
            assert "raw log output text" in all_args_str

    def test_raw_log_receives_prompt_used(self, _session_env) -> None:
        """append_raw_log should be called with the prompt_used from the result."""
        sess = _session_env
        fake_result = CardRunResult(
            status=CardRunStatus.completed,
            runtime_ms=100,
            agent_output="output",
            prompt_used="prompt for raw log",
        )
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = fake_result

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._append_postmortem") as mock_pm,
            patch("silverquillm.agent_session.append_raw_log") as mock_raw,
            patch("silverquillm.agent_session._get_postmortem_path", return_value=Path("/fake/postmortem.jsonl")),
            patch("silverquillm.agent_session._get_raw_log_path", return_value=Path("/fake/raw.jsonl")),
        ):
            sess.run_card()

            assert mock_raw.called
            all_args_str = str(mock_raw.call_args.args) + str(mock_raw.call_args.kwargs)
            assert "prompt for raw log" in all_args_str

    def test_postmortem_fallback_when_agent_output_empty(self, _session_env) -> None:
        """When agent_output is empty, postmortem should use a fallback containing status."""
        sess = _session_env
        fake_result = CardRunResult(
            status=CardRunStatus.no_output,
            runtime_ms=100,
            agent_output="",
            prompt_used="the prompt",
        )
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = fake_result

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._append_postmortem") as mock_pm,
            patch("silverquillm.agent_session.append_raw_log") as mock_raw,
            patch("silverquillm.agent_session._get_postmortem_path", return_value=Path("/fake/postmortem.jsonl")),
            patch("silverquillm.agent_session._get_raw_log_path", return_value=Path("/fake/raw.jsonl")),
        ):
            sess.run_card()

            assert mock_pm.called
            all_args_str = str(mock_pm.call_args.args) + str(mock_pm.call_args.kwargs)
            # Should contain a fallback that includes the status value
            assert "no_output" in all_args_str

    def test_postmortem_fallback_when_prompt_used_empty(self, _session_env) -> None:
        """When prompt_used is empty, postmortem should fall back to '(strategy-level)'."""
        sess = _session_env
        fake_result = CardRunResult(
            status=CardRunStatus.completed,
            runtime_ms=100,
            agent_output="some output",
            prompt_used="",
        )
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = fake_result

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._append_postmortem") as mock_pm,
            patch("silverquillm.agent_session.append_raw_log") as mock_raw,
            patch("silverquillm.agent_session._get_postmortem_path", return_value=Path("/fake/postmortem.jsonl")),
            patch("silverquillm.agent_session._get_raw_log_path", return_value=Path("/fake/raw.jsonl")),
        ):
            sess.run_card()

            assert mock_pm.called
            all_args_str = str(mock_pm.call_args.args) + str(mock_pm.call_args.kwargs)
            assert "(strategy-level)" in all_args_str
