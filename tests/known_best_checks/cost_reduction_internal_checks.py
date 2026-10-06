"""Known-Best engine checks moved out of the Audited Engine Tests' test_cost_reduction.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_280.card_impl import Forest
from engine.card import Creature
from engine.casting import get_cost_reduction
from engine.game_state import GameState
from engine.types import ManaCost, ManaType, Phase, Step
from test_interface import Side, Zone, card, create_game
from test_utils import DeterministicPlayer

from silverquillm.table import Table, moves, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)


def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
    step: Step | None = None,
) -> GameState:
    p1 = DeterministicPlayer("P1", life=20)
    p2 = DeterministicPlayer("P2", life=20)
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



# ---------------------------------------------------------------------------
# How much a reduction takes off
# ---------------------------------------------------------------------------

class TestGetCostReduction:
    """The reduction a card gets, clamped to its generic mana."""





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



# ---------------------------------------------------------------------------
# Casting with a reduced cost
# ---------------------------------------------------------------------------

