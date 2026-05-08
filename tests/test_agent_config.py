"""Tests for TODO item 2: Refactor BenchmarkConfig to use nested agent: block.

Tests verify:
- AgentConfig dataclass exists with correct fields and defaults.
- BenchmarkConfig embeds an AgentConfig via the ``agent`` attribute.
- load_config() correctly parses nested ``agent:`` YAML blocks.
- load_config() supports flat legacy keys in YAML for backward compat.
- Edge cases: missing agent block, partial agent block, nested overrides flat.
"""

from __future__ import annotations

import tempfile
import textwrap
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from silverquillm.config import AgentConfig, BenchmarkConfig, load_config


# Minimal valid top-level config (required fields only).
_MINIMAL_RAW = {
    "name": "test-run",
    "set_code": "SOS",
    "model_name": "test-model",
    "model_provider": "test-provider",
}


def _write_yaml(tmp_path: Path, content: str) -> Path:
    """Helper: write YAML content to a temp file and return the path."""
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------------------
# AgentConfig dataclass
# ---------------------------------------------------------------------------
class TestAgentConfig:
    """Tests for the AgentConfig dataclass itself."""

    def test_has_expected_fields(self) -> None:
        """AgentConfig must expose adapter, max_test_rounds, timeout_per_card, disable_web_search."""
        names = {f.name for f in dc_fields(AgentConfig)}
        assert names == {"adapter", "max_test_rounds", "timeout_per_card", "disable_web_search"}

    def test_default_adapter(self) -> None:
        """Default adapter should be 'opencode'."""
        cfg = AgentConfig()
        assert cfg.adapter == "opencode"

    def test_default_max_test_rounds(self) -> None:
        cfg = AgentConfig()
        assert cfg.max_test_rounds == 3

    def test_default_timeout_per_card(self) -> None:
        cfg = AgentConfig()
        assert cfg.timeout_per_card == 300

    def test_default_disable_web_search(self) -> None:
        cfg = AgentConfig()
        assert cfg.disable_web_search is True

    def test_custom_values(self) -> None:
        """AgentConfig accepts keyword overrides."""
        cfg = AgentConfig(adapter="custom", max_test_rounds=5, timeout_per_card=600, disable_web_search=False)
        assert cfg.adapter == "custom"
        assert cfg.max_test_rounds == 5
        assert cfg.timeout_per_card == 600
        assert cfg.disable_web_search is False


# ---------------------------------------------------------------------------
# BenchmarkConfig.agent field
# ---------------------------------------------------------------------------
class TestBenchmarkConfigAgent:
    """Tests that BenchmarkConfig embeds AgentConfig correctly."""

    def test_agent_field_exists_and_is_agent_config(self) -> None:
        """BenchmarkConfig must have an ``agent`` attribute of type AgentConfig."""
        cfg = BenchmarkConfig(**_MINIMAL_RAW)
        assert isinstance(cfg.agent, AgentConfig)

    def test_agent_defaults_when_not_specified(self) -> None:
        """When no agent info is supplied, defaults from AgentConfig should apply."""
        cfg = BenchmarkConfig(**_MINIMAL_RAW)
        assert cfg.agent.adapter == "opencode"
        assert cfg.agent.max_test_rounds == 3
        assert cfg.agent.timeout_per_card == 300
        assert cfg.agent.disable_web_search is True

    def test_explicit_agent_config_object(self) -> None:
        """Passing an AgentConfig directly should be used as-is."""
        ac = AgentConfig(adapter="myagent", max_test_rounds=10)
        cfg = BenchmarkConfig(**_MINIMAL_RAW, agent=ac)
        assert cfg.agent is ac
        assert cfg.agent.adapter == "myagent"
        assert cfg.agent.max_test_rounds == 10


# ---------------------------------------------------------------------------
# load_config() — nested agent: block
# ---------------------------------------------------------------------------
class TestLoadConfigNestedAgent:
    """Tests that load_config properly handles the nested agent: YAML block."""

    def test_nested_agent_block_parsed(self, tmp_path: Path) -> None:
        """A full nested agent: block should populate agent fields."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
            agent:
              adapter: custom-adapter
              max_test_rounds: 5
              timeout_per_card: 600
              disable_web_search: false
        """)
        cfg = load_config(str(p))
        assert cfg.agent.adapter == "custom-adapter"
        assert cfg.agent.max_test_rounds == 5
        assert cfg.agent.timeout_per_card == 600
        assert cfg.agent.disable_web_search is False

    def test_missing_agent_block_uses_defaults(self, tmp_path: Path) -> None:
        """When the agent: block is absent, AgentConfig defaults apply."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
        """)
        cfg = load_config(str(p))
        assert isinstance(cfg.agent, AgentConfig)
        assert cfg.agent.adapter == "opencode"
        assert cfg.agent.max_test_rounds == 3

    def test_partial_agent_block(self, tmp_path: Path) -> None:
        """A partial agent: block should fill in defaults for missing keys."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
            agent:
              adapter: partial-adapter
        """)
        cfg = load_config(str(p))
        assert cfg.agent.adapter == "partial-adapter"
        assert cfg.agent.max_test_rounds == 3  # default
        assert cfg.agent.timeout_per_card == 300  # default
        assert cfg.agent.disable_web_search is True  # default

    def test_flat_legacy_keys_in_yaml(self, tmp_path: Path) -> None:
        """Flat legacy keys at top level should still be lifted into AgentConfig."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
            agent_tool: legacy-tool
            max_test_rounds: 8
        """)
        cfg = load_config(str(p))
        assert cfg.agent.adapter == "legacy-tool"
        assert cfg.agent.max_test_rounds == 8

    def test_nested_block_overrides_flat_keys(self, tmp_path: Path) -> None:
        """When both flat and nested keys exist, nested should take precedence."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
            agent_tool: old-tool
            agent:
              adapter: new-tool
        """)
        cfg = load_config(str(p))
        assert cfg.agent.adapter == "new-tool"

    def test_config_example_yaml_loads(self) -> None:
        """config.example.yaml should be loadable and use the nested agent block."""
        example = Path(__file__).resolve().parent.parent / "config.example.yaml"
        if not example.exists():
            pytest.skip("config.example.yaml not found")
        cfg = load_config(str(example))
        assert isinstance(cfg.agent, AgentConfig)
        assert cfg.agent.adapter == "opencode"

    def test_non_agent_fields_unaffected(self, tmp_path: Path) -> None:
        """Top-level non-agent fields should still load correctly alongside nested agent."""
        p = _write_yaml(tmp_path, """\
            name: run1
            set_code: SOS
            model_name: m1
            model_provider: p1
            max_context: 100000
            temperature: 0.5
            agent:
              adapter: x
        """)
        cfg = load_config(str(p))
        assert cfg.max_context == 100000
        assert cfg.temperature == 0.5
        assert cfg.agent.adapter == "x"
