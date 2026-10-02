"""Reference test for FDN 121 — Koma, World-Eater (token identity).

"Whenever Koma deals combat damage to a player, create four 3/3 blue Serpent
creature tokens named Koma's Coil." The per-token mint routes through the
shared ``make_creature_token`` factory while keeping the named-token name.
This test drives a combat-damage event through the registered trigger and pins
the count (four) and each minted token's identity (name, subtypes, explicit
blue colour, base P/T, ``is_token``).
"""

from __future__ import annotations

from cards.fdn.fdn_121.card_impl import KomaWorldEater
from engine.protection import get_colors
from engine.types import Color
from test_utils import scenario_game as create_game


def _coil_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False) and getattr(o, "name", None) == "Koma's Coil"
    ]


class TestKomaToken:
    def test_combat_damage_mints_four_blue_serpents(self) -> None:
        from engine.combat import combat_damage_step
        from test_utils import declare_attackers, enter_permanent, resolve_stack

        game = create_game()
        p1, p2 = game.players
        koma = enter_permanent(game, p1, KomaWorldEater())
        koma.summoning_sick = False
        declare_attackers(game, [koma.name])
        combat_damage_step(game)
        resolve_stack(game)
        assert p2.life == 12
        tokens = _coil_tokens(game, p1)
        assert len(tokens) == 4
        for token in tokens:
            assert token.subtypes == {"Serpent"} and get_colors(token) == {Color.BLUE}
            assert (token.power, token.toughness) == (3, 3) and token.is_token
