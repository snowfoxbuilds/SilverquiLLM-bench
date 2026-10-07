"""The cost-reduction hook in the casting pipeline.

A spell's cost is its printed cost less its reduction, the reduction never
taking more than the generic part (colored mana is never reduced) and a card
with no reduction costing its printed cost. Each is seen by what a player can
cast with the mana in their pool: Ghalta, Primal Hunger costs {X} less, X
being the total power of its controller's creatures, so the creatures on the
battlefield set its reduction.

``_apply_cost_reduction`` is still checked directly: it is pure arithmetic on
a mana cost, with no game.
"""

from __future__ import annotations

from cards.fdn.fdn_100.card_impl import BeastKinRanger
from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_222.card_impl import GhaltaPrimalHunger
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_280.card_impl import Forest
from cards.fdn.spg_80.card_impl import ParadiseDruid
from test_interface import Side, Zone, card, create_game

from engine.card import Creature
from engine.casting import _apply_cost_reduction
from engine.game_state import GameState
from engine.types import ManaCost, ManaType, Phase
from table import Table, moves, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)


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


def _short_by_one_then_paid(spell, battlefield, green: int, *, note: str) -> None:
    """With ``green`` mana in the pool the spell cannot be cast; one more
    green, from a Forest, pays for it, and it resolves."""
    forest = card(Forest)
    game = create_game(
        Side(hand=[spell], battlefield=[forest, *battlefield], mana={ManaType.GREEN: green}),
        Side(),
        start=MAIN,
    )
    t = Table(game)
    t.act_illegal(0, spell, note=f"{green} mana is one short: {note}")
    t.act(0, forest, then=[taps(forest)])
    t.act(0, spell, then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(spell, Zone.BATTLEFIELD)])
    t.run()


# ---------------------------------------------------------------------------
# A card with no reduction costs its printed cost
# ---------------------------------------------------------------------------

class TestCostReductionDefault:
    """A card with no cost reduction costs exactly its printed cost."""

    def test_creature_default_cost_reduction_is_zero(self):
        _short_by_one_then_paid(card(BeastKinRanger), [], 2, note="Beast-Kin Ranger costs its full {2}{G}")

    def test_instant_default_cost_reduction_is_zero(self):
        think, island, drawn = card(ThinkTwice), card(Island), card(Plains)
        game = create_game(
            Side(hand=[think], battlefield=[island], library=[drawn], mana={ManaType.BLUE: 1}),
            Side(),
            start=MAIN,
        )
        t = Table(game)
        t.act_illegal(0, think, note="Think Twice costs its full {1}{U}")
        t.act(0, island, then=[taps(island)])
        t.act(0, think, then=[moves(think, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(think, Zone.GRAVEYARD), moves(drawn, Zone.HAND)])
        t.run()


# ---------------------------------------------------------------------------
# How much a reduction takes off
# ---------------------------------------------------------------------------

class TestGetCostReduction:
    """The reduction a card gets, clamped to its generic mana."""

    def test_default_card_has_zero_reduction(self):
        _short_by_one_then_paid(
            card(QuakestriderCeratops), [], 5, note="Quakestrider Ceratops costs its full {3}{G}{G}{G}"
        )

    def test_card_with_reduction_of_3(self):
        _short_by_one_then_paid(
            card(GhaltaPrimalHunger), [BrazenScourge], 8, note="power 3 takes {3} off Ghalta: {7}{G}{G}"
        )

    def test_reduction_clamped_to_generic(self):
        _short_by_one_then_paid(
            card(GhaltaPrimalHunger),
            [QuakestriderCeratops],
            1,
            note="power 12 takes off only Ghalta's {10}: {G}{G} remain",
        )

    def test_reduction_exactly_equals_generic(self):
        _short_by_one_then_paid(
            card(GhaltaPrimalHunger),
            [BrazenScourge, BrazenScourge, SavannahLions, SavannahLions],
            1,
            note="power 10 takes off all of Ghalta's {10}: {G}{G} remain",
        )




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
# Casting with a reduced cost
# ---------------------------------------------------------------------------

class TestCastSpellWithReduction:
    """Casting pays the reduced cost from the mana pool."""

    def test_cast_with_reduction_succeeds_with_exact_mana(self):
        """Power 9 makes Ghalta {1}{G}{G}: three mana casts it."""
        ghalta = card(GhaltaPrimalHunger)
        game = create_game(
            Side(hand=[ghalta], battlefield=[BrazenScourge] * 3, mana={ManaType.GREEN: 3}),
            Side(),
            start=MAIN,
        )
        t = Table(game)
        t.act(0, ghalta, then=[moves(ghalta, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(ghalta, Zone.BATTLEFIELD)])
        t.run()

    def test_cast_with_zero_reduction_needs_full_cost(self):
        """With no creatures Ghalta costs all twelve mana: three is not enough."""
        ghalta = card(GhaltaPrimalHunger)
        game = create_game(Side(hand=[ghalta], mana={ManaType.GREEN: 3}), Side(), start=MAIN)
        t = Table(game)
        t.act_illegal(0, ghalta, note="no reduction: Ghalta costs {10}{G}{G}")
        t.run()

    def test_cast_with_full_reduction_only_needs_colored(self):
        """Power 12 removes all of Ghalta's generic mana: {G}{G} casts it."""
        ghalta = card(GhaltaPrimalHunger)
        game = create_game(
            Side(hand=[ghalta], battlefield=[QuakestriderCeratops], mana={ManaType.GREEN: 2}),
            Side(),
            start=MAIN,
        )
        t = Table(game)
        t.act(0, ghalta, then=[moves(ghalta, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(ghalta, Zone.BATTLEFIELD)])
        t.run()

    def test_mana_pool_drained_by_reduced_cost(self):
        """Ghalta at {1}{G}{G} out of five green leaves exactly two: enough
        for Paradise Druid's {1}{G}, and then nothing for Llanowar Elves."""
        ghalta, druid, elves = card(GhaltaPrimalHunger), card(ParadiseDruid), card(LlanowarElves)
        game = create_game(
            Side(hand=[ghalta, druid, elves], battlefield=[BrazenScourge] * 3, mana={ManaType.GREEN: 5}),
            Side(),
            start=MAIN,
        )
        t = Table(game)
        t.act(0, ghalta, then=[moves(ghalta, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(ghalta, Zone.BATTLEFIELD)])
        t.act(0, druid, then=[moves(druid, Zone.STACK)], note="two green are left")
        t.pass_(0)
        t.pass_(1, then=[moves(druid, Zone.BATTLEFIELD)])
        t.act_illegal(0, elves, note="and no more")
        t.run()
