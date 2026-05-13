"""Tests for TODO item 8: Signal handler for graceful interrupt cleanup.

Tests verify:
- _interrupt_handler exists and is callable
- _interrupt_handler kills the active adapter when session is set
- _interrupt_handler raises KeyboardInterrupt
- _interrupt_handler handles None _active_session gracefully
- _interrupt_handler handles missing/None _adapter gracefully
- Signal handlers are registered at start of run()
- Signal handlers are restored after the card loop
- _active_session is set before run_card() and cleared in finally block
- KeyboardInterrupt during card loop breaks cleanly
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import signal

import pytest

import silverquillm.cli as cli_mod
from silverquillm.cli import _interrupt_handler


# ---------------------------------------------------------------------------
# Helper: save/restore _active_session around tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _restore_active_session():
    """Ensure _active_session is restored after each test."""
    original = cli_mod._active_session
    yield
    cli_mod._active_session = original


# ---------------------------------------------------------------------------
# Tests for _interrupt_handler function
# ---------------------------------------------------------------------------


class TestInterruptHandler:
    """Tests for the _interrupt_handler function itself."""

    def test_interrupt_handler_exists_and_callable(self):
        """_interrupt_handler should be importable and callable."""
        assert callable(_interrupt_handler)

    def test_interrupt_handler_raises_keyboard_interrupt(self):
        """_interrupt_handler must always raise KeyboardInterrupt."""
        cli_mod._active_session = None
        with pytest.raises(KeyboardInterrupt):
            _interrupt_handler(signal.SIGINT.value, None)

    def test_interrupt_handler_kills_adapter_when_session_set(self):
        """When _active_session is set, handler should call _adapter.kill()."""
        mock_session = MagicMock()
        mock_adapter = MagicMock()
        mock_session._adapter = mock_adapter

        cli_mod._active_session = mock_session
        with pytest.raises(KeyboardInterrupt):
            _interrupt_handler(signal.SIGINT.value, None)
        mock_adapter.kill.assert_called_once()

    def test_interrupt_handler_none_active_session(self):
        """When _active_session is None, handler should not crash and still raise."""
        cli_mod._active_session = None
        with pytest.raises(KeyboardInterrupt):
            _interrupt_handler(signal.SIGINT.value, None)

    def test_interrupt_handler_adapter_is_none(self):
        """When _active_session._adapter is None, handler should not crash."""
        mock_session = MagicMock()
        mock_session._adapter = None

        cli_mod._active_session = mock_session
        # Accessing None.kill() would raise AttributeError,
        # but the handler's try/except should swallow it
        with pytest.raises(KeyboardInterrupt):
            _interrupt_handler(signal.SIGINT.value, None)

    def test_interrupt_handler_adapter_kill_raises(self):
        """If adapter.kill() raises, handler should still raise KeyboardInterrupt."""
        mock_session = MagicMock()
        mock_session._adapter.kill.side_effect = RuntimeError("kill failed")

        cli_mod._active_session = mock_session
        with pytest.raises(KeyboardInterrupt):
            _interrupt_handler(signal.SIGINT.value, None)

    def test_interrupt_handler_with_sigterm(self):
        """Handler should work the same way when called with SIGTERM."""
        mock_session = MagicMock()
        cli_mod._active_session = mock_session
        with pytest.raises(KeyboardInterrupt):
            _interrupt_handler(signal.SIGTERM.value, None)
        mock_session._adapter.kill.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for signal registration/restoration in run()
# ---------------------------------------------------------------------------


class TestSignalRegistration:
    """Tests that signal handlers are registered and restored in run()."""

    def _make_config_mock(self):
        cfg = MagicMock(
            set_code="TST", model_name="m", model_provider="p",
            timeout=60, card_filter=None, collectors=None,
            prototype=None, strategy=None,
            card_specs_dir="/fake/specs",
        )
        return cfg

    @patch("signal.signal")
    @patch("silverquillm.cli.save_run_summary_v2")
    @patch("silverquillm.cli.aggregate_run", return_value={})
    @patch("silverquillm.cli.save_engine_final")
    @patch("silverquillm.cli.init_run_engine", return_value="/tmp/fake-engine")
    @patch("silverquillm.cli.init_results_dir", return_value="/tmp/fake-results")
    @patch("silverquillm.preflight.preflight_check")
    @patch("silverquillm.cli.load_card_specs")
    @patch("silverquillm.cli.load_config")
    def test_signal_handlers_registered_at_start(
        self, mock_load_config, mock_load_specs, mock_preflight,
        mock_init_results, mock_init_engine, mock_save_engine,
        mock_agg, mock_save_summary, mock_signal
    ):
        """Signal handlers for SIGINT and SIGTERM should be registered."""
        from click.testing import CliRunner
        from silverquillm.cli import main

        mock_load_config.return_value = self._make_config_mock()
        mock_load_specs.return_value = [
            {"name": "Card1", "card_dir_name": "001", "collector_number": "001"}
        ]
        mock_signal.return_value = signal.SIG_DFL

        # Patch AgentSession to avoid real work
        with patch("silverquillm.cli.AgentSession") as mock_agent_cls:
            mock_session = MagicMock()
            mock_session.run_card.side_effect = RuntimeError("skip")
            mock_session.run_dir = None
            mock_agent_cls.return_value = mock_session

            runner = CliRunner()
            runner.invoke(main, ["run", "--config", "fake.yaml"])

        # Check that signal.signal was called with SIGINT and _interrupt_handler
        sigint_register_calls = [
            c for c in mock_signal.call_args_list
            if len(c[0]) >= 2 and c[0][0] == signal.SIGINT and c[0][1] is _interrupt_handler
        ]
        sigterm_register_calls = [
            c for c in mock_signal.call_args_list
            if len(c[0]) >= 2 and c[0][0] == signal.SIGTERM and c[0][1] is _interrupt_handler
        ]

        assert len(sigint_register_calls) >= 1, "SIGINT handler should be registered"
        assert len(sigterm_register_calls) >= 1, "SIGTERM handler should be registered"

    @patch("signal.signal")
    @patch("silverquillm.cli.save_run_summary_v2")
    @patch("silverquillm.cli.aggregate_run", return_value={})
    @patch("silverquillm.cli.save_engine_final")
    @patch("silverquillm.cli.init_run_engine", return_value="/tmp/fake-engine")
    @patch("silverquillm.cli.init_results_dir", return_value="/tmp/fake-results")
    @patch("silverquillm.preflight.preflight_check")
    @patch("silverquillm.cli.load_card_specs")
    @patch("silverquillm.cli.load_config")
    def test_signal_handlers_restored_after_loop(
        self, mock_load_config, mock_load_specs, mock_preflight,
        mock_init_results, mock_init_engine, mock_save_engine,
        mock_agg, mock_save_summary, mock_signal
    ):
        """Original signal handlers should be restored after the card loop."""
        from click.testing import CliRunner
        from silverquillm.cli import main

        mock_load_config.return_value = self._make_config_mock()
        mock_load_specs.return_value = [
            {"name": "Card1", "card_dir_name": "001", "collector_number": "001"}
        ]

        sentinel_sigint = MagicMock(name="orig_sigint")
        sentinel_sigterm = MagicMock(name="orig_sigterm")

        # Registration calls return original handlers; restore calls don't matter
        mock_signal.side_effect = lambda sig, handler: {
            (signal.SIGINT, _interrupt_handler): sentinel_sigint,
            (signal.SIGTERM, _interrupt_handler): sentinel_sigterm,
        }.get((sig, handler), MagicMock())

        with patch("silverquillm.cli.AgentSession") as mock_agent_cls:
            mock_session = MagicMock()
            mock_session.run_card.side_effect = RuntimeError("skip")
            mock_session.run_dir = None
            mock_agent_cls.return_value = mock_session

            runner = CliRunner()
            runner.invoke(main, ["run", "--config", "fake.yaml"])

        # Check restoration calls exist
        restore_sigint = [
            c for c in mock_signal.call_args_list
            if len(c[0]) >= 2 and c[0][0] == signal.SIGINT and c[0][1] is sentinel_sigint
        ]
        restore_sigterm = [
            c for c in mock_signal.call_args_list
            if len(c[0]) >= 2 and c[0][0] == signal.SIGTERM and c[0][1] is sentinel_sigterm
        ]
        assert len(restore_sigint) >= 1, "SIGINT original handler should be restored"
        assert len(restore_sigterm) >= 1, "SIGTERM original handler should be restored"


# ---------------------------------------------------------------------------
# Tests for _active_session tracking and KeyboardInterrupt handling
# ---------------------------------------------------------------------------


class TestActiveSessionTracking:
    """Tests that _active_session is properly set and cleared."""

    def _make_config_mock(self):
        return MagicMock(
            set_code="TST", model_name="m", model_provider="p",
            timeout=60, card_filter=None, collectors=None,
            prototype=None, strategy=None,
            card_specs_dir="/fake/specs",
        )

    @patch("signal.signal", return_value=signal.SIG_DFL)
    @patch("silverquillm.cli.save_run_summary_v2")
    @patch("silverquillm.cli.aggregate_run", return_value={})
    @patch("silverquillm.cli.save_engine_final")
    @patch("silverquillm.cli.init_run_engine", return_value="/tmp/fake-engine")
    @patch("silverquillm.cli.init_results_dir", return_value="/tmp/fake-results")
    @patch("silverquillm.preflight.preflight_check")
    @patch("silverquillm.cli.load_card_specs")
    @patch("silverquillm.cli.load_config")
    @patch("silverquillm.cli.AgentSession")
    def test_active_session_cleared_in_finally(
        self, mock_agent_cls, mock_load_config, mock_load_specs,
        mock_preflight, mock_init_results, mock_init_engine,
        mock_save_engine, mock_agg, mock_save_summary, mock_signal
    ):
        """_active_session should be None after card processing (cleared in finally)."""
        from click.testing import CliRunner
        from silverquillm.cli import main

        mock_load_config.return_value = self._make_config_mock()
        mock_load_specs.return_value = [
            {"name": "TestCard", "card_dir_name": "001", "collector_number": "001"}
        ]
        mock_session = MagicMock()
        mock_session.run_card.side_effect = RuntimeError("test error")
        mock_session.run_dir = None
        mock_agent_cls.return_value = mock_session

        runner = CliRunner()
        runner.invoke(main, ["run", "--config", "fake.yaml"])

        assert cli_mod._active_session is None

    @patch("signal.signal", return_value=signal.SIG_DFL)
    @patch("silverquillm.cli.save_run_summary_v2")
    @patch("silverquillm.cli.aggregate_run", return_value={})
    @patch("silverquillm.cli.save_engine_final")
    @patch("silverquillm.cli.init_run_engine", return_value="/tmp/fake-engine")
    @patch("silverquillm.cli.init_results_dir", return_value="/tmp/fake-results")
    @patch("silverquillm.preflight.preflight_check")
    @patch("silverquillm.cli.load_card_specs")
    @patch("silverquillm.cli.load_config")
    @patch("silverquillm.cli.AgentSession")
    def test_keyboard_interrupt_breaks_loop_cleanly(
        self, mock_agent_cls, mock_load_config, mock_load_specs,
        mock_preflight, mock_init_results, mock_init_engine,
        mock_save_engine, mock_agg, mock_save_summary, mock_signal
    ):
        """KeyboardInterrupt during card loop should break cleanly, not crash."""
        from click.testing import CliRunner
        from silverquillm.cli import main

        mock_load_config.return_value = self._make_config_mock()
        mock_load_specs.return_value = [
            {"name": "Card1", "card_dir_name": "001", "collector_number": "001"},
            {"name": "Card2", "card_dir_name": "002", "collector_number": "002"},
        ]
        mock_session = MagicMock()
        mock_session.run_card.side_effect = KeyboardInterrupt()
        mock_session.run_dir = None
        mock_agent_cls.return_value = mock_session

        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", "fake.yaml"])

        # Should not propagate KeyboardInterrupt
        assert result.exception is None or not isinstance(
            result.exception, KeyboardInterrupt
        ), "KeyboardInterrupt should be caught, not propagated"
        assert cli_mod._active_session is None

    @patch("signal.signal", return_value=signal.SIG_DFL)
    @patch("silverquillm.cli.save_run_summary_v2")
    @patch("silverquillm.cli.aggregate_run", return_value={})
    @patch("silverquillm.cli.save_engine_final")
    @patch("silverquillm.cli.init_run_engine", return_value="/tmp/fake-engine")
    @patch("silverquillm.cli.init_results_dir", return_value="/tmp/fake-results")
    @patch("silverquillm.preflight.preflight_check")
    @patch("silverquillm.cli.load_card_specs")
    @patch("silverquillm.cli.load_config")
    @patch("silverquillm.cli.AgentSession")
    def test_keyboard_interrupt_stops_processing_remaining_cards(
        self, mock_agent_cls, mock_load_config, mock_load_specs,
        mock_preflight, mock_init_results, mock_init_engine,
        mock_save_engine, mock_agg, mock_save_summary, mock_signal
    ):
        """After KeyboardInterrupt, remaining cards should not be processed."""
        from click.testing import CliRunner
        from silverquillm.cli import main

        mock_load_config.return_value = self._make_config_mock()
        mock_load_specs.return_value = [
            {"name": "Card1", "card_dir_name": "001", "collector_number": "001"},
            {"name": "Card2", "card_dir_name": "002", "collector_number": "002"},
            {"name": "Card3", "card_dir_name": "003", "collector_number": "003"},
        ]
        mock_session = MagicMock()
        # First card raises KeyboardInterrupt
        mock_session.run_card.side_effect = KeyboardInterrupt()
        mock_session.run_dir = None
        mock_agent_cls.return_value = mock_session

        runner = CliRunner()
        runner.invoke(main, ["run", "--config", "fake.yaml"])

        # AgentSession constructor should only be called once (for Card1)
        # because the loop breaks after the interrupt
        assert mock_agent_cls.call_count == 1, (
            f"Expected 1 AgentSession creation (interrupted on first card), got {mock_agent_cls.call_count}"
        )
