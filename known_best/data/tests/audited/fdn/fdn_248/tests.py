"""Thousand-Year Storm copy counts and retargeting, seen in play.

Each copy shows in what it does: a copy of Burst Lightning aimed at player 1
costs them 2 more life, a copy of Think Twice draws one more card. Unless a
test says otherwise, player 0 controls Thousand-Year Storm and casts in their
first main phase.
"""

from __future__ import annotations

from cards.fdn.fdn_43.card_impl import InspirationFromBeyond
from cards.fdn.fdn_71.card_impl import Stab
from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from cards.fdn.fdn_162.card_impl import RunAwayTogether
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_244.card_impl import Progenitus
from cards.fdn.fdn_248.card_impl import ThousandYearStorm, ThousandYearStormAbility1
from cards.fdn.fdn_249.card_impl import AdventuringGear, AdventuringGearAbility2
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import Decision, ManaType, Phase, Side, Zone, card, create_game, player

from table import Table, appears, copied, life, moves, off_stack, on_stack, taps

STORM = ThousandYearStormAbility1
MAIN = (Phase.PRECOMBAT_MAIN, 0)
KEEP_TARGETS = Decision.no()
NEW_TARGETS = Decision.yes()


def _table(p0: Side, p1: Side | None = None, *, start=MAIN) -> Table:
    return Table(create_game(p0, p1 or Side(), start=start))


def _resolve(t: Table, *then, choices=(), first: int = 0, note: str = "", fallback=None) -> None:
    """Both players pass, ``first`` first, and the top of the stack resolves;
    ``choices`` answer the questions its resolution asks player 0 — or
    ``fallback`` does, once the engine has rejected a choice from them."""
    if fallback is not None:
        assert first == 0
        t.pass_(0, branches=[list(choices), list(fallback)])
        t.pass_(1, then=list(then), note=note)
    elif first == 0:
        t.pass_(0, choices=list(choices))
        t.pass_(1, then=list(then), note=note)
    else:
        t.pass_(1)
        t.pass_(0, choices=list(choices), then=list(then), note=note)


def _hit(t: Table, seat: int, amount: int = 2):
    return life(seat, t.expected.players[seat].life - amount)


def _cast_at_table(t: Table, seat: int, spell, *choices, storms: int = 1, then=(), note: str = "") -> None:
    """``seat`` casts ``spell``; each of their Storms triggers, ordered by
    the caster when there are several (rule 603.3b)."""
    order = [STORM] * storms if storms > 1 else []
    t.act(
        seat,
        spell,
        choices=[*choices, *order],
        then=[moves(spell, Zone.STACK), *[on_stack(STORM, seat)] * storms, *then],
        note=note,
    )


def _copies(t: Table, cls: type, copies: int, *, retarget=(KEEP_TARGETS,)) -> None:
    """The Storm trigger on top resolves into ``copies`` copies of a ``cls``
    spell, each answering its retarget question from ``retarget``."""
    _resolve(t, off_stack(STORM), *[copied(cls, 0)] * copies, choices=retarget)


def _bolt(t: Table, bolt, *, copies: int, at: int = 1, storms: int = 1) -> None:
    """Player 0 casts Burst Lightning at player ``at``; Storm makes ``copies``
    copies, which keep the target; every copy and then the spell deal 2."""
    _cast_at_table(t, 0, bolt, player(at), storms=storms)
    for _ in range(storms):
        _copies(t, BurstLightning, copies)
        for _ in range(copies):
            _resolve(t, off_stack(BurstLightning), _hit(t, at))
    _resolve(t, moves(bolt, Zone.GRAVEYARD), _hit(t, at))


