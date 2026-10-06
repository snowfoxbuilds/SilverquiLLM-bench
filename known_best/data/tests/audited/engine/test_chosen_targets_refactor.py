"""Targets chosen as a spell is cast belong to that spell on the stack until it
resolves (rules 601.2c, 608.2b).

Seen at the table:
- casting a targeted spell does nothing to its target yet;
- the spell resolves against the targets chosen when it was cast, however
  many it has, and a targetless spell asks for none;
- each spell on the stack keeps its own targets, and resolving one leaves
  the others' alone;
- a card cast again chooses its targets anew, never reusing an earlier
  casting's.
"""

from __future__ import annotations

from cards.fdn.fdn_43.card_impl import InspirationFromBeyond
from cards.fdn.fdn_79.card_impl import Boltwave
from cards.fdn.fdn_90.card_impl import IncineratingBlast
from cards.fdn.fdn_105.card_impl import FellingBlow
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_162.card_impl import RunAwayTogether
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_212.card_impl import BiteDown
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import ManaType, Phase, Side, Zone, card, create_game, player

from silverquillm.table import Table, life, moves, taps


def _main_phase(p0: Side, p1: Side) -> Table:
    """Player 0's precombat main phase, with player 0 to act."""
    return Table(create_game(p0, p1, start=(Phase.PRECOMBAT_MAIN, 0)))


def _resolve(t: Table, *results, note: str = "") -> None:
    """Both players pass, and the top of the stack resolves."""
    t.pass_(0)
    t.pass_(1, then=list(results), note=note)


# ---------------------------------------------------------------------------
# Casting a spell does nothing to its targets yet
# ---------------------------------------------------------------------------


class TestChosenTargetsNotSetAtCastTime:
    def test_targeted_instant_no_chosen_targets_after_cast(self):
        bolt, lions = card(BurstLightning), card(SavannahLions)
        t = _main_phase(Side(hand=[bolt], mana={ManaType.RED: 1}), Side(battlefield=[lions]))
        t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)], note="the Lions is untouched while Burst Lightning waits")
        _resolve(t, moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD))
        t.run()

    def test_targeted_sorcery_no_chosen_targets_after_cast(self):
        blast, scourge = card(IncineratingBlast), card(BrazenScourge)
        t = _main_phase(Side(hand=[blast], mana={ManaType.RED: 5}), Side(battlefield=[scourge]))
        t.act(0, blast, choices=[scourge], then=[moves(blast, Zone.STACK)], note="the Scourge is untouched while the sorcery waits")
        _resolve(t, moves(blast, Zone.GRAVEYARD), moves(scourge, Zone.GRAVEYARD))
        t.run()

    def test_no_targets_spell_no_chosen_targets_after_cast(self):
        think, plains = card(ThinkTwice), card(Plains)
        t = _main_phase(Side(hand=[think], library=[plains], mana={ManaType.BLUE: 2}), Side(battlefield=[SavannahLions]))
        t.act(0, think, then=[moves(think, Zone.STACK)], note="Think Twice asks for no target")
        _resolve(t, moves(think, Zone.GRAVEYARD), moves(plains, Zone.HAND))
        t.run()


# ---------------------------------------------------------------------------
# A spell on the stack holds the targets chosen as it was cast
# ---------------------------------------------------------------------------


class TestStackObjectTargets:
    def test_stack_object_stores_chosen_targets(self):
        bolt, lions, elves = card(BurstLightning), card(SavannahLions), card(LlanowarElves)
        t = _main_phase(Side(hand=[bolt], mana={ManaType.RED: 1}), Side(battlefield=[lions, elves]))
        t.act(0, bolt, choices=[elves], then=[moves(bolt, Zone.STACK)])
        _resolve(t, moves(bolt, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD))
        final = t.run()
        assert final.where(lions) is Zone.BATTLEFIELD

    def test_stack_object_targets_for_multi_target_spell(self):
        together = card(RunAwayTogether)
        mine, my_other = card(SavannahLions), card(LlanowarElves)
        theirs, their_other = card(BrazenScourge), card(SavannahLions)
        t = _main_phase(
            Side(hand=[together], battlefield=[mine, my_other], mana={ManaType.BLUE: 2}),
            Side(battlefield=[theirs, their_other]),
        )
        t.act(0, together, choices=[mine, theirs], distinct=True, then=[moves(together, Zone.STACK)])
        _resolve(t, moves(together, Zone.GRAVEYARD), moves(mine, Zone.HAND), moves(theirs, Zone.HAND))
        t.run()

    def test_no_targets_spell_has_empty_targets_on_stack(self):
        wave = card(Boltwave)
        t = _main_phase(Side(hand=[wave], mana={ManaType.RED: 1}), Side(battlefield=[SavannahLions]))
        t.act(0, wave, then=[moves(wave, Zone.STACK)], note="Boltwave asks for no target")
        _resolve(t, moves(wave, Zone.GRAVEYARD), life(1, 17))
        t.run()


# ---------------------------------------------------------------------------
# The spell resolves against its chosen targets
# ---------------------------------------------------------------------------


