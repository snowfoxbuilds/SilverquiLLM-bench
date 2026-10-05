"""Reference test for FDN 39 — Grappling Kraken.

A **triggered ability that targets**: landfall taps the opponent's only
creature and puts a stun counter on it.
"""

from __future__ import annotations

from cards.fdn.fdn_39.card_impl import GrapplingKraken, GrapplingKrakenAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_274.card_impl import Island
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, life, moves, off_stack, on_stack, taps


class TestGrapplingKrakenProperties:
    def test_static_data(self):
        card_ = GrapplingKraken(owner=None)
        assert printed_class(card_) is GrapplingKraken
        assert card_.mana_cost == ManaCost.parse("{4}{U}{U}")
        assert (card_.base_power, card_.base_toughness) == (5, 6)
        assert card_.subtypes == {"Kraken"}


class TestGrapplingKrakenLandfall:
    def test_landfall_taps_and_stuns_opponent_creature(self):
        """The tapped Lions cannot block the Kraken. (Known-Best does not keep a
        stunned permanent tapped, rule 122.1d, so the stun counter goes
        unjudged.)"""
        island, lions, kraken = card(Island), card(SavannahLions), card(GrapplingKraken)
        game = create_game(
            Side(battlefield=[kraken], hand=[island]),
            Side(battlefield=[lions]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(
            0, island, then=[moves(island, Zone.BATTLEFIELD), on_stack(GrapplingKrakenAbility1, 0)]
        )
        t.pass_(0)
        t.pass_(1, then=[off_stack(GrapplingKrakenAbility1), taps(lions)])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, kraken, then=[taps(kraken)])
        t.pass_(0)
        t.pass_(1)
        t.act_illegal(1, lions, scoped={lions: kraken}, note="a tapped creature cannot block")
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 15)])
        t.run()

    def test_no_opponent_creature_is_a_noop(self):
        """With no opponent creature there is no legal target, so the
        landfall trigger is removed and nothing goes on the stack (rule
        603.3d)."""
        island = card(Island)
        game = create_game(
            Side(battlefield=[GrapplingKraken], hand=[island]), Side(), start=(Phase.PRECOMBAT_MAIN, 0)
        )
        t = Table(game)
        t.act(0, island, then=[moves(island, Zone.BATTLEFIELD)], note="no landfall trigger on the stack")
        t.run()

    def test_landfall_only_from_your_own_land(self):
        """A land the opponent plays does not trigger the Kraken's landfall."""
        island, lions = card(Island), card(SavannahLions)
        game = create_game(
            Side(battlefield=[GrapplingKraken]),
            Side(battlefield=[lions], hand=[island]),
            start=(Phase.PRECOMBAT_MAIN, 1),
        )
        t = Table(game)
        t.act(
            1,
            island,
            then=[moves(island, Zone.BATTLEFIELD)],
            note="no landfall trigger, the Lions stays untapped",
        )
        t.run()
