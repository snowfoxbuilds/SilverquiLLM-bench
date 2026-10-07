"""Audited tests for FDN 61 — High-Society Hunter.

"Whenever another nontoken creature dies, draw a card." The card is drawn by
the player who controlled the Hunter when the ability triggered (rule 603.3a),
even if the Hunter leaves the battlefield before the ability resolves and
returns as a new object (400.7).
"""

from __future__ import annotations

from cards.fdn.fdn_61.card_impl import HighSocietyHunter, HighSocietyHunterAbility3
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility2
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Phase, Side, Zone, card, create_game

from table import Table, appears, gains_control, moves, off_stack, on_stack, taps


def _tap(t, seat, lands):
    for land in lands:
        t.act(seat, land, then=[taps(land)])


def _bolt_own_lions(t, mountain, bolt, lions):
    """Player 0 kills their own Savannah Lions; the Hunter's trigger goes on
    the stack for its controller, player 0."""
    _tap(t, 0, [mountain])
    t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(
        1,
        then=[
            moves(bolt, Zone.GRAVEYARD),
            moves(lions, Zone.GRAVEYARD),
            on_stack(HighSocietyHunterAbility3, 0),
        ],
    )


class TestHighSocietyHunterDraw:
    def test_draws_when_another_nontoken_creature_dies(self) -> None:
        lions, bolt, mountain, drawn = (
            card(SavannahLions),
            card(BurstLightning),
            card(Mountain),
            card(Plains),
        )
        game = create_game(
            Side(battlefield=[HighSocietyHunter, lions, mountain], hand=[bolt], library=[drawn]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _bolt_own_lions(t, mountain, bolt, lions)
        t.pass_(0)
        t.pass_(1, then=[off_stack(HighSocietyHunterAbility3), moves(drawn, Zone.HAND)])
        t.run()

    def test_pending_draw_stays_with_its_controller_after_the_hunter_leaves(self) -> None:
        """Player 0 takes player 1's Hunter with Involuntary Employment; its
        trigger for the Lions still draws for player 0 after player 0 kills
        the Hunter in response. (Known-Best's ``destroy`` cannot find a stolen
        permanent, so Abrade's damage kills it.)"""
        hunter, lions = card(HighSocietyHunter), card(SavannahLions)
        employment, bolt, abrade = card(InvoluntaryEmployment), card(BurstLightning), card(Abrade)
        mountains = [card(Mountain) for _ in range(7)]
        drawn = card(Plains)
        game = create_game(
            Side(battlefield=[lions, *mountains], hand=[employment, bolt, abrade], library=[drawn]),
            Side(battlefield=[hunter]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _tap(t, 0, mountains[:4])
        t.act(0, employment, choices=[hunter], then=[moves(employment, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(employment, Zone.GRAVEYARD), gains_control(hunter, 0), appears(0)])
        _bolt_own_lions(t, mountains[4], bolt, lions)
        _tap(t, 0, mountains[5:])
        t.act(0, abrade, choices=[AbradeAbility2, hunter], then=[moves(abrade, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(abrade, Zone.GRAVEYARD), moves(hunter, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(HighSocietyHunterAbility3), moves(drawn, Zone.HAND)])
        t.run()
