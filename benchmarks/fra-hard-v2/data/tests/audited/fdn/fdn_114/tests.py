"""Reference test for FDN 114 — Treetop Snarespinner.

A **targeted activated ability** with an extra sorcery-speed timing gate:
"{2}{G}: Put a +1/+1 counter on target creature you control. Activate only as
a sorcery." The target is chosen at activation and the counter lands when the
ability resolves; each test shows the counter by the extra damage the
creature deals in combat, and the gate by an activation that does not take
effect while the mana stays available.
"""

from __future__ import annotations

from cards.fdn.fdn_114.card_impl import TreetopSnarespinner, TreetopSnarespinnerAbility3
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_226.card_impl import InspiringCall
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import printed_class
from engine.types import Keyword, ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, branch, card, create_game

from silverquillm.table import Table, life, moves, off_stack, on_stack, taps

SNARE = TreetopSnarespinnerAbility3


def _table(*, hand=(), creatures=(), theirs=(), green=3, start=(Phase.PRECOMBAT_MAIN, 0)):
    game = create_game(
        Side(hand=list(hand), battlefield=[TreetopSnarespinner, *creatures], library=[Forest],
             mana={ManaType.GREEN: green}),
        Side(battlefield=list(theirs), library=[Forest]),
        start=start,
    )
    return Table(game)


def _activate(t, target, **options):
    t.act(0, SNARE, choices=[target], then=[on_stack(SNARE, 0)], **options)
    t.pass_(0)
    t.pass_(1, then=[off_stack(SNARE)])


def _attack_alone(t, attacker, damage):
    """``attacker`` attacks alone this turn and is not blocked."""
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, attacker, then=[taps(attacker)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 20 - damage)])


class TestTreetopSnarespinnerProperties:
    def test_static_data(self):
        card = TreetopSnarespinner(owner=None)
        assert printed_class(card) is TreetopSnarespinner
        assert card.mana_cost == ManaCost.parse("{3}{G}")
        assert (card.base_power, card.base_toughness) == (1, 4)
        assert "Spider" in card.subtypes
        assert Keyword.REACH in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords


class TestTreetopSnarespinnerAbility:
    def test_counter_added_after_resolution(self):
        lions = card(SavannahLions)
        t = _table(creatures=[lions])
        _activate(t, lions)
        _attack_alone(t, lions, 3)
        t.run()

    def test_cost_is_paid(self):
        """{2}{G} empties a pool of three green: once the first activation has
        resolved, still in the main phase with the stack empty, a second
        activation cannot be paid."""
        lions = card(SavannahLions)
        t = _table(creatures=[lions])
        t.act(0, SNARE, choices=[lions], then=[on_stack(SNARE, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(SNARE)])
        t.act_illegal(0, SNARE, choices=[lions], note="no mana is left")
        t.run()

    def test_target_captured_on_stack(self):
        """The counter goes on the creature chosen as the target: of two
        Savannah Lions, the chosen one attacks for 3."""
        chosen, other = card(SavannahLions), card(SavannahLions)
        t = _table(creatures=[other, chosen])
        _activate(t, chosen)
        _attack_alone(t, chosen, 3)
        t.run()

    def test_cannot_target_creature_you_do_not_control(self):
        """Option-set invariant: only creatures the controller controls are
        legal targets. Asked for the opponent's Lions first, the engine must
        not put the counter there: either it is not offered, and the player's
        own Lions is chosen, or it is rejected, and the next answer chooses
        the own Lions. The own Lions then attacks for 3."""
        mine, theirs = card(SavannahLions), card(SavannahLions)
        t = _table(creatures=[mine], theirs=[theirs])
        t.act(0, branches=[branch(SNARE, choices=[theirs, mine]), branch(SNARE, choices=[mine])],
              then=[on_stack(SNARE, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(SNARE)])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, mine, then=[taps(mine)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 17)], note="the counter is on player 0's own Lions")
        t.run()

    def test_sorcery_speed_gate_rejects_outside_main(self):
        """Legality invariant: the sorcery-speed gate rejects activation in
        the beginning of combat step before any cost — the three green stay
        to cast Inspiring Call."""
        lions, call = card(SavannahLions), card(InspiringCall)
        t = _table(hand=[call], creatures=[lions], start=(Step.BEGIN_COMBAT, 0))
        t.act_illegal(0, SNARE, choices=[lions], note="not a main phase")
        t.act(0, call, then=[moves(call, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(call, Zone.GRAVEYARD)])
        t.run()

    def test_sorcery_speed_gate_rejects_with_nonempty_stack(self):
        """With Giant Growth on the stack it is not sorcery timing; once the
        stack is empty the three green left still pay for the ability."""
        lions, growth = card(SavannahLions), card(GiantGrowth)
        t = _table(hand=[growth], creatures=[lions], green=4)
        t.act(0, growth, choices=[lions], then=[moves(growth, Zone.STACK)])
        t.act_illegal(0, SNARE, choices=[lions], note="a spell is on the stack")
        t.pass_(0)
        t.pass_(1, then=[moves(growth, Zone.GRAVEYARD)])
        _activate(t, lions)
        t.run()