class TestChosenTargetsSetAtResolveTime:
    def test_chosen_targets_set_on_card_during_resolution(self):
        blast, spared, chosen = card(IncineratingBlast), card(BrazenScourge), card(BrazenScourge)
        t = _main_phase(Side(hand=[blast], mana={ManaType.RED: 5}), Side(battlefield=[spared, chosen]))
        t.act(0, blast, choices=[chosen], then=[moves(blast, Zone.STACK)])
        _resolve(t, moves(blast, Zone.GRAVEYARD), moves(chosen, Zone.GRAVEYARD), note="only the chosen Scourge is dealt 6")
        t.run()

    def test_chosen_targets_available_inside_on_resolve_callback(self):
        """Bite Down reads its first target's power as it resolves: a Giant
        Growth that resolves first lets the 2/1 Lions deal 5 to the 3/3."""
        bite, growth, lions, scourge = card(BiteDown), card(GiantGrowth), card(SavannahLions), card(BrazenScourge)
        t = _main_phase(
            Side(hand=[bite, growth], battlefield=[lions], mana={ManaType.GREEN: 3}),
            Side(battlefield=[scourge]),
        )
        t.act(0, bite, choices=[lions, scourge], then=[moves(bite, Zone.STACK)])
        t.act(0, growth, choices=[lions], then=[moves(growth, Zone.STACK)])
        _resolve(t, moves(growth, Zone.GRAVEYARD))
        _resolve(t, moves(bite, Zone.GRAVEYARD), moves(scourge, Zone.GRAVEYARD))
        t.run()

    def test_multi_target_available_in_on_resolve(self):
        """Felling Blow uses both its targets as it resolves: the Lions gets a
        +1/+1 counter, then deals 3 damage to the 3/3 Scourge."""
        blow, lions, scourge, bystander = card(FellingBlow), card(SavannahLions), card(BrazenScourge), card(BrazenScourge)
        t = _main_phase(
            Side(hand=[blow], battlefield=[lions], mana={ManaType.GREEN: 3}),
            Side(battlefield=[bystander, scourge]),
        )
        t.act(0, blow, choices=[lions, scourge], then=[moves(blow, Zone.STACK)])
        _resolve(t, moves(blow, Zone.GRAVEYARD), moves(scourge, Zone.GRAVEYARD))
        t.run()


# ---------------------------------------------------------------------------
# Each spell on the stack keeps its own targets
# ---------------------------------------------------------------------------


class TestMultipleSpellsIndependentTargets:
    def test_two_spells_different_targets_on_stack(self):
        first, second, lions = card(BurstLightning), card(BurstLightning), card(SavannahLions)
        t = _main_phase(Side(hand=[first, second], mana={ManaType.RED: 2}), Side(battlefield=[lions]))
        t.act(0, first, choices=[lions], then=[moves(first, Zone.STACK)])
        t.act(0, second, choices=[player(1)], then=[moves(second, Zone.STACK)])
        _resolve(t, moves(second, Zone.GRAVEYARD), life(1, 18))
        _resolve(t, moves(first, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD))
        t.run()

    def test_resolving_first_does_not_affect_second_targets(self):
        first, second = card(BurstLightning), card(BurstLightning)
        lions, elves = card(SavannahLions), card(LlanowarElves)
        t = _main_phase(Side(hand=[first, second], mana={ManaType.RED: 2}), Side(battlefield=[lions, elves]))
        t.act(0, first, choices=[lions], then=[moves(first, Zone.STACK)])
        t.act(0, second, choices=[elves], then=[moves(second, Zone.STACK)])
        _resolve(t, moves(second, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD), note="the Lions survives the first to resolve")
        _resolve(t, moves(first, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD))
        t.run()


# ---------------------------------------------------------------------------
# A card cast again chooses its targets anew
# ---------------------------------------------------------------------------


class TestNoStaleTargetLeakage:
    def test_copy_before_resolve_has_no_chosen_targets(self):
        """Burst Lightning kills the Lions, comes back to hand through
        Inspiration from Beyond, and is cast again at player 1."""
        bolt, inspiration, lions, mountain = card(BurstLightning), card(InspirationFromBeyond), card(SavannahLions), card(Mountain)
        milled = [card(Plains), card(Plains), card(Plains)]
        t = _main_phase(
            Side(hand=[bolt, inspiration], battlefield=[mountain], library=milled, mana={ManaType.RED: 1, ManaType.BLUE: 3}),
            Side(battlefield=[lions]),
        )
        t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
        _resolve(t, moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD))
        t.act(0, inspiration, then=[moves(inspiration, Zone.STACK)])
        t.pass_(0, choices=[bolt])
        t.pass_(1, then=[*(moves(c, Zone.GRAVEYARD) for c in milled), moves(bolt, Zone.HAND), moves(inspiration, Zone.GRAVEYARD)])
        t.act(0, mountain, then=[taps(mountain)])
        t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)], note="the second casting targets player 1")
        _resolve(t, moves(bolt, Zone.GRAVEYARD), life(1, 18))
        t.run()

    def test_resolve_original_does_not_affect_clone(self):
        first, second = card(BurstLightning), card(BurstLightning)
        lions, elves = card(SavannahLions), card(LlanowarElves)
        t = _main_phase(Side(hand=[first, second], mana={ManaType.RED: 2}), Side(battlefield=[lions, elves]))
        t.act(0, first, choices=[lions], then=[moves(first, Zone.STACK)])
        _resolve(t, moves(first, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD))
        t.act(0, second, choices=[elves], then=[moves(second, Zone.STACK)], note="a second Burst Lightning chooses its own target")
        _resolve(t, moves(second, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD))
        t.run()
