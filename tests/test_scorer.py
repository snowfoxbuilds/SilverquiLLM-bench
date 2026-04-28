"""Tests for TODO item 13: Scoring calculator.

Tests verify:
- Leaderboard dataclass structure (all three category dicts).
- compute_scores with mock eval results for 3 agents × 5 cards.
- weighted_score matches hand-calculated values using known tier weights.
- improvement_delta = Cat2 audited_pass_rate - Cat1 audited_pass_rate.
- discrimination_score = 0 when all agents have identical pass rates.
- difficulty_calibration correct for known inputs.
- generate_leaderboard returns valid Markdown with expected category sections.
- Edge cases: empty results, single agent, all passing, all failing.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from benchmark.scorer import (
    AgentCat1Scores,
    AgentCat2Scores,
    AgentCat3Scores,
    Leaderboard,
    compute_scores,
    generate_leaderboard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TIER_DATA_5CARDS = {
    "card_a": "trivial",   # weight 1
    "card_b": "simple",    # weight 2
    "card_c": "medium",    # weight 3
    "card_d": "complex",   # weight 4
    "card_e": "expert",    # weight 5
}


def _write_results(tmp_path: Path, results: list[dict]) -> Path:
    """Write a results.json file into tmp_path and return the directory."""
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "results.json").write_text(json.dumps(results))
    return results_dir


def _make_audited_result(
    agent: str,
    card_id: str,
    blind_passed: int,
    blind_total: int,
    tested_passed: int,
    tested_total: int,
) -> dict:
    """Create an audited eval result dict."""
    return {
        "agent": agent,
        "card_id": card_id,
        "eval_type": "audited",
        "blind_passed": blind_passed,
        "blind_total": blind_total,
        "tested_passed": tested_passed,
        "tested_total": tested_total,
    }


def _make_self_result(
    agent: str,
    card_id: str,
    blind_passed: int,
    blind_total: int,
    tested_passed: int = 0,
    tested_total: int = 0,
) -> dict:
    """Create a self-eval result dict using only real EvalResult fields."""
    return {
        "agent": agent,
        "card_id": card_id,
        "eval_type": "self",
        "blind_passed": blind_passed,
        "blind_total": blind_total,
        "tested_passed": tested_passed,
        "tested_total": tested_total,
    }


def _make_cross_result(
    agent: str,
    card_id: str,
    test_author: str,
    blind_passed: int,
    blind_total: int,
    tested_passed: int = 0,
    tested_total: int = 0,
) -> dict:
    return {
        "agent": agent,
        "card_id": card_id,
        "eval_type": f"cross:{test_author}",
        "blind_passed": blind_passed,
        "blind_total": blind_total,
        "tested_passed": tested_passed,
        "tested_total": tested_total,
    }


# ---------------------------------------------------------------------------
# Dataclass structure
# ---------------------------------------------------------------------------


class TestLeaderboardStructure:
    """Leaderboard and per-agent dataclasses have the correct fields."""

    def test_leaderboard_has_three_category_dicts(self) -> None:
        lb = Leaderboard()
        assert hasattr(lb, "category1")
        assert hasattr(lb, "category2")
        assert hasattr(lb, "category3")
        assert isinstance(lb.category1, dict)
        assert isinstance(lb.category2, dict)
        assert isinstance(lb.category3, dict)

    def test_cat1_fields(self) -> None:
        names = {f.name for f in dc_fields(AgentCat1Scores)}
        assert names == {
            "audited_pass_rate",
            "card_pass_rate",
            "cross_eval_pass_rate",
            "weighted_score",
        }

    def test_cat2_fields(self) -> None:
        names = {f.name for f in dc_fields(AgentCat2Scores)}
        assert names == {
            "audited_pass_rate",
            "card_pass_rate",
            "cross_eval_pass_rate",
            "weighted_score",
            "improvement_delta",
        }

    def test_cat3_fields(self) -> None:
        names = {f.name for f in dc_fields(AgentCat3Scores)}
        assert names == {
            "audit_survival_rate",
            "discrimination_score",
            "difficulty_calibration",
            "coverage",
        }


# ---------------------------------------------------------------------------
# weighted_score hand calculation
# ---------------------------------------------------------------------------


class TestWeightedScore:
    """Verify weighted_score matches hand calculation with known tier weights."""

    def test_weighted_score_hand_calc(self, tmp_path: Path) -> None:
        """Agent passes card_a (w=1) and card_d (w=4), fails card_b, card_c, card_e.

        Expected = (1*1 + 2*0 + 3*0 + 4*1 + 5*0) / (1+2+3+4+5) = 5/15 = 1/3
        """
        results = [
            # blind_passed==blind_total means card passes
            _make_audited_result("agentX", "card_a", 3, 3, 3, 3),  # pass
            _make_audited_result("agentX", "card_b", 1, 3, 1, 3),  # fail
            _make_audited_result("agentX", "card_c", 0, 2, 0, 2),  # fail
            _make_audited_result("agentX", "card_d", 5, 5, 5, 5),  # pass
            _make_audited_result("agentX", "card_e", 2, 4, 2, 4),  # fail
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, TIER_DATA_5CARDS)
        expected = 5.0 / 15.0
        assert lb.category1["agentX"].weighted_score == pytest.approx(expected)

    def test_weighted_score_all_pass(self, tmp_path: Path) -> None:
        """All cards pass → weighted_score = 1.0."""
        results = [
            _make_audited_result("agentX", "card_a", 2, 2, 2, 2),
            _make_audited_result("agentX", "card_b", 2, 2, 2, 2),
            _make_audited_result("agentX", "card_c", 2, 2, 2, 2),
            _make_audited_result("agentX", "card_d", 2, 2, 2, 2),
            _make_audited_result("agentX", "card_e", 2, 2, 2, 2),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, TIER_DATA_5CARDS)
        assert lb.category1["agentX"].weighted_score == pytest.approx(1.0)

    def test_weighted_score_all_fail(self, tmp_path: Path) -> None:
        """All cards fail → weighted_score = 0.0."""
        results = [
            _make_audited_result("agentX", "card_a", 0, 2, 0, 2),
            _make_audited_result("agentX", "card_b", 0, 2, 0, 2),
            _make_audited_result("agentX", "card_c", 0, 2, 0, 2),
            _make_audited_result("agentX", "card_d", 0, 2, 0, 2),
            _make_audited_result("agentX", "card_e", 0, 2, 0, 2),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, TIER_DATA_5CARDS)
        assert lb.category1["agentX"].weighted_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# improvement_delta
# ---------------------------------------------------------------------------


class TestImprovementDelta:
    """Cat2 improvement_delta = Cat2 audited - Cat1 audited."""

    def test_improvement_delta_positive(self, tmp_path: Path) -> None:
        """Agent improves from blind to tested: delta > 0."""
        results = [
            # blind: 2/4 pass, tested: 4/4 pass
            _make_audited_result("agentA", "card_a", 2, 4, 4, 4),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, TIER_DATA_5CARDS)
        cat1_rate = lb.category1["agentA"].audited_pass_rate
        cat2_rate = lb.category2["agentA"].audited_pass_rate
        delta = lb.category2["agentA"].improvement_delta
        assert delta == pytest.approx(cat2_rate - cat1_rate)
        assert delta > 0

    def test_improvement_delta_zero_when_same(self, tmp_path: Path) -> None:
        """Same pass rates in blind and tested → delta = 0."""
        results = [
            _make_audited_result("agentA", "card_a", 3, 5, 3, 5),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, TIER_DATA_5CARDS)
        assert lb.category2["agentA"].improvement_delta == pytest.approx(0.0)

    def test_improvement_delta_negative(self, tmp_path: Path) -> None:
        """Worse tested than blind → negative delta."""
        results = [
            _make_audited_result("agentA", "card_a", 4, 4, 2, 4),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, TIER_DATA_5CARDS)
        assert lb.category2["agentA"].improvement_delta < 0


# ---------------------------------------------------------------------------
# Category 3: audit_survival_rate and coverage from real EvalResult fields
# ---------------------------------------------------------------------------


class TestAuditSurvivalRate:
    """audit_survival_rate = self-eval blind_passed / blind_total."""

    def test_survival_rate_computed_from_self_eval_blind_fields(self, tmp_path: Path) -> None:
        """Agent's own tests: 8 of 10 pass against own impl → survival = 0.8."""
        results = [
            _make_self_result("agentA", "card_a", 3, 5),
            _make_self_result("agentA", "card_b", 5, 5),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        # total self blind_passed=3+5=8, blind_total=5+5=10 → 0.8
        assert lb.category3["agentA"].audit_survival_rate == pytest.approx(0.8)

    def test_survival_rate_perfect(self, tmp_path: Path) -> None:
        """All self-eval tests pass → survival = 1.0."""
        results = [
            _make_self_result("agentA", "card_a", 5, 5),
            _make_self_result("agentA", "card_b", 3, 3),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        assert lb.category3["agentA"].audit_survival_rate == pytest.approx(1.0)

    def test_survival_rate_zero_when_all_fail(self, tmp_path: Path) -> None:
        """All self-eval tests fail → survival = 0.0."""
        results = [
            _make_self_result("agentA", "card_a", 0, 5),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        assert lb.category3["agentA"].audit_survival_rate == pytest.approx(0.0)

    def test_survival_rate_zero_when_no_self_results(self, tmp_path: Path) -> None:
        """Agent has audited results but no self-eval → survival = 0.0."""
        results = [
            _make_audited_result("agentA", "card_a", 3, 5, 3, 5),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        assert lb.category3["agentA"].audit_survival_rate == pytest.approx(0.0)

    def test_survival_ignores_non_self_eval(self, tmp_path: Path) -> None:
        """Only self-eval results count toward survival, not audited or cross."""
        results = [
            _make_self_result("agentA", "card_a", 2, 4),            # self: 2/4
            _make_audited_result("agentA", "card_a", 4, 4, 4, 4),   # audited (ignored)
            _make_cross_result("agentA", "card_a", "agentB", 4, 4), # cross (ignored)
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        assert lb.category3["agentA"].audit_survival_rate == pytest.approx(0.5)


class TestCoverage:
    """coverage = fraction of all cards with agent self-eval blind_total > 0."""

    def test_coverage_from_self_eval_blind_total(self, tmp_path: Path) -> None:
        """Agent has self-eval for 2 of 3 cards → coverage = 2/3."""
        results = [
            _make_self_result("agentA", "card_a", 3, 5),  # blind_total>0
            _make_self_result("agentA", "card_b", 2, 3),  # blind_total>0
            # card_c not present in self-eval but exists in audited
            _make_audited_result("agentA", "card_c", 1, 2, 1, 2),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        # all_cards = {card_a, card_b, card_c}, agent has self-eval for a & b
        assert lb.category3["agentA"].coverage == pytest.approx(2 / 3)

    def test_coverage_full_when_all_cards_have_self_tests(self, tmp_path: Path) -> None:
        """Agent has self-eval with tests for every card → coverage = 1.0."""
        results = [
            _make_self_result("agentA", "card_a", 3, 5),
            _make_self_result("agentA", "card_b", 2, 3),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        assert lb.category3["agentA"].coverage == pytest.approx(1.0)

    def test_coverage_zero_when_blind_total_is_zero(self, tmp_path: Path) -> None:
        """Self-eval with blind_total=0 does not count as covered."""
        results = [
            _make_self_result("agentA", "card_a", 0, 0),  # blind_total=0
            _make_audited_result("agentA", "card_a", 3, 5, 3, 5),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        assert lb.category3["agentA"].coverage == pytest.approx(0.0)

    def test_coverage_accounts_for_all_cards_across_agents(self, tmp_path: Path) -> None:
        """Coverage denominator is all unique cards, not just this agent's."""
        results = [
            _make_self_result("agentA", "card_a", 3, 5),  # A covers card_a
            _make_self_result("agentB", "card_a", 2, 5),  # B covers card_a
            _make_self_result("agentB", "card_b", 4, 4),  # B covers card_b
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        # all_cards = {card_a, card_b}; agentA covers only card_a → 1/2
        assert lb.category3["agentA"].coverage == pytest.approx(0.5)
        # agentB covers both → 2/2 = 1.0
        assert lb.category3["agentB"].coverage == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# discrimination_score
# ---------------------------------------------------------------------------


class TestDiscriminationScore:
    """Discrimination score: variance in pass rates across agents."""

    def test_discrimination_zero_when_all_identical(self, tmp_path: Path) -> None:
        """All agents have identical pass rates → discrimination = 0."""
        results = []
        for agent in ("agentA", "agentB", "agentC"):
            results.append(_make_self_result(agent, "card_a", 3, 5))
            # Cross results: each agent's impl tested by others' tests gets same rate
            for author in ("agentA", "agentB", "agentC"):
                if author != agent:
                    results.append(
                        _make_cross_result(agent, "card_a", author, 3, 5)
                    )
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        for agent in ("agentA", "agentB", "agentC"):
            assert lb.category3[agent].discrimination_score == pytest.approx(0.0)

    def test_discrimination_positive_when_varied(self, tmp_path: Path) -> None:
        """Different pass rates across agents → positive discrimination."""
        results = []
        # Agent A writes tests; agents have different pass rates against them
        results.append(_make_self_result("agentA", "card_a", 5, 5))
        results.append(_make_self_result("agentB", "card_a", 0, 5))
        results.append(_make_self_result("agentC", "card_a", 2, 5))
        # Cross: B and C's impls tested against A's tests
        results.append(_make_cross_result("agentB", "card_a", "agentA", 0, 5))
        results.append(_make_cross_result("agentC", "card_a", "agentA", 2, 5))
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        assert lb.category3["agentA"].discrimination_score > 0


# ---------------------------------------------------------------------------
# difficulty_calibration
# ---------------------------------------------------------------------------


class TestDifficultyCalibration:
    """Fraction of tests passed by some but not all agents."""

    def test_calibration_when_all_pass(self, tmp_path: Path) -> None:
        """All agents pass all tests → difficulty_calibration = 0."""
        results = []
        for agent in ("agentA", "agentB"):
            results.append(_make_self_result(agent, "card_a", 5, 5))
            for author in ("agentA", "agentB"):
                if author != agent:
                    results.append(
                        _make_cross_result(agent, "card_a", author, 5, 5)
                    )
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        for agent in ("agentA", "agentB"):
            assert lb.category3[agent].difficulty_calibration == pytest.approx(0.0)

    def test_calibration_partial(self, tmp_path: Path) -> None:
        """Some agents pass, some fail → fraction > 0."""
        results = []
        # agentA self: all pass
        results.append(_make_self_result("agentA", "card_a", 5, 5))
        results.append(_make_self_result("agentB", "card_a", 0, 5))
        # Cross: B's impl fails A's tests
        results.append(_make_cross_result("agentB", "card_a", "agentA", 0, 5))
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, {})
        # agentA's tests: self=1.0 pass, cross:agentA for agentB=0.0
        # Some pass, not all → calibration = 1/1 = 1.0
        assert lb.category3["agentA"].difficulty_calibration == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 3 agents × 5 cards integration
# ---------------------------------------------------------------------------


class TestThreeAgentsFiveCards:
    """Full integration: 3 agents × 5 cards with known outcomes."""

    @pytest.fixture()
    def setup_results(self, tmp_path: Path):
        """Create mock results for 3 agents × 5 cards.

        Agents: alpha, beta, gamma
        Cards: card_a(trivial/1), card_b(simple/2), card_c(medium/3),
               card_d(complex/4), card_e(expert/5)

        Blind pass pattern (all audited tests pass for card):
          alpha: card_a ✓, card_b ✓, card_c ✗, card_d ✗, card_e ✗
          beta:  card_a ✓, card_b ✓, card_c ✓, card_d ✗, card_e ✗
          gamma: card_a ✓, card_b ✓, card_c ✓, card_d ✓, card_e ✓
        """
        results = []
        # (agent, card, blind_p, blind_t, tested_p, tested_t)
        configs = [
            ("alpha", "card_a", 3, 3, 3, 3),
            ("alpha", "card_b", 2, 2, 2, 2),
            ("alpha", "card_c", 1, 3, 2, 3),
            ("alpha", "card_d", 0, 4, 3, 4),
            ("alpha", "card_e", 1, 5, 4, 5),
            ("beta",  "card_a", 2, 2, 2, 2),
            ("beta",  "card_b", 3, 3, 3, 3),
            ("beta",  "card_c", 4, 4, 4, 4),
            ("beta",  "card_d", 1, 3, 3, 3),
            ("beta",  "card_e", 0, 2, 0, 2),
            ("gamma", "card_a", 1, 1, 1, 1),
            ("gamma", "card_b", 5, 5, 5, 5),
            ("gamma", "card_c", 3, 3, 3, 3),
            ("gamma", "card_d", 2, 2, 2, 2),
            ("gamma", "card_e", 4, 4, 4, 4),
        ]
        for agent, card, bp, bt, tp, tt in configs:
            results.append(_make_audited_result(agent, card, bp, bt, tp, tt))

        rd = _write_results(tmp_path, results)
        return compute_scores(rd, TIER_DATA_5CARDS)

    def test_all_three_agents_present(self, setup_results: Leaderboard) -> None:
        lb = setup_results
        for cat_dict in (lb.category1, lb.category2):
            assert set(cat_dict.keys()) == {"alpha", "beta", "gamma"}

    def test_alpha_weighted_score(self, setup_results: Leaderboard) -> None:
        """alpha passes card_a(w=1) + card_b(w=2) = 3/15."""
        lb = setup_results
        expected = (1 + 2) / (1 + 2 + 3 + 4 + 5)
        assert lb.category1["alpha"].weighted_score == pytest.approx(expected)

    def test_beta_weighted_score(self, setup_results: Leaderboard) -> None:
        """beta passes card_a(w=1) + card_b(w=2) + card_c(w=3) = 6/15."""
        lb = setup_results
        expected = (1 + 2 + 3) / 15
        assert lb.category1["beta"].weighted_score == pytest.approx(expected)

    def test_gamma_weighted_score(self, setup_results: Leaderboard) -> None:
        """gamma passes all 5 cards → 15/15 = 1.0."""
        lb = setup_results
        assert lb.category1["gamma"].weighted_score == pytest.approx(1.0)

    def test_cat1_audited_pass_rate(self, setup_results: Leaderboard) -> None:
        """alpha blind: (3+2+1+0+1)/(3+2+3+4+5) = 7/17."""
        lb = setup_results
        assert lb.category1["alpha"].audited_pass_rate == pytest.approx(7 / 17)

    def test_cat2_audited_pass_rate(self, setup_results: Leaderboard) -> None:
        """alpha tested: (3+2+2+3+4)/(3+2+3+4+5) = 14/17."""
        lb = setup_results
        assert lb.category2["alpha"].audited_pass_rate == pytest.approx(14 / 17)

    def test_improvement_delta_for_alpha(self, setup_results: Leaderboard) -> None:
        lb = setup_results
        expected_delta = (14 / 17) - (7 / 17)
        assert lb.category2["alpha"].improvement_delta == pytest.approx(expected_delta)

    def test_gamma_no_improvement(self, setup_results: Leaderboard) -> None:
        """gamma: all pass in both blind and tested → delta = 0."""
        lb = setup_results
        # gamma blind: (1+5+3+2+4)/(1+5+3+2+4)=15/15=1.0
        # gamma tested: (1+5+3+2+4)/(1+5+3+2+4)=15/15=1.0
        assert lb.category2["gamma"].improvement_delta == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: empty results, single agent."""

    def test_empty_results(self, tmp_path: Path) -> None:
        """Empty results dir → empty leaderboard."""
        rd = _write_results(tmp_path, [])
        lb = compute_scores(rd, TIER_DATA_5CARDS)
        assert lb.category1 == {}
        assert lb.category2 == {}
        assert lb.category3 == {}

    def test_single_agent_single_card(self, tmp_path: Path) -> None:
        """Single agent, single card still produces valid scores."""
        results = [
            _make_audited_result("solo", "card_c", 3, 3, 3, 3),
        ]
        rd = _write_results(tmp_path, results)
        lb = compute_scores(rd, TIER_DATA_5CARDS)
        assert "solo" in lb.category1
        assert lb.category1["solo"].weighted_score == pytest.approx(1.0)
        assert lb.category1["solo"].card_pass_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# generate_leaderboard
# ---------------------------------------------------------------------------


class TestGenerateLeaderboard:
    """generate_leaderboard returns valid Markdown."""

    @pytest.fixture()
    def sample_leaderboard(self) -> Leaderboard:
        lb = Leaderboard()
        lb.category1["alpha"] = AgentCat1Scores(
            audited_pass_rate=0.8,
            card_pass_rate=0.6,
            cross_eval_pass_rate=0.7,
            weighted_score=0.75,
        )
        lb.category2["alpha"] = AgentCat2Scores(
            audited_pass_rate=0.9,
            card_pass_rate=0.8,
            cross_eval_pass_rate=0.85,
            weighted_score=0.88,
            improvement_delta=0.1,
        )
        lb.category3["alpha"] = AgentCat3Scores(
            audit_survival_rate=0.95,
            discrimination_score=0.12,
            difficulty_calibration=0.60,
            coverage=0.80,
        )
        return lb

    def test_contains_all_category_headers(self, sample_leaderboard: Leaderboard) -> None:
        md = generate_leaderboard(sample_leaderboard)
        assert "## Category 1" in md
        assert "## Category 2" in md
        assert "## Category 3" in md

    def test_contains_agent_name(self, sample_leaderboard: Leaderboard) -> None:
        md = generate_leaderboard(sample_leaderboard)
        assert "alpha" in md

    def test_contains_markdown_table_separators(self, sample_leaderboard: Leaderboard) -> None:
        md = generate_leaderboard(sample_leaderboard)
        assert "|---" in md

    def test_cat2_shows_delta(self, sample_leaderboard: Leaderboard) -> None:
        md = generate_leaderboard(sample_leaderboard)
        # Delta column should contain +10.0% for improvement_delta=0.1
        assert "+10.0%" in md

    def test_empty_leaderboard_still_has_headers(self) -> None:
        lb = Leaderboard()
        md = generate_leaderboard(lb)
        assert "## Category 1" in md
        assert "## Category 2" in md
        assert "## Category 3" in md

    def test_multiple_agents_ranked(self) -> None:
        lb = Leaderboard()
        lb.category1["low"] = AgentCat1Scores(weighted_score=0.2)
        lb.category1["high"] = AgentCat1Scores(weighted_score=0.9)
        md = generate_leaderboard(lb)
        # "high" should appear before "low" (higher weighted_score = rank 1)
        high_pos = md.index("high")
        low_pos = md.index("low")
        assert high_pos < low_pos, "Higher weighted_score agent should rank first"
