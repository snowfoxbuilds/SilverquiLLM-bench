"""Reference test for FDN 204 — Krenko, Mob Boss (Phase H token minter).

"{T}: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins
you control." The mint fires from an activated ability, so activating it through
the real engine path (the same bridge the executor uses) and resolving the stack
drives it directly. With only Krenko (itself a Goblin) on the battlefield, X = 1,
so exactly one 1/1 red Goblin token is minted with the exact characteristics.
"""
from __future__ import annotations

from cards.fdn.fdn_204.card_impl import KrenkoMobBoss
from engine.protection import get_colors
from engine.types import Color, Zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _goblin_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and "Goblin" in getattr(o, "subtypes", set())
    ]


class TestKrenkoMobBossMint:
    def test_activated_ability_mints_11_red_goblin_tokens(self) -> None:
        krenko = KrenkoMobBoss()
        game = create_game()
        set_board_state(game, 0, battlefield=[krenko])

        activate_card_ability(game, game.players[0], krenko, 0)
        resolve_stack(game)

        goblins = _goblin_tokens(game, 0)
        assert len(goblins) == 1  # X = 1 (Krenko is the only Goblin controlled)
        token = goblins[0]
        assert token.subtypes == {"Goblin"}
        assert get_colors(token) == {Color.RED}
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert token.is_token is True