def _think(t: Table, think, library: list, *, copies: int, storms: int = 1, flashback: bool = False) -> None:
    """Player 0 casts Think Twice; each copy and then the spell draw a card
    from ``library``, which the drawn cards are taken from."""
    _cast_at_table(t, 0, think, storms=storms, note="flashback" if flashback else "")
    for _ in range(storms):
        _copies(t, ThinkTwice, copies)
        for _ in range(copies):
            _resolve(t, off_stack(ThinkTwice), moves(library.pop(0), Zone.HAND))
    _resolve(t, moves(think, Zone.EXILE if flashback else Zone.GRAVEYARD), moves(library.pop(0), Zone.HAND))


def _next_turn_main(t: Table, seat: int) -> None:
    t.pass_to(Phase.PRECOMBAT_MAIN, seat)


# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------


class TestThousandYearStormProperties:
    def test_static_data(self):
        storm = ThousandYearStorm(owner=None)
        assert printed_class(storm) is ThousandYearStorm
        assert storm.mana_cost == ManaCost.parse("{4}{U}{R}")


# ---------------------------------------------------------------------------
# Each trigger keeps its own spell and copy count
# ---------------------------------------------------------------------------


class TestStormPerTriggerState:
    def test_response_order_B_copies_B_A_copies_nothing(self):
        """Burst Lightning, then Think Twice in response to its Storm trigger:
        Think Twice's trigger copies it once, Burst Lightning's copies nothing,
        and neither copies the other spell."""
        bolt, think = card(BurstLightning), card(ThinkTwice)
        library = [card(Plains), card(Plains)]
        t = _table(Side(hand=[bolt, think], battlefield=[ThousandYearStorm], library=list(library),
                        mana={ManaType.RED: 1, ManaType.BLUE: 2}))
        _cast_at_table(t, 0, bolt, player(1))
        _cast_at_table(t, 0, think, note="in response to Burst Lightning's trigger")
        _copies(t, ThinkTwice, 1)
        _resolve(t, off_stack(ThinkTwice), moves(library[0], Zone.HAND))
        _resolve(t, moves(think, Zone.GRAVEYARD), moves(library[1], Zone.HAND))
        _copies(t, BurstLightning, 0)
        _resolve(t, moves(bolt, Zone.GRAVEYARD), life(1, 18))
        t.run()

    def test_three_spells_counts_zero_one_two(self):
        bolts = [card(BurstLightning) for _ in range(3)]
        t = _table(Side(hand=bolts, battlefield=[ThousandYearStorm], mana={ManaType.RED: 3}))
        for copies, bolt in enumerate(bolts):
            _bolt(t, bolt, copies=copies)
        t.run()

    def test_turn_rollover_resets_count(self):
        first, second, mountain = card(BurstLightning), card(BurstLightning), card(Mountain)
        t = _table(
            Side(hand=[first, second], battlefield=[ThousandYearStorm, mountain], library=[card(Plains)]),
            Side(library=[card(Plains)]),
        )
        t.act(0, mountain, then=[taps(mountain)])
        _bolt(t, first, copies=0)
        _next_turn_main(t, 0)
        t.act(0, mountain, then=[taps(mountain)])
        _bolt(t, second, copies=0)
        t.run()

    def test_countered_triggering_spell_makes_no_copies_and_copies_no_other(self):
        """Player 1 counters the second Burst Lightning: its trigger makes no
        copies, and never falls back to copying the first one."""
        first, second, offer = card(BurstLightning), card(BurstLightning), card(AnOfferYouCantRefuse)
        t = _table(
            Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={ManaType.RED: 2}),
            Side(hand=[offer], mana={ManaType.BLUE: 1}),
        )
        _cast_at_table(t, 0, first, player(1))
        _cast_at_table(t, 0, second, player(1))
        t.pass_(0)
        t.act(1, offer, choices=[second], then=[moves(offer, Zone.STACK)])
        _resolve(
            t,
            moves(offer, Zone.GRAVEYARD), moves(second, Zone.GRAVEYARD), appears(0), appears(0),
            first=1,
        )
        _copies(t, BurstLightning, 0)
        _copies(t, BurstLightning, 0)
        _resolve(t, moves(first, Zone.GRAVEYARD), life(1, 18))
        t.run()

    def test_independent_targets_for_simultaneous_triggers(self):
        """Two Storm triggers pending at once, copying different spells, choose
        new targets independently: Burst Lightning's two copies go to the
        second Brazen Scourge and Stab's copy to the Savannah Lions."""
        filler, stab, bolt = card(BurstLightning), card(Stab), card(BurstLightning)
        c1, c2, c3 = card(BrazenScourge), card(BrazenScourge), card(SavannahLions)
        t = _table(
            Side(hand=[filler, stab, bolt], battlefield=[ThousandYearStorm],
                 mana={ManaType.RED: 2, ManaType.BLACK: 1}),
            Side(battlefield=[c1, c2, c3]),
        )
        _bolt(t, filler, copies=0)
        _cast_at_table(t, 0, stab, c1)
        _cast_at_table(t, 0, bolt, c1, note="in response to Stab's trigger")
        _resolve(t, off_stack(STORM), copied(BurstLightning, 0), copied(BurstLightning, 0),
                 choices=[NEW_TARGETS, c2])
        _resolve(t, off_stack(BurstLightning))
        _resolve(t, off_stack(BurstLightning), moves(c2, Zone.GRAVEYARD))
        _resolve(t, moves(bolt, Zone.GRAVEYARD))
        _resolve(t, off_stack(STORM), copied(Stab, 0), choices=[NEW_TARGETS, c3])
        _resolve(t, off_stack(Stab), moves(c3, Zone.GRAVEYARD))
        _resolve(t, moves(stab, Zone.GRAVEYARD), moves(c1, Zone.GRAVEYARD))
        t.run()


