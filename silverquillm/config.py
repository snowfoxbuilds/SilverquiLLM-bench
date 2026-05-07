"""Benchmark configuration loading and validation.

Loads YAML configuration files into a validated ``BenchmarkConfig`` dataclass.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field, fields, MISSING
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    name: str
    set_code: str
    model_name: str
    model_provider: str
    max_context: int = 200_000
    temperature: float = 0.0
    agent_tool: str = "opencode"
    max_test_rounds: int = 3
    timeout_per_card: int = 300
    disable_web_search: bool = True
    card_specs_dir: str = ""
    engine_docs_path: str = ""
    template_dir: str = ""
    output_dir: str = ""


# Fields that have no default and must be present in config YAML
_REQUIRED_FIELDS = {
    f.name for f in fields(BenchmarkConfig)
    if f.default is MISSING and f.default_factory is MISSING  # type: ignore[misc]
}


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

    # Filter to only known fields
    known = {f.name for f in fields(BenchmarkConfig)}
    filtered = {k: v for k, v in raw.items() if k in known}

    return BenchmarkConfig(**filtered)
