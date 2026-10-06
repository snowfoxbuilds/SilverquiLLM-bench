"""Audited tests for FDN 709 — Confiscate.

"Enchant permanent. You control enchanted permanent." Control shows on the
Player View as the permanent moving to the caster's side, and in play as the
caster attacking with it on their next turn; when Confiscate leaves, control
returns.
"""

from __future__ import annotations

from cards.fdn.fdn_139.card_impl import CatharCommando, CatharCommandoAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_709.card_impl import Confiscate
from engine.card import Aura, printed_class
from engine.types import ManaCost
from test_interface import Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, gains_control, life, moves, off_stack, on_stack, taps


class TestConfiscateProperties:
    def test_static_data(self):
        confiscate = Confiscate(owner=None)
        assert printed_class(confiscate) is Confiscate
        assert confiscate.mana_cost == ManaCost.parse("{4}{U}{U}")
        assert isinstance(confiscate, Aura)


def _confiscate(theirs=(), *, extra_mine=()):
    """Player 0 taps six Islands and casts Confiscate on player 1's Savannah
    Lions."""
    confiscate, lions = card(Confiscate), card(SavannahLions)
    islands = [card(Island) for _ in range(6)]
    game = create_game(
        Side(hand=[confiscate], battlefield=[*islands, *extra_mine], library=[card(Plains)]),
        Side(battlefield=[lions, *theirs], library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    for island in islands:
        t.act(0, island, then=[taps(island)])
    t.act(0, confiscate, choices=[lions], then=[moves(confiscate, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(confiscate, Zone.BATTLEFIELD), gains_control(lions, 0)])
    return t, confiscate, lions


class TestConfiscateControl:
    def test_caster_controls_the_enchanted_permanent(self):
        """The Lions comes under player 0's control: it cannot attack the turn
        it changed control (rule 302.6), and attacks player 1 on player 0's
        next turn."""
        t, _, lions = _confiscate()
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act_illegal(0, lions, note="summoning sick under its new controller")
        t.pass_(0)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, lions, then=[taps(lions)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 18)])
        t.run()

    def test_control_returns_when_confiscate_leaves(self):
        """Player 1's Cathar Commando destroys Confiscate, and the Lions goes
        back to player 1's side."""
        commando, plains = card(CatharCommando), card(Plains)
        t, confiscate, lions = _confiscate([commando, plains])
        t.pass_(0)
        t.act(1, plains, then=[taps(plains)])
        t.act(1, CatharCommandoAbility2, choices=[confiscate],
              then=[moves(commando, Zone.GRAVEYARD), on_stack(CatharCommandoAbility2, 1)])
        t.pass_(1)
        t.pass_(0, then=[off_stack(CatharCommandoAbility2), moves(confiscate, Zone.GRAVEYARD),
                         gains_control(lions, 1)])
        t.run()