# ---------------------------------------------------------------------------
# Retargeting a copy uses the copied spell's whole targeting rules
# ---------------------------------------------------------------------------


def _second_spell(p1: Side, spell, *, p0_battlefield=(), mana=None) -> Table:
    """Player 0 holds Burst Lightning and ``spell``, and casts the Burst
    Lightning at player 1 first, so ``spell`` is copied once."""
    prior = card(BurstLightning)
    t = _table(
        Side(hand=[prior, spell], battlefield=[ThousandYearStorm, *p0_battlefield],
             mana=mana if mana is not None else {ManaType.RED: 2}),
        p1,
    )
    _bolt(t, prior, copies=0)
    return t


class TestStormCopyRetargeting:
    def test_copy_retains_targets_and_resolves(self):
        """Declining the retarget, the copy keeps the original's target: the
        3/3 takes 2 twice and dies."""
        c1, bolt = card(BrazenScourge), card(BurstLightning)
        t = _second_spell(Side(battlefield=[c1]), bolt)
        _cast_at_table(t, 0, bolt, c1)
        _copies(t, BurstLightning, 1)
        _resolve(t, off_stack(BurstLightning))
        _resolve(t, moves(bolt, Zone.GRAVEYARD), moves(c1, Zone.GRAVEYARD))
        t.run()

    def test_copy_dependent_retarget_offers_only_matching_equipment(self):
        """Retargeted to the second Ceratops, Fiery Annihilation's copy may
        exile only the Equipment attached to it: player 0 would rather exile
        the first Ceratops's Adventuring Gear, which is not a legal target —
        not offered, or offered and rejected."""
        c1, c2 = card(QuakestriderCeratops), card(QuakestriderCeratops)
        eq1, eq2 = card(AdventuringGear), card(AdventuringGear)
        prior, fiery = card(BurstLightning), card(FieryAnnihilation)
        mountains = [card(Mountain) for _ in range(4)]
        t = _table(
            Side(hand=[prior, fiery], battlefield=[ThousandYearStorm, *mountains], library=[card(Plains)]),
            Side(battlefield=[c1, c2, eq1, eq2], mana={ManaType.COLORLESS: 2}),
            start=(Phase.PRECOMBAT_MAIN, 1),
        )
        for gear, creature in ((eq1, c1), (eq2, c2)):
            t.act(1, gear, choices=[creature], then=[on_stack(AdventuringGearAbility2, 1)])
            t.pass_(1)
            t.pass_(0, then=[off_stack(AdventuringGearAbility2)])
        _next_turn_main(t, 0)
        t.act(0, mountains[0], then=[taps(mountains[0])])
        _bolt(t, prior, copies=0)
        for mountain in mountains[1:]:
            t.act(0, mountain, then=[taps(mountain)])
        _cast_at_table(t, 0, fiery, c1)
        _resolve(t, off_stack(STORM), copied(FieryAnnihilation, 0), choices=[NEW_TARGETS, c2, eq1, eq2],
                 fallback=[NEW_TARGETS, c2, eq2])
        _resolve(t, off_stack(FieryAnnihilation), moves(eq2, Zone.EXILE), note="each Ceratops survives 5")
        _resolve(t, moves(fiery, Zone.GRAVEYARD))
        t.run()

    def test_copy_new_target_leave_and_return_rejected(self):
        """The copy's new target, Spectral Sailor, leaves and returns before
        the copy resolves: the returned Sailor is a new object and is not hit,
        while the original still hits its own target."""
        c1, sailor, together = card(SavannahLions), card(SpectralSailor), card(RunAwayTogether)
        mine, bolt = card(SavannahLions), card(BurstLightning)
        t = _second_spell(
            Side(hand=[together], battlefield=[c1, sailor], mana={ManaType.BLUE: 3}),
            bolt,
            p0_battlefield=[mine],
        )
        _cast_at_table(t, 0, bolt, c1)
        _resolve(t, off_stack(STORM), copied(BurstLightning, 0), choices=[NEW_TARGETS, sailor])
        t.pass_(0)
        t.act(1, together, choices=[sailor, mine], then=[moves(together, Zone.STACK)])
        _resolve(t, moves(together, Zone.GRAVEYARD), moves(sailor, Zone.HAND), moves(mine, Zone.HAND), first=1)
        t.pass_(0)
        t.act(1, sailor, then=[moves(sailor, Zone.STACK)], note="Spectral Sailor has flash")
        _resolve(t, moves(sailor, Zone.BATTLEFIELD), first=1)
        _resolve(t, off_stack(BurstLightning), note="the returned Sailor is not hit")
        _resolve(t, moves(bolt, Zone.GRAVEYARD), moves(c1, Zone.GRAVEYARD))
        t.run()

    def test_copy_cannot_target_protected_permanent(self):
        """Player 0 would rather the copy hit Progenitus, but a permanent with
        protection from the copied spell is not a legal target — not offered,
        or offered and rejected — so the copy hits the Lions."""
        c1, c2, progenitus, bolt = card(SavannahLions), card(SavannahLions), card(Progenitus), card(BurstLightning)
        t = _second_spell(Side(battlefield=[c1, c2, progenitus]), bolt)
        _cast_at_table(t, 0, bolt, c1)
        _resolve(t, off_stack(STORM), copied(BurstLightning, 0), choices=[NEW_TARGETS, progenitus, c2],
                 fallback=[NEW_TARGETS, c2])
        _resolve(t, off_stack(BurstLightning), moves(c2, Zone.GRAVEYARD))
        _resolve(t, moves(bolt, Zone.GRAVEYARD), moves(c1, Zone.GRAVEYARD))
        t.run()


