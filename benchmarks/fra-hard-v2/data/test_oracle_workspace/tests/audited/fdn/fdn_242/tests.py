"""Lathril's unblocked combat damage creates the specified Elf Warriors."""

from cards.fdn.fdn_242.card_impl import LathrilBladeOfTheElves
from engine.combat import combat_damage_step
from engine.protection import get_colors
from engine.types import Color
from test_utils import (
    behavioral_game,
    declare_attackers,
    declare_blockers,
    enter_permanent,
    resolve_stack,
)


def test_combat_damage_mints_green_elf_warriors():
    game = behavioral_game()
    player, opponent = game.players
    card = enter_permanent(game, player, LathrilBladeOfTheElves())
    card.summoning_sick = False
    declare_attackers(game, [card])
    declare_blockers(game, {})
    combat_damage_step(game)
    resolve_stack(game)
    assert opponent.life == 18
    tokens = [
        obj for obj in game.get_battlefield(player).get_all() if getattr(obj, "is_token", False)
    ]
    assert len(tokens) == 2
    for token in tokens:
        assert token.subtypes == {"Elf", "Warrior"}
        assert (token.base_power, token.base_toughness) == (1, 1)
        assert get_colors(token) == {Color.GREEN}
