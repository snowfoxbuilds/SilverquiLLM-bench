"""Reference test for FDN 44 — Kaito, Cunning Infiltrator.

Demonstrates **Pattern 4 — loyalty ability with targeting** (Phase D) for an
optional "**target creature you control**":

* ``+1`` — "Up to one target creature you control can't be blocked this turn.
  Draw a card, then discard a card." The target is optional (``targeting`` may
  return ``[]``) and is filtered to creatures the *controller* controls; the
  draw/discard happens whether or not a creature was targeted.
* ``−2`` / ``−9`` — untargeted.

The target is chosen at activation and applied at resolution. Kaito's loyalty
shows in which loyalty abilities the rules allow, and "can't be blocked" in a
block that does not take effect.
"""

from __future__ import annotations

from cards.fdn.fdn_44.card_impl import (
    KaitoCunningInfiltrator,
    KaitoCunningInfiltratorAbility1,
    KaitoCunningInfiltratorAbility2,
    KaitoCunningInfiltratorAbility3,
)
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from engine.card import printed_class
from engine.types import ManaCost, Supertype
from test_interface import Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, life, moves, off_stack, on_stack, taps


class TestKaitoProperties:
    def test_static_data(self):
        kaito = KaitoCunningInfiltrator(owner=None)
        assert printed_class(kaito) is KaitoCunningInfiltrator
        assert kaito.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert kaito.starting_loyalty == 3
        assert Supertype.LEGENDARY in kaito.supertypes
        assert "Kaito" in kaito.subtypes


def _plus_one(t, *, choices, drawn, fallback=None):
    """Player 0 activates Kaito's +1 with an empty hand, so it draws
    ``drawn`` and must discard it; ``fallback`` answers instead once the
    engine has rejected a choice from ``choices``. (Known-Best discards the
    last card in hand rather than asking which, so the tests leave no choice
    to make.)"""
    branches = [[KaitoCunningInfiltratorAbility2, *choices]]
    if fallback is not None:
        branches.append([KaitoCunningInfiltratorAbility2, *fallback])
    t.act(0, branches=branches, then=[on_stack(KaitoCunningInfiltratorAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(KaitoCunningInfiltratorAbility2), moves(drawn, Zone.GRAVEYARD)])


def _unblockable_attack(t, attacker, blocker):
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, attacker, then=[taps(attacker)])
    t.pass_(0)
    t.pass_(1)
    t.act_illegal(
        1, blocker, scoped={blocker: attacker}, note="the target can't be blocked this turn"
    )
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 18), on_stack(KaitoCunningInfiltratorAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(KaitoCunningInfiltratorAbility1)])


class TestKaitoPlusOne:
    def _setup(self, theirs=()):
        mine, drawn = card(SavannahLions), card(Island)
        game = create_game(
            Side(battlefield=[KaitoCunningInfiltrator, mine], library=[drawn]),
            Side(battlefield=list(theirs)),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        return Table(game), mine, drawn

    def test_target_cant_be_blocked_and_draw_discard(self):
        blocker = card(LlanowarElves)
        t, mine, drawn = self._setup([blocker])
        _plus_one(t, choices=[mine], drawn=drawn)
        _unblockable_attack(t, mine, blocker)
        t.run()

    def test_targets_only_own_creatures(self):
        """ "Target creature you control": the opponent's creature, preferred
        first, is not a legal choice — not offered, or offered and rejected —
        so the +1 targets player 0's Lions, which then can't be blocked."""
        theirs = card(LlanowarElves)
        t, mine, drawn = self._setup([theirs])
        _plus_one(t, choices=[theirs, mine], drawn=drawn, fallback=[mine])
        _unblockable_attack(t, mine, theirs)
        t.run()

    def test_up_to_one_activates_with_no_creature(self):
        """No creature to target: the ability still activates, and the
        draw/discard still happens."""
        drawn = card(Island)
        game = create_game(
            Side(battlefield=[KaitoCunningInfiltrator], library=[drawn]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _plus_one(t, choices=[], drawn=drawn)
        t.run()

    def test_once_per_turn(self):
        t, mine, drawn = self._setup()
        _plus_one(t, choices=[mine], drawn=drawn)
        t.act_illegal(
            0, KaitoCunningInfiltratorAbility2, choices=[mine], note="one loyalty ability per turn"
        )
        t.act_illegal(0, KaitoCunningInfiltratorAbility3, note="the −2 is a loyalty ability too")
        t.run()


class TestKaitoUntargeted:
    def test_minus_two_creates_ninja_token(self):
        """The −2 leaves Kaito at 1, too little for another −2 next turn; the
        2/1 Ninja hits for 2, which puts a loyalty counter on Kaito."""
        game = create_game(
            Side(battlefield=[KaitoCunningInfiltrator], library=[card(Plains)]),
            Side(library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(
            0, KaitoCunningInfiltratorAbility3, then=[on_stack(KaitoCunningInfiltratorAbility3, 0)]
        )
        t.pass_(0)
        t.pass_(1, then=[off_stack(KaitoCunningInfiltratorAbility3), appears(0)])
        t.pass_to(Step.UPKEEP, 0)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act_illegal(0, KaitoCunningInfiltratorAbility3, note="Kaito has 1 loyalty")
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, token(1), then=[taps(token(1))])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 18), on_stack(KaitoCunningInfiltratorAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(KaitoCunningInfiltratorAbility1)])
        t.run()
