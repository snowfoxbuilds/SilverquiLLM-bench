"""Reference test for FDN 200 — Goblin Surprise (Phase H token minter).

Mode 2 of this modal instant is "Create two 1/1 red Goblin creature tokens",
minted from ``on_resolve`` when ``chosen_mode == 1``. The test harness cannot
pick a mode through casting, so this drives ``on_resolve`` directly with the
mode set on the spell — the same code path the executor runs — and proves both
Goblins carry the exact 1/1 red Goblin characteristics.
"""
from __future__ import annotations

from cards.fdn.fdn_200.card_impl import GoblinSurprise
from engine.protection import get_colors
from engine.types import Color, Zone
from test_utils import create_game


def _goblin_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and "Goblin" in getattr(o, "subtypes", set())
    ]


class TestGoblinSurpriseMint:
    def test_token_mode_mints_two_11_red_goblin_tokens(self) -> None:
        spell = GoblinSurprise()
        game = create_game()
        spell.controller = game.players[0]
        spell.chosen_mode = 1  # "Create two 1/1 red Goblin creature tokens."
        spell.on_resolve(game)

        goblins = _goblin_tokens(game, 0)
        assert len(goblins) == 2
        for token in goblins:
            assert token.subtypes == {"Goblin"}
            assert get_colors(token) == {Color.RED}
            assert token.base_power == 1
            assert token.base_toughness == 1
            assert token.is_token is True
