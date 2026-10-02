"""Audited tests for FDN 88 — Goblin Negotiation.

"Goblin Negotiation deals X damage to target creature. Create a number of 1/1
red Goblin creature tokens equal to the amount of excess damage dealt to that
creature this way." X is chosen and paid while casting (rules 107.3a, 601.2b,
601.2f).
"""

from __future__ import annotations

from cards.fdn.fdn_88.card_impl import GoblinNegotiation
from engine.card import Creature
from engine.decisions import Decision
from engine.protection import get_colors
from engine.types import Color, ManaType
from test_utils import (
    behavioral_game,
    cast_card,
    fund_mana_cost,
    object_preference,
    prefer,
    put_on_battlefield,
)


def _goblin_tokens(game, player):
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if getattr(obj, "is_token", False) and "Goblin" in getattr(obj, "subtypes", set())
    ]


class TestGoblinNegotiationMint:
    def test_excess_damage_mints_11_red_goblin_tokens(self) -> None:
        game = behavioral_game()
        player, opponent = game.players
        target = put_on_battlefield(
            game, opponent, Creature(name="Grizzly Bears", subtypes={"Bear"}, base_power=2, base_toughness=2)
        )
        spell = GoblinNegotiation(owner=player)
        fund_mana_cost(player, spell.mana_cost)
        player.mana_pool.add(ManaType.COLORLESS, 4)
        prefer(player, Decision.number(4), object_preference(game, target))
        cast_card(game, player, spell)

        # X = 4 dealt to a 2/2: 2 lethal, 2 excess -> two Goblin tokens.
        assert player.mana_pool.total() == 0
        assert game.get_graveyard(opponent).contains(target)
        goblins = _goblin_tokens(game, player)
        assert len(goblins) == 2
        for token in goblins:
            assert token.subtypes == {"Goblin"}
            assert get_colors(token) == {Color.RED}
            assert (token.power, token.toughness) == (1, 1)
