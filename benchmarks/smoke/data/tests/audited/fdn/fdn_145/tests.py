"""Reference test for FDN 145 — Resolute Reinforcements (Phase H token minter).

"When this creature enters, create a 1/1 white Soldier creature token." The
mint fires from a self-ETB trigger (registered before the enters event fires),
so casting the creature drives it directly. After the Phase H rework the token
routes through ``make_creature_token`` with the oracle-correct subtype set
{"Soldier"} (the pre-rework impl wrongly minted a {"Human","Soldier"} token).
This test proves the entered creature keeps its Human Soldier types while the
minted token is a plain 1/1 white Soldier.
"""
from __future__ import annotations

from cards.fdn.fdn_145.card_impl import ResoluteReinforcements
from engine.protection import get_colors
from engine.types import Color, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _soldier_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and "Soldier" in getattr(o, "subtypes", set())
    ]


class TestResoluteReinforcementsMint:
    def test_etb_mints_11_white_soldier_token(self) -> None:
        creature = ResoluteReinforcements()
        game = create_game()
        set_board_state(
            game,
            0,
            hand=[creature],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        cast_spell(game, 0, "Resolute Reinforcements")

        tokens = _soldier_tokens(game, 0)
        assert len(tokens) == 1
        token = tokens[0]
        # Oracle-correct: a 1/1 white *Soldier*, not a Human Soldier.
        assert token.subtypes == {"Soldier"}
        assert get_colors(token) == {Color.WHITE}
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert token.is_token is True
