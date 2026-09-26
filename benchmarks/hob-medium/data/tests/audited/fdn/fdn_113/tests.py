"""Sylvan Scavenging resolves its controller's end-step token choice."""

from cards.fdn.fdn_113.card_impl import SylvanScavenging
from engine.card import Creature
from engine.decisions import Decision
from engine.protection import get_colors
from engine.types import Color, Phase, Step
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    enter_permanent,
    prefer,
    put_on_battlefield,
    resolve_stack,
)


def test_end_step_token_mode_mints_green_raccoon():
    game = behavioral_game()
    player = game.players[0]
    put_on_battlefield(game, player, Creature(name="Behemoth", base_power=4, base_toughness=4))
    enter_permanent(game, player, SylvanScavenging())
    prefer(player, Decision.mode("token"))
    advance_game_to_phase(game, Phase.ENDING, Step.END)
    resolve_stack(game)
    tokens = [
        card for card in game.get_battlefield(player).get_all() if getattr(card, "is_token", False)
    ]
    assert len(tokens) == 1
    token = tokens[0]
    assert token.name == "Raccoon" and token.subtypes == {"Raccoon"}
    assert (token.base_power, token.base_toughness) == (3, 3)
    assert get_colors(token) == {Color.GREEN}
