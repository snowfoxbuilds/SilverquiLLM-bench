"""Tests for TODO item 3: All BenchmarkConfig consumers use nested agent config.

Verifies that:
- No source modules access old flat config attributes (agent_tool, max_test_rounds,
  timeout_per_card, disable_web_search) directly on BenchmarkConfig.
- Deprecated backward-compat properties have been removed from BenchmarkConfig.
- BenchmarkConfig construction uses agent=AgentConfig(...) properly.
- Key consumer modules (agent_session, run_utils) access config.agent.* correctly.
"""

from __future__ import annotations

import ast
import re
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from silverquillm.config import AgentConfig, BenchmarkConfig


# Root of the silverquillm package
_PKG_DIR = Path(__file__).resolve().parent.parent / "silverquillm"

# Minimal kwargs to construct a valid BenchmarkConfig
_MINIMAL = dict(
    name="test",
    set_code="SOS",
    model_name="m",
    model_provider="p",
)

# Old flat attribute names that should NOT appear as direct BenchmarkConfig attributes
_OLD_FLAT_ATTRS = ["agent_tool", "max_test_rounds", "timeout_per_card", "disable_web_search"]


# ---------------------------------------------------------------------------
# Deprecated properties removed
# ---------------------------------------------------------------------------
class TestDeprecatedPropertiesRemoved:
    """Backward-compat properties must no longer exist on BenchmarkConfig."""

    @pytest.mark.parametrize("attr", _OLD_FLAT_ATTRS)
    def test_flat_attr_not_on_benchmark_config(self, attr: str) -> None:
        """BenchmarkConfig instances must not expose '{attr}' as a direct attribute."""
        cfg = BenchmarkConfig(**_MINIMAL)
        assert not hasattr(cfg, attr), (
            f"BenchmarkConfig still exposes deprecated attribute '{attr}'"
        )

    @pytest.mark.parametrize("attr", _OLD_FLAT_ATTRS)
    def test_flat_attr_not_class_level(self, attr: str) -> None:
        """BenchmarkConfig class must not have a property or descriptor for '{attr}'."""
        assert not hasattr(BenchmarkConfig, attr), (
            f"BenchmarkConfig class still defines '{attr}' (property/descriptor)"
        )


# ---------------------------------------------------------------------------
# BenchmarkConfig construction uses agent=AgentConfig(...)
# ---------------------------------------------------------------------------
class TestBenchmarkConfigConstruction:
    """BenchmarkConfig must accept agent=AgentConfig(...) and reject old flat kwargs."""

    def test_construct_with_agent_config(self) -> None:
        """Passing agent=AgentConfig(...) should set config.agent properly."""
        ac = AgentConfig(adapter="custom", max_test_rounds=7, timeout_per_card=120)
        cfg = BenchmarkConfig(**_MINIMAL, agent=ac)
        assert cfg.agent is ac
        assert cfg.agent.adapter == "custom"
        assert cfg.agent.max_test_rounds == 7
        assert cfg.agent.timeout_per_card == 120

    def test_default_agent_config_when_omitted(self) -> None:
        """Omitting agent= should provide default AgentConfig."""
        cfg = BenchmarkConfig(**_MINIMAL)
        assert isinstance(cfg.agent, AgentConfig)
        assert cfg.agent.adapter == "opencode"
        assert cfg.agent.max_test_rounds == 3

    def test_old_flat_kwargs_rejected(self) -> None:
        """Passing old flat kwargs (agent_tool, max_test_rounds, etc.) to BenchmarkConfig must raise TypeError."""
        with pytest.raises(TypeError):
            BenchmarkConfig(**_MINIMAL, agent_tool="foo")  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            BenchmarkConfig(**_MINIMAL, max_test_rounds=5)  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            BenchmarkConfig(**_MINIMAL, timeout_per_card=60)  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            BenchmarkConfig(**_MINIMAL, disable_web_search=False)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Source-code audit: no old flat config access in silverquillm/
