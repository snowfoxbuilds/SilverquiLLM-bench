"""Audited tests for FDN 669 — Basilisk Collar.

"Equipped creature has deathtouch and lifelink. Equip {2}." Lifelink shows
as the attacking player's life total, deathtouch as a 2/1 destroying a 12/8
it deals damage to.
"""

from __future__ import annotations

from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_669.card_impl import BasiliskCollar, BasiliskCollarAbility2
from test_interface import Phase, Side, Step, Zone, card, create_game

from table import Table, life, moves, off_stack, on_stack, taps


def _equipped_lions(*theirs):
    """Player 0 equips Basilisk Collar to Savannah Lions, paying {2} with two
    Plains, against player 1's ``theirs``."""
    lions, collar = card(SavannahLions), card(BasiliskCollar)
    plains = [card(Plains), card(Plains)]
    game = create_game(
        Side(battlefield=[lions, collar, *plains]),
        Side(battlefield=list(theirs)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    for land in plains:
        t.act(0, land, then=[taps(land)])
    t.act(0, BasiliskCollarAbility2, choices=[lions], then=[on_stack(BasiliskCollarAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(BasiliskCollarAbility2)])
    return t, lions


class TestBasiliskCollarBehaviour:
    def test_lifelink_gains_the_damage_dealt(self):
        """The equipped 2/1 attacks unblocked: player 1 loses 2 and player 0
        gains 2."""
        t, lions = _equipped_lions()
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, lions, then=[taps(lions)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 18), life(0, 22)])
        t.run()

    def test_deathtouch_destroys_a_larger_blocker(self):
        """The 12/8 blocks the equipped 2/1: 2 damage is lethal, so both die,
        and player 0 still gains 2."""
        ceratops = card(QuakestriderCeratops)
        t, lions = _equipped_lions(ceratops)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, lions, then=[taps(lions)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, ceratops, scoped={ceratops: lions})
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.GRAVEYARD), moves(ceratops, Zone.GRAVEYARD), life(0, 22)])
        t.run()

    def test_unequipped_creature_has_neither(self):
        """Without the Collar the 12/8 blocks the 2/1 and survives, and no life
        is gained."""
        lions, ceratops = card(SavannahLions), card(QuakestriderCeratops)
        game = create_game(
            Side(battlefield=[lions, card(BasiliskCollar)]),
            Side(battlefield=[ceratops]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, lions, then=[taps(lions)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, ceratops, scoped={ceratops: lions})
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.GRAVEYARD)])
        t.run()


class TestBasiliskCollarCosts:
    def test_casting_it_costs_one_mana(self):
        """With no mana the Collar cannot be cast; a Plains' {W} pays its {1}."""
        collar, plains = card(BasiliskCollar), card(Plains)
        t = Table(create_game(Side(hand=[collar], battlefield=[plains]), Side(), start=(Phase.PRECOMBAT_MAIN, 0)))
        t.act_illegal(0, collar)
        t.act(0, plains, then=[taps(plains)])
        t.act(0, collar, then=[moves(collar, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(collar, Zone.BATTLEFIELD)])
        t.run()

    def test_equip_needs_two_mana(self):
        """With one Plains tapped for {W} the Collar's equip {2} cannot be paid."""
        lions, collar, plains = card(SavannahLions), card(BasiliskCollar), card(Plains)
        t = Table(create_game(Side(battlefield=[lions, collar, plains]), Side(), start=(Phase.PRECOMBAT_MAIN, 0)))
        t.act(0, plains, then=[taps(plains)])
        t.act_illegal(0, BasiliskCollarAbility2, choices=[lions])
        t.run()
