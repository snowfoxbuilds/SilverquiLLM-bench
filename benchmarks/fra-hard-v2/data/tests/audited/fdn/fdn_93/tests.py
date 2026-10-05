"""Audited tests for FDN 93 — Searslicer Goblin.

"Raid — At the beginning of your end step, if you attacked this turn, create a
1/1 red Goblin creature token." Each test plays the turn through public
actions: a real attack declaration, then the end step (rules 508.1, 207.2c).
"""

from __future__ import annotations

from cards.fdn.fdn_93.card_impl import SearslicerGoblin
from engine.protection import get_colors
from engine.turn import untap_step
from engine.types import Color, Phase, Step
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    declare_attackers,
    declare_blockers,
    enter_permanent,
    resolve_stack,
)


def _goblin_tokens(game, player):
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if getattr(obj, "is_token", False) and "Goblin" in getattr(obj, "subtypes", set())
    ]


def _searslicer_in_play():
    game = behavioral_game()
    player = game.players[0]
    goblin = enter_permanent(game, player, SearslicerGoblin())
    untap_step(game)
    return game, player, goblin


class TestSearslicerGoblinMint:
    def test_raid_end_step_mints_11_red_goblin_token(self) -> None:
        game, player, goblin = _searslicer_in_play()
        declare_attackers(game, [goblin])
        declare_blockers(game, {})
        advance_game_to_phase(game, Phase.ENDING, Step.END)
        resolve_stack(game)

        tokens = _goblin_tokens(game, player)
        assert len(tokens) == 1
        token = tokens[0]
        assert token.subtypes == {"Goblin"}
        assert get_colors(token) == {Color.RED}
        assert (token.power, token.toughness) == (1, 1)

    def test_no_attack_means_no_goblin(self) -> None:
        game, player, _goblin = _searslicer_in_play()
        advance_game_to_phase(game, Phase.ENDING, Step.END)
        resolve_stack(game)
        assert _goblin_tokens(game, player) == []
