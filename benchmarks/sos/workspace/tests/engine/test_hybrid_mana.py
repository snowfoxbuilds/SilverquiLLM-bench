"""Tests for hybrid mana parsing and cost payment.

Verifies:
- ManaCost.parse() correctly handles hybrid mana symbols like {B/G}.
- Hybrid symbols are generic — any two-color hybrid pair works ({W/U}, {R/G}, etc.).
- Mixed costs with hybrid + generic + colored pips parse correctly.
- CMC includes hybrid symbols (each counts as 1).
- ManaPool.can_pay() correctly evaluates hybrid costs with backtracking.
- ManaPool.pay() correctly deducts mana for hybrid costs.
- Payment works with only one color available, only the other, and mixed pools.
- Edge cases: empty pool, insufficient mana, multiple hybrid symbols competing
  for the same color.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.types import HybridManaSymbol, ManaCost, ManaType


# ---------------------------------------------------------------------------
# Parsing — hybrid mana symbols
# ---------------------------------------------------------------------------
class TestHybridManaParsing:
    """Tests for ManaCost.parse() with hybrid mana symbols."""

    def test_parse_single_bg_hybrid(self) -> None:
        """Parsing {B/G} should produce one hybrid symbol with BLACK and GREEN."""
        mc = ManaCost.parse("{B/G}")
        assert mc.generic == 0
        assert mc.pips == {}
        assert len(mc.hybrid) == 1
        assert mc.hybrid[0].option_a == ManaType.BLACK
        assert mc.hybrid[0].option_b == ManaType.GREEN

    def test_parse_double_bg_hybrid_fiend_artisan(self) -> None:
        """Parsing {B/G}{B/G} (Fiend Artisan) should produce two hybrid symbols."""
        mc = ManaCost.parse("{B/G}{B/G}")
        assert mc.generic == 0
        assert mc.pips == {}
        assert len(mc.hybrid) == 2
        for sym in mc.hybrid:
            assert sym.option_a == ManaType.BLACK
            assert sym.option_b == ManaType.GREEN

    def test_parse_wu_hybrid(self) -> None:
        """Parsing {W/U} should produce a WHITE/BLUE hybrid symbol."""
        mc = ManaCost.parse("{W/U}")
        assert len(mc.hybrid) == 1
        assert mc.hybrid[0].option_a == ManaType.WHITE
        assert mc.hybrid[0].option_b == ManaType.BLUE

    def test_parse_rg_hybrid(self) -> None:
        """Parsing {R/G} should produce a RED/GREEN hybrid symbol."""
        mc = ManaCost.parse("{R/G}")
        assert len(mc.hybrid) == 1
        assert mc.hybrid[0].option_a == ManaType.RED
        assert mc.hybrid[0].option_b == ManaType.GREEN

    def test_parse_wb_hybrid(self) -> None:
        """Parsing {W/B} should produce a WHITE/BLACK hybrid symbol."""
        mc = ManaCost.parse("{W/B}")
        assert len(mc.hybrid) == 1
        assert mc.hybrid[0].option_a == ManaType.WHITE
        assert mc.hybrid[0].option_b == ManaType.BLACK

    def test_parse_ur_hybrid(self) -> None:
        """Parsing {U/R} should produce a BLUE/RED hybrid symbol."""
        mc = ManaCost.parse("{U/R}")
        assert len(mc.hybrid) == 1
        assert mc.hybrid[0].option_a == ManaType.BLUE
        assert mc.hybrid[0].option_b == ManaType.RED

    def test_parse_hybrid_with_generic(self) -> None:
        """Parsing {2}{B/G} should produce generic=2 and one hybrid symbol."""
        mc = ManaCost.parse("{2}{B/G}")
        assert mc.generic == 2
        assert mc.pips == {}
        assert len(mc.hybrid) == 1
        assert mc.hybrid[0].option_a == ManaType.BLACK
        assert mc.hybrid[0].option_b == ManaType.GREEN

    def test_parse_hybrid_with_colored_pips(self) -> None:
        """Parsing {R}{B/G} should produce one red pip and one hybrid symbol."""
        mc = ManaCost.parse("{R}{B/G}")
        assert mc.generic == 0
        assert mc.pips == {ManaType.RED: 1}
        assert len(mc.hybrid) == 1
        assert mc.hybrid[0].option_a == ManaType.BLACK
        assert mc.hybrid[0].option_b == ManaType.GREEN

    def test_parse_hybrid_with_generic_and_colored(self) -> None:
        """Parsing {1}{W}{W/U} — generic + colored pip + hybrid."""
        mc = ManaCost.parse("{1}{W}{W/U}")
        assert mc.generic == 1
        assert mc.pips == {ManaType.WHITE: 1}
        assert len(mc.hybrid) == 1
        assert mc.hybrid[0].option_a == ManaType.WHITE
        assert mc.hybrid[0].option_b == ManaType.BLUE

    def test_parse_multiple_different_hybrids(self) -> None:
        """Parsing {W/U}{B/G} should produce two different hybrid symbols."""
        mc = ManaCost.parse("{W/U}{B/G}")
        assert len(mc.hybrid) == 2
        assert mc.hybrid[0].option_a == ManaType.WHITE
        assert mc.hybrid[0].option_b == ManaType.BLUE
        assert mc.hybrid[1].option_a == ManaType.BLACK
        assert mc.hybrid[1].option_b == ManaType.GREEN


# ---------------------------------------------------------------------------
# CMC — hybrid symbols contribute 1 each
# ---------------------------------------------------------------------------
class TestHybridManaCMC:
    """Tests for ManaCost.cmc with hybrid symbols."""

    def test_cmc_single_hybrid(self) -> None:
        """A single hybrid symbol should have CMC of 1."""
        mc = ManaCost.parse("{B/G}")
        assert mc.cmc == 1

    def test_cmc_double_hybrid(self) -> None:
        """{B/G}{B/G} should have CMC of 2."""
        mc = ManaCost.parse("{B/G}{B/G}")
        assert mc.cmc == 2

    def test_cmc_hybrid_plus_generic(self) -> None:
        """{2}{B/G} should have CMC of 3."""
        mc = ManaCost.parse("{2}{B/G}")
        assert mc.cmc == 3

    def test_cmc_hybrid_plus_colored_pip(self) -> None:
        """{R}{W/U} should have CMC of 2."""
        mc = ManaCost.parse("{R}{W/U}")
        assert mc.cmc == 2


# ---------------------------------------------------------------------------
# can_pay — hybrid costs
# ---------------------------------------------------------------------------
class TestHybridManaCanPay:
    """Tests for ManaPool.can_pay() with hybrid mana costs."""

    def test_can_pay_bg_hybrid_with_only_black(self) -> None:
        """{B/G}{B/G} should be payable with 2 black mana."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 2)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.can_pay(cost) is True

    def test_can_pay_bg_hybrid_with_only_green(self) -> None:
        """{B/G}{B/G} should be payable with 2 green mana."""
        pool = ManaPool()
        pool.add(ManaType.GREEN, 2)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.can_pay(cost) is True

    def test_can_pay_bg_hybrid_with_mixed(self) -> None:
        """{B/G}{B/G} should be payable with 1 black + 1 green."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 1)
        pool.add(ManaType.GREEN, 1)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.can_pay(cost) is True

    def test_cannot_pay_bg_hybrid_with_wrong_color(self) -> None:
        """{B/G}{B/G} should NOT be payable with 2 red mana."""
        pool = ManaPool()
        pool.add(ManaType.RED, 2)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.can_pay(cost) is False

    def test_cannot_pay_bg_hybrid_with_empty_pool(self) -> None:
        """{B/G} should NOT be payable with an empty pool."""
        pool = ManaPool()
        cost = ManaCost.parse("{B/G}")
        assert pool.can_pay(cost) is False

    def test_cannot_pay_bg_hybrid_insufficient_mana(self) -> None:
        """{B/G}{B/G} should NOT be payable with only 1 black and no green."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 1)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.can_pay(cost) is False

    def test_can_pay_hybrid_plus_generic_with_excess(self) -> None:
        """{2}{B/G} should be payable with 1 black + 2 colorless."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 1)
        pool.add(ManaType.COLORLESS, 2)
        cost = ManaCost.parse("{2}{B/G}")
        assert pool.can_pay(cost) is True

    def test_cannot_pay_hybrid_plus_generic_insufficient(self) -> None:
        """{2}{B/G} needs 3 total; 1 black + 1 colorless is only 2."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 1)
        pool.add(ManaType.COLORLESS, 1)
        cost = ManaCost.parse("{2}{B/G}")
        assert pool.can_pay(cost) is False

    def test_can_pay_hybrid_backtracking_needed(self) -> None:
        """Two different hybrids competing for the same color require backtracking.

        Cost: {W/U}{U/R} with pool of 1W + 1U.
        Greedy would assign W to first hybrid, then U to second — works.
        But also W→first, R→second would fail (no R).
        The solver must find the valid assignment.
        """
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        pool.add(ManaType.BLUE, 1)
        cost = ManaCost.parse("{W/U}{U/R}")
        assert pool.can_pay(cost) is True

    def test_can_pay_hybrid_backtracking_constraint(self) -> None:
        """Two hybrids sharing a color with only 1 of that color available.

        Cost: {W/U}{W/B} with pool 1W + 1U.
        Greedy assigns W to first — then second needs W or B, neither available.
        Backtrack: assign U to first, then W to second — works.
        """
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        pool.add(ManaType.BLUE, 1)
        cost = ManaCost.parse("{W/U}{W/B}")
        assert pool.can_pay(cost) is True

    def test_cannot_pay_hybrid_backtracking_impossible(self) -> None:
        """Two hybrids sharing colors where no valid assignment exists.

        Cost: {W/U}{W/U} with pool 1W + 0U — only 1 mana for 2 hybrid symbols.
        """
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        cost = ManaCost.parse("{W/U}{W/U}")
        assert pool.can_pay(cost) is False


