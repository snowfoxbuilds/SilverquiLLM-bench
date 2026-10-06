"""Audited tests for FDN 172 — Eaten Alive.

"As an additional cost to cast this spell, sacrifice a creature or pay
{3}{B}. Exile target creature or planeswalker." The sacrifice shows as the
creature going to its owner's graveyard while the spell is cast; the mana
alternative shows in what the caster can and cannot afford; with neither
alternative payable the spell cannot be cast.

Every script names the alternative it pays, as the engine may ask even when
only one of them can be paid; a cast the rules forbid tries each alternative
in turn.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_172.card_impl import EatenAlive, EatenAliveAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_709.card_impl import Confiscate
from engine.types import ManaType
from test_interface import Decision, Phase, Side, Zone, card, create_game

from silverquillm.table import Table, gains_control, moves, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)
SACRIFICE = Decision.ability(index=0, printed=EatenAliveAbility1)
PAY_MANA = Decision.ability(index=1, printed=EatenAliveAbility1)


def _either_alternative(eaten):
    """Casting Eaten Alive paying the sacrifice, or else paying the mana."""
    return [[eaten, SACRIFICE], [eaten, PAY_MANA]]


def _resolve(t, eaten, target):
    t.pass_(0)
    t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD), moves(target, Zone.EXILE)])


class TestEatenAliveAdditionalCost:
    def test_sacrificing_a_creature_pays_the_additional_cost(self):
        """With only {B} in the pool, the caster sacrifices their creature and
        the target is exiled."""
        eaten, mine, theirs = card(EatenAlive), card(SavannahLions), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], battlefield=[mine], library=[card(Plains)], mana={ManaType.BLACK: 1}),
            Side(battlefield=[theirs], library=[card(Plains)]),
            start=MAIN,
        ))
        t.act(0, eaten, SACRIFICE, choices=[theirs], then=[moves(eaten, Zone.STACK), moves(mine, Zone.GRAVEYARD)])
        _resolve(t, eaten, theirs)
        t.run()

    def test_paying_three_and_black_pays_the_additional_cost(self):
        """With no creature to sacrifice, {3}{B} on top of {B} casts it."""
        eaten, theirs = card(EatenAlive), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], library=[card(Plains)], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 3}),
            Side(battlefield=[theirs], library=[card(Plains)]),
            start=MAIN,
        ))
        t.act(0, eaten, PAY_MANA, choices=[theirs], then=[moves(eaten, Zone.STACK)])
        _resolve(t, eaten, theirs)
        t.run()

    def test_neither_alternative_payable_cannot_cast(self):
        """No creature to sacrifice and one mana short of {3}{B}{B}: the spell
        cannot be cast, though {B} alone pays its mana cost."""
        eaten, theirs = card(EatenAlive), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], library=[card(Plains)], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 2}),
            Side(battlefield=[theirs], library=[card(Plains)]),
            start=MAIN,
        ))
        t.act_illegal(0, branches=_either_alternative(eaten), choices=[theirs])
        t.run()

    def test_the_sacrificed_creature_may_be_the_target(self):
        """Sacrificing the creature it targets is legal; with its target gone
        the spell does nothing and goes to the graveyard (rule 608.2b)."""
        eaten, mine = card(EatenAlive), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], battlefield=[mine], library=[card(Plains)], mana={ManaType.BLACK: 1}),
            Side(library=[card(Plains)]),
            start=MAIN,
        ))
        t.act(0, eaten, SACRIFICE, choices=[mine], then=[moves(eaten, Zone.STACK), moves(mine, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD)])
        t.run()

    def test_without_black_mana_it_cannot_be_cast_even_with_a_creature(self):
        """A creature to sacrifice pays only the additional cost: with no {B}
        for the mana cost, the spell cannot be cast."""
        eaten, mine, theirs = card(EatenAlive), card(SavannahLions), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], battlefield=[mine], library=[card(Plains)], mana={ManaType.COLORLESS: 4}),
            Side(battlefield=[theirs], library=[card(Plains)]),
            start=MAIN,
        ))
        t.act_illegal(0, branches=_either_alternative(eaten), choices=[theirs])
        t.run()


class TestEatenAliveTiming:
    def test_it_cannot_be_cast_on_another_players_turn(self):
        """A sorcery: player 0, with {B} and a creature to sacrifice, cannot
        cast it while player 1's main phase has the stack empty."""
        eaten, mine, theirs = card(EatenAlive), card(SavannahLions), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], battlefield=[mine], library=[card(Plains)], mana={ManaType.BLACK: 1}),
            Side(battlefield=[theirs], library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 1),
        ))
        t.pass_(1)
        t.act_illegal(0, branches=_either_alternative(eaten), choices=[theirs])
        t.run()


def _confiscate_their_lions(t, confiscate, lions, islands):
    """Player 0 taps six Islands and casts Confiscate on player 1's Lions."""
    for island in islands:
        t.act(0, island, then=[taps(island)])
    t.act(0, confiscate, choices=[lions], then=[moves(confiscate, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(confiscate, Zone.BATTLEFIELD), gains_control(lions, 0)])


class TestEatenAliveAcrossControlChanges:
    def _game(self, *, their_swamp=False):
        eaten, confiscate, lions, swamp = card(EatenAlive), card(Confiscate), card(SavannahLions), card(Swamp)
        islands = [card(Island) for _ in range(6)]
        mine = Side(hand=[eaten, confiscate], battlefield=[*islands, swamp],
                    library=[card(Plains), card(Plains)])
        theirs = Side(battlefield=[lions], library=[card(Plains), card(Plains)])
        if their_swamp:
            mine = Side(hand=[confiscate], battlefield=islands, library=[card(Plains), card(Plains)])
            theirs = Side(hand=[eaten], battlefield=[lions, swamp], library=[card(Plains), card(Plains)])
        t = Table(create_game(mine, theirs, start=MAIN))
        _confiscate_their_lions(t, confiscate, lions, islands)
        return t, eaten, confiscate, lions, swamp

    def test_a_creature_you_gained_control_of_can_be_sacrificed(self):
        """Player 0 controls player 1's Lions through Confiscate and, with only
        {B}, sacrifices it to cast Eaten Alive at it: the Lions goes to its
        owner's graveyard, the Confiscate with it, and the spell, its target
        gone, does nothing (rule 608.2b)."""
        t, eaten, confiscate, lions, swamp = self._game()
        t.act(0, swamp, then=[taps(swamp)])
        t.act(0, eaten, SACRIFICE, choices=[lions], then=[
            moves(eaten, Zone.STACK), moves(lions, Zone.GRAVEYARD), moves(confiscate, Zone.GRAVEYARD),
        ])
        t.pass_(0)
        t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD)])
        t.run()

    def test_a_creature_you_own_but_no_longer_control_cannot_be_sacrificed(self):
        """Player 1 still owns the Lions player 0 took with Confiscate, but
        controls no creature: with only {B}, Eaten Alive cannot be cast."""
        t, eaten, _, lions, swamp = self._game(their_swamp=True)
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        t.act(1, swamp, then=[taps(swamp)])
        t.act_illegal(1, branches=_either_alternative(eaten), choices=[lions])
        t.run()
