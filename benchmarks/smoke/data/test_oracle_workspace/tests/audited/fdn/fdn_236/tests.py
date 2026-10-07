"""Audited tests for FDN 236 — Wildwood Scourge.

"This creature enters with X +1/+1 counters on it. Whenever one or more +1/+1
counters are put on another non-Hydra creature you control, put a +1/+1
counter on this creature." Its size shows in how much damage it survives.
"""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_195.card_impl import FanaticalFirebrand, FanaticalFirebrandAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_236.card_impl import WildwoodScourge, WildwoodScourgeAbility2
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import Decision, ManaType, Phase, Side, Zone, card, create_game

from table import Table, moves, off_stack, on_stack, taps


def _cast_scourge(t, scourge, x, *, then):
    t.act(0, scourge, choices=[Decision.number(x)], then=[moves(scourge, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=list(then))


def _cast(t, land, spell, target, *, then=()):
    t.act(0, land, then=[taps(land)])
    t.act(0, spell, choices=[target], then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), *then])


def _a_target(query):
    """The Firebrand's target question, which unlike a priority question
    cannot be declined."""
    return query.min > 0


def _ping(t, brand, target, *, then=()):
    """Player 0 sacrifices ``brand`` to deal 1 damage to ``target``; the
    Firebrand, itself a legal target, is the action's preference, so the
    target question is answered by its own key."""
    t.act(0, brand, per_query={_a_target: [target]}, then=[moves(brand, Zone.GRAVEYARD), on_stack(FanaticalFirebrandAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(FanaticalFirebrandAbility2), *then])


class TestWildwoodScourgeProperties:
    def test_name_and_cost(self) -> None:
        card = WildwoodScourge(owner=None)
        assert printed_class(card) is WildwoodScourge
        assert card.mana_cost == ManaCost.parse("{X}{G}")

    def test_x_zero_enters_at_zero_zero_no_fabrication(self) -> None:
        """With X = 0 it enters with no counters as a 0/0 and dies."""
        scourge = card(WildwoodScourge)
        game = create_game(Side(hand=[scourge], mana={ManaType.GREEN: 1}), Side(), start=(Phase.PRECOMBAT_MAIN, 0))
        t = Table(game)
        _cast_scourge(t, scourge, 0, then=[moves(scourge, Zone.GRAVEYARD)])
        t.run()

    def test_enters_with_x_counters(self) -> None:
        """X = 3 is chosen and paid while casting (rules 601.2b, 601.2f): the
        3/3 survives one Burst Lightning and dies to a second."""
        scourge, bolt, other_bolt = card(WildwoodScourge), card(BurstLightning), card(BurstLightning)
        mountain, other_mountain = card(Mountain), card(Mountain)
        game = create_game(
            Side(hand=[scourge, bolt, other_bolt], battlefield=[mountain, other_mountain],
                 mana={ManaType.GREEN: 1, ManaType.COLORLESS: 3}),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast_scourge(t, scourge, 3, then=[moves(scourge, Zone.BATTLEFIELD)])
        _cast(t, mountain, bolt, scourge)
        _cast(t, other_mountain, other_bolt, scourge, then=[moves(scourge, Zone.GRAVEYARD)])
        t.run()


class TestWildwoodScourgeTriggerRegistration:
    def test_condition_matches_other_nonhydra_creature_you_control(self) -> None:
        """A counter on player 0's Lions grows the 1/1 Scourge to a 2/2, which
        survives 1 damage; a counter on player 1's Elves does not grow it, so
        a second 1 damage kills it."""
        scourge, lions, elves = card(WildwoodScourge), card(SavannahLions), card(LlanowarElves)
        flight, other_flight, plains, other_plains = card(FleetingFlight), card(FleetingFlight), card(Plains), card(Plains)
        brand, other_brand = card(FanaticalFirebrand), card(FanaticalFirebrand)
        game = create_game(
            Side(hand=[scourge, flight, other_flight], battlefield=[lions, plains, other_plains, brand, other_brand],
                 mana={ManaType.GREEN: 2}),
            Side(battlefield=[elves]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast_scourge(t, scourge, 1, then=[moves(scourge, Zone.BATTLEFIELD)])
        _cast(t, plains, flight, lions, then=[on_stack(WildwoodScourgeAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(WildwoodScourgeAbility2)])
        _ping(t, brand, scourge)
        _cast(t, other_plains, other_flight, elves)
        _ping(t, other_brand, scourge, then=[moves(scourge, Zone.GRAVEYARD)])
        t.run()
