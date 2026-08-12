"""Reference test for FDN 14 — Guarded Heir (Phase H token minter).

"When this creature enters, create two 3/3 white Knight creature tokens." The
mint fires from a self-ETB trigger, so casting the creature drives it directly.
After the Phase H rework the tokens route through ``make_creature_token`` with
the exact 3/3 white Knight characteristics ``token_id_map.json`` records.
"""
from __future__ import annotations

from cards.fdn.fdn_14.card_impl import GuardedHeir
from engine.protection import get_colors
from engine.types import Color, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _knight_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and "Knight" in getattr(o, "subtypes", set())
    ]


class TestGuardedHeirMint:
    def test_etb_mints_two_33_white_knight_tokens(self) -> None:
        creature = GuardedHeir()
        game = create_game()
        set_board_state(
            game,
            0,
            hand=[creature],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 5},
        )
        cast_spell(game, 0, "Guarded Heir")

        knights = _knight_tokens(game, 0)
        assert len(knights) == 2
        for token in knights:
            assert token.subtypes == {"Knight"}
            assert get_colors(token) == {Color.WHITE}
            assert token.base_power == 3
            assert token.base_toughness == 3
            assert token.is_token is True
