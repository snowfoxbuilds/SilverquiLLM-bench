"""Reference test for FDN 148 — Stroke of Midnight (Phase H token minter).

"Destroy target nonland permanent. Its controller creates a 1/1 white Human
creature token." The mint fires from the instant's ``on_resolve``, so casting
it at a legal target drives the real path. After the Phase H rework the token
routes through ``make_creature_token`` with the oracle-correct name/subtype
"Human" (the pre-rework impl minted a nameless "Human Token" with no subtype).
"""
from __future__ import annotations

from cards.fdn.fdn_148.card_impl import StrokeOfMidnight
from engine.card import Creature
from engine.protection import get_colors
from engine.types import Color, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _human_tokens(game, player_index):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and "Human" in getattr(o, "subtypes", set())
    ]


class TestStrokeOfMidnightMint:
    def test_on_resolve_mints_11_white_human_token(self) -> None:
        spell = StrokeOfMidnight()
        victim = Creature(
            name="Grizzly Bears", subtypes={"Bear"}, base_power=2, base_toughness=2
        )
        game = create_game()
        # Victim under player 0's control; player 0 casts Stroke targeting it,
        # so player 0 (the target's controller) receives the Human token.
        set_board_state(game, 0, battlefield=[victim])
        set_board_state(
            game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2}
        )
        cast_spell(game, 0, "Stroke of Midnight", targets=[victim])

        # Victim destroyed.
        assert not game.players[0].zones[Zone.BATTLEFIELD].contains(victim)

        tokens = _human_tokens(game, 0)
        assert len(tokens) == 1
        token = tokens[0]
        assert token.name == "Human"
        assert token.subtypes == {"Human"}
        assert get_colors(token) == {Color.WHITE}
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert token.is_token is True
