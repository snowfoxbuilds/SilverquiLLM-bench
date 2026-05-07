"""Tests for TODO item 21: Category 4 scoring – Engine Extension Quality.

Tests verify:
- AgentCat4Scores dataclass holds all four metrics with correct defaults.
- compute_cat4_scores with no cards returns zero/default metrics.
- Regression rate computed as cards-with-regressions / total-cards.
- Regression-free streak tracks longest consecutive run without regressions.
- Engine churn counts added+removed lines from engine_diff.patch files.
- Mechanic reuse rate detects imports of previously added engine files.
- Edge cases: all cards regress, no regressions, single card, no engine changes.
- generate_leaderboard includes Category 4 table.
- save_aggregates includes Category 4 data.
- Regression-free streak handles various patterns (start, middle, end).
"""

from __future__ import annotations

import json
from dataclasses import fields as dc_fields
from pathlib import Path

import pytest

from silverquillm.scorer import (
    AgentCat4Scores,
    Leaderboard,
    compute_cat4_scores,
    generate_leaderboard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card_dir(
    run_dir: Path,
    card_id: str,
    *,
    has_regression: bool = False,
    patch_text: str | None = None,
    failed_tests: list[str] | None = None,
    regression_results: dict | list | None = None,
) -> Path:
    """Create a card directory with optional result.json and engine_diff.patch."""
    card_dir = run_dir / "cards" / card_id
    card_dir.mkdir(parents=True, exist_ok=True)

    # Build result.json
    result: dict = {}
    if has_regression and regression_results is None and failed_tests is None:
        # Default: use regression_results format
        result["regression_results"] = {
            "card_results": [{"card_id": "earlier_card", "passed": False}]
        }
    if regression_results is not None:
        result["regression_results"] = regression_results
    if failed_tests is not None:
        result["failed_tests"] = failed_tests

    if result:
        (card_dir / "result.json").write_text(json.dumps(result))

    if patch_text is not None:
        (card_dir / "engine_diff.patch").write_text(patch_text)

    return card_dir


SIMPLE_PATCH = """\
--- a/engine/foo.py
+++ b/engine/foo.py
@@ -1,3 +1,4 @@
 class Foo:
+    value = 1
-    pass
"""

NEW_FILE_PATCH = """\
--- /dev/null
+++ b/engine/keywords.py
@@ -0,0 +1,3 @@
+class Keywords:
+    pass
+    # new file
"""

IMPORT_PATCH = """\
--- a/engine/card_impl.py
+++ b/engine/card_impl.py
@@ -1,2 +1,3 @@
+from engine.keywords import Keywords
 class CardImpl:
     pass
"""


# ---------------------------------------------------------------------------
# AgentCat4Scores dataclass
# ---------------------------------------------------------------------------


class TestAgentCat4ScoresDataclass:
    """Verify the AgentCat4Scores dataclass structure and defaults."""

    def test_has_all_four_fields(self):
        field_names = {f.name for f in dc_fields(AgentCat4Scores)}
        assert field_names == {
            "regression_rate",
            "regression_free_streak",
            "engine_churn",
            "mechanic_reuse_rate",
        }

    def test_defaults_are_zero(self):
        scores = AgentCat4Scores()
        assert scores.regression_rate == 0.0
        assert scores.regression_free_streak == 0
        assert scores.engine_churn == 0
        assert scores.mechanic_reuse_rate == 0.0

    def test_field_types(self):
        scores = AgentCat4Scores(
            regression_rate=0.5,
            regression_free_streak=3,
            engine_churn=42,
            mechanic_reuse_rate=0.25,
        )
        assert isinstance(scores.regression_rate, float)
        assert isinstance(scores.regression_free_streak, int)
        assert isinstance(scores.engine_churn, int)
        assert isinstance(scores.mechanic_reuse_rate, float)


# ---------------------------------------------------------------------------
# compute_cat4_scores: empty / no cards
# ---------------------------------------------------------------------------


class TestComputeCat4Empty:
    """compute_cat4_scores with no cards or empty run dir."""

    def test_empty_card_order(self, tmp_path):
        result = compute_cat4_scores(tmp_path, [])
        assert result.regression_rate == 0.0
        assert result.regression_free_streak == 0
        assert result.engine_churn == 0
        assert result.mechanic_reuse_rate == 0.0

    def test_card_order_with_missing_dirs(self, tmp_path):
        """Card IDs listed but no card dirs exist on disk."""
        result = compute_cat4_scores(tmp_path, ["nonexistent_a", "nonexistent_b"])
        assert result.regression_rate == 0.0
        assert result.regression_free_streak == 0
        assert result.engine_churn == 0


# ---------------------------------------------------------------------------
# Regression rate
# ---------------------------------------------------------------------------


class TestRegressionRate:
    """Verify regression_rate = cards_with_regressions / total_cards."""

    def test_no_regressions(self, tmp_path):
        for cid in ["c1", "c2", "c3"]:
            _make_card_dir(tmp_path, cid, has_regression=False)
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3"])
        assert result.regression_rate == pytest.approx(0.0)

    def test_all_regressions(self, tmp_path):
        for cid in ["c1", "c2", "c3"]:
            _make_card_dir(tmp_path, cid, has_regression=True)
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3"])
        assert result.regression_rate == pytest.approx(1.0)

    def test_partial_regressions(self, tmp_path):
        _make_card_dir(tmp_path, "c1", has_regression=False)
        _make_card_dir(tmp_path, "c2", has_regression=True)
        _make_card_dir(tmp_path, "c3", has_regression=False)
        _make_card_dir(tmp_path, "c4", has_regression=True)
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3", "c4"])
        assert result.regression_rate == pytest.approx(0.5)

    def test_regression_via_failed_tests_field(self, tmp_path):
        """Backward compat: regressions detected via top-level failed_tests."""
        _make_card_dir(tmp_path, "c1", failed_tests=["test_foo::test_bar"])
        _make_card_dir(tmp_path, "c2")
        result = compute_cat4_scores(tmp_path, ["c1", "c2"])
        assert result.regression_rate == pytest.approx(0.5)

    def test_regression_via_list_format(self, tmp_path):
        """regression_results as a list (alternative format)."""
        _make_card_dir(
            tmp_path, "c1",
            regression_results=[{"card_id": "x", "passed": False}],
        )
        _make_card_dir(tmp_path, "c2")
        result = compute_cat4_scores(tmp_path, ["c1", "c2"])
        assert result.regression_rate == pytest.approx(0.5)

    def test_single_card_no_regression(self, tmp_path):
        _make_card_dir(tmp_path, "c1", has_regression=False)
        result = compute_cat4_scores(tmp_path, ["c1"])
        assert result.regression_rate == pytest.approx(0.0)

    def test_single_card_with_regression(self, tmp_path):
        _make_card_dir(tmp_path, "c1", has_regression=True)
        result = compute_cat4_scores(tmp_path, ["c1"])
        assert result.regression_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Regression-free streak
# ---------------------------------------------------------------------------


class TestRegressionFreeStreak:
    """Longest consecutive sequence of cards without regressions."""

    def test_all_clean(self, tmp_path):
        for cid in ["c1", "c2", "c3", "c4"]:
            _make_card_dir(tmp_path, cid)
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3", "c4"])
        assert result.regression_free_streak == 4

    def test_all_regressed(self, tmp_path):
        for cid in ["c1", "c2", "c3"]:
            _make_card_dir(tmp_path, cid, has_regression=True)
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3"])
        assert result.regression_free_streak == 0

    def test_streak_at_start(self, tmp_path):
        """Streak of 3 clean cards, then a regression."""
        _make_card_dir(tmp_path, "c1")
        _make_card_dir(tmp_path, "c2")
        _make_card_dir(tmp_path, "c3")
        _make_card_dir(tmp_path, "c4", has_regression=True)
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3", "c4"])
        assert result.regression_free_streak == 3

    def test_streak_at_end(self, tmp_path):
        """Regression first, then 3 clean cards at end."""
        _make_card_dir(tmp_path, "c1", has_regression=True)
        _make_card_dir(tmp_path, "c2")
        _make_card_dir(tmp_path, "c3")
        _make_card_dir(tmp_path, "c4")
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3", "c4"])
        assert result.regression_free_streak == 3

    def test_streak_in_middle(self, tmp_path):
        """Regression, then 2 clean, then regression, then 1 clean."""
        _make_card_dir(tmp_path, "c1", has_regression=True)
        _make_card_dir(tmp_path, "c2")
        _make_card_dir(tmp_path, "c3")
        _make_card_dir(tmp_path, "c4", has_regression=True)
        _make_card_dir(tmp_path, "c5")
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3", "c4", "c5"])
        assert result.regression_free_streak == 2

    def test_alternating_regressions(self, tmp_path):
        """Alternating: clean, regress, clean, regress -> max streak = 1."""
        _make_card_dir(tmp_path, "c1")
        _make_card_dir(tmp_path, "c2", has_regression=True)
        _make_card_dir(tmp_path, "c3")
        _make_card_dir(tmp_path, "c4", has_regression=True)
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3", "c4"])
        assert result.regression_free_streak == 1

    def test_single_clean_card(self, tmp_path):
        _make_card_dir(tmp_path, "c1")
        result = compute_cat4_scores(tmp_path, ["c1"])
        assert result.regression_free_streak == 1


# ---------------------------------------------------------------------------
# Engine churn
# ---------------------------------------------------------------------------


class TestEngineChurn:
    """Engine churn counts added+removed lines from patches."""

    def test_no_patches(self, tmp_path):
        _make_card_dir(tmp_path, "c1")
        result = compute_cat4_scores(tmp_path, ["c1"])
        assert result.engine_churn == 0

    def test_simple_patch(self, tmp_path):
        # SIMPLE_PATCH has 1 added line (+    value = 1) and 1 removed (-    pass)
        _make_card_dir(tmp_path, "c1", patch_text=SIMPLE_PATCH)
        result = compute_cat4_scores(tmp_path, ["c1"])
        assert result.engine_churn == 2

    def test_new_file_patch(self, tmp_path):
        # NEW_FILE_PATCH: 3 added lines (starting with +)
        _make_card_dir(tmp_path, "c1", patch_text=NEW_FILE_PATCH)
        result = compute_cat4_scores(tmp_path, ["c1"])
        assert result.engine_churn == 3

    def test_churn_accumulates_across_cards(self, tmp_path):
        _make_card_dir(tmp_path, "c1", patch_text=SIMPLE_PATCH)
        _make_card_dir(tmp_path, "c2", patch_text=NEW_FILE_PATCH)
        result = compute_cat4_scores(tmp_path, ["c1", "c2"])
        assert result.engine_churn == 5  # 2 + 3


# ---------------------------------------------------------------------------
# Mechanic reuse rate
# ---------------------------------------------------------------------------


class TestMechanicReuseRate:
    """Mechanic reuse detects imports of engine files added by earlier cards."""

    def test_no_reuse_single_card(self, tmp_path):
        _make_card_dir(tmp_path, "c1", patch_text=NEW_FILE_PATCH)
        result = compute_cat4_scores(tmp_path, ["c1"])
        assert result.mechanic_reuse_rate == pytest.approx(0.0)

    def test_reuse_detected(self, tmp_path):
        # Card 1 adds engine/keywords.py, card 2 imports from engine.keywords
        _make_card_dir(tmp_path, "c1", patch_text=NEW_FILE_PATCH)
        _make_card_dir(tmp_path, "c2", patch_text=IMPORT_PATCH)
        result = compute_cat4_scores(tmp_path, ["c1", "c2"])
        # reuse_count=1 / max(total_cards-1, 0) = 1/1 = 1.0
        assert result.mechanic_reuse_rate == pytest.approx(1.0)

    def test_no_reuse_when_no_prior_files(self, tmp_path):
        """First card can't reuse anything, second card adds but doesn't import."""
        _make_card_dir(tmp_path, "c1", patch_text=SIMPLE_PATCH)
        _make_card_dir(tmp_path, "c2", patch_text=NEW_FILE_PATCH)
        result = compute_cat4_scores(tmp_path, ["c1", "c2"])
        assert result.mechanic_reuse_rate == pytest.approx(0.0)

    def test_partial_reuse(self, tmp_path):
        """3 cards: first adds file, second reuses, third doesn't."""
        _make_card_dir(tmp_path, "c1", patch_text=NEW_FILE_PATCH)
        _make_card_dir(tmp_path, "c2", patch_text=IMPORT_PATCH)
        _make_card_dir(tmp_path, "c3", patch_text=SIMPLE_PATCH)
        result = compute_cat4_scores(tmp_path, ["c1", "c2", "c3"])
        # reuse_count=1, divisor=max(3-1,0)=2 -> 0.5
        assert result.mechanic_reuse_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Leaderboard includes Category 4
# ---------------------------------------------------------------------------


class TestLeaderboardCategory4:
    """generate_leaderboard includes Category 4 table."""

    def test_category4_header_present(self):
        lb = Leaderboard(
            category4={"agent_x": AgentCat4Scores(
                regression_rate=0.2,
                regression_free_streak=5,
                engine_churn=42,
                mechanic_reuse_rate=0.75,
            )}
        )
        md = generate_leaderboard(lb)
        assert "Category 4" in md
        assert "Engine Extension Quality" in md

    def test_category4_table_columns(self):
        lb = Leaderboard(
            category4={"agent_x": AgentCat4Scores(
                regression_rate=0.2,
                regression_free_streak=5,
                engine_churn=42,
                mechanic_reuse_rate=0.75,
            )}
        )
        md = generate_leaderboard(lb)
        assert "Regression Rate" in md
        assert "Reg-Free Streak" in md
        assert "Engine Churn" in md
        assert "Mechanic Reuse" in md

    def test_category4_agent_data_in_table(self):
        lb = Leaderboard(
            category4={"agent_x": AgentCat4Scores(
                regression_rate=0.2,
                regression_free_streak=5,
                engine_churn=42,
                mechanic_reuse_rate=0.75,
            )}
        )
        md = generate_leaderboard(lb)
        assert "agent_x" in md
        assert "42" in md  # engine_churn rendered
        assert "5" in md   # streak rendered

    def test_empty_category4(self):
        lb = Leaderboard()
        md = generate_leaderboard(lb)
        # Should still have the Category 4 header
        assert "Category 4" in md


# ---------------------------------------------------------------------------
# save_aggregates includes Category 4
# ---------------------------------------------------------------------------


class TestSaveAggregatesCategory4:
    """save_aggregates writes Category 4 data to summary.json."""

    def test_summary_json_has_category4(self, tmp_path):
        from silverquillm.results import save_aggregates

        results_dir = tmp_path / "results"
        lb = Leaderboard(
            category4={"agent_a": AgentCat4Scores(
                regression_rate=0.1,
                regression_free_streak=8,
                engine_churn=100,
                mechanic_reuse_rate=0.5,
            )}
        )
        save_aggregates(results_dir, [], lb)

        summary = json.loads((results_dir / "summary.json").read_text())
        assert "category4" in summary["leaderboard"]
        cat4_data = summary["leaderboard"]["category4"]["agent_a"]
        assert cat4_data["regression_rate"] == pytest.approx(0.1)
        assert cat4_data["regression_free_streak"] == 8
        assert cat4_data["engine_churn"] == 100
        assert cat4_data["mechanic_reuse_rate"] == pytest.approx(0.5)

    def test_leaderboard_md_written(self, tmp_path):
        from silverquillm.results import save_aggregates

        results_dir = tmp_path / "results"
        lb = Leaderboard(
            category4={"agent_b": AgentCat4Scores(
                regression_rate=0.0,
                regression_free_streak=10,
                engine_churn=50,
                mechanic_reuse_rate=1.0,
            )}
        )
        save_aggregates(results_dir, [], lb)

        md = (results_dir / "leaderboard.md").read_text()
        assert "Category 4" in md
        assert "agent_b" in md
