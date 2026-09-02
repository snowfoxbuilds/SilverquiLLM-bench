"""Reference test for FDN 47 — Mischievous Mystic (token identity).

"Whenever you draw your second card each turn, create a 1/1 blue Faerie
creature token with flying." The mint routes through the shared
``make_creature_token`` factory. This test drives two draw events through the
registered trigger — proving the first draw mints nothing and the second draw
mints the Faerie — and pins that token's identity (subtypes, explicit blue
colour, base P/T, flying, ``is_token``).
"""
from __future__ import annotations

from cards.fdn.fdn_47.card_impl import MischievousMystic
from engine.events import DrawsCardTriggeredEvent
from engine.protection import get_colors
from engine.stack import priority_loop
from engine.types import Color, Keyword
from test_utils import create_game, set_board_state


def _faerie_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and getattr(o, "name", None) == "Faerie"
    ]


class TestMischievousMysticToken:
    def test_second_draw_mints_blue_flying_faerie(self) -> None:
        game = create_game()
        p1 = game.players[0]
        mystic = MischievousMystic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[mystic])
        mystic.register_triggers(game)

        # First draw this turn: nothing (only the *second* draw triggers).
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        priority_loop(game)
        assert len(_faerie_tokens(game, p1)) == 0

        # Second draw this turn mints the Faerie.
        game.trigger_manager.fire_event(game, DrawsCardTriggeredEvent(player=p1))
        priority_loop(game)

        tokens = _faerie_tokens(game, p1)
        assert len(tokens) == 1
        tok = tokens[0]
        assert tok.subtypes == {"Faerie"}
        assert get_colors(tok) == {Color.BLUE}
        assert (tok.base_power, tok.base_toughness) == (1, 1)
        assert Keyword.FLYING & tok.keywords
        assert tok.is_token is True
