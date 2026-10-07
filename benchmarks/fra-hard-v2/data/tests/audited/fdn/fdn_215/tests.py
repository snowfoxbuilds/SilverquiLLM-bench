"""Audited tests for FDN 215 — Bushwhack.

"Choose one — • Search your library for a basic land card, reveal it, put it
into your hand, then shuffle. • Target creature you control fights target
creature you don't control." The mode and the fight's targets are chosen
while casting (rule 601.2b-c): the first target only among the caster's
creatures, the second only among the others'.

A target that changes control before Bushwhack resolves is reached through
High Fae Trickster and Involuntary Employment.
"""

from __future__ import annotations

from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_215.card_impl import Bushwhack, BushwhackAbility2, BushwhackAbility3
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_250.card_impl import BurnishedHart
from cards.fdn.fdn_264.card_impl import RoguesPassage
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest as FdnForest
from engine.card import printed_class
from engine.types import ManaCost, ManaType
from test_interface import Phase as TablePhase
from test_interface import Side, card, create_game, shuffled
from test_interface import Zone as TableZone

from table import Table, appears, gains_control, moves, taps


def _table(mine=(), theirs=(), library=()):
    bushwhack = card(Bushwhack)
    game = create_game(
        Side(hand=[bushwhack], battlefield=list(mine), library=list(library), mana={ManaType.GREEN: 1}),
        Side(battlefield=list(theirs)),
        start=(TablePhase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), bushwhack


def _cast(t, bushwhack, *choices, found=(), then=(), fallback=None, found_fallback=None):
    """Player 0 casts Bushwhack answering its mode and targets from
    ``choices``, and both players pass, resolving it; player 0's pass answers
    the search from ``found``. ``fallback`` and ``found_fallback`` answer
    instead once the engine has rejected a choice the first answers made."""
    if fallback is None:
        t.act(0, bushwhack, choices=list(choices), then=[moves(bushwhack, TableZone.STACK)])
    else:
        t.act(0, branches=[[bushwhack, *choices], [bushwhack, *fallback]], then=[moves(bushwhack, TableZone.STACK)])
    if found_fallback is None:
        t.pass_(0, choices=list(found))
    else:
        t.pass_(0, branches=[list(found), list(found_fallback)])
    t.pass_(1, then=[moves(bushwhack, TableZone.GRAVEYARD), *then])


class TestBushwhackProperties:
    def test_static_data(self):
        bw = Bushwhack(owner=None)
        assert printed_class(bw) is Bushwhack
        assert bw.mana_cost == ManaCost.parse("{G}")


class TestBushwhackFight:
    def test_each_creature_deals_its_power_to_the_other(self):
        """The 3/3 kills the 1/1 and survives the 1 damage it takes."""
        ours, theirs = card(BrazenScourge), card(LlanowarElves)
        t, bushwhack = _table([ours], [theirs])
        _cast(t, bushwhack, BushwhackAbility3, ours, theirs, then=[moves(theirs, TableZone.GRAVEYARD)])
        t.run()

    def test_mutual_destruction(self):
        ours, theirs = card(BurnishedHart), card(BurnishedHart)
        t, bushwhack = _table([ours], [theirs])
        _cast(t, bushwhack, BushwhackAbility3, ours, theirs,
              then=[moves(ours, TableZone.GRAVEYARD), moves(theirs, TableZone.GRAVEYARD)])
        t.run()

    def test_fight_targets_split_by_control(self):
        """The caster prefers the opponent's creature for every target; the
        first target can only be the caster's creature — the 1/1 is not
        offered for it, or offered and rejected — so the 3/3 fights the 1/1.
        Choosing the 1/1 first would fight it with nothing of ours."""
        ours, theirs = card(BrazenScourge), card(LlanowarElves)
        t, bushwhack = _table([ours], [theirs])
        _cast(t, bushwhack, BushwhackAbility3, theirs, ours, then=[moves(theirs, TableZone.GRAVEYARD)],
              fallback=[BushwhackAbility3, ours, theirs])
        t.run()


class TestBushwhackSearch:
    def test_finds_basic_land_and_puts_it_in_hand(self):
        forest, passage = card(FdnForest), card(RoguesPassage)
        t, bushwhack = _table(library=[forest, passage])
        _cast(t, bushwhack, BushwhackAbility2, found=[forest], then=[moves(forest, TableZone.HAND)])
        t.run(chance=[shuffled(passage)])

    def test_search_offers_only_basics(self):
        """The caster prefers the nonbasic Rogue's Passage, but only the basic
        Forest can be found: the Passage is not offered, or offered and
        rejected."""
        forest, passage = card(FdnForest), card(RoguesPassage)
        t, bushwhack = _table(library=[passage, forest])
        _cast(t, bushwhack, BushwhackAbility2, found=[passage, forest], then=[moves(forest, TableZone.HAND)],
              found_fallback=[forest])
        t.run(chance=[shuffled(passage)])


class TestBushwhackFightRevalidation:

    def test_target_control_change_before_resolution_no_fight(self):
        """Negative revalidation: with Bushwhack on the stack, player 0, whose
        High Fae Trickster lets them cast Involuntary Employment at instant
        speed, takes the opponent's Llanowar Elves, so it is no longer 'a
        creature you don't control'. The fight needs both legal targets, so
        nothing happens and the 1/1 Elves survives."""
        ours, theirs = card(BrazenScourge), card(LlanowarElves)
        bushwhack, employment = card(Bushwhack), card(InvoluntaryEmployment)
        mountains = [card(Mountain) for _ in range(4)]
        game = create_game(
            Side(hand=[bushwhack, employment], battlefield=[ours, HighFaeTrickster, *mountains], mana={ManaType.GREEN: 1}),
            Side(battlefield=[theirs]),
            start=(TablePhase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, bushwhack, choices=[BushwhackAbility3, ours, theirs], then=[moves(bushwhack, TableZone.STACK)])
        for mountain in mountains:
            t.act(0, mountain, then=[taps(mountain)])
        t.act(0, employment, choices=[theirs], then=[moves(employment, TableZone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(employment, TableZone.GRAVEYARD), gains_control(theirs, 0), appears(0)])
        t.pass_(0)
        t.pass_(1, then=[moves(bushwhack, TableZone.GRAVEYARD)], note="no fight: the Elves survives")
        t.run()
