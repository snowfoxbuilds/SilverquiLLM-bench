"""Mischievous Mystic observes actual draws, including the first-draw negative."""

from cards.fdn.fdn_47.card_impl import MischievousMystic
from engine.game import draw_card
from engine.protection import get_colors
from engine.types import Color, Keyword
from test_utils import behavioral_game, enter_permanent, resolve_stack


def test_second_draw_mints_blue_flying_faerie():
    game = behavioral_game()
    player = game.players[0]
    enter_permanent(game, player, MischievousMystic())
    draw_card(game, player)
    resolve_stack(game)
    assert len(game.get_hand(player).get_all()) == 1
    assert not any(getattr(c, "is_token", False) for c in game.get_battlefield(player).get_all())
    draw_card(game, player)
    resolve_stack(game)
    assert len(game.get_hand(player).get_all()) == 2
    tokens = [c for c in game.get_battlefield(player).get_all() if getattr(c, "is_token", False)]
    assert len(tokens) == 1
    token = tokens[0]
    assert token.name == "Faerie" and token.subtypes == {"Faerie"}
    assert (token.base_power, token.base_toughness) == (1, 1)
    assert get_colors(token) == {Color.BLUE} and token.keywords & Keyword.FLYING
