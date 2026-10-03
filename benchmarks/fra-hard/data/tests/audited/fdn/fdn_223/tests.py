"""Audited tests for FDN 223 — Giant Growth.

"Target creature gets +3/+3 until end of turn." The effect is locked onto
that creature when the spell resolves (rule 611.2c); if the creature leaves
the battlefield it returns as a new object the effect no longer applies to
(400.7).
"""

from __future__ import annotations

from cards.fdn.fdn_223.card_impl import GiantGrowth
from engine.card import Creature
from engine.game import destroy, exile
from engine.types import Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    enter_permanent,
    fund_mana_cost,
    object_preference,
    prefer,
)


def _grown():
    game = behavioral_game()
    player = game.players[0]
    target = enter_permanent(game, player, Creature(name="Bear", base_power=2, base_toughness=2))
    bystander = enter_permanent(game, player, Creature(name="Bystander", base_power=1, base_toughness=1))
    spell = GiantGrowth(owner=player)
    fund_mana_cost(player, spell.mana_cost)
    prefer(player, object_preference(game, target))
    cast_card(game, player, spell)
    assert (target.power, target.toughness) == (5, 5)
    return game, player, target, bystander


class TestGiantGrowth:
    def test_target_gets_plus_three_until_end_of_turn(self) -> None:
        game, _player, target, bystander = _grown()
        assert (bystander.power, bystander.toughness) == (1, 1)

        advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
        assert (target.power, target.toughness) == (2, 2)

    def test_pump_ends_when_the_target_is_exiled_and_returned(self) -> None:
        game, player, target, _bystander = _grown()
        exile(game, target)
        move_to_zone(game, target, Zone.EXILE, Zone.BATTLEFIELD)
        assert game.get_battlefield(player).contains(target)
        assert (target.power, target.toughness) == (2, 2)

    def test_pump_ends_when_the_target_dies_and_returns(self) -> None:
        game, player, target, _bystander = _grown()
        destroy(game, target)
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        assert game.get_battlefield(player).contains(target)
        assert (target.power, target.toughness) == (2, 2)
