"""Tests for TODO item 11: Agent session manager.

Tests verify:
- AgentSession dataclass has required fields (card_name, workspace, config).
- BlindResult and TestInformedResult dataclasses have expected fields.
- setup_workspace copies card_spec.json, template.py, engine_api.md, rules_overview.md,
  base_classes.py into the workspace.
- run_card() delegates to CardStrategy and returns CardRunResult.
- run_blind / run_test_informed standalone wrappers delegate to run_card().
- cleanup removes the temp directory.
- Standalone functions match TODO contract names.
- Error handling: timeout, no workspace, etc.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from dataclasses import fields as dc_fields
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.agent_session import (
    AgentSession,
    BlindResult,
    TestInformedResult,
    cleanup,
    run_blind,
    run_test_informed,
    setup_workspace,
)
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.strategies import CardRunResult, CardRunStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> BenchmarkConfig:
    defaults = dict(
        name="test-bench",
        set_code="FDN",
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
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


@pytest.fixture()
def config():
    return _make_config()


@pytest.fixture()
def session(config, tmp_path):
    """Create a session with a fake card_dir containing card_spec.json."""
    card_dir = tmp_path / "card_data"
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
    sess = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
    yield sess
    # Safety cleanup in case test didn't
    sess.cleanup()


# ---------------------------------------------------------------------------
# AgentSession dataclass contract
# ---------------------------------------------------------------------------


class TestAgentSessionDataclass:
    """AgentSession must expose the four fields from the TODO spec."""

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(AgentSession)

    def test_card_name_property(self, session):
        assert session.card_name == "Grizzly Bears"

    def test_workspace_none_before_setup(self, session):
        assert session.workspace is None

    def test_config_field(self, session, config):
        assert session.config is config


# ---------------------------------------------------------------------------
# BlindResult / TestInformedResult dataclasses
# ---------------------------------------------------------------------------


class TestResultDataclasses:
    def test_blind_result_fields(self):
        field_names = {f.name for f in dc_fields(BlindResult)}
        assert {"impl_path", "tokens", "runtime_seconds", "peak_context", "status"} <= field_names

    def test_test_informed_result_fields(self):
        field_names = {f.name for f in dc_fields(TestInformedResult)}
        assert {
            "impl_path", "tests_path", "iterations", "tokens",
            "runtime_seconds", "peak_context", "rules_lookups", "status",
        } <= field_names


# ---------------------------------------------------------------------------
# setup_workspace
# ---------------------------------------------------------------------------


class TestSetupWorkspace:
    """setup_workspace must create a temp dir with required reference files."""

    def test_creates_workspace_directory(self, session):
        ws = session.setup_workspace()
        assert ws.is_dir()
        assert session.workspace == ws

    def test_copies_card_spec_json(self, session):
        ws = session.setup_workspace()
        spec_file = ws / "card_spec.json"
        assert spec_file.exists()
        loaded = json.loads(spec_file.read_text())
        assert loaded["name"] == "Grizzly Bears"

    def test_creates_template_py(self, session):
        ws = session.setup_workspace()
        template = ws / "template.py"
        assert template.exists()
        content = template.read_text()
        # Template should contain a class definition
        assert "class" in content.lower() or "def" in content.lower()

    def test_copies_engine_api_md(self, session):
        ws = session.setup_workspace()
        assert (ws / "engine_api.md").exists()

    def test_copies_rules_overview_md(self, session):
        ws = session.setup_workspace()
        assert (ws / "rules_overview.md").exists()

    def test_copies_base_classes_py(self, session):
        ws = session.setup_workspace()
        assert (ws / "base_classes.py").exists()

    def test_standalone_setup_workspace_returns_session(self, config, tmp_path):
        card_dir = tmp_path / "card_data"
        card_dir.mkdir()
        (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
        sess = setup_workspace(
            card_name="Grizzly Bears",
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(card_dir),
        )
        try:
            assert isinstance(sess, AgentSession)
            assert sess.workspace is not None
            assert sess.workspace.is_dir()
        finally:
            sess.cleanup()


# ---------------------------------------------------------------------------
# run_blind (delegates to run_card via strategy)
# ---------------------------------------------------------------------------


class TestRunBlind:
    """run_blind delegates to run_card() which uses the strategy pattern."""

    def test_returns_ok_when_impl_produced(self, session):
        ws = session.setup_workspace()

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[ws / "card_impl.py"],
            runtime_ms=100,
        )

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            result = run_blind(session)

        assert isinstance(result, BlindResult)
        assert result.status == "completed"
        assert result.impl_path is not None
        assert result.impl_path.name == "card_impl.py"

    def test_returns_ok_with_seeded_template_when_agent_does_nothing(self, session):
        """card_impl.py is pre-seeded as the template, so it always exists."""
        session.setup_workspace()

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            runtime_ms=50,
        )

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            result = run_blind(session)

        assert result.status == "completed"
        assert result.impl_path is not None
        assert result.impl_path.name == "card_impl.py"

    def test_returns_timeout_on_timeout(self, session):
        session.setup_workspace()

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.timeout,
            runtime_ms=300000,
        )

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            result = run_blind(session)

        assert result.status == "timeout"

    def test_raises_without_workspace(self, session):
        with pytest.raises(RuntimeError, match="[Ww]orkspace"):
            run_blind(session)

    def test_records_positive_runtime(self, session):
        session.setup_workspace()

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            runtime_ms=150,
        )

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            result = run_blind(session)

        assert result.runtime_seconds >= 0


# ---------------------------------------------------------------------------
# run_test_informed (delegates to run_card via strategy)
# ---------------------------------------------------------------------------


class TestRunTestInformed:
    """run_test_informed delegates to run_card() which uses the strategy pattern."""

    def test_returns_completed_when_strategy_completes(self, session):
        ws = session.setup_workspace()

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            runtime_ms=200,
        )
        (ws / "card_impl.py").write_text("x = 2\n")
        (ws / "tests.py").write_text("def test_pass(): pass\n")

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            result = run_test_informed(session, ws / "card_impl.py")

        assert isinstance(result, TestInformedResult)
        assert result.status == "completed"
        assert result.impl_path is not None

    def test_standalone_raises_without_workspace(self, session):
        with pytest.raises(RuntimeError, match="[Ww]orkspace"):
            run_test_informed(session, Path("/nonexistent"))

    def test_returns_timeout_on_timeout(self, session):
        session.setup_workspace()

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.timeout,
            runtime_ms=300000,
        )

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            result = run_test_informed(session, Path("/dummy"))

        assert result.status == "timeout"


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """cleanup must remove the temporary workspace directory."""

    def test_removes_workspace_dir(self, session):
        ws = session.setup_workspace()
        assert ws.exists()
        cleanup(session)
        assert not ws.exists()
        assert session.workspace is None

    def test_cleanup_idempotent(self, session):
        session.setup_workspace()
        cleanup(session)
        # Second call should not raise
        cleanup(session)

    def test_cleanup_without_setup(self, session):
        # Should not raise even if never set up
        cleanup(session)
