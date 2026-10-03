"""Reference test for FDN 64 — Infestation Sage.

"When this creature dies, create a 1/1 black and green Insect creature token
with flying." The mint routes through ``make_creature_token``, so this test
drives the death trigger and proves the produced token carries the exact spec
characteristics. The Insect is *two* colours — black and green — which a token
must carry as an explicit ``colors`` set for ``get_colors`` (and the replay
executor's colour correlation) to see, since a token has no mana cost.
"""

from __future__ import annotations

from cards.fdn.fdn_64.card_impl import InfestationSage
from engine.protection import get_colors
from engine.types import Color, Keyword, ManaCost
from test_utils import resolve_stack
from test_utils import scenario_game as create_game


def _insects(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and getattr(o, "name", None) == "Insect"
    ]


class TestInfestationSageProperties:
    def test_static_data(self) -> None:
        c = InfestationSage(owner=None)
        assert c.name == "Infestation Sage"
        assert c.mana_cost == ManaCost.parse("{B}")


class TestInfestationSageDeathToken:
    def test_death_mints_flying_black_green_insect(self) -> None:
        from engine.game import destroy
        from test_utils import enter_permanent

        game = create_game()
        player = game.players[0]
        sage = enter_permanent(game, player, InfestationSage())
        destroy(game, sage)
        resolve_stack(game)
        tokens = [
            c for c in game.get_battlefield(player).get_all() if getattr(c, "is_token", False)
        ]
        assert len(tokens) == 1
        token = tokens[0]
        assert token.subtypes == {"Insect"} and get_colors(token) == {Color.BLACK, Color.GREEN}
        assert (token.power, token.toughness) == (1, 1) and token.keywords & Keyword.FLYING
