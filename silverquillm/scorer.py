"""Scoring calculator for benchmark leaderboards.

Computes metrics from SCORING.md across four independent categories:
- Category 1 (Blind): pure spec-to-code implementation quality
- Category 2 (Tested): implementation with test-driven iteration
- Category 3 (Test Quality): how good the agent's tests are
- Category 4 (Engine Extension Quality): engine extension without regressions

Public API:
- ``Leaderboard`` — dataclass holding per-agent scores for each category.
- ``compute_scores`` — compute all metrics from evaluation results.
- ``compute_cat4_scores`` — compute Category 4 metrics from run artifacts.
- ``generate_leaderboard`` — render leaderboard as Markdown tables.
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from silverquillm.card_classifier import TIER_WEIGHTS

logger = logging.getLogger(__name__)

__all__ = [
    "Leaderboard",
    "AgentCat1Scores",
    "AgentCat2Scores",
    "AgentCat3Scores",
    "AgentCat4Scores",
    "compute_scores",
    "compute_cat4_scores",
    "generate_leaderboard",
]


# ---------------------------------------------------------------------------
# Per-agent score dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AgentCat1Scores:
    """Category 1 (Blind Implementation) scores for a single agent."""

    audited_pass_rate: float = 0.0
    card_pass_rate: float = 0.0
    cross_eval_pass_rate: float = 0.0
    weighted_score: float = 0.0


@dataclass
class AgentCat2Scores:
    """Category 2 (Implementation with Tests) scores for a single agent."""

    audited_pass_rate: float = 0.0
    card_pass_rate: float = 0.0
    cross_eval_pass_rate: float = 0.0
    weighted_score: float = 0.0
    improvement_delta: float = 0.0


@dataclass
class AgentCat3Scores:
    """Category 3 (Test Quality) scores for a single agent."""

    audit_survival_rate: float = 0.0
    discrimination_score: float = 0.0
    difficulty_calibration: float = 0.0
    coverage: float = 0.0


@dataclass
class AgentCat4Scores:
    """Category 4 (Engine Extension Quality) scores for a single agent."""

    regression_rate: float = 0.0
    regression_free_streak: int = 0
    engine_churn: int = 0
    mechanic_reuse_rate: float = 0.0


@dataclass
class Leaderboard:
    """Per-agent scores for all four categories."""

    category1: dict[str, AgentCat1Scores] = field(default_factory=dict)
    category2: dict[str, AgentCat2Scores] = field(default_factory=dict)
    category3: dict[str, AgentCat3Scores] = field(default_factory=dict)
    category4: dict[str, AgentCat4Scores] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_div(numerator: float, denominator: float) -> float:
    """Return numerator / denominator, or 0.0 if denominator is zero."""
    return numerator / denominator if denominator else 0.0


def _weighted_score(
    card_results: dict[str, bool],
    tier_data: dict[str, str],
) -> float:
    """Compute weighted score per SCORING.md.

    ``card_results`` maps card_id -> whether all audited tests pass.
    ``tier_data`` maps card_id -> tier name (e.g. "simple", "complex").

    Formula: Σ(w_c × pass(c)) / Σ(w_c)
    where w_c is the tier weight and pass(c) = 1 if all audited tests pass.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for card_id, passed_all in card_results.items():
        tier = tier_data.get(card_id, "medium")
        w = TIER_WEIGHTS.get(tier, 3)
        total_weight += w
        if passed_all:
            weighted_sum += w
    return _safe_div(weighted_sum, total_weight)


def _discrimination_score(
    per_test_pass_rates: list[list[float]],
) -> float:
    """Compute discrimination score.

    For each test, compute variance in pass rates across agents' implementations.
    Return the mean variance. High variance = good differentiation.

    ``per_test_pass_rates`` is a list where each element is a list of
    per-agent pass rates for a single test.
    """
    if not per_test_pass_rates:
        return 0.0

    variances = []
    for rates in per_test_pass_rates:
        if len(rates) < 2:
            variances.append(0.0)
        else:
            variances.append(statistics.variance(rates))
    return _safe_div(sum(variances), len(variances))


