"""Reference test for FDN 184 — Rune-Scarred Demon (Phase F self-ETB).

"When this creature enters, search your library for a card, put it into your
hand, then shuffle." — an own-enters trigger. Before Phase F the ETB event
fired before the card registered, so the tutor was driven by a bespoke
``on_resolve`` workaround. The Phase F ordering flip makes the registered
trigger fire on the Demon's own entry, so the ``on_resolve`` self-tutor was
removed — these tests prove the tutor happens **exactly once** per entry.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_162.card_impl import RunAwayTogether
from cards.fdn.fdn_184.card_impl import RuneScarredDemon, RuneScarredDemonAbility2
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from test_interface import ManaType, Phase, Side, Zone, card, create_game, shuffled

from silverquillm.table import Table, moves, off_stack, on_stack, taps


def _cast_demon(t, demon, wanted, lands=()):
    """Player 0 casts the Demon and its trigger finds ``wanted``."""
    for land in lands:
        t.act(0, land, then=[taps(land)])
    t.act(0, demon, then=[moves(demon, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(demon, Zone.BATTLEFIELD), on_stack(RuneScarredDemonAbility2, 0)])
    t.pass_(0, choices=[wanted])
    t.pass_(1, then=[off_stack(RuneScarredDemonAbility2), moves(wanted, Zone.HAND)])


class TestRuneScarredDemonSelfETB:
    def test_tutor_fires_exactly_once(self) -> None:
        """The chosen card moves to hand; the other stays in the library —
        exactly one tutor fired (a double-fire would have taken both)."""
        demon, wanted, other = card(RuneScarredDemon), card(SavannahLions), card(Plains)
        game = create_game(
            Side(hand=[demon], library=[other, wanted], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 5}),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast_demon(t, demon, wanted)
        t.run(chance=[shuffled(other)])

    def test_reentry_tutors_once_again(self):
        """Run Away Together returns the Demon to hand; recast, it enters as
        a new object and tutors once more."""
        demon, first, second, third = card(RuneScarredDemon), card(SavannahLions), card(Plains), card(Island)
        run_away, lions = card(RunAwayTogether), card(SavannahLions)
        islands = [card(Island), card(Island)]
        swamps = [card(Swamp) for _ in range(7)]
        game = create_game(
            Side(
                hand=[demon, run_away],
                battlefield=[*islands, *swamps],
                library=[second, first, third],
                mana={ManaType.BLACK: 2, ManaType.COLORLESS: 5},
            ),
            Side(battlefield=[lions]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast_demon(t, demon, first)
        for land in islands:
            t.act(0, land, then=[taps(land)])
        t.act(0, run_away, choices=[demon, lions], then=[moves(run_away, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(demon, Zone.HAND), moves(lions, Zone.HAND), moves(run_away, Zone.GRAVEYARD)])
        _cast_demon(t, demon, second, lands=swamps)
        t.run(chance=[shuffled(second, third), shuffled(third)])
