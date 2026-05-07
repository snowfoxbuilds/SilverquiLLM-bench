"""Tests for TODO item 9: AgentSession uses AgentAdapter.

Verifies that agent_session.py delegates to the adapter pattern rather than
hardcoding OpenCode-specific subprocess logic.
"""

from __future__ import annotations

import inspect
from dataclasses import fields as dc_fields
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.adapters import AgentAdapter, register_adapter
from silverquillm.agent_session import AgentSession
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(adapter_name: str = "mock_test_adapter", **overrides) -> BenchmarkConfig:
    defaults = dict(
        name="test-bench",
        set_code="FDN",
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
        agent=AgentConfig(
            adapter=adapter_name,
            max_test_rounds=3,
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


class MockAdapter(AgentAdapter):
    """A simple mock adapter for testing adapter integration."""

    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__(config)
        self.setup_called = False
        self.teardown_called = False
        self.run_calls: list[tuple[str, Path]] = []
        self.run_return = "mock agent output"

    def setup(self) -> None:
        self.setup_called = True

    def teardown(self) -> None:
        self.teardown_called = True

    def run(self, prompt: str, workspace: Path) -> str:
        self.run_calls.append((prompt, workspace))
        return self.run_return


@pytest.fixture(autouse=True)
def _register_mock_adapter():
    """Register and unregister the mock adapter for each test."""
    from silverquillm.adapters.base import _ADAPTER_REGISTRY
    _ADAPTER_REGISTRY["mock_test_adapter"] = MockAdapter
    yield
    _ADAPTER_REGISTRY.pop("mock_test_adapter", None)


@pytest.fixture()
def session(tmp_path):
    """Create a session with a fake card_dir containing card_spec.json."""
    import json
    card_dir = tmp_path / "card_data"
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
    config = _make_config()
    return AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))


# ---------------------------------------------------------------------------
# Tests: Adapter resolution
# ---------------------------------------------------------------------------

