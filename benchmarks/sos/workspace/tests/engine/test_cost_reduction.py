"""Tests for cost-reduction hook in the casting pipeline.

Covers:
- CardImpl.cost_reduction() default returns 0
- get_cost_reduction returns the card's cost_reduction clamped to generic mana
- _apply_cost_reduction creates a new ManaCost with reduced generic
- Reduction cannot go below 0 generic (colored costs are never reduced)
- Zero reduction leaves cost unchanged
- Reduction exactly equal to generic → generic becomes 0
- Reduction exceeding generic → generic floors at 0
- Integration with cast_spell: reduced cost is used for payment
- Cost reduction hook is invoked during the casting pipeline
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.casting import (
    CastingError,
    _apply_cost_reduction,
    get_cost_reduction,
    cast_spell,
)
from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, ManaType, Phase, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
    step: Step | None = None,
) -> GameState:
    p1 = DeterministicPlayer("P1", life=20, script=[])
    p2 = DeterministicPlayer("P2", life=20, script=[])
    game = GameState(players=[p1, p2])
    game.phase = phase
    if step is not None:
        game.step = step
    return game


class ReducedCostCreature(Creature):
    """A creature with {4}{R}{R} that gets a fixed reduction."""

    def __init__(self, reduction: int = 3) -> None:
        super().__init__(
            name="Test Reduced Creature",
            mana_cost=ManaCost.parse("{4}{R}{R}"),
            base_power=4,
            base_toughness=4,
        )
        self._reduction = reduction

    def cost_reduction(self, game: GameState) -> int:
        return self._reduction


class ReducedCostInstant(Instant):
    """An instant with {3}{U} that gets a fixed reduction."""

    def __init__(self, reduction: int = 2) -> None:
        super().__init__(
            name="Test Reduced Instant",
            mana_cost=ManaCost.parse("{3}{U}"),
        )
        self._reduction = reduction

    def cost_reduction(self, game: GameState) -> int:
        return self._reduction


# ---------------------------------------------------------------------------
# Unit tests: CardImpl.cost_reduction default
# ---------------------------------------------------------------------------

class TestCostReductionDefault:
    """The base CardImpl.cost_reduction() must return 0."""

    def test_creature_default_cost_reduction_is_zero(self):
        game = _make_game()
        card = Creature(
            name="Vanilla Bear",
            mana_cost=ManaCost.parse("{1}{G}"),
            base_power=2,
            base_toughness=2,
        )
        assert card.cost_reduction(game) == 0

    def test_instant_default_cost_reduction_is_zero(self):
        game = _make_game()
        card = Instant(name="Zap", mana_cost=ManaCost.parse("{R}"))
        assert card.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# Unit tests: get_cost_reduction
# ---------------------------------------------------------------------------

class TestGetCostReduction:
    """Tests for the get_cost_reduction helper."""

    def test_default_card_has_zero_reduction(self):
        game = _make_game()
        card = Creature(
            name="Vanilla",
            mana_cost=ManaCost.parse("{2}{G}"),
            base_power=2,
            base_toughness=2,
        )
        assert get_cost_reduction(game, card, game.players[0]) == 0

    def test_card_with_reduction_of_3(self):
        """Embercleave scenario: {4}{R}{R} with reduction 3 → returns 3."""
        game = _make_game()
        card = ReducedCostCreature(reduction=3)
        assert get_cost_reduction(game, card, game.players[0]) == 3

    def test_reduction_clamped_to_generic(self):
        """Reduction cannot exceed the generic portion of the cost."""
        game = _make_game()
        card = ReducedCostCreature(reduction=10)
        # Generic is 4, so reduction is clamped to 4
        assert get_cost_reduction(game, card, game.players[0]) == 4

    def test_reduction_exactly_equals_generic(self):
        """Reduction == generic → returns generic (reduces it to 0)."""
        game = _make_game()
        card = ReducedCostCreature(reduction=4)
        assert get_cost_reduction(game, card, game.players[0]) == 4

    def test_negative_reduction_clamped_to_zero(self):
        """Negative reduction values are treated as 0."""
        game = _make_game()
        card = ReducedCostCreature(reduction=-1)
        assert get_cost_reduction(game, card, game.players[0]) == 0

    def test_reduction_on_card_with_no_generic_mana(self):
        """A card like {R}{R} with no generic → reduction is 0."""
        game = _make_game()

        class PureColoredCreature(Creature):
            def __init__(self):
                super().__init__(
                    name="Pure Red",
                    mana_cost=ManaCost.parse("{R}{R}"),
                    base_power=2,
                    base_toughness=1,
                )

            def cost_reduction(self, game):
                return 5

        card = PureColoredCreature()
        # Generic is 0, so even a reduction of 5 is clamped to 0
        assert get_cost_reduction(game, card, game.players[0]) == 0


# ---------------------------------------------------------------------------
# Unit tests: _apply_cost_reduction
# ---------------------------------------------------------------------------

class TestApplyCostReduction:
    """Tests for _apply_cost_reduction."""

    def test_reduce_generic_by_3(self):
        """{4}{R}{R} with reduction 3 → {1}{R}{R}."""
        cost = ManaCost.parse("{4}{R}{R}")
        reduced = _apply_cost_reduction(cost, 3)
        assert reduced.generic == 1
        assert reduced.pips == {ManaType.RED: 2}

    def test_reduce_generic_to_zero(self):
        """{4}{R}{R} with reduction 4 → {0}{R}{R} = {R}{R}."""
        cost = ManaCost.parse("{4}{R}{R}")
        reduced = _apply_cost_reduction(cost, 4)
        assert reduced.generic == 0
        assert reduced.pips == {ManaType.RED: 2}

    def test_zero_reduction_leaves_cost_unchanged(self):
        cost = ManaCost.parse("{4}{R}{R}")
        reduced = _apply_cost_reduction(cost, 0)
        assert reduced.generic == 4
        assert reduced.pips == {ManaType.RED: 2}

    def test_original_cost_not_mutated(self):
        """_apply_cost_reduction must not mutate the original cost."""
        cost = ManaCost.parse("{4}{R}{R}")
        _apply_cost_reduction(cost, 3)
        assert cost.generic == 4

    def test_reduction_beyond_generic_floors_at_zero(self):
        """{1}{R} with reduction 5 → {R} (generic can't go negative)."""
        cost = ManaCost.parse("{1}{R}")
        reduced = _apply_cost_reduction(cost, 5)
        assert reduced.generic == 0
        assert reduced.pips == {ManaType.RED: 1}

    def test_colored_pips_never_reduced(self):
        """{2}{W}{U} with reduction 2 → {W}{U}. Colored pips stay."""
        cost = ManaCost.parse("{2}{W}{U}")
        reduced = _apply_cost_reduction(cost, 2)
        assert reduced.generic == 0
        assert reduced.pips[ManaType.WHITE] == 1
        assert reduced.pips[ManaType.BLUE] == 1

    def test_colored_pips_preserved_when_reduction_exceeds_generic(self):
        """{1}{B}{B}{B} with reduction 99 → {B}{B}{B}."""
        cost = ManaCost.parse("{1}{B}{B}{B}")
        reduced = _apply_cost_reduction(cost, 99)
        assert reduced.generic == 0
        assert reduced.pips[ManaType.BLACK] == 3


# ---------------------------------------------------------------------------
# Integration tests: cast_spell with cost reduction
# ---------------------------------------------------------------------------

class TestCastSpellWithReduction:
    """Integration: cast_spell uses the cost reduction hook."""

    def test_cast_with_reduction_succeeds_with_exact_mana(self):
        """Card costs {4}{R}{R}, reduction 3 → effective {1}{R}{R}.
        Player has 1 generic + 2 red = 3 total mana, should succeed."""
        game = _make_game()
        p1 = game.players[0]
        card = ReducedCostCreature(reduction=3)
        card.owner = p1
        card.controller = p1
        game.get_hand(p1).add(card)

        # Add exactly enough mana for reduced cost: {1}{R}{R}
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        p1.mana_pool.add(ManaType.RED, 2)

        cast_spell(game, p1, card)
        # Card should be on the stack now (as a StackObject)
        assert not game.stack.is_empty()

    def test_cast_with_zero_reduction_needs_full_cost(self):
        """Card with 0 reduction needs full {4}{R}{R} = 6 mana."""
        game = _make_game()
        p1 = game.players[0]
        card = ReducedCostCreature(reduction=0)
        card.owner = p1
        card.controller = p1
        game.get_hand(p1).add(card)

        # Only 3 mana — not enough for full cost
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        p1.mana_pool.add(ManaType.RED, 2)

        with pytest.raises(CastingError):
            cast_spell(game, p1, card)

    def test_cast_with_full_reduction_only_needs_colored(self):
        """Reduction == generic → only colored pips needed.
        {4}{R}{R} with reduction 4 → {R}{R}."""
        game = _make_game()
        p1 = game.players[0]
        card = ReducedCostCreature(reduction=4)
        card.owner = p1
        card.controller = p1
        game.get_hand(p1).add(card)

        # Only 2 red mana — enough when generic is fully reduced
        p1.mana_pool.add(ManaType.RED, 2)

        cast_spell(game, p1, card)
        assert not game.stack.is_empty()

    def test_mana_pool_drained_by_reduced_cost(self):
        """After casting with reduction, mana pool should have leftover mana."""
        game = _make_game()
        p1 = game.players[0]
        card = ReducedCostCreature(reduction=3)
        card.owner = p1
        card.controller = p1
        game.get_hand(p1).add(card)

        # Give 5 mana total: 3 colorless + 2 red
        # Reduced cost is {1}{R}{R} = 3 mana → should have 2 colorless left
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        p1.mana_pool.add(ManaType.RED, 2)

        cast_spell(game, p1, card)
        # 2 colorless should remain (3 - 1 = 2)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
