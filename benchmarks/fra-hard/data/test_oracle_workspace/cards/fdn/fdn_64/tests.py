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
from test_utils import create_game, resolve_stack, set_board_state


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

        game = create_game()
        p1 = game.players[0]
        sage = InfestationSage()
        set_board_state(game, 0, battlefield=[sage])
        sage.register_triggers(game)

        destroy(game, sage)
        resolve_stack(game)

        insects = _insects(game, p1)
        assert len(insects) == 1
        insect = insects[0]
        assert insect.subtypes == {"Insect"}
        assert (insect.base_power, insect.base_toughness) == (1, 1)
        assert insect.is_token is True
        assert get_colors(insect) == {Color.BLACK, Color.GREEN}
        assert Keyword.FLYING in insect.keywords