class TestAdapterResolution:
    """AgentSession resolves adapters via get_adapter, not hardcoded logic."""

    def test_get_adapter_returns_registered_adapter(self, session):
        """_get_adapter() should resolve to the adapter from the registry."""
        adapter = session._get_adapter()
        assert isinstance(adapter, MockAdapter)

    def test_get_adapter_uses_config_adapter_name(self, tmp_path):
        """The adapter is resolved from config.agent.adapter."""
        import json
        from silverquillm.adapters.base import _ADAPTER_REGISTRY

        class AnotherAdapter(AgentAdapter):
            def setup(self): pass
            def teardown(self): pass
            def run(self, prompt, workspace): return "another"

        _ADAPTER_REGISTRY["another_test"] = AnotherAdapter
        try:
            card_dir = tmp_path / "card_data"
            card_dir.mkdir()
            (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
            config = _make_config(adapter_name="another_test")
            sess = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
            adapter = sess._get_adapter()
            assert isinstance(adapter, AnotherAdapter)
        finally:
            _ADAPTER_REGISTRY.pop("another_test", None)

    def test_adapter_is_lazily_created(self, session):
        """Adapter should not exist until first access."""
        assert session._adapter is None
        session._get_adapter()
        assert session._adapter is not None

    def test_adapter_is_cached(self, session):
        """Subsequent calls to _get_adapter return the same instance."""
        a1 = session._get_adapter()
        a2 = session._get_adapter()
        assert a1 is a2


# ---------------------------------------------------------------------------
# Tests: Adapter lifecycle (setup / teardown)
# ---------------------------------------------------------------------------

class TestAdapterLifecycle:
    """setup_workspace calls adapter.setup(); cleanup calls adapter.teardown()."""

    def test_setup_workspace_calls_adapter_setup(self, session):
        """setup_workspace must call adapter.setup()."""
        with patch("silverquillm.agent_session.generate_template", return_value="# template"):
            session.setup_workspace()
        adapter = session._adapter
        assert isinstance(adapter, MockAdapter)
        assert adapter.setup_called is True

    def test_cleanup_calls_adapter_teardown(self, session):
        """cleanup must call adapter.teardown()."""
        with patch("silverquillm.agent_session.generate_template", return_value="# template"):
            session.setup_workspace()
        adapter = session._adapter
        session.cleanup()
        assert adapter.teardown_called is True

    def test_cleanup_sets_adapter_to_none(self, session):
        """After cleanup, _adapter should be reset to None."""
        with patch("silverquillm.agent_session.generate_template", return_value="# template"):
            session.setup_workspace()
        session.cleanup()
        assert session._adapter is None

    def test_cleanup_without_adapter_does_not_crash(self, session):
        """cleanup should be safe to call even if adapter was never created."""
        # No setup_workspace called, so _adapter is None
        session.cleanup()  # Should not raise

    def test_teardown_exception_is_swallowed(self, session):
        """If adapter.teardown() raises, cleanup should still complete."""
        with patch("silverquillm.agent_session.generate_template", return_value="# template"):
            session.setup_workspace()
        adapter = session._adapter
        adapter.teardown = MagicMock(side_effect=RuntimeError("teardown boom"))
        # Should not raise
        session.cleanup()
        assert session._adapter is None


# ---------------------------------------------------------------------------
# Tests: Agent invocation via adapter
# ---------------------------------------------------------------------------

class TestAdapterInvocation:
    """_run_opencode delegates to adapter.run(), not subprocess."""

    def test_run_opencode_delegates_to_adapter_run(self, session, tmp_path):
        """_run_opencode should call adapter.run(prompt, workspace)."""
        adapter = MockAdapter(session.config)
        session._adapter = adapter
        workspace = tmp_path / "ws"
        workspace.mkdir()
        result = session._run_opencode("hello prompt", workspace)
        assert result == "mock agent output"
        assert len(adapter.run_calls) == 1
        assert adapter.run_calls[0] == ("hello prompt", workspace)

    def test_run_opencode_does_not_call_subprocess(self, session, tmp_path):
        """Adapter-based _run_opencode must not use subprocess.run/Popen."""
        adapter = MockAdapter(session.config)
        session._adapter = adapter
        workspace = tmp_path / "ws"
        workspace.mkdir()
        with patch("subprocess.run", side_effect=AssertionError("subprocess.run should not be called")), \
             patch("subprocess.Popen", side_effect=AssertionError("Popen should not be called")):
            session._run_opencode("test", workspace)

    def test_run_blind_uses_adapter(self, session):
        """run_blind_implementation should use the adapter for agent invocation."""
        with patch("silverquillm.agent_session.generate_template", return_value="# template"):
            workspace = session.setup_workspace()
        adapter = session._adapter
        # Create a blind_impl.py so the result is "ok"
        (workspace / "blind_impl.py").write_text("# impl")
        result = session.run_blind_implementation(workspace)
        assert len(adapter.run_calls) >= 1

    def test_adapter_run_error_propagates(self, session, tmp_path):
        """If adapter.run() raises, it should propagate from _run_opencode."""
        class FailingAdapter(MockAdapter):
            def run(self, prompt, workspace):
                raise RuntimeError("agent failed")

        session._adapter = FailingAdapter(session.config)
        workspace = tmp_path / "ws"
        workspace.mkdir()
        with pytest.raises(RuntimeError, match="agent failed"):
            session._run_opencode("prompt", workspace)


# ---------------------------------------------------------------------------
# Tests: No hardcoded OpenCode logic remains in session flow
# ---------------------------------------------------------------------------

class TestNoHardcodedOpenCode:
    """AgentSession should be adapter-agnostic for invocation."""

    def test_run_opencode_method_delegates_to_adapter(self, session):
        """_run_opencode body should use adapter.run, not subprocess calls."""
        import silverquillm.agent_session as mod
        source = inspect.getsource(mod.AgentSession._run_opencode)
        # Must reference the adapter
        assert "self._get_adapter" in source or "adapter.run" in source
        # Must not directly invoke subprocess.run or subprocess.Popen
        assert "subprocess.run(" not in source
        assert "subprocess.Popen(" not in source

    def test_adapter_field_exists_on_session(self, session):
        """AgentSession should have an _adapter field."""
        field_names = {f.name for f in dc_fields(session)}
        assert "_adapter" in field_names

    def test_session_imports_adapter_module(self):
        """agent_session.py should import from silverquillm.adapters."""
        import silverquillm.agent_session as mod
        source = inspect.getsource(mod)
        assert "from silverquillm.adapters import" in source


# ---------------------------------------------------------------------------
# Tests: Mock adapter works end-to-end
# ---------------------------------------------------------------------------

class TestMockAdapterEndToEnd:
    """Session works with any adapter implementing the interface."""

    def test_full_blind_run_with_mock_adapter(self, session):
        """Complete blind implementation flow using mock adapter."""
        with patch("silverquillm.agent_session.generate_template", return_value="# template"):
            workspace = session.setup_workspace()

        adapter = session._adapter
        assert adapter.setup_called is True

        # Simulate agent creating the implementation file
        adapter.run_return = "done"
        (workspace / "blind_impl.py").write_text("class Card: pass")

        result = session.run_blind_implementation(workspace)
        assert result.status == "ok"
        assert len(adapter.run_calls) >= 1

        session.cleanup()
        assert adapter.teardown_called is True
