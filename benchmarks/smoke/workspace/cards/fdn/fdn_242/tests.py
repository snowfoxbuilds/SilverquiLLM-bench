"""Reference test for FDN 242 — Lathril, Blade of the Elves (token identity).

"Whenever Lathril deals combat damage to a player, create that many 1/1 green
Elf Warrior creature tokens." The per-token mint routes through the shared
``make_creature_token`` factory. This test drives a combat-damage event of
amount 2 through the registered trigger and pins both the "that many" count
and each minted token's identity (subtypes, explicit green colour, base P/T,
``is_token``).
"""
from __future__ import annotations

from cards.fdn.fdn_242.card_impl import LathrilBladeOfTheElves
from engine.events import DealsDamageTriggeredEvent
from engine.protection import get_colors
from engine.stack import priority_loop
from engine.types import Color
from test_utils import create_game, set_board_state


def _elf_warrior_tokens(game, player):
    bf = game.get_battlefield(player)
    return [
        o
        for o in bf.get_all()
        if getattr(o, "is_token", False)
        and getattr(o, "name", None) == "Elf Warrior"
    ]


class TestLathrilToken:
    def test_combat_damage_mints_green_elf_warriors(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lathril = LathrilBladeOfTheElves(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lathril])
        lathril.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            DealsDamageTriggeredEvent(
                source=lathril, target=p2, amount=2, is_combat=True
            ),
        )
        priority_loop(game)

        tokens = _elf_warrior_tokens(game, p1)
        assert len(tokens) == 2  # "that many" = 2 combat damage
        for tok in tokens:
            assert tok.subtypes == {"Elf", "Warrior"}
            assert get_colors(tok) == {Color.GREEN}
            assert (tok.base_power, tok.base_toughness) == (1, 1)
            assert tok.is_token is True