def _difficulty_calibration(
    per_test_pass_rates: list[list[float]],
) -> float:
    """Fraction of tests passed by some but not all agents.

    Each element of ``per_test_pass_rates`` is a list of binary pass values
    (0.0 or 1.0) per agent for a single test.
    """
    if not per_test_pass_rates:
        return 0.0

    sweet_spot = 0
    for rates in per_test_pass_rates:
        if not rates:
            continue
        any_pass = any(r > 0 for r in rates)
        all_pass = all(r > 0 for r in rates)
        if any_pass and not all_pass:
            sweet_spot += 1
    return _safe_div(sweet_spot, len(per_test_pass_rates))


# ---------------------------------------------------------------------------
# EvalResult loading
# ---------------------------------------------------------------------------


def _load_eval_results(results_dir: Path) -> list[dict[str, Any]]:
    """Load all EvalResult JSON files from *results_dir*.

    Supports two layouts:
    1. A single ``results.json`` file containing a list of result dicts.
    2. Multiple ``*.json`` files each containing a single result dict or list.
    """
    results: list[dict[str, Any]] = []
    results_file = results_dir / "results.json"
    if results_file.exists():
        data = json.loads(results_file.read_text())
        if isinstance(data, list):
            results.extend(data)
        else:
            results.append(data)
        return results

    for f in sorted(results_dir.glob("*.json")):
        data = json.loads(f.read_text())
        if isinstance(data, list):
            results.extend(data)
        else:
            results.append(data)
    return results


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def compute_scores(
    results_dir: Path,
    tier_data: dict[str, str],
    *,
    run_dirs: dict[str, Path] | None = None,
    card_order: list[str] | None = None,
) -> Leaderboard:
    """Compute all metrics from evaluation results.

    Parameters
    ----------
    results_dir:
        Directory containing JSON evaluation results (EvalResult dicts).
    tier_data:
        Mapping of card_id -> tier name (e.g. ``{"card_a": "simple"}``).
    run_dirs:
        Optional mapping of agent name -> run directory path.  When
        provided together with *card_order*, Category 4 scores are
        computed automatically for each agent.
    card_order:
        Ordered list of card IDs representing the sequence cards were
        processed in.  Required when *run_dirs* is provided.

    Returns
    -------
    Leaderboard with per-agent scores across all four categories.
    """
    raw = _load_eval_results(results_dir)
    lb = Leaderboard()

    # Group results by agent
    # TODO: group by (agent, model) for multi-model leaderboards
    agents: set[str] = set()
    # Keyed by (agent, card_id, eval_type) -> result dict
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in raw:
        agent = r["agent"]
        agents.add(agent)
        key = (agent, r["card_id"], r["eval_type"])
        by_key[key] = r

    # Collect all card_ids from results
    all_cards: set[str] = set()
    for r in raw:
        all_cards.add(r["card_id"])

    sorted_agents = sorted(agents)

    # ------------------------------------------------------------------
    # Category 1 & 2: computed from audited and cross eval results
    # ------------------------------------------------------------------
    for agent in sorted_agents:
        # --- Audited metrics (blind & tested) ---
        blind_total_passed = 0
        blind_total_tests = 0
        tested_total_passed = 0
        tested_total_tests = 0
        blind_card_pass: dict[str, bool] = {}  # card_id -> all passed?
        tested_card_pass: dict[str, bool] = {}

        for card_id in sorted(all_cards):
            key = (agent, card_id, "audited")
            r = by_key.get(key)
            if r is None:
                blind_card_pass[card_id] = False
                tested_card_pass[card_id] = False
                continue

            bp = r.get("blind_passed", 0)
            bt = r.get("blind_total", 0)
            tp = r.get("tested_passed", 0)
            tt = r.get("tested_total", 0)

            blind_total_passed += bp
            blind_total_tests += bt
            tested_total_passed += tp
            tested_total_tests += tt

            blind_card_pass[card_id] = (bp == bt and bt > 0)
            tested_card_pass[card_id] = (tp == tt and tt > 0)

        # --- Cross-eval metrics (blind & tested) ---
        blind_cross_passed = 0
        blind_cross_total = 0
        tested_cross_passed = 0
        tested_cross_total = 0

        for key, r in by_key.items():
            a, card_id, eval_type = key
            if a != agent:
                continue
            if not eval_type.startswith("cross:"):
                continue
            blind_cross_passed += r.get("blind_passed", 0)
            blind_cross_total += r.get("blind_total", 0)
            tested_cross_passed += r.get("tested_passed", 0)
            tested_cross_total += r.get("tested_total", 0)

        # Cat 1
        cat1 = AgentCat1Scores(
            audited_pass_rate=_safe_div(blind_total_passed, blind_total_tests),
            card_pass_rate=_safe_div(
                sum(1 for v in blind_card_pass.values() if v),
                len(blind_card_pass) if blind_card_pass else 0,
            ),
            cross_eval_pass_rate=_safe_div(blind_cross_passed, blind_cross_total),
            weighted_score=_weighted_score(blind_card_pass, tier_data),
        )
        lb.category1[agent] = cat1

        # Cat 2
        cat1_audited = cat1.audited_pass_rate
        cat2_audited = _safe_div(tested_total_passed, tested_total_tests)
        cat2 = AgentCat2Scores(
            audited_pass_rate=cat2_audited,
            card_pass_rate=_safe_div(
                sum(1 for v in tested_card_pass.values() if v),
                len(tested_card_pass) if tested_card_pass else 0,
            ),
            cross_eval_pass_rate=_safe_div(tested_cross_passed, tested_cross_total),
            weighted_score=_weighted_score(tested_card_pass, tier_data),
            improvement_delta=cat2_audited - cat1_audited,
        )
        lb.category2[agent] = cat2

    # ------------------------------------------------------------------
    # Category 3: Test Quality
    # ------------------------------------------------------------------
    for agent in sorted_agents:
        # Audit survival: fraction of agent's own tests that pass against
        # their own implementation (self-eval).  Tests that fail against
        # the author's own code are likely incorrect and would not survive
        # a human audit.  Derived purely from EvalResult.blind_* fields.
        agent_self_results = [
            r for r in raw
            if r["agent"] == agent and r["eval_type"] == "self"
        ]
        self_passed = sum(r.get("blind_passed", 0) for r in agent_self_results)
        self_total = sum(r.get("blind_total", 0) for r in agent_self_results)
        audit_survival = _safe_div(self_passed, self_total)

        # Coverage: fraction of cards for which the agent produced at
        # least one test (blind_total > 0 in self-eval).  Measures how
        # broadly the agent's test suite covers the card set.
        cards_with_tests = sum(
            1 for r in agent_self_results if r.get("blind_total", 0) > 0
        )
        coverage = _safe_div(cards_with_tests, len(all_cards)) if all_cards else 0.0

        # Per-test discrimination and difficulty calibration
        # For each of the agent's tests, collect pass rates across all agents' impls
        # We use cross-eval results where this agent's tests were used
        per_test_rates: list[list[float]] = []

        # Gather cross-eval results where *this agent's* tests are used
        cross_results_for_tests: dict[str, list[float]] = {}
        for key, r in by_key.items():
            a, card_id, eval_type = key
            if eval_type == f"cross:{agent}":
                # This is another agent's impl tested against *agent*'s tests
                ckey = card_id
                if ckey not in cross_results_for_tests:
                    cross_results_for_tests[ckey] = []
                total = r.get("blind_total", 0)
                passed = r.get("blind_passed", 0)
                rate = _safe_div(passed, total)
                cross_results_for_tests[ckey].append(rate)

        # Also include self-eval pass rates
        for card_id in sorted(all_cards):
            self_key = (agent, card_id, "self")
            r = by_key.get(self_key)
            if r is None:
                continue
            total = r.get("blind_total", 0)
            passed = r.get("blind_passed", 0)
            rate = _safe_div(passed, total)
            if card_id not in cross_results_for_tests:
                cross_results_for_tests[card_id] = []
            cross_results_for_tests[card_id].append(rate)

        for card_id in sorted(cross_results_for_tests):
            rates = cross_results_for_tests[card_id]
            if rates:
                per_test_rates.append(rates)

        cat3 = AgentCat3Scores(
            audit_survival_rate=audit_survival,
            discrimination_score=_discrimination_score(per_test_rates),
            difficulty_calibration=_difficulty_calibration(per_test_rates),
            coverage=coverage,
        )
        lb.category3[agent] = cat3

    # ------------------------------------------------------------------
    # Category 4: Engine Extension Quality
    # ------------------------------------------------------------------
    if run_dirs and card_order is not None:
        for agent in sorted_agents:
            agent_run_dir = run_dirs.get(agent)
            if agent_run_dir is not None:
                lb.category4[agent] = compute_cat4_scores(
                    agent_run_dir, card_order,
                )

    return lb