# ---------------------------------------------------------------------------
# The copy count is the caster's instant and sorcery casts this turn
# ---------------------------------------------------------------------------


def _storm_spell(t: Table, storm) -> None:
    t.act(0, storm, then=[moves(storm, Zone.STACK)])
    _resolve(t, moves(storm, Zone.BATTLEFIELD))


class TestStormAuthoritativeCount:
    def test_late_entering_storm_captures_full_prior_count(self):
        bolts = [card(BurstLightning) for _ in range(3)]
        storm = card(ThousandYearStorm)
        mountains = [card(Mountain) for _ in range(3)]
        t = _table(Side(hand=[*bolts, storm], battlefield=mountains,
                        mana={ManaType.BLUE: 1, ManaType.RED: 1, ManaType.COLORLESS: 4}))
        for bolt, mountain in zip(bolts[:2], mountains):
            t.act(0, mountain, then=[taps(mountain)])
            t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
            _resolve(t, moves(bolt, Zone.GRAVEYARD), _hit(t, 1))
        _storm_spell(t, storm)
        t.act(0, mountains[2], then=[taps(mountains[2])])
        _bolt(t, bolts[2], copies=2)
        t.run()

    def test_two_storms_one_late_capture_same_count_without_double_increment(self):
        bolts = [card(BurstLightning) for _ in range(3)]
        storm = card(ThousandYearStorm)
        mountains = [card(Mountain) for _ in range(3)]
        t = _table(Side(hand=[*bolts, storm], battlefield=[ThousandYearStorm, *mountains],
                        mana={ManaType.BLUE: 1, ManaType.RED: 1, ManaType.COLORLESS: 4}))
        for copies, (bolt, mountain) in enumerate(zip(bolts[:2], mountains)):
            t.act(0, mountain, then=[taps(mountain)])
            _bolt(t, bolt, copies=copies)
        _storm_spell(t, storm)
        t.act(0, mountains[2], then=[taps(mountains[2])])
        _bolt(t, bolts[2], copies=2, storms=2)
        t.run()

    def test_turn_rollover_clears_both_players_histories(self):
        """Each player casts on turn 1 with their own Storm; on turn 2 each
        player's next spell makes no copies."""
        p0_bolts, p1_bolts = [card(BurstLightning) for _ in range(2)], [card(BurstLightning) for _ in range(2)]
        p0_mountains, p1_mountains = [card(Mountain) for _ in range(2)], [card(Mountain) for _ in range(2)]
        t = _table(
            Side(hand=p0_bolts, battlefield=[ThousandYearStorm, *p0_mountains]),
            Side(hand=p1_bolts, battlefield=[ThousandYearStorm, *p1_mountains], library=[card(Plains)]),
        )

        def bolt(seat, spell, mountain, *, active):
            """``seat`` casts at the other player; the caster passes first,
            then after a resolution the active player does."""
            t.act(seat, mountain, then=[taps(mountain)])
            _cast_at_table(t, seat, spell, player(1 - seat))
            _resolve(t, off_stack(STORM), first=seat)
            _resolve(t, moves(spell, Zone.GRAVEYARD), _hit(t, 1 - seat), first=active)

        bolt(0, p0_bolts[0], p0_mountains[0], active=0)
        t.pass_(0)
        bolt(1, p1_bolts[0], p1_mountains[0], active=0)
        _next_turn_main(t, 1)
        bolt(1, p1_bolts[1], p1_mountains[1], active=1)
        t.pass_(1)
        bolt(0, p0_bolts[1], p0_mountains[1], active=1)
        t.run()

    def test_nonqualifying_spell_does_not_add_to_copy_count(self):
        lions, bolt = card(SavannahLions), card(BurstLightning)
        t = _table(Side(hand=[lions, bolt], battlefield=[ThousandYearStorm],
                        mana={ManaType.WHITE: 1, ManaType.RED: 1}))
        t.act(0, lions, then=[moves(lions, Zone.STACK)], note="a creature spell does not trigger Storm")
        _resolve(t, moves(lions, Zone.BATTLEFIELD))
        _bolt(t, bolt, copies=0)
        t.run()


