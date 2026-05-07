"""Result recording and output artifact generation.

Writes benchmark results to a per-run directory structure under
``benchmarks/sos/results/``.  Each run gets its own folder so results
from different models or re-runs never collide.

Public API:
- ``generate_run_name`` — create a unique run folder name from config.
- ``init_results_dir`` — set up the per-run directory tree.
- ``save_card_result`` — persist a single card's evaluation artifacts.
- ``save_run_summary`` — write ``summary.json`` for the run.
- ``save_aggregates`` — write cross-run aggregates to the parent results dir.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from silverquillm.config import BenchmarkConfig
from silverquillm.evaluator import EvalResult
from silverquillm.scorer import Leaderboard, generate_leaderboard

__all__ = [
    "generate_run_name",
    "init_results_dir",
    "save_card_result",
    "save_run_summary",
    "save_aggregates",
]

# Default base directory for SOS benchmark results
_DEFAULT_RESULTS_BASE = Path("benchmarks/sos/results")


# ---------------------------------------------------------------------------
# Run naming
# ---------------------------------------------------------------------------


def generate_run_name(config: BenchmarkConfig) -> str:
    """Return a unique run name from the config's model name and current time.

    Format: ``{model_name}_{ISO-timestamp}`` where the timestamp uses
    ``-`` as time separators (colons are filesystem-unfriendly).

    Example: ``claude-sonnet-4_2026-04-28T18-30``

    The *config.output_dir* field is **not** used here — it controls the
    parent directory in :func:`init_results_dir`.  The ``run_name`` parameter
    on ``init_results_dir`` is the proper override mechanism.
    """
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H-%M")
    return f"{config.model_name}_{ts}"


# ---------------------------------------------------------------------------
# Directory initialisation
# ---------------------------------------------------------------------------


def init_results_dir(
    config: BenchmarkConfig,
    run_name: str | None = None,
    *,
    base_dir: Path | None = None,
) -> Path:
    """Create the per-run results directory tree.

    Layout::

        {base_dir}/{run_name}/
        ├── config.yaml
        └── cards/

    Parameters
    ----------
    config:
        The benchmark configuration — serialised as ``config.yaml``.
    run_name:
        Explicit run name.  When *None*, :func:`generate_run_name` is used.
    base_dir:
        Override the parent results directory.  Defaults to
        ``benchmarks/sos/results/``.

    Returns
    -------
    Path
        The created run directory.
    """
    if run_name is None:
        run_name = generate_run_name(config)

    if base_dir is not None:
        results_base = base_dir
    elif config.output_dir:
        results_base = Path(config.output_dir)
    else:
        results_base = _DEFAULT_RESULTS_BASE
    run_dir = results_base / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    cards_dir = run_dir / "cards"
    cards_dir.mkdir(exist_ok=True)

    # Write config snapshot
    config_dict = {
        f.name: getattr(config, f.name)
        for f in config.__dataclass_fields__.values()
    }
    # Convert nested dataclasses (e.g. AgentConfig) to plain dicts for safe YAML
    for key, val in config_dict.items():
        if hasattr(val, "__dataclass_fields__"):
            config_dict[key] = asdict(val)
    config_path = run_dir / "config.yaml"
    config_path.write_text(yaml.dump(config_dict, default_flow_style=False))

    return run_dir


# ---------------------------------------------------------------------------
# Per-card result saving
# ---------------------------------------------------------------------------


def save_card_result(
    run_dir: Path,
    card_id: str,
    blind_result: dict[str, Any] | None = None,
    test_result: dict[str, Any] | None = None,
    eval_results: list[EvalResult] | list[dict[str, Any]] | None = None,
) -> Path:
    """Write all artifacts for a single card evaluation.

    Layout::

        cards/{card_id}/
        ├── blind_impl.py
        ├── tested_impl.py
        ├── tests.py
        ├── iterations/   (iteration_1/, iteration_2/, …)
        └── result.json

    Parameters
    ----------
    run_dir:
        Path to the run directory (as returned by :func:`init_results_dir`).
    card_id:
        Unique card identifier.
    blind_result:
        Dict with at least ``impl_source`` key (blind implementation code)
        and optional metadata.  May also contain ``iterations``.
    test_result:
        Dict with ``impl_source`` (tested impl), ``tests_source`` (test
        code), and optional ``iterations``.
    eval_results:
        List of :class:`EvalResult` (or equivalent dicts) for self/cross/audited.

    Returns
    -------
    Path
        The per-card directory.
    """
    card_dir = run_dir / "cards" / card_id
    card_dir.mkdir(parents=True, exist_ok=True)

    # --- Write implementation files ---
    blind_result = blind_result or {}
    test_result = test_result or {}

    blind_source = blind_result.get("impl_source", "")
    if blind_source:
        (card_dir / "blind_impl.py").write_text(blind_source)

    tested_source = test_result.get("impl_source", "")
    if tested_source:
        (card_dir / "tested_impl.py").write_text(tested_source)

    tests_source = test_result.get("tests_source", "")
    if tests_source:
        (card_dir / "tests.py").write_text(tests_source)

    # --- Write iterations ---
    iterations_dir = card_dir / "iterations"
    iterations_dir.mkdir(exist_ok=True)

    for source, label in [
        (blind_result, "blind"),
        (test_result, "tested"),
    ]:
        iterations = source.get("iterations", [])
        # iterations may be an int (count) or a list of iteration dicts
        if isinstance(iterations, int):
            iterations = [{} for _ in range(iterations)]
        for i, iteration_data in enumerate(iterations, 1):
            iter_dir = iterations_dir / f"iteration_{i}"
            iter_dir.mkdir(exist_ok=True)
            # Write iteration data as JSON
            (iter_dir / f"{label}.json").write_text(
                json.dumps(iteration_data, indent=2, default=str)
            )

    # --- Build and write result.json ---
    result_record = _build_result_record(card_id, blind_result, test_result, eval_results)
    (card_dir / "result.json").write_text(
        json.dumps(result_record, indent=2, default=str)
    )

    return card_dir


def _build_result_record(
    card_id: str,
    blind_result: dict[str, Any],
    test_result: dict[str, Any],
    eval_results: list[Any] | None,
) -> dict[str, Any]:
    """Build the per-card result.json record.

    Schema (per BENCHMARK-RUNNER.md):
    - card_id
    - agent
    - complexity_tier
    - implementation (blind/tested metrics)
    - self_eval
    - cross_eval
    - audited_eval
    """
    agent = blind_result.get("agent", test_result.get("agent", "unknown"))
    model = blind_result.get("model", test_result.get("model", "unknown"))
    complexity_tier = blind_result.get(
        "complexity_tier",
        blind_result.get(
            "tier",
            test_result.get("complexity_tier", test_result.get("tier", "unknown")),
        ),
    )

    # Build implementation metrics — preserve all keys except large source
    # blobs and internal bookkeeping, so tokens/runtime/peak_context etc.
    # flow through automatically.
    _IMPL_EXCLUDE = {"impl_source", "tests_source", "agent", "model", "complexity_tier", "tier", "iterations"}

    blind_metrics = {
        k: v for k, v in blind_result.items() if k not in _IMPL_EXCLUDE
    }
    _blind_iters = blind_result.get("iterations", [])
    blind_metrics["iterations"] = _blind_iters if isinstance(_blind_iters, int) else len(_blind_iters)

    tested_metrics = {
        k: v for k, v in test_result.items() if k not in _IMPL_EXCLUDE
    }
    _tested_iters = test_result.get("iterations", [])
    tested_metrics["iterations"] = _tested_iters if isinstance(_tested_iters, int) else len(_tested_iters)

    # Canonical schema: implementation.blind / implementation.tested hold all
    # per-phase metrics. self_eval/audited_eval hold test-run outcomes.
    record: dict[str, Any] = {
        "card_id": card_id,
        "status": test_result.get("status", blind_result.get("status", "ok")),
        "agent": agent,
        "model": model,
        "complexity_tier": complexity_tier,
        "implementation": {
            "blind": blind_metrics,
            "tested": tested_metrics,
        },
        "self_eval": {},
        "cross_eval": [],
        "audited_eval": {},
    }

    # Populate eval results using nested-by-phase format
    if eval_results:
        for er in eval_results:
            if isinstance(er, EvalResult):
                er_dict = asdict(er)
            else:
                er_dict = dict(er)

            eval_type = er_dict.get("eval_type", "")
            entry = {
                "blind": {
                    "passed": er_dict.get("blind_passed", 0),
                    "failed": er_dict.get("blind_failed", 0),
                    "total": er_dict.get("blind_total", 0),
                    "errors": [e for e in er_dict.get("errors", [])],
                },
                "tested": {
                    "passed": er_dict.get("tested_passed", 0),
                    "failed": er_dict.get("tested_failed", 0),
                    "total": er_dict.get("tested_total", 0),
                    "errors": [],
                },
            }

            if eval_type == "self":
                record["self_eval"] = entry
            elif eval_type.startswith("cross:"):
                test_agent = eval_type.split(":", 1)[1]
                impl_agent = er_dict.get("agent", agent)
                cross_entry = {
                    "impl_agent": impl_agent,
                    "test_agent": test_agent,
                    **entry,
                }
                record["cross_eval"].append(cross_entry)
            elif eval_type == "audited":
                record["audited_eval"] = entry

    return record


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------


def save_run_summary(
    run_dir: Path,
    all_results: list[dict[str, Any]],
) -> Path:
    """Write ``summary.json`` with per-run aggregate stats.

    Parameters
    ----------
    run_dir:
        The run directory.
    all_results:
        List of per-card result records (as produced by :func:`save_card_result`).

    Returns
    -------
    Path
        Path to the written ``summary.json``.
    """
    card_count = len(all_results)

    # Collect unique agents
    agents = sorted({r.get("agent", "unknown") for r in all_results})

    # Tally complexity tiers
    tier_counts: dict[str, int] = {}
    for r in all_results:
        tier = r.get("complexity_tier", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    # Aggregate eval stats
    self_total_passed = 0
    self_total_tests = 0
    audited_total_passed = 0
    audited_total_tests = 0

    for r in all_results:
        se = r.get("self_eval", {})
        tested = se.get("tested", {})
        self_total_passed += tested.get("passed", 0)
        self_total_tests += tested.get("total", 0)

        ae = r.get("audited_eval", {})
        ae_tested = ae.get("tested", {})
        audited_total_passed += ae_tested.get("passed", 0)
        audited_total_tests += ae_tested.get("total", 0)

    summary = {
        "card_count": card_count,
        "agents": agents,
        "tier_counts": tier_counts,
        "self_eval": {
            "total_passed": self_total_passed,
            "total_tests": self_total_tests,
        },
        "audited_eval": {
            "total_passed": audited_total_passed,
            "total_tests": audited_total_tests,
        },
    }

    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary_path


# ---------------------------------------------------------------------------
# Cross-run aggregates
# ---------------------------------------------------------------------------


def save_aggregates(
    results_dir: Path,
    run_dirs: list[Path],
    leaderboard: Leaderboard,
) -> None:
    """Write cross-run aggregate files to the parent results directory.

    Creates::

        {results_dir}/
        ├── leaderboard.md
        ├── cross_eval_matrix.json
        └── summary.json

    Parameters
    ----------
    results_dir:
        The parent results directory (e.g. ``benchmarks/sos/results/``).
    run_dirs:
        List of per-run directories to aggregate.
    leaderboard:
        Pre-computed :class:`Leaderboard` instance.
    """
    results_dir.mkdir(parents=True, exist_ok=True)

    # --- leaderboard.md ---
    lb_md = generate_leaderboard(leaderboard)
    (results_dir / "leaderboard.md").write_text(lb_md)

    # --- cross_eval_matrix.json ---
    matrix = _build_cross_eval_matrix(run_dirs)
    (results_dir / "cross_eval_matrix.json").write_text(
        json.dumps(matrix, indent=2)
    )

    # --- summary.json (aggregate across runs) ---
    aggregate = _build_aggregate_summary(run_dirs, leaderboard)
    (results_dir / "summary.json").write_text(
        json.dumps(aggregate, indent=2)
    )


def _build_cross_eval_matrix(run_dirs: list[Path]) -> dict[str, Any]:
    """Build cross-eval matrix from per-card result.json files.

    Schema::

        {
            "card_id": {
                "impl_agent": {
                    "test_agent": {"passed": N, "failed": M}
                }
            }
        }

    For single-model runs this is empty (no cross entries).
    """
    matrix: dict[str, dict[str, dict[str, dict[str, int]]]] = {}

    for run_dir in run_dirs:
        cards_dir = run_dir / "cards"
        if not cards_dir.exists():
            continue
        for card_path in sorted(cards_dir.iterdir()):
            if not card_path.is_dir():
                continue
            result_file = card_path / "result.json"
            if not result_file.exists():
                continue

            data = json.loads(result_file.read_text())
            card_id = data.get("card_id", card_path.name)
            impl_agent = data.get("agent", "unknown")
            cross_eval = data.get("cross_eval", [])

            if not cross_eval:
                continue

            if card_id not in matrix:
                matrix[card_id] = {}
            if impl_agent not in matrix[card_id]:
                matrix[card_id][impl_agent] = {}

            for entry in cross_eval:
                test_agent = entry.get("test_agent", "unknown")
                tested = entry.get("tested", {})
                matrix[card_id][impl_agent][test_agent] = {
                    "passed": tested.get("passed", 0),
                    "failed": tested.get("failed", 0),
                }

    return matrix


def _build_aggregate_summary(
    run_dirs: list[Path],
    leaderboard: Leaderboard,
) -> dict[str, Any]:
    """Build aggregate summary.json across all runs."""
    total_cards = 0
    all_agents: set[str] = set()
    all_tiers: dict[str, int] = {}

    for run_dir in run_dirs:
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            continue
        run_summary = json.loads(summary_path.read_text())
        total_cards += run_summary.get("card_count", 0)
        for agent in run_summary.get("agents", []):
            all_agents.add(agent)
        for tier, count in run_summary.get("tier_counts", {}).items():
            all_tiers[tier] = all_tiers.get(tier, 0) + count

    return {
        "total_runs": len(run_dirs),
        "card_count": total_cards,
        "agents": sorted(all_agents),
        "tier_counts": all_tiers,
        "leaderboard": {
            "category1": {
                agent: {
                    "weighted_score": s.weighted_score,
                    "audited_pass_rate": s.audited_pass_rate,
                }
                for agent, s in leaderboard.category1.items()
            },
            "category2": {
                agent: {
                    "weighted_score": s.weighted_score,
                    "audited_pass_rate": s.audited_pass_rate,
                }
                for agent, s in leaderboard.category2.items()
            },
            "category4": {
                agent: {
                    "regression_rate": s.regression_rate,
                    "regression_free_streak": s.regression_free_streak,
                    "engine_churn": s.engine_churn,
                    "mechanic_reuse_rate": s.mechanic_reuse_rate,
                }
                for agent, s in leaderboard.category4.items()
            },
        },
    }