# ---------------------------------------------------------------------------
# Category 4: Engine Extension Quality
# ---------------------------------------------------------------------------


def _count_patch_lines(patch_text: str) -> int:
    """Count lines changed (added + removed) in a unified diff patch.

    Only counts lines starting with ``+`` or ``-`` that are not part of
    the ``---``/``+++`` file headers.
    """
    count = 0
    for line in patch_text.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def _detect_engine_files_added(patch_text: str) -> set[str]:
    """Extract engine file paths that were newly added in a patch.

    A new file in unified diff is indicated by ``--- /dev/null`` followed
    by ``+++ b/engine/...``.
    """
    added: set[str] = set()
    lines = patch_text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("--- /dev/null") and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.startswith("+++ b/engine/"):
                # Extract the relative path after "b/"
                path = next_line[len("+++ b/"):].strip()
                added.add(path)
        elif line.startswith("--- a/dev/null") and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.startswith("+++ b/engine/"):
                path = next_line[len("+++ b/"):].strip()
                added.add(path)
    return added


def _detect_engine_files_imported(patch_text: str, known_files: set[str]) -> bool:
    """Check if a patch imports from any of the known engine files.

    Heuristic: look for ``from engine.<module>`` or ``import engine.<module>``
    patterns in added lines (``+`` lines) where the module corresponds to
    a file in *known_files*.
    """
    if not known_files:
        return False

    # Build set of module names from file paths
    # e.g. "engine/keywords.py" -> "keywords"
    module_names: set[str] = set()
    for fp in known_files:
        # Strip leading "engine/" and trailing ".py"
        name = fp
        if name.startswith("engine/"):
            name = name[len("engine/"):]
        if name.endswith(".py"):
            name = name[:-3]
        if name:
            module_names.add(name)

    if not module_names:
        return False

    for line in patch_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for mod in module_names:
            if f"from engine.{mod}" in line or f"import engine.{mod}" in line:
                return True
            # Also check for relative imports within engine
            if f"from .{mod}" in line or f"import .{mod}" in line:
                return True
    return False


