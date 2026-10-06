"""Audited tests for FDN 112 — Spinner of Souls.

"Whenever another nontoken creature you control dies, you may reveal cards
from the top of your library until you reveal a creature card. Put that card
into your hand and the rest on the bottom of your library in a random order."
"You" is the player who controlled Spinner when the ability triggered (rule
603.3a), even if Spinner leaves the battlefield before it resolves.
"""

from __future__ import annotations

from cards.fdn.fdn_112.card_impl import SpinnerOfSouls, SpinnerOfSoulsAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Decision, ManaType, Phase, Side, Zone, card, create_game, shuffled

from silverquillm.table import Table, appears, gains_control, moves, off_stack, on_stack

MAIN = (Phase.PRECOMBAT_MAIN, 0)


def _kill(t, bolt, victim, *, then=()):
    """Player 0 casts Burst Lightning on their own ``victim``; it dies and
    Spinner of Souls triggers for player 0."""
    t.act(0, bolt, choices=[victim], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(victim, Zone.GRAVEYARD),
                     on_stack(SpinnerOfSoulsAbility2, 0), *then])


class TestSpinnerOfSoulsReveal:
    def test_puts_a_creature_card_into_hand_when_another_creature_you_control_dies(self) -> None:
        lions, bolt, forest, found = card(SavannahLions), card(BurstLightning), card(Forest), card(SavannahLions)
        game = create_game(
            Side(hand=[bolt], battlefield=[SpinnerOfSouls, lions], library=[forest, found, Plains],
                 mana={ManaType.RED: 1}),
            Side(),
            start=MAIN,
        )
        t = Table(game)
        _kill(t, bolt, lions)
        t.pass_(0, choices=[Decision.yes()])
        t.pass_(1, then=[off_stack(SpinnerOfSoulsAbility2), moves(found, Zone.HAND),
                         moves(forest, Zone.LIBRARY, bottom=True)],
                note="the first creature card goes to hand, the Forest revealed before it to the bottom")
        t.run(chance=[shuffled(forest)])

    def test_pending_reveal_stays_with_its_controller_after_spinner_leaves(self) -> None:
        spinner, employment, lions, bolt = card(SpinnerOfSouls), card(InvoluntaryEmployment), card(SavannahLions), card(BurstLightning)
        shock, second, forest, found = card(BurstLightning), card(BurstLightning), card(Forest), card(SavannahLions)
        game = create_game(
            Side(hand=[employment, bolt], battlefield=[lions], library=[forest, found, Plains],
                 mana={ManaType.RED: 5}),
            Side(hand=[shock, second], battlefield=[spinner], library=[Forest, SavannahLions], mana={ManaType.RED: 2}),
            start=MAIN,
        )
        t = Table(game)
        # Player 0 takes control of player 1's Spinner, then their Lions dies.
        t.act(0, employment, choices=[spinner], then=[moves(employment, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(employment, Zone.GRAVEYARD), gains_control(spinner, 0), appears(0)])
        _kill(t, bolt, lions)
        # In response, player 1 deals 4 damage to the 4/3 Spinner; the reveal is still player 0's.
        t.pass_(0)
        t.act(1, shock, choices=[spinner], then=[moves(shock, Zone.STACK)])
        t.act(1, second, choices=[spinner], then=[moves(second, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(second, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[moves(shock, Zone.GRAVEYARD), moves(spinner, Zone.GRAVEYARD)])
        t.pass_(0, choices=[Decision.yes()])
        t.pass_(1, then=[off_stack(SpinnerOfSoulsAbility2), moves(found, Zone.HAND),
                         moves(forest, Zone.LIBRARY, bottom=True)],
                note="player 0 reveals from their own library, not the Spinner owner's")
        t.run(chance=[shuffled(forest)])
