"""Reference test for FDN 176 — Liliana, Dreadhorde General (+1 Zombie).

Phase H implements Liliana's ``+1: Create a 2/2 black Zombie creature token``
(grpId 94170). This drives the +1 through the real loyalty-activation path and
asserts the minted token's characteristics match the token map. (The passive
dies-trigger draw and the -4/-9 abilities are simplified stubs, out of scope.)
"""

from __future__ import annotations

from cards.fdn.fdn_176.card_impl import LilianaDreadhordeGeneral
from engine.protection import get_colors
from engine.types import CardType, Color, Phase, Zone
from test_utils import (
    activate_loyalty_ability,
    create_game,
    resolve_stack,
    set_board_state,
)


def _zombie_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and "Zombie" in getattr(o, "subtypes", set())
    ]


class TestLilianaPlusOne:
    def test_plus_one_mints_a_2_2_black_zombie(self) -> None:
        game = create_game()
        player = game.players[0]
        liliana = LilianaDreadhordeGeneral()
        set_board_state(game, 0, battlefield=[liliana])
        game.phase = Phase.PRECOMBAT_MAIN
        assert _zombie_tokens(game, 0) == []

        # +1 is loyalty index 0; drive it through the real activation path.
        activate_loyalty_ability(game, player, liliana, 0)
        resolve_stack(game)

        zombies = _zombie_tokens(game, 0)
        assert len(zombies) == 1
        zombie = zombies[0]
        assert CardType.CREATURE in zombie.card_types
        assert zombie.subtypes == {"Zombie"}
        assert zombie.base_power == 2 and zombie.base_toughness == 2
        assert get_colors(zombie) == {Color.BLACK}
        # +1 raised loyalty from 6 to 7.
        assert liliana.loyalty == 7