# ---------------------------------------------------------------------------
# pay — hybrid costs
# ---------------------------------------------------------------------------
class TestHybridManaPay:
    """Tests for ManaPool.pay() with hybrid mana costs."""

    def test_pay_bg_hybrid_with_only_black(self) -> None:
        """{B/G}{B/G} paid with 2 black should deduct 2 black."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 2)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.pay(cost) is True
        assert pool.get(ManaType.BLACK) == 0
        assert pool.total() == 0

    def test_pay_bg_hybrid_with_only_green(self) -> None:
        """{B/G}{B/G} paid with 2 green should deduct 2 green."""
        pool = ManaPool()
        pool.add(ManaType.GREEN, 2)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.pay(cost) is True
        assert pool.get(ManaType.GREEN) == 0

    def test_pay_bg_hybrid_with_mixed(self) -> None:
        """{B/G}{B/G} paid with 1B + 1G should deduct one of each."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 1)
        pool.add(ManaType.GREEN, 1)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.pay(cost) is True
        assert pool.total() == 0

    def test_pay_hybrid_insufficient_returns_false(self) -> None:
        """pay should return False when pool cannot cover hybrid cost."""
        pool = ManaPool()
        pool.add(ManaType.RED, 2)
        cost = ManaCost.parse("{B/G}{B/G}")
        assert pool.pay(cost) is False

    def test_pay_hybrid_insufficient_leaves_pool_unchanged(self) -> None:
        """Failed hybrid payment should not modify the pool."""
        pool = ManaPool()
        pool.add(ManaType.RED, 2)
        cost = ManaCost.parse("{B/G}{B/G}")
        pool.pay(cost)
        assert pool.get(ManaType.RED) == 2
        assert pool.total() == 2

    def test_pay_hybrid_plus_generic(self) -> None:
        """{2}{B/G} with 1B + 2C should succeed and deduct correctly."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 1)
        pool.add(ManaType.COLORLESS, 2)
        cost = ManaCost.parse("{2}{B/G}")
        assert pool.pay(cost) is True
        assert pool.get(ManaType.BLACK) == 0
        assert pool.get(ManaType.COLORLESS) == 0

    def test_pay_hybrid_plus_colored_pip(self) -> None:
        """{R}{B/G} with 1R + 1G should deduct correctly."""
        pool = ManaPool()
        pool.add(ManaType.RED, 1)
        pool.add(ManaType.GREEN, 1)
        cost = ManaCost.parse("{R}{B/G}")
        assert pool.pay(cost) is True
        assert pool.get(ManaType.RED) == 0
        assert pool.get(ManaType.GREEN) == 0

    def test_pay_hybrid_leaves_excess_mana(self) -> None:
        """{B/G} with 3B should deduct only 1 black, leaving 2."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 3)
        cost = ManaCost.parse("{B/G}")
        assert pool.pay(cost) is True
        assert pool.get(ManaType.BLACK) == 2

    def test_pay_hybrid_tracks_color_spent(self) -> None:
        """After paying {B/G} with black, last_payment_colors should include BLACK."""
        pool = ManaPool()
        pool.add(ManaType.BLACK, 1)
        cost = ManaCost.parse("{B/G}")
        pool.pay(cost)
        from benchmarks.sos.workspace.engine.types import Color
        assert Color.BLACK in pool.last_payment_colors
