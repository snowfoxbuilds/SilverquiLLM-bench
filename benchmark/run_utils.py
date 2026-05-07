"""Utility helpers for the benchmark run orchestration loop.

Provides ``_session_results_to_dicts`` for converting agent session result
dataclasses to plain dicts suitable for ``save_card_result``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from benchmark.agent_session import BlindResult, TestInformedResult
from benchmark.config import BenchmarkConfig


def _session_results_to_dicts(
    blind: BlindResult,
    tested: TestInformedResult | None,
    spec: dict[str, Any],
    config: BenchmarkConfig,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert result dataclasses to dicts for ``save_card_result``.

    Reads source code from the file paths stored in the result objects.
    Must be called **before** ``session.cleanup()`` destroys the workspace.

    Parameters
    ----------
    blind:
        Result from the blind implementation phase.
    tested:
        Result from the test-informed phase (may be *None* if skipped).
    spec:
        The card specification dict.
    config:
        Benchmark configuration.

    Returns
    -------
    tuple[dict, dict]
        ``(blind_result_dict, test_result_dict)`` ready for
        :func:`benchmark.results.save_card_result`.
    """
    blind_dict: dict[str, Any] = {
        "status": blind.status,
        "tokens": blind.tokens,
        "runtime_seconds": blind.runtime_seconds,
        "peak_context": blind.peak_context,
        "agent": config.agent_tool,
        "model": config.model_name,
        "complexity_tier": spec.get("tier", "unknown"),
        "impl_source": _read_source(blind.impl_path),
    }

    test_dict: dict[str, Any] = {}
    if tested is not None:
        test_dict = {
            "status": tested.status,
            "tokens": tested.tokens,
            "runtime_seconds": tested.runtime_seconds,
            "peak_context": tested.peak_context,
            "iterations": tested.iterations,
            "rules_lookups": tested.rules_lookups,
            "agent": config.agent_tool,
            "model": config.model_name,
            "complexity_tier": spec.get("tier", "unknown"),
            "impl_source": _read_source(tested.impl_path),
            "tests_source": _read_source(tested.tests_path),
        }

    return blind_dict, test_dict


def _read_source(path: Path | None) -> str:
    """Read source code from a path, returning empty string if unavailable."""
    if path is None:
        return ""
    try:
        return Path(path).read_text()
    except (OSError, IOError):
        return ""
