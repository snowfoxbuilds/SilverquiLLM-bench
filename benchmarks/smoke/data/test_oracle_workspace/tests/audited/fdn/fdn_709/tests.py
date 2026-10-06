"""Audited tests for FDN 709 — Confiscate.

"Enchant permanent. You control enchanted permanent." Control shows on the
Player View as the permanent moving to its controller's side, and in play as
who may attack with it: a creature that comes under a new controller cannot
attack for them until it has been theirs continuously since their most
recent turn began (CR 302.6). A Confiscate enchanting another Confiscate
takes it over first, so its controller gains what that one enchants
(CR 613.8); when either leaves, control follows what remains.
"""

from __future__ import annotations

from cards.fdn.fdn_139.card_impl import CatharCommando, CatharCommandoAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_709.card_impl import Confiscate
from test_interface import Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, gains_control, life, moves, off_stack, on_stack, taps


def _islands(n=6):
    return [card(Island) for _ in range(n)]


def _cast(t, seat, confiscate, target, islands, *, then=()):
    """``seat`` taps six Islands and casts ``confiscate`` on ``target``; it
    resolves with ``then``."""
    for island in islands:
        t.act(seat, island, then=[taps(island)])
    t.act(seat, confiscate, choices=[target], then=[moves(confiscate, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(confiscate, Zone.BATTLEFIELD), *then])


def _attack(t, seat, creature, damage_to, life_after):
    """``seat`` attacks with ``creature``, unblocked."""
    t.act(seat, creature, then=[taps(creature)])
    t.pass_(seat)
    t.pass_(1 - seat)
    t.pass_(1 - seat)
    t.pass_(seat)
    t.pass_(1 - seat, then=[life(damage_to, life_after)])


def _confiscate(theirs=(), *, their_hand=(), their_islands=0):
    """Player 0 taps six Islands and casts Confiscate on player 1's Savannah
    Lions."""
    confiscate, lions = card(Confiscate), card(SavannahLions)
    islands = _islands()
    mine_back = _islands(their_islands)
    game = create_game(
        Side(hand=[confiscate], battlefield=islands, library=[card(Plains), card(Plains)]),
        Side(hand=list(their_hand), battlefield=[lions, *theirs, *mine_back],
             library=[card(Plains), card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    _cast(t, 0, confiscate, lions, islands, then=[gains_control(lions, 0)])
    return t, confiscate, lions, mine_back


class TestConfiscateControl:
    def test_caster_controls_the_enchanted_permanent(self):
        """The Lions comes under player 0's control: it cannot attack the turn
        it changed control (rule 302.6), and attacks player 1 on player 0's
        next turn."""
        t, _, lions, _ = _confiscate()
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act_illegal(0, lions, note="summoning sick under its new controller")
        t.pass_(0)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack(t, 0, lions, 1, 18)
        t.run()

    def test_enchanting_your_own_creature_changes_nothing(self):
        """Confiscate on player 0's own Lions: control does not change, so the
        Lions attacks that same turn."""
        confiscate, lions = card(Confiscate), card(SavannahLions)
        islands = _islands()
        t = Table(create_game(Side(hand=[confiscate], battlefield=[lions, *islands]), Side(),
                              start=(Phase.PRECOMBAT_MAIN, 0)))
        _cast(t, 0, confiscate, lions, islands)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack(t, 0, lions, 1, 18)
        t.run()

    def test_control_returns_when_confiscate_leaves(self):
        """Player 1's Cathar Commando destroys Confiscate, and the Lions goes
        back to player 1's side."""
        commando, plains = card(CatharCommando), card(Plains)
        t, confiscate, lions, _ = _confiscate([commando, plains])
        t.pass_(0)
        t.act(1, plains, then=[taps(plains)])
        t.act(1, CatharCommandoAbility2, choices=[confiscate],
              then=[moves(commando, Zone.GRAVEYARD), on_stack(CatharCommandoAbility2, 1)])
        t.pass_(1)
        t.pass_(0, then=[off_stack(CatharCommandoAbility2), moves(confiscate, Zone.GRAVEYARD), gains_control(lions, 1)])
        t.run()

    def test_a_creature_returned_on_its_owners_turn_cannot_attack_that_turn(self):
        """On player 1's turn their Cathar Commando destroys Confiscate: the
        Lions is player 1's again, but only since this turn began, so it
        cannot attack until player 1's next turn."""
        commando, plains = card(CatharCommando), card(Plains)
        t, confiscate, lions, _ = _confiscate([commando, plains])
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        t.act(1, plains, then=[taps(plains)])
        t.act(1, CatharCommandoAbility2, choices=[confiscate],
              then=[moves(commando, Zone.GRAVEYARD), on_stack(CatharCommandoAbility2, 1)])
        t.pass_(1)
        t.pass_(0, then=[off_stack(CatharCommandoAbility2), moves(confiscate, Zone.GRAVEYARD), gains_control(lions, 1)])
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act_illegal(1, lions, note="summoning sick: control changed this turn")
        t.pass_(1)
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        _attack(t, 1, lions, 0, 18)
        t.run()


class TestConfiscateChain:
    def _chain(self, extra_mine=()):
        """Player 0 confiscates player 1's Lions; on player 1's next turn
        their own Confiscate takes over player 0's, and with it the Lions."""
        second = card(Confiscate)
        t, first, lions, their_islands = _confiscate(their_hand=[second], their_islands=6)
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        _cast(t, 1, second, first, their_islands, then=[gains_control(first, 1), gains_control(lions, 1)])
        return t, first, second, lions

    def test_a_confiscate_on_a_confiscate_takes_what_it_enchants(self):
        """The Lions follows the first Confiscate to player 1, and having
        changed control this turn it cannot attack until their next turn."""
        t, _, _, lions = self._chain()
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act_illegal(1, lions, note="summoning sick: control changed this turn")
        t.pass_(1)
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        _attack(t, 1, lions, 0, 18)
        t.run()

    def test_when_the_second_confiscate_leaves_the_first_takes_back_control(self):
        """Player 0's Cathar Commando destroys player 1's Confiscate: the first
        Confiscate is player 0's again, and so is the Lions."""
        commando, plains = card(CatharCommando), card(Plains)
        second = card(Confiscate)
        confiscate, lions = card(Confiscate), card(SavannahLions)
        islands, their_islands = _islands(), _islands()
        t = Table(create_game(
            Side(hand=[confiscate], battlefield=[*islands, commando, plains], library=[card(Plains), card(Plains)]),
            Side(hand=[second], battlefield=[lions, *their_islands], library=[card(Plains), card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        ))
        _cast(t, 0, confiscate, lions, islands, then=[gains_control(lions, 0)])
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        _cast(t, 1, second, confiscate, their_islands, then=[gains_control(confiscate, 1), gains_control(lions, 1)])
        t.pass_(1)
        t.act(0, plains, then=[taps(plains)])
        t.act(0, CatharCommandoAbility2, choices=[second], then=[moves(commando, Zone.GRAVEYARD), on_stack(CatharCommandoAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(CatharCommandoAbility2), moves(second, Zone.GRAVEYARD), gains_control(confiscate, 0), gains_control(lions, 0)])
        t.run()

    def test_when_the_first_confiscate_leaves_the_owner_takes_back_control(self):
        """Player 1's own Cathar Commando destroys the first Confiscate: the
        Lions returns to player 1, and the second Confiscate, enchanting
        nothing, goes to the graveyard."""
        commando, plains = card(CatharCommando), card(Plains)
        second = card(Confiscate)
        first, lions = card(Confiscate), card(SavannahLions)
        islands, their_islands = _islands(), _islands()
        t = Table(create_game(
            Side(hand=[first], battlefield=islands, library=[card(Plains), card(Plains)]),
            Side(hand=[second], battlefield=[lions, *their_islands, commando, plains],
                 library=[card(Plains), card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        ))
        _cast(t, 0, first, lions, islands, then=[gains_control(lions, 0)])
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        _cast(t, 1, second, first, their_islands, then=[gains_control(first, 1), gains_control(lions, 1)])
        t.act(1, plains, then=[taps(plains)])
        t.act(1, CatharCommandoAbility2, choices=[first], then=[moves(commando, Zone.GRAVEYARD), on_stack(CatharCommandoAbility2, 1)])
        t.pass_(1)
        t.pass_(0, then=[off_stack(CatharCommandoAbility2), moves(first, Zone.GRAVEYARD), moves(second, Zone.GRAVEYARD)])
        t.run()


class TestConfiscateCosts:
    def test_five_mana_cannot_cast_it(self):
        """With five Islands tapped Confiscate's {4}{U}{U} cannot be paid."""
        confiscate, lions = card(Confiscate), card(SavannahLions)
        islands = _islands(5)
        t = Table(create_game(Side(hand=[confiscate], battlefield=islands), Side(battlefield=[lions]),
                              start=(Phase.PRECOMBAT_MAIN, 0)))
        for island in islands:
            t.act(0, island, then=[taps(island)])
        t.act_illegal(0, confiscate, choices=[lions])
        t.run()
