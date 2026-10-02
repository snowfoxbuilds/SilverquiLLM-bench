"""Audited tests for FDN 200 — Goblin Surprise.

"Choose one — • Creatures you control get +2/+0 until end of turn.
• Create two 1/1 red Goblin creature tokens."

The mode is chosen while casting (rule 601.2b, 700.2a), so each test casts the
spell with a mode preference and observes the resolved outcome.
"""

from __future__ import annotations

from cards.fdn.fdn_200.card_impl import GoblinSurprise
from engine.card import Creature
from engine.decisions import Decision
from engine.protection import get_colors
from engine.types import Color, Phase, Step
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    enter_permanent,
    fund_mana_cost,
    prefer,
)


def _goblin_tokens(game, player):
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if getattr(obj, "is_token", False) and "Goblin" in getattr(obj, "subtypes", set())
    ]


def _cast(mode: str):
    game = behavioral_game()
    player = game.players[0]
    spell = GoblinSurprise(owner=player)
    fund_mana_cost(player, spell.mana_cost)
    prefer(player, Decision.mode(mode))
    return game, player, spell


class TestGoblinSurpriseMint:
    def test_token_mode_mints_two_11_red_goblin_tokens(self) -> None:
        game, player, spell = _cast("Tokens")
        cast_card(game, player, spell)

        goblins = _goblin_tokens(game, player)
        assert len(goblins) == 2
        for token in goblins:
            assert token.subtypes == {"Goblin"}
            assert get_colors(token) == {Color.RED}
            assert (token.power, token.toughness) == (1, 1)
            assert token.is_token is True
        assert player.mana_pool.total() == 0


class TestGoblinSurprisePump:
    def test_pump_mode_gives_creatures_you_control_plus_two_until_end_of_turn(self) -> None:
        game, player, spell = _cast("Pump")
        opponent = game.players[1]
        mine = enter_permanent(game, player, Creature(name="Mine", base_power=2, base_toughness=2))
        theirs = enter_permanent(game, opponent, Creature(name="Theirs", base_power=2, base_toughness=2))
        cast_card(game, player, spell)

        assert (mine.power, mine.toughness) == (4, 2)
        assert (theirs.power, theirs.toughness) == (2, 2)
        assert _goblin_tokens(game, player) == []

        advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
        assert (mine.power, mine.toughness) == (2, 2)