# ---------------------------------------------------------------------------
class TestNoOldFlatAccessInSource:
    """Scan silverquillm/ source files to ensure no code accesses config.<old_attr> directly."""

    # Patterns like `config.agent_tool`, `self.config.agent_tool`, etc.
    # We look for `.agent_tool`, `.max_test_rounds`, `.timeout_per_card`, `.disable_web_search`
    # as attribute access *not* inside `config.agent.<attr>`.
    _OLD_ACCESS_PATTERNS = [
        # Matches `.agent_tool` NOT preceded by `.agent`
        re.compile(r'(?<!agent)\.agent_tool\b'),
        # Matches `.max_test_rounds` NOT preceded by `.agent`
        re.compile(r'(?<!agent)\.max_test_rounds\b'),
        # Matches `.timeout_per_card` NOT preceded by `.agent`
        re.compile(r'(?<!agent)\.timeout_per_card\b'),
        # Matches `.disable_web_search` NOT preceded by `.agent`
        re.compile(r'(?<!agent)\.disable_web_search\b'),
    ]

    def _source_files(self) -> list[Path]:
        """Return all .py files in the silverquillm package (excluding config.py field definitions)."""
        return sorted(_PKG_DIR.glob("*.py"))

    def test_no_flat_config_access_outside_config_module(self) -> None:
        """No module in silverquillm/ (except config.py internals) should use config.<old_attr>."""
        violations: list[str] = []
        for py_file in self._source_files():
            if py_file.name == "config.py":
                # config.py defines fields in AgentConfig; those lines are fine.
                # Only check for property definitions or backward-compat shims.
                continue
            content = py_file.read_text()
            for pattern in self._OLD_ACCESS_PATTERNS:
                for match in pattern.finditer(content):
                    # Find line number
                    line_no = content[:match.start()].count("\n") + 1
                    violations.append(
                        f"{py_file.name}:{line_no}: {match.group()}"
                    )
        assert not violations, (
            "Found old flat config access patterns in source:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# Key consumers: agent_session.py uses config.agent.*
# ---------------------------------------------------------------------------
class TestAgentSessionConsumer:
    """Verify agent_session.py accesses agent config via config.agent.*."""

    def test_agent_session_uses_nested_timeout(self) -> None:
        """agent_session.py should reference config.agent.timeout_per_card."""
        source = (_PKG_DIR / "agent_session.py").read_text()
        assert "config.agent.timeout_per_card" in source or "self.config.agent.timeout_per_card" in source

    def test_agent_session_uses_nested_max_test_rounds(self) -> None:
        """agent_session.py should reference config.agent.max_test_rounds."""
        source = (_PKG_DIR / "agent_session.py").read_text()
        assert "config.agent.max_test_rounds" in source or "self.config.agent.max_test_rounds" in source


# ---------------------------------------------------------------------------
# Key consumers: run_utils.py uses config.agent.*
# ---------------------------------------------------------------------------
class TestRunUtilsConsumer:
    """Verify run_utils.py accesses agent config via config.agent.*."""

    def test_run_utils_uses_nested_adapter(self) -> None:
        """run_utils.py should reference config.agent.adapter (not config.agent_tool)."""
        source = (_PKG_DIR / "run_utils.py").read_text()
        assert "config.agent.adapter" in source
        # Must NOT use old flat access
        assert "config.agent_tool" not in source


# ---------------------------------------------------------------------------
# AgentConfig fields accessible via config.agent
# ---------------------------------------------------------------------------
class TestNestedAccessWorks:
    """Verify that all agent fields are accessible via config.agent.<field>."""

    def test_all_agent_fields_accessible(self) -> None:
        """Every AgentConfig field should be accessible through config.agent.<field>."""
        ac = AgentConfig(adapter="test-adapter", max_test_rounds=5, timeout_per_card=120, disable_web_search=False)
        cfg = BenchmarkConfig(**_MINIMAL, agent=ac)
        assert cfg.agent.adapter == "test-adapter"
        assert cfg.agent.max_test_rounds == 5
        assert cfg.agent.timeout_per_card == 120
        assert cfg.agent.disable_web_search is False

    def test_agent_field_names_match_expected(self) -> None:
        """AgentConfig should have exactly the expected fields."""
        names = {f.name for f in dc_fields(AgentConfig)}
        assert names == {"adapter", "max_test_rounds", "timeout_per_card", "disable_web_search"}
