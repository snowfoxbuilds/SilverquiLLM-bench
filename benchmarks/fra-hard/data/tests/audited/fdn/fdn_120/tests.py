"""Audited tests for FDN 120 — Fiendish Panda.

"When this creature dies, return another target non-Bear creature card with
mana value less than or equal to this creature's power from your graveyard to
the battlefield." Its power is read as it last existed on the battlefield
(rule 603.10a), separately for each time it died.
"""

from __future__ import annotations

from cards.fdn.fdn_120.card_impl import FiendishPanda
from engine.card import Creature
from engine.game import add_counter, destroy
from engine.types import ManaCost, Zone
from engine.zones import move_to_zone
from test_utils import behavioral_game, enter_permanent, resolve_stack


def _dead_creature(game, player, mana_value: int) -> Creature:
    card = Creature(
        name=f"Mana value {mana_value}", mana_cost=ManaCost(generic=mana_value),
        base_power=1, base_toughness=1, owner=player,
    )
    game.get_graveyard(player).add(card)
    return card


class TestFiendishPandaDies:
    def test_returns_a_creature_card_with_mana_value_up_to_its_power(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        returned = _dead_creature(game, player, 3)
        panda = enter_permanent(game, player, FiendishPanda())
        destroy(game, panda)
        resolve_stack(game)
        assert game.get_battlefield(player).contains(returned)

    def test_uses_its_power_as_it_died(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        returned = _dead_creature(game, player, 5)
        panda = enter_permanent(game, player, FiendishPanda())
        add_counter(game, panda, "+1/+1", 3)
        destroy(game, panda)
        resolve_stack(game)
        assert game.get_battlefield(player).contains(returned)

    def test_each_death_keeps_its_own_power(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        returned = _dead_creature(game, player, 5)
        panda = enter_permanent(game, player, FiendishPanda())
        add_counter(game, panda, "+1/+1", 3)
        destroy(game, panda)  # power 6 as it died
        move_to_zone(game, panda, Zone.GRAVEYARD, Zone.BATTLEFIELD)
        destroy(game, panda)  # power 3 this time
        resolve_stack(game)
        assert game.get_battlefield(player).contains(returned)