def compute_cat4_scores(
    run_dir: Path,
    card_order: list[str],
) -> AgentCat4Scores:
    """Compute Category 4 (Engine Extension Quality) metrics for a single run.

    Parameters
    ----------
    run_dir:
        Path to the run directory containing ``cards/<card_id>/`` subdirs.
        Each card dir may contain ``engine_diff.patch`` and ``result.json``.
    card_order:
        Ordered list of card IDs representing the sequence cards were
        processed in.  Order matters for regression-free streak and
        mechanic reuse calculations.

    Returns
    -------
    AgentCat4Scores with all four metrics populated.
    """
    cards_dir = run_dir / "cards"

    total_churn = 0
    regression_count = 0
    total_cards = len(card_order)
    reuse_count = 0

    # Track engine files added by previous cards for mechanic reuse detection
    engine_files_added_so_far: set[str] = set()

    # Track regression-free streak
    current_streak = 0
    max_streak = 0

    for card_id in card_order:
        card_dir = cards_dir / card_id
        if not card_dir.exists():
            continue

        # --- Engine churn from engine_diff.patch ---
        patch_file = card_dir / "engine_diff.patch"
        patch_text = ""
        if patch_file.exists():
            patch_text = patch_file.read_text()
            total_churn += _count_patch_lines(patch_text)

        # --- Regression data from result.json ---
        result_file = card_dir / "result.json"
        has_regression = False
        if result_file.exists():
            try:
                result_data = json.loads(result_file.read_text())
                # Regression data stored as regression_results or failed_tests
                regression_results = result_data.get("regression_results", {})
                if isinstance(regression_results, dict):
                    card_results = regression_results.get("card_results", [])
                    for cr in card_results:
                        if not cr.get("passed", True):
                            has_regression = True
                            break
                elif isinstance(regression_results, list):
                    for cr in regression_results:
                        if not cr.get("passed", True):
                            has_regression = True
                            break

                # Also check top-level failed_tests (backward compat)
                if not has_regression:
                    failed_tests = result_data.get("failed_tests", [])
                    if failed_tests:
                        has_regression = True
            except (json.JSONDecodeError, KeyError):
                pass

        if has_regression:
            regression_count += 1
            current_streak = 0
        else:
            current_streak += 1
            max_streak = max(max_streak, current_streak)

        # --- Mechanic reuse detection ---
        if patch_text and engine_files_added_so_far:
            if _detect_engine_files_imported(patch_text, engine_files_added_so_far):
                reuse_count += 1

        # Track new engine files added by this card
        if patch_text:
            new_files = _detect_engine_files_added(patch_text)
            engine_files_added_so_far |= new_files

    return AgentCat4Scores(
        regression_rate=_safe_div(regression_count, total_cards),
        regression_free_streak=max_streak,
        engine_churn=total_churn,
        mechanic_reuse_rate=_safe_div(reuse_count, max(total_cards - 1, 0)) if total_cards > 1 else 0.0,
    )


