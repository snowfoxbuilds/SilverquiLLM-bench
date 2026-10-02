"""Reference test for FDN 241 — Heroic Reinforcements (Phase H token minter).

Heroic Reinforcements is a sorcery that, on resolution, creates two 1/1 white
Soldier creature tokens. After the Phase H rework the mint routes through
``cards.fdn.tokens.make_creature_token`` so each Soldier carries the exact
characteristics ``token_id_map.json`` records (1/1 white Soldier). This test
drives the real ``on_resolve`` path (cast + resolve) and proves both tokens
have those characteristics.
"""
from __future__ import annotations

from cards.fdn.fdn_241.card_impl import HeroicReinforcements
from engine.protection import get_colors
from engine.types import Color, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _tokens(game, player_index, subtype):
    bf = game.players[player_index].zones[Zone.BATTLEFIELD]
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and subtype in getattr(o, "subtypes", set())
    ]


class TestHeroicReinforcementsMint:
    def test_mints_two_11_white_soldier_tokens(self) -> None:
        spell = HeroicReinforcements()
        game = create_game()
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 2},
        )
        cast_spell(game, 0, "Heroic Reinforcements")

        soldiers = _tokens(game, 0, "Soldier")
        assert len(soldiers) == 2
        for token in soldiers:
            assert token.subtypes == {"Soldier"}
            assert get_colors(token) == {Color.WHITE}
            assert token.base_power == 1
            assert token.base_toughness == 1
            assert token.is_token is True