# ---------------------------------------------------------------------------
# Casting the same card again counts each cast
# ---------------------------------------------------------------------------


class TestStormRepeatedObjectCasts:

    def test_recast_same_object_three_times_zero_one_two(self):
        """Think Twice cast three times: from hand, from hand again after
        Inspiration from Beyond's copy returns it, and with flashback. Each
        cast counts every instant and sorcery cast before it, so the copies
        go 0, 2 (Think Twice and Inspiration), 3."""
        think, inspiration = card(ThinkTwice), card(InspirationFromBeyond)
        library = [card(Plains) for _ in range(14)]
        t = _table(Side(hand=[think, inspiration], battlefield=[ThousandYearStorm], library=list(library),
                        mana={ManaType.BLUE: 10}))
        _think(t, think, library, copies=0)
        _cast_at_table(t, 0, inspiration)
        _copies(t, InspirationFromBeyond, 1)
        milled = [library.pop(0) for _ in range(3)]
        _resolve(t, off_stack(InspirationFromBeyond), *[moves(c, Zone.GRAVEYARD) for c in milled],
                 moves(think, Zone.HAND), choices=[think], note="the copy returns Think Twice")
        milled = [library.pop(0) for _ in range(3)]
        _resolve(t, moves(inspiration, Zone.GRAVEYARD), *[moves(c, Zone.GRAVEYARD) for c in milled])
        _think(t, think, library, copies=2)
        _think(t, think, library, copies=3, flashback=True)
        t.run()

    def test_recast_same_object_twice_first_zero_second_one(self):
        """Think Twice cast from hand makes no copies; cast again with
        flashback, the same card makes one."""
        think = card(ThinkTwice)
        library = [card(Plains) for _ in range(3)]
        t = _table(Side(hand=[think], battlefield=[ThousandYearStorm], library=list(library),
                        mana={ManaType.BLUE: 5}))
        _think(t, think, library, copies=0)
        _think(t, think, library, copies=1, flashback=True)
        t.run()

    def test_mixed_repeated_and_distinct_final_A_captures_two(self):
        """Think Twice, then Burst Lightning, then the same Think Twice with
        flashback: the last cast has two casts before it."""
        think, bolt = card(ThinkTwice), card(BurstLightning)
        islands, mountain = [card(Island) for _ in range(5)], card(Mountain)
        library = [card(Plains) for _ in range(4)]
        t = _table(Side(hand=[think, bolt], battlefield=[ThousandYearStorm, *islands, mountain],
                        library=list(library)))
        for island in islands[:2]:
            t.act(0, island, then=[taps(island)])
        _think(t, think, library, copies=0)
        t.act(0, mountain, then=[taps(mountain)])
        _bolt(t, bolt, copies=1)
        for island in islands[2:]:
            t.act(0, island, then=[taps(island)])
        _think(t, think, library, copies=2, flashback=True)
        t.run()

    def test_two_storms_repeated_object_same_count_single_occurrence(self):
        think = card(ThinkTwice)
        library = [card(Plains) for _ in range(4)]
        t = _table(Side(hand=[think], battlefield=[ThousandYearStorm, ThousandYearStorm], library=list(library),
                        mana={ManaType.BLUE: 5}))
        _think(t, think, library, copies=0, storms=2)
        _think(t, think, library, copies=1, storms=2, flashback=True)
        t.run()

    def test_turn_rollover_earlier_occurrence_of_same_object_does_not_count(self):
        """Think Twice cast on turn 1 does not count on turn 3: cast again with
        flashback, it makes no copies."""
        think = card(ThinkTwice)
        islands = [card(Island) for _ in range(3)]
        library = [card(Plains) for _ in range(3)]
        t = _table(
            Side(hand=[think], battlefield=[ThousandYearStorm, *islands], library=list(library)),
            Side(library=[card(Plains)]),
        )
        for island in islands[:2]:
            t.act(0, island, then=[taps(island)])
        _think(t, think, library, copies=0)
        _next_turn_main(t, 0)
        library.pop(0)
        for island in islands:
            t.act(0, island, then=[taps(island)])
        _think(t, think, library, copies=0, flashback=True)
        t.run()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


