"""Known-Best checks moved out of fdn_120's FDN Audited Tests: #169: Known-Best's Fake Your Own Death, the only instant-speed way back to the battlefield, fires its granted dies trigger again for the returned object,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

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