# ---------------------------------------------------------------------------
# Leaderboard rendering
# ---------------------------------------------------------------------------


def generate_leaderboard(scores: Leaderboard) -> str:
    """Render the leaderboard as Markdown tables matching SCORING.md format.

    Returns a string containing three Markdown tables (one per category).
    """
    lines: list[str] = []

    # --- Category 1 ---
    lines.append("## Category 1: Blind Implementation")
    lines.append("")
    lines.append(
        "| Rank | Model | Audited | Card Pass | Cross-Eval | Weighted |"
    )
    lines.append(
        "|------|-------|---------|-----------|------------|----------|"
    )
    sorted_cat1 = sorted(
        scores.category1.items(),
        key=lambda x: x[1].weighted_score,
        reverse=True,
    )
    for rank, (agent, s) in enumerate(sorted_cat1, 1):
        lines.append(
            f"| {rank} | {agent} "
            f"| {s.audited_pass_rate:.1%} "
            f"| {s.card_pass_rate:.1%} "
            f"| {s.cross_eval_pass_rate:.1%} "
            f"| {s.weighted_score:.1%} |"
        )
    lines.append("")

    # --- Category 2 ---
    lines.append("## Category 2: Implementation with Tests")
    lines.append("")
    lines.append(
        "| Rank | Model | Audited | Card Pass | Cross-Eval | Weighted | Delta |"
    )
    lines.append(
        "|------|-------|---------|-----------|------------|----------|-------|"
    )
    sorted_cat2 = sorted(
        scores.category2.items(),
        key=lambda x: x[1].weighted_score,
        reverse=True,
    )
    for rank, (agent, s) in enumerate(sorted_cat2, 1):
        delta_sign = "+" if s.improvement_delta >= 0 else ""
        lines.append(
            f"| {rank} | {agent} "
            f"| {s.audited_pass_rate:.1%} "
            f"| {s.card_pass_rate:.1%} "
            f"| {s.cross_eval_pass_rate:.1%} "
            f"| {s.weighted_score:.1%} "
            f"| {delta_sign}{s.improvement_delta:.1%} |"
        )
    lines.append("")

    # --- Category 3 ---
    lines.append("## Category 3: Test Quality")
    lines.append("")
    lines.append(
        "| Rank | Model | Audit Survival | Discrimination | Difficulty Cal. | Coverage |"
    )
    lines.append(
        "|------|-------|----------------|----------------|-----------------|----------|"
    )
    sorted_cat3 = sorted(
        scores.category3.items(),
        key=lambda x: x[1].discrimination_score,
        reverse=True,
    )
    for rank, (agent, s) in enumerate(sorted_cat3, 1):
        lines.append(
            f"| {rank} | {agent} "
            f"| {s.audit_survival_rate:.0%} "
            f"| {s.discrimination_score:.2f} "
            f"| {s.difficulty_calibration:.0%} "
            f"| {s.coverage:.0%} |"
        )
    lines.append("")

    # --- Category 4 ---
    lines.append("## Category 4: Engine Extension Quality")
    lines.append("")
    lines.append(
        "| Rank | Model | Regression Rate | Reg-Free Streak | Engine Churn | Mechanic Reuse |"
    )
    lines.append(
        "|------|-------|-----------------|-----------------|--------------|----------------|"
    )
    sorted_cat4 = sorted(
        scores.category4.items(),
        key=lambda x: (-x[1].regression_rate, x[1].regression_free_streak),
        reverse=True,
    )
    for rank, (agent, s) in enumerate(sorted_cat4, 1):
        lines.append(
            f"| {rank} | {agent} "
            f"| {s.regression_rate:.1%} "
            f"| {s.regression_free_streak} "
            f"| {s.engine_churn} "
            f"| {s.mechanic_reuse_rate:.1%} |"
        )
    lines.append("")

    return "\n".join(lines)
