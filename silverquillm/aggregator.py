"""Run-level result aggregation.

After post-run evaluation completes, aggregates all per-card ``result.json``
files into a single ``run_summary.json`` at the run level.

Public API:

- ``RunSummary`` — dataclass holding the full run summary.
- ``aggregate_run`` — pure function that reads card results and produces a summary.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from silverquillm.results import load_card_result

logger = logging.getLogger(__name__)

__all__ = [
    "RunSummary",
    "TierBreakdown",
    "CardSummary",
    "aggregate_run",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TierBreakdown:
    """Per-complexity-tier statistics."""

    tier: str
    card_count: int = 0
    completed_count: int = 0
    avg_audited_pass_rate: float = 0.0


@dataclass
class CardSummary:
    """Per-card summary entry."""

    card_id: str
    status: str
    self_eval_pass_rate: float | None = None
    audited_eval_pass_rate: float | None = None


@dataclass
class RunSummary:
    """Full run-level summary aggregating all per-card results."""

    # Run metadata
    run_id: str = ""
    model_name: str = ""
    adapter: str = ""
    mode: str = ""
    timestamp: str = ""
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    # Scorecard
    total_cards: int = 0
    cards_completed: int = 0
    cards_timeout: int = 0
    cards_no_output: int = 0

    # Per-tier breakdown
    tier_breakdown: list[TierBreakdown] = field(default_factory=list)

    # Aggregate stats
    total_tokens: int = 0
    total_runtime_ms: float = 0.0
    avg_tokens_per_card: float = 0.0
    avg_runtime_per_card: float = 0.0

    # Per-card summaries
    card_summaries: list[CardSummary] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pass_rate(eval_dict: dict[str, Any] | None) -> float | None:
    """Compute pass rate from an eval dict with passed/total keys."""
    if eval_dict is None:
        return None
    total = eval_dict.get("total", 0)
    if total == 0:
        return None
    passed = eval_dict.get("passed", 0)
    return passed / total


def _extract_tokens(impl: dict[str, Any]) -> int:
    """Extract total token count from implementation dict.

    Handles both dict shape ``{"input": N, "output": M, "total": T}``
    and plain integer (legacy / EvalResultV2 serialization).
    """
    tokens = impl.get("tokens")
    if tokens is None:
        return 0
    if isinstance(tokens, int):
        return tokens
    if isinstance(tokens, dict):
        return tokens.get("total", 0)
    return 0


def _extract_runtime_ms(impl: dict[str, Any]) -> float:
    """Extract runtime_ms from implementation dict."""
    return impl.get("runtime_ms", 0.0)


# Legacy status values that should be treated as "completed".
_COMPLETED_ALIASES: frozenset[str] = frozenset({"completed", "ok", "success"})


def _normalize_status(status: str) -> str:
    """Normalize legacy status strings to canonical values.

    ``"ok"`` and ``"success"`` (from v1 results) are mapped to ``"completed"``.
    All other values pass through unchanged.
    """
    if status in _COMPLETED_ALIASES:
        return "completed"
    return status


def _derive_timestamp(run_dir: Path) -> str:
    """Derive a deterministic timestamp from the most recent result.json mtime.

    Returns an ISO-8601 UTC string, or empty string if no result files exist.
    """
    cards_dir = run_dir / "cards"
    latest_mtime: float = 0.0
    if cards_dir.exists():
        for result_file in cards_dir.rglob("result.json"):
            mtime = result_file.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime
    if latest_mtime == 0.0:
        return ""
    return datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Core aggregation
# ---------------------------------------------------------------------------


def aggregate_run(run_dir: Path) -> RunSummary:
    """Aggregate all per-card ``result.json`` files into a :class:`RunSummary`.

    Pure function: reads from ``run_dir/cards/*/result.json`` and produces
    a summary.  Does *not* write any files — callers decide persistence.

    Parameters
    ----------
    run_dir:
        Path to the run directory containing a ``cards/`` subdirectory.

    Returns
    -------
    RunSummary
        The aggregated summary.
    """
    cards_dir = run_dir / "cards"
    card_results: list[dict[str, Any]] = []

    if cards_dir.exists():
        for card_path in sorted(cards_dir.iterdir()):
            if not card_path.is_dir():
                continue
            try:
                result = load_card_result(card_path)
                card_results.append(result)
            except FileNotFoundError:
                logger.debug("No result.json in %s, skipping", card_path)
            except Exception:
                logger.warning("Failed to load result.json from %s", card_path, exc_info=True)

    # -- Run metadata (inferred from first card or run_dir name) --
    run_id = run_dir.name
    model_name = ""
    adapter = ""
    mode = ""
    if card_results:
        first = card_results[0]
        model_name = first.get("model_name", "")
        adapter = first.get("adapter", "")
        mode = first.get("mode", "")

    # Try to load config snapshot if present
    config_snapshot: dict[str, Any] = {}
    config_path = run_dir / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            config_snapshot = yaml.safe_load(config_path.read_text()) or {}
        except Exception:
            pass
    # Also try config.json
    config_json_path = run_dir / "config.json"
    if not config_snapshot and config_json_path.exists():
        try:
            config_snapshot = json.loads(config_json_path.read_text())
        except Exception:
            pass

    # -- Normalize statuses in-place for consistent counting --
    for r in card_results:
        raw_status = r.get("status", "unknown")
        r["status"] = _normalize_status(raw_status)

    # -- Scorecard --
    total_cards = len(card_results)
    cards_completed = sum(1 for r in card_results if r.get("status") == "completed")
    cards_timeout = sum(1 for r in card_results if r.get("status") == "timeout")
    cards_no_output = sum(1 for r in card_results if r.get("status") == "no_output")

    # -- Per-tier breakdown --
    tier_data: dict[str, dict[str, Any]] = {}
    for r in card_results:
        tier = r.get("complexity_tier", "unknown")
        if tier not in tier_data:
            tier_data[tier] = {"card_count": 0, "completed_count": 0, "audited_rates": []}
        tier_data[tier]["card_count"] += 1
        if r.get("status") == "completed":
            tier_data[tier]["completed_count"] += 1
        audited_rate = _pass_rate(r.get("audited_eval"))
        if audited_rate is not None:
            tier_data[tier]["audited_rates"].append(audited_rate)

    tier_breakdown = []
    for tier_name in sorted(tier_data):
        td = tier_data[tier_name]
        rates = td["audited_rates"]
        avg_rate = sum(rates) / len(rates) if rates else 0.0
        tier_breakdown.append(
            TierBreakdown(
                tier=tier_name,
                card_count=td["card_count"],
                completed_count=td["completed_count"],
                avg_audited_pass_rate=avg_rate,
            )
        )

    # -- Aggregate stats --
    total_tokens = 0
    total_runtime_ms = 0.0
    for r in card_results:
        impl = r.get("implementation", {})
        total_tokens += _extract_tokens(impl)
        total_runtime_ms += _extract_runtime_ms(impl)

    avg_tokens = total_tokens / total_cards if total_cards > 0 else 0.0
    avg_runtime = total_runtime_ms / total_cards if total_cards > 0 else 0.0

    # -- Per-card summaries --
    card_summaries = []
    for r in card_results:
        card_id = r.get("card_id", "")
        status = r.get("status", "unknown")
        self_rate = _pass_rate(r.get("self_eval"))
        audited_rate = _pass_rate(r.get("audited_eval"))
        card_summaries.append(
            CardSummary(
                card_id=card_id,
                status=status,
                self_eval_pass_rate=self_rate,
                audited_eval_pass_rate=audited_rate,
            )
        )

    timestamp = _derive_timestamp(run_dir)

    return RunSummary(
        run_id=run_id,
        model_name=model_name,
        adapter=adapter,
        mode=mode,
        timestamp=timestamp,
        config_snapshot=config_snapshot,
        total_cards=total_cards,
        cards_completed=cards_completed,
        cards_timeout=cards_timeout,
        cards_no_output=cards_no_output,
        tier_breakdown=tier_breakdown,
        total_tokens=total_tokens,
        total_runtime_ms=total_runtime_ms,
        avg_tokens_per_card=avg_tokens,
        avg_runtime_per_card=avg_runtime,
        card_summaries=card_summaries,
    )


def save_run_summary_v2(run_dir: Path, summary: RunSummary) -> Path:
    """Persist a :class:`RunSummary` as ``run_summary.json``.

    Parameters
    ----------
    run_dir:
        The run directory.
    summary:
        The aggregated summary to write.

    Returns
    -------
    Path
        Path to the written ``run_summary.json``.
    """
    out_path = run_dir / "run_summary.json"
    data = asdict(summary)
    out_path.write_text(json.dumps(data, indent=2))
    return out_path
