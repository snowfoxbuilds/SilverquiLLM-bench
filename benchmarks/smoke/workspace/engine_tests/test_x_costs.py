"""A spell with {X} in its cost: X is chosen while casting (rule 601.2b) and
paid as part of the total cost (601.2f); on the stack its mana value counts X
(202.3e), and the permanent it becomes keeps that choice (400.7d)."""

from __future__ import annotations

from engine.card import Creature
from engine.decisions import Decision
from engine.types import ManaCost, ManaType, Zone
from test_utils import behavioral_game, cast_card, fund_mana_cost, prefer


class _XCounterCreature(Creature):
    """{X}{R} 1/1: enters with X +1/+1 counters."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="X Counter Creature", mana_cost=ManaCost.parse("{X}{R}"),
            base_power=1, base_toughness=1, **kwargs,
        )

    def enters_battlefield_with(self, game, event) -> None:
        x_value = getattr(self, "x_value", 0)
        if event.from_zone == Zone.STACK and x_value > 0:
            event.counters["+1/+1"] = event.counters.get("+1/+1", 0) + x_value


def _cast_with_three_extra_mana(chosen_x: int):
    game = behavioral_game()
    player = game.players[0]
    creature = _XCounterCreature(owner=player)
    fund_mana_cost(player, creature.mana_cost)
    player.mana_pool.add(ManaType.COLORLESS, 3)
    prefer(player, Decision.number(chosen_x))
    cast_card(game, player, creature)
    return game, player, creature


def test_x_is_chosen_paid_and_kept_by_the_permanent():
    game, player, creature = _cast_with_three_extra_mana(3)
    assert game.get_battlefield(player).contains(creature)
    assert player.mana_pool.total() == 0
    assert creature.counters.get("+1/+1", 0) == 3
    assert creature.power == 4


def test_x_of_zero_pays_no_extra_mana_and_adds_no_counters():
    game, player, creature = _cast_with_three_extra_mana(0)
    assert game.get_battlefield(player).contains(creature)
    assert player.mana_pool.total() == 3
    assert creature.counters == {}
