"""Regression tests for FDN 160 — An Offer You Can't Refuse.

"Counter target noncreature spell. Its controller creates two Treasure
tokens." Player 1 casts spells on their turn and player 0 answers with An
Offer. A countered spell goes to its owner's graveyard, a flashbacked one to
exile (rule 702.34a), and the countered spell's controller gets the Treasures
only when the counter happens: a target that already left the stack makes
the whole spell do nothing (rule 608.2b).
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_274.card_impl import Island
from engine.card import Instant
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game, player

from table import Table, appears, moves, taps


def _table(p0: Side, p1: Side) -> Table:
    """Player 1's main phase; player 0 holds An Offer."""
    return Table(create_game(p0, p1, start=(Phase.PRECOMBAT_MAIN, 1)))


def _offer(t: Table, offer, target, *countered) -> None:
    """Player 0 casts An Offer at ``target``; it resolves, countering it, and
    player 1 makes two Treasures."""
    t.act(0, offer, choices=[target], then=[moves(offer, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[*countered, appears(1), appears(1), moves(offer, Zone.GRAVEYARD)])


class TestAnOfferProperties:
    def test_is_instant(self) -> None:
        assert isinstance(AnOfferYouCantRefuse(owner=None), Instant)

    def test_mana_cost(self) -> None:
        assert AnOfferYouCantRefuse(owner=None).mana_cost == ManaCost.parse("{U}")


class TestAnOfferCounters:
    def test_countered_spell_to_owner_graveyard_with_treasures(self) -> None:
        offer, bolt = card(AnOfferYouCantRefuse), card(BurstLightning)
        t = _table(Side(hand=[offer], mana={ManaType.BLUE: 1}), Side(hand=[bolt], mana={ManaType.RED: 1}))
        t.act(1, bolt, choices=[player(0)], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        _offer(t, offer, bolt, moves(bolt, Zone.GRAVEYARD))
        t.run()

    def test_flashback_countered_spell_exiled_with_treasures(self) -> None:
        """Countering a flashbacked spell exiles it (rule 702.34a); the
        Treasures still come, since the counter happened."""
        offer, think = card(AnOfferYouCantRefuse), card(ThinkTwice)
        t = _table(
            Side(hand=[offer], mana={ManaType.BLUE: 1}),
            Side(graveyard=[think], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2}),
        )
        t.act(1, think, then=[moves(think, Zone.STACK)], note="cast by flashback")
        t.pass_(1)
        _offer(t, offer, think, moves(think, Zone.EXILE))
        t.run()

    def test_creature_spell_is_not_targetable(self) -> None:
        """With only a creature spell on the stack, An Offer has no legal
        target and cannot be cast."""
        offer, lions = card(AnOfferYouCantRefuse), card(SavannahLions)
        t = _table(Side(hand=[offer], mana={ManaType.BLUE: 1}), Side(hand=[lions], mana={ManaType.WHITE: 1}))
        t.act(1, lions, then=[moves(lions, Zone.STACK)])
        t.pass_(1)
        t.act_illegal(0, offer, note="a creature spell is not a target")
        t.pass_(0, then=[moves(lions, Zone.BATTLEFIELD)])
        t.run()

    def test_counter_fizzles_when_occurrence_departed_no_treasures(self) -> None:
        """Rule 608.2b: player 0's second Offer counters Think Twice first,
        and player 1 casts it again by flashback; the first Offer's target
        left the stack, so it does nothing — no counter and no more
        Treasures."""
        first, second = card(AnOfferYouCantRefuse), card(AnOfferYouCantRefuse)
        think, p1_draw = card(ThinkTwice), card(Island)
        islands = [card(Island) for _ in range(3)]
        t = _table(
            Side(hand=[first, second], mana={ManaType.BLUE: 2}),
            Side(hand=[think], battlefield=islands, library=[p1_draw], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1}),
        )
        t.act(1, think, then=[moves(think, Zone.STACK)])
        t.pass_(1)
        t.act(0, first, choices=[think], then=[moves(first, Zone.STACK)])
        _offer(t, second, think, moves(think, Zone.GRAVEYARD))
        for island in islands:
            t.act(1, island, then=[taps(island)])
        t.act(1, think, then=[moves(think, Zone.STACK)], note="cast again by flashback")
        t.pass_(1)
        t.pass_(0, then=[moves(p1_draw, Zone.HAND), moves(think, Zone.EXILE)])
        t.pass_(1)
        t.pass_(0, then=[moves(first, Zone.GRAVEYARD)], note="the first Offer does nothing: no Treasures")
        t.run()
