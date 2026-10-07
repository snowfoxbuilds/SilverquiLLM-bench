"""Lathril's unblocked combat damage creates that many 1/1 Elf Warriors.

Lathril deals 2 combat damage, so its trigger makes two tokens; on the next
turn they attack beside it as 1/1s, and Lathril's damage makes two more.
"""

from cards.fdn.fdn_242.card_impl import LathrilBladeOfTheElves, LathrilBladeOfTheElvesAbility2
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import Side, Step, card, create_game, token

from table import Table, appears, life, off_stack, on_stack, taps


def _attack(t: Table, attackers, *, damage) -> None:
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, *attackers, then=[taps(a) for a in attackers])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[*damage, on_stack(LathrilBladeOfTheElvesAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(LathrilBladeOfTheElvesAbility2), appears(0), appears(0)])


def test_combat_damage_mints_green_elf_warriors():
    lathril = card(LathrilBladeOfTheElves)
    game = create_game(
        Side(battlefield=[lathril], library=[card(Plains)]),
        Side(library=[card(Plains)]),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    _attack(t, [lathril], damage=[life(1, 18)])
    _attack(t, [lathril, token(1), token(2)], damage=[life(1, 14)])
    t.run()
