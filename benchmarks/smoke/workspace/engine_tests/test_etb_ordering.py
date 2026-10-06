"""Own-ETB trigger ordering (rule 603.3a).

An entering permanent's own abilities see its own entry, so a permanent's own
enters trigger fires on its own entry (rule 603.6a). These tests prove both
directions, each by what goes on the stack:

* an own-enters ("When this creature enters") trigger fires once on its own
  entry — Helpful Hunter draws one card;
* a token copy of that creature fires its own enters trigger once and does
  not loop — Electroduplicate copies Helpful Hunter;
* an "another …"-filtered trigger does **not** fire on its own entry, but
  fires once when a *different* creature enters — Beast-Kin Ranger.
"""

from __future__ import annotations

from cards.fdn.fdn_16.card_impl import HelpfulHunter, HelpfulHunterAbility1
from cards.fdn.fdn_100.card_impl import BeastKinRanger, BeastKinRangerAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_163.card_impl import SelfReflection
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Phase, Side, Zone, card, create_game

from silverquillm.table import Table, appears, moves, off_stack, on_stack, taps


def _tap(t: Table, *lands) -> None:
    for land in lands:
        t.act(0, land, then=[taps(land)])


def _cast_creature(t: Table, creature, *, then_enters=()) -> None:
    """Player 0 casts ``creature``; both pass and it enters, with
    ``then_enters`` the changes its entry causes."""
    t.act(0, creature, then=[moves(creature, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(creature, Zone.BATTLEFIELD), *then_enters])


class TestOwnETBFiresOnOwnEntry:
    def test_self_etb_fires_exactly_once(self) -> None:
        hunter, drawn = card(HelpfulHunter), card(Plains)
        lands = [card(Plains), card(Plains)]
        game = create_game(
            Side(battlefield=lands, hand=[hunter], library=[drawn, Plains]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _tap(t, *lands)
        _cast_creature(t, hunter, then_enters=[on_stack(HelpfulHunterAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(HelpfulHunterAbility1), moves(drawn, Zone.HAND)], note="one card drawn, nothing more on the stack")
        t.run()

    def test_self_etb_via_create_token_no_loop(self) -> None:
        hunter, duplicate, drawn = card(HelpfulHunter), card(SelfReflection), card(Plains)
        lands = [card(Island), card(Island), *(card(Plains) for _ in range(4))]
        game = create_game(
            Side(battlefield=[hunter, *lands], hand=[duplicate], library=[drawn, Plains]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _tap(t, *lands)
        t.act(0, duplicate, choices=[hunter], then=[moves(duplicate, Zone.STACK)])
        t.pass_(0)
        t.pass_(
            1,
            then=[moves(duplicate, Zone.GRAVEYARD), appears(0), on_stack(HelpfulHunterAbility1, 0)],
            note="the token copy's own enters trigger",
        )
        t.pass_(0)
        t.pass_(1, then=[off_stack(HelpfulHunterAbility1), moves(drawn, Zone.HAND)], note="it fires once, with no loop")
        t.run()


class TestAnotherFilteredETBDoesNotSelfFire:
    def test_another_filter_does_not_self_fire(self) -> None:
        ranger = card(BeastKinRanger)
        lands = [card(Forest), card(Plains), card(Plains)]
        game = create_game(
            Side(battlefield=lands, hand=[ranger]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _tap(t, *lands)
        _cast_creature(t, ranger)
        final = t.run()
        assert final.stack == ()

    def test_another_filter_fires_for_a_different_creature(self) -> None:
        ranger, lions = card(BeastKinRanger), card(SavannahLions)
        lands = [card(Forest), card(Plains), card(Plains), card(Plains)]
        game = create_game(
            Side(battlefield=lands, hand=[ranger, lions]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _tap(t, *lands[:3])
        _cast_creature(t, ranger)
        _tap(t, lands[3])
        _cast_creature(t, lions, then_enters=[on_stack(BeastKinRangerAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(BeastKinRangerAbility2)], note="it fired exactly once")
        t.run()
