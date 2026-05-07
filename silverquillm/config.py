"""Benchmark configuration loading and validation.

Loads YAML configuration files into a validated ``BenchmarkConfig`` dataclass.
"""

from __future__ import annotations

import warnings
import yaml
from dataclasses import dataclass, field, fields, MISSING
from pathlib import Path
from typing import Any


@dataclass
class AgentConfig:
    """Configuration for the agent adapter and its behaviour."""

    adapter: str = "opencode"
    max_test_rounds: int = 3
    timeout_per_card: int = 300
    disable_web_search: bool = True


# Names of AgentConfig fields, used for backward-compat lifting.
_AGENT_FIELD_NAMES = {f.name for f in fields(AgentConfig)}

# Legacy flat-key → AgentConfig field mapping (for backward compat).
_LEGACY_AGENT_ALIASES: dict[str, str] = {
    "agent_tool": "adapter",
}


@dataclass(init=False)
class BenchmarkConfig:
    """Configuration for a benchmark run.

    Agent-related fields (``adapter``, ``max_test_rounds``, ``timeout_per_card``,
    ``disable_web_search``) live inside a nested :class:`AgentConfig` accessible
    via the ``agent`` attribute.  For backward compatibility the legacy flat
    keywords (``agent_tool``, ``max_test_rounds``, ``timeout_per_card``,
    ``disable_web_search``) are still accepted by the constructor and exposed as
    properties that delegate to ``agent.*``.
    """

    name: str
    set_code: str
    model_name: str
    model_provider: str
    max_context: int = 200_000
    temperature: float = 0.0
    agent: AgentConfig = field(default_factory=AgentConfig)
    card_specs_dir: str = ""
    engine_docs_path: str = ""
    template_dir: str = ""
    output_dir: str = ""

    def __init__(
        self,
        name: str,
        set_code: str,
        model_name: str,
        model_provider: str,
        max_context: int = 200_000,
        temperature: float = 0.0,
        agent: AgentConfig | None = None,
        card_specs_dir: str = "",
        engine_docs_path: str = "",
        template_dir: str = "",
        output_dir: str = "",
        # Legacy flat kwargs (backward compat) -------------------------
        agent_tool: str | None = None,
        max_test_rounds: int | None = None,
        timeout_per_card: int | None = None,
        disable_web_search: bool | None = None,
    ) -> None:
        self.name = name
        self.set_code = set_code
        self.model_name = model_name
        self.model_provider = model_provider
        self.max_context = max_context
        self.temperature = temperature
        self.card_specs_dir = card_specs_dir
        self.engine_docs_path = engine_docs_path
        self.template_dir = template_dir
        self.output_dir = output_dir

        # Build AgentConfig: start from explicit nested, overlay legacy flat keys
        self.agent = agent if agent is not None else AgentConfig()

        if agent_tool is not None:
            self.agent.adapter = agent_tool
        if max_test_rounds is not None:
            self.agent.max_test_rounds = max_test_rounds
        if timeout_per_card is not None:
            self.agent.timeout_per_card = timeout_per_card
        if disable_web_search is not None:
            self.agent.disable_web_search = disable_web_search

    # ------------------------------------------------------------------
    # Backward-compatibility properties (deprecated, delegate to agent.*)
    # ------------------------------------------------------------------

    @property
    def agent_tool(self) -> str:
        """Deprecated: use ``agent.adapter`` instead."""
        return self.agent.adapter

    @agent_tool.setter
    def agent_tool(self, value: str) -> None:
        self.agent.adapter = value

    @property
    def max_test_rounds(self) -> int:
        """Deprecated: use ``agent.max_test_rounds`` instead."""
        return self.agent.max_test_rounds

    @max_test_rounds.setter
    def max_test_rounds(self, value: int) -> None:
        self.agent.max_test_rounds = value

    @property
    def timeout_per_card(self) -> int:
        """Deprecated: use ``agent.timeout_per_card`` instead."""
        return self.agent.timeout_per_card

    @timeout_per_card.setter
    def timeout_per_card(self, value: int) -> None:
        self.agent.timeout_per_card = value

    @property
    def disable_web_search(self) -> bool:
        """Deprecated: use ``agent.disable_web_search`` instead."""
        return self.agent.disable_web_search

    @disable_web_search.setter
    def disable_web_search(self, value: bool) -> None:
        self.agent.disable_web_search = value


# Fields that have no default and must be present in config YAML
_REQUIRED_FIELDS = {
    f.name for f in fields(BenchmarkConfig)
    if f.default is MISSING and f.default_factory is MISSING  # type: ignore[misc]
}


def _build_agent_config(raw: dict[str, Any]) -> AgentConfig:
    """Build an ``AgentConfig`` from the raw YAML dict.

    Supports three styles:
    1. Nested ``agent:`` block (preferred).
    2. Flat legacy keys (``agent_tool``, ``max_test_rounds``, …) at top level.
    3. A mix of both (nested wins on conflict).
    """
    agent_raw: dict[str, Any] = {}

    # Collect flat legacy keys
    for legacy_key, agent_field in _LEGACY_AGENT_ALIASES.items():
        if legacy_key in raw:
            agent_raw[agent_field] = raw[legacy_key]

    for fname in _AGENT_FIELD_NAMES:
        if fname in raw:
            agent_raw[fname] = raw[fname]

    # Overlay nested block (takes precedence)
    nested = raw.get("agent")
    if nested is not None and not isinstance(nested, dict):
        raise ValueError(
            f"agent config must be a mapping, got {type(nested).__name__}"
        )
    if isinstance(nested, dict):
        agent_raw.update(nested)

    # Filter to known AgentConfig fields
    known_agent = {f.name for f in fields(AgentConfig)}
    filtered = {k: v for k, v in agent_raw.items() if k in known_agent}
    return AgentConfig(**filtered)


def load_config(path: str) -> BenchmarkConfig:
    """Load and validate a YAML config file.

    Parameters
    ----------
    path:
        Filesystem path to a YAML configuration file.

    Returns
    -------
    BenchmarkConfig
        Validated configuration dataclass.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If required fields are missing from the YAML.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML mapping at the top level")

    missing = _REQUIRED_FIELDS - set(raw.keys())
    if missing:
        raise ValueError(f"Missing required config fields: {', '.join(sorted(missing))}")

    # Build nested AgentConfig
    agent_cfg = _build_agent_config(raw)

    # Filter to only known BenchmarkConfig dataclass fields (excluding agent-delegated ones)
    known = {f.name for f in fields(BenchmarkConfig)}
    # Exclude legacy flat keys and property-shadowed names
    skip_keys = _AGENT_FIELD_NAMES | set(_LEGACY_AGENT_ALIASES.keys())
    filtered = {k: v for k, v in raw.items() if k in known and k not in skip_keys}
    filtered["agent"] = agent_cfg

    return BenchmarkConfig(**filtered)
