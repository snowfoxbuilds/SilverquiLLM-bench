"""Regression tests for FDN 48 — Refute.

"Counter target spell. Draw a card, then discard a card." Player 1 casts
spells on their turn and player 0 answers with Refute. A countered spell goes
to its owner's graveyard (rule 701.5a), a flashbacked one to exile (rule
702.34a). A target that already left the stack makes the whole spell do
nothing (rule 608.2b): no counter, and no draw or discard.
"""

from __future__ import annotations

from cards.fdn.fdn_9.card_impl import DazzlingAngel, DazzlingAngelAbility2
from cards.fdn.fdn_48.card_impl import Refute
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_248.card_impl import ThousandYearStorm, ThousandYearStormAbility1
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import Instant
from engine.types import ManaCost
from test_interface import (
    Decision,
    ManaType,
    Phase,
    Side,
    Zone,
    card,
    create_game,
    player,
    spell_copy,
)

from table import Table, copied, life, moves, off_stack, on_stack, taps

KEEP_TARGETS = Decision.no()


def _table(p0: Side, p1: Side) -> Table:
    """Player 1's main phase; player 0 holds Refute and three blue mana."""
    return Table(create_game(p0, p1, start=(Phase.PRECOMBAT_MAIN, 1)))


def _refute(t: Table, refute, target, drawn, *countered) -> None:
    """Player 0 casts Refute at ``target``; it resolves, countering it, and
    player 0 draws ``drawn`` and discards it."""
    t.act(0, refute, choices=[target], then=[moves(refute, Zone.STACK)])
    t.pass_(0, choices=[drawn])
    t.pass_(1, then=[*countered, moves(drawn, Zone.HAND), moves(drawn, Zone.GRAVEYARD), moves(refute, Zone.GRAVEYARD)])


class TestRefuteProperties:
    def test_is_instant(self) -> None:
        assert isinstance(Refute(owner=None), Instant)

    def test_mana_cost(self) -> None:
        assert Refute(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")



class TestRefuteCounters:
    def test_ordinary_countered_spell_to_owner_graveyard(self) -> None:
        """The countered Burst Lightning goes to its owner's graveyard, and
        Refute to its own owner's."""
        refute, drawn, bolt = card(Refute), card(Forest), card(BurstLightning)
        t = _table(
            Side(hand=[refute], library=[drawn], mana={ManaType.BLUE: 3}),
            Side(hand=[bolt], mana={ManaType.RED: 1}),
        )
        t.act(1, bolt, choices=[player(0)], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        _refute(t, refute, bolt, drawn, moves(bolt, Zone.GRAVEYARD))
        t.run()

    def test_flashback_countered_spell_exiled(self) -> None:
        """Countering a flashbacked spell exiles it (rule 702.34a)."""
        refute, drawn, think = card(Refute), card(Forest), card(ThinkTwice)
        t = _table(
            Side(hand=[refute], library=[drawn], mana={ManaType.BLUE: 3}),
            Side(graveyard=[think], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2}),
        )
        t.act(1, think, then=[moves(think, Zone.STACK)], note="cast by flashback")
        t.pass_(1)
        _refute(t, refute, think, drawn, moves(think, Zone.EXILE))
        t.run()

    def test_refute_draws_and_discards_on_successful_counter(self) -> None:
        """The drawn card passes through player 0's hand to the graveyard,
        leaving the rest of their library and hand as they were."""
        refute, drawn, kept, held, bolt = card(Refute), card(Forest), card(Island), card(Island), card(BurstLightning)
        t = _table(
            Side(hand=[refute, held], library=[drawn, kept], mana={ManaType.BLUE: 3}),
            Side(hand=[bolt], mana={ManaType.RED: 1}),
        )
        t.act(1, bolt, choices=[player(0)], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        _refute(t, refute, bolt, drawn, moves(bolt, Zone.GRAVEYARD))
        t.run()

    def test_counter_fizzles_when_occurrence_departed_and_recast(self) -> None:
        """Rule 608.2b: player 0's second Refute counters Think Twice first,
        and player 1 casts it again by flashback; the first Refute's target
        left the stack, so it does nothing — the recast Think Twice is not
        touched, and player 0 draws nothing."""
        first, second, drawn, spare = card(Refute), card(Refute), card(Forest), card(Forest)
        think, p1_draw = card(ThinkTwice), card(Island)
        islands = [card(Island) for _ in range(3)]
        t = _table(
            Side(hand=[first, second], library=[drawn, spare], mana={ManaType.BLUE: 6}),
            Side(hand=[think], battlefield=islands, library=[p1_draw], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1}),
        )
        t.act(1, think, then=[moves(think, Zone.STACK)])
        t.pass_(1)
        t.act(0, first, choices=[think], then=[moves(first, Zone.STACK)])
        _refute(t, second, think, drawn, moves(think, Zone.GRAVEYARD))
        for island in islands:
            t.act(1, island, then=[taps(island)])
        t.act(1, think, then=[moves(think, Zone.STACK)], note="cast again by flashback")
        t.pass_(1)
        t.pass_(0, then=[moves(p1_draw, Zone.HAND), moves(think, Zone.EXILE)])
        t.pass_(1)
        t.pass_(0, then=[moves(first, Zone.GRAVEYARD)], note="the first Refute does nothing: no draw")
        t.run()

    def test_copy_countered_distinctly_from_original(self) -> None:
        """A spell copy is its own stack object: Refute counters Thousand-Year
        Storm's copy of the second Burst Lightning, and the original still
        deals its 2."""
        refute, drawn = card(Refute), card(Forest)
        first, second = card(BurstLightning), card(BurstLightning)
        t = _table(
            Side(hand=[refute], library=[drawn], mana={ManaType.BLUE: 3}),
            Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={ManaType.RED: 2}),
        )
        for bolt, copies, life_after in ((first, 0, 18), (second, 1, None)):
            t.act(1, bolt, choices=[player(0)], then=[moves(bolt, Zone.STACK), on_stack(ThousandYearStormAbility1, 1)])
            t.pass_(1, choices=[KEEP_TARGETS])
            t.pass_(0, then=[off_stack(ThousandYearStormAbility1), *[copied(BurstLightning, 1)] * copies])
            if life_after is not None:
                t.pass_(1)
                t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), life(0, life_after)])
        t.pass_(1)
        _refute(t, refute, spell_copy(1), drawn, off_stack(BurstLightning))
        t.pass_(1)
        t.pass_(0, then=[moves(second, Zone.GRAVEYARD), life(0, 16)])
        t.run()

    def test_trigger_sharing_source_card_is_not_a_target_spell(self) -> None:
        """A triggered ability on the stack is not a spell, though it has a
        source card: with only Dazzling Angel's trigger on the stack, Refute
        has no legal target and cannot be cast."""
        refute, lions = card(Refute), card(SavannahLions)
        t = _table(
            Side(hand=[refute], mana={ManaType.BLUE: 3}),
            Side(hand=[lions], battlefield=[DazzlingAngel], mana={ManaType.WHITE: 1}),
        )
        t.act(1, lions, then=[moves(lions, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(lions, Zone.BATTLEFIELD), on_stack(DazzlingAngelAbility2, 1)])
        t.pass_(1)
        t.act_illegal(0, refute, note="no spell to target")
        t.pass_(0, then=[off_stack(DazzlingAngelAbility2), life(1, 21)])
        t.run()
