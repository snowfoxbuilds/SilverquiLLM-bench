"""Casting and resolving spells, and playing lands (rules 601, 608, 305).

Most tests play a position through the Test Interface and judge each rule by
what the players see: where a card goes, whose life changes, what goes on the
stack, and whether an action is offered at all. Supporting cards are real FDN
cards:

- Burst Lightning ({R} instant, 2 damage to any target), Boltwave ({R}
  sorcery, 3 damage to each opponent), Savannah Lions ({W} 2/1), Helpful
  Hunter ({1}{W}), Spectral Sailor ({U} flash flier) and Firespitter Whelp
  show casting, timing and payment;
- Thousand-Year Storm copies an instant or sorcery once for each other one its
  controller cast before it this turn, so the copies it makes show the
  spell-cast history;
- Firebrand Archer deals 1 damage to each opponent whenever its controller
  casts a noncreature spell, so its trigger shows each cast;
- Etali, Primal Storm casts a spell from exile without paying its mana cost
  when it attacks, and Think Twice has flashback.

The remaining tests check engine helpers directly, or reach positions no FDN
card can make.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_7.card_impl import CrystalBarricade
from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.fdn.fdn_16.card_impl import HelpfulHunter, HelpfulHunterAbility1
from cards.fdn.fdn_26.card_impl import TwinbladeBlessing
from cards.fdn.fdn_48.card_impl import Refute
from cards.fdn.fdn_71.card_impl import Stab
from cards.fdn.fdn_79.card_impl import Boltwave
from cards.fdn.fdn_106.card_impl import LootExuberantExplorer
from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_130.card_impl import QuickDrawKatana
from cards.fdn.fdn_134.card_impl import AjaniCallerOfThePride
from cards.fdn.fdn_137.card_impl import AuthorityOfTheConsuls
from cards.fdn.fdn_144.card_impl import MischievousPup, MischievousPupAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_177.card_impl import MacabreWaltz
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_194.card_impl import EtaliPrimalStorm, EtaliPrimalStormAbility1
from cards.fdn.fdn_196.card_impl import FirebrandArcher, FirebrandArcherAbility1
from cards.fdn.fdn_197.card_impl import FirespitterWhelp, FirespitterWhelpAbility2
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_248.card_impl import ThousandYearStorm, ThousandYearStormAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Side, card, create_game, player, spell_copy
from test_utils import DeterministicPlayer

from engine.card import (
    Creature,
    Enchantment,
    Instant,
    Sorcery,
)
from engine.casting import (
    _PERMANENT_TYPES,
    can_cast_at_instant_speed,
)
from engine.decisions import Decision
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Zone
from table import Table, appears, copied, life, moves, off_stack, on_stack, taps, wins

R, W, U = ManaType.RED, ManaType.WHITE, ManaType.BLUE
NO_NEW_TARGETS = Decision.no()


def _table(p0: Side | None = None, p1: Side | None = None, *, start=(Phase.PRECOMBAT_MAIN, 0)) -> Table:
    """A table for a game built at ``start``, player 0's precombat main phase
    by default."""
    return Table(create_game(p0 or Side(), p1 or Side(), start=start))


def _cast(t: Table, seat: int, spell, *choices, then=(), note: str = "") -> None:
    """``seat`` casts ``spell``, answering its questions with ``choices``."""
    t.act(seat, spell, choices=choices, then=[moves(spell, Zone.STACK), *then], note=note)


def _resolve(t: Table, *, then=(), choices=(), chooser: int | None = None, note: str = "") -> None:
    """Both players pass in turn, starting with the player asked, and the top
    of the stack resolves with ``then``; ``choices`` answer the questions the
    resolution asks ``chooser`` (by default the player who passes first)."""
    first = t.asked
    chooser = first if chooser is None else chooser
    t.pass_(first, choices=choices if chooser == first else ())
    t.pass_(1 - first, choices=choices if chooser != first else (), then=then, note=note)


def _add_mana(player: DeterministicPlayer, mana_type: ManaType, amount: int) -> None:
    """Shortcut to add mana to a player's pool."""
    player.mana_pool.add(mana_type, amount)



# ---------------------------------------------------------------------------
# Timing — sorcery speed: active player, main phase, empty stack (307.1)
# ---------------------------------------------------------------------------

class TestIsSorcerySpeed:
    """A sorcery is cast only by the active player, in a main phase, with an
    empty stack; Boltwave shows it, with {R} in the pool so mana is never what
    stops it."""

    def test_precombat_main_active_player_empty_stack_is_true(self):
        wave = card(Boltwave)
        t = _table(Side(hand=[wave], mana={R: 1}))
        _cast(t, 0, wave)
        _resolve(t, then=[moves(wave, Zone.GRAVEYARD), life(1, 17)])
        t.run()

    def test_postcombat_main_active_player_empty_stack_is_true(self):
        wave, mountain = card(Boltwave), card(Mountain)
        t = _table(Side(hand=[wave], battlefield=[mountain]))
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.act(0, mountain, then=[taps(mountain)])
        _cast(t, 0, wave)
        _resolve(t, then=[moves(wave, Zone.GRAVEYARD), life(1, 17)])
        t.run()

    def test_non_active_player_returns_false(self):
        wave, bolt = card(Boltwave), card(BurstLightning)
        t = _table(Side(), Side(hand=[wave, bolt], mana={R: 1}))
        t.pass_(0)
        t.act_illegal(1, wave, note="player 1 is not the active player")
        _cast(t, 1, bolt, player(0), note="the {R} was there all along")
        t.run()

    def test_combat_phase_returns_false(self):
        wave = card(Boltwave)
        t = _table(Side(hand=[wave], mana={R: 1}), start=(Step.BEGIN_COMBAT, 0))
        t.act_illegal(0, wave, note="not a main phase")
        t.run()

    def test_beginning_phase_returns_false(self):
        wave = card(Boltwave)
        t = _table(Side(hand=[wave], mana={R: 1}), start=(Step.UPKEEP, 0))
        t.act_illegal(0, wave, note="not a main phase")
        t.run()

    def test_ending_phase_returns_false(self):
        wave = card(Boltwave)
        t = _table(Side(hand=[wave], mana={R: 1}), start=(Step.END, 0))
        t.act_illegal(0, wave, note="not a main phase")
        t.run()

    def test_nonempty_stack_returns_false(self):
        wave, bolt = card(Boltwave), card(BurstLightning)
        t = _table(Side(hand=[wave, bolt], mana={R: 2}))
        _cast(t, 0, bolt, player(1))
        t.act_illegal(0, wave, note="Burst Lightning is on the stack")
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        _cast(t, 0, wave, note="the stack is empty again")
        _resolve(t, then=[moves(wave, Zone.GRAVEYARD), life(1, 15)])
        t.run()


# ---------------------------------------------------------------------------
# Timing helper tests — can_cast_at_instant_speed
# ---------------------------------------------------------------------------

class TestCanCastAtInstantSpeed:
    """Verify instant-speed detection: instant type or FLASH keyword."""

    def test_instant_returns_true(self):
        assert can_cast_at_instant_speed(Instant(name="Bolt")) is True

    def test_sorcery_returns_false(self):
        assert can_cast_at_instant_speed(Sorcery(name="Div")) is False

    def test_creature_without_flash_returns_false(self):
        assert can_cast_at_instant_speed(
            Creature(name="Bear", base_power=2, base_toughness=2)
        ) is False

    def test_creature_with_flash_returns_true(self):
        card = Creature(name="Viper", base_power=2, base_toughness=1, keywords=Keyword.FLASH)
        assert can_cast_at_instant_speed(card) is True

    def test_enchantment_with_flash_returns_true(self):
        card = Enchantment(name="Leyline", keywords=Keyword.FLASH)
        assert can_cast_at_instant_speed(card) is True



# ---------------------------------------------------------------------------
# Casting — hand → stack → resolution → destination zone (601.2a, 608.3)
# ---------------------------------------------------------------------------

class TestCastSpellCreature:
    """A creature spell goes from hand to the stack, then onto the
    battlefield under its caster's control."""

    def test_cast_puts_creature_on_stack(self):
        lions = card(SavannahLions)
        t = _table(Side(hand=[lions], mana={W: 1}))
        _cast(t, 0, lions, note="the Lions is player 0's spell on the stack")
        t.run()

    def test_cast_removes_creature_from_hand(self):
        lions, plains = card(SavannahLions), card(Plains)
        t = _table(Side(hand=[lions, plains], mana={W: 1}))
        _cast(t, 0, lions, note="only the Lions leaves the hand")
        final = t.run()
        assert final.where(lions) is Zone.STACK and final.where(plains) is Zone.HAND

    def test_resolve_creature_to_battlefield(self):
        lions = card(SavannahLions)
        t = _table(Side(hand=[lions], mana={W: 1}))
        _cast(t, 0, lions)
        _resolve(t, then=[moves(lions, Zone.BATTLEFIELD)])
        final = t.run()
        assert final.where(lions) is Zone.BATTLEFIELD


class TestCastSpellInstant:
    """An instant goes to its owner's graveyard as it resolves."""

    def test_resolve_instant_to_graveyard(self):
        bolt = card(BurstLightning)
        t = _table(Side(hand=[bolt], mana={R: 1}))
        _cast(t, 0, bolt, player(1))
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.run()


class TestCastSpellSorcery:
    """A sorcery goes to its owner's graveyard as it resolves."""

    def test_resolve_sorcery_to_graveyard(self):
        wave = card(Boltwave)
        t = _table(Side(hand=[wave], mana={R: 1}))
        _cast(t, 0, wave)
        _resolve(t, then=[moves(wave, Zone.GRAVEYARD), life(1, 17)])
        t.run()


# ---------------------------------------------------------------------------
# Casting — timing (307.1, 302.1)
# ---------------------------------------------------------------------------

class TestCastSpellTimingRejections:
    """A sorcery or a creature without flash is cast only at sorcery speed."""

    def test_sorcery_during_combat_phase_raises(self):
        wave, mountain = card(Boltwave), card(Mountain)
        t = _table(Side(hand=[wave], battlefield=[mountain]), start=(Step.BEGIN_COMBAT, 0))
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.pass_(0)  # declares no attackers
        t.act(0, mountain, then=[taps(mountain)])
        t.act_illegal(0, wave, note="the declare attackers step is no main phase")
        t.run()

    def test_creature_during_combat_phase_raises(self):
        lions = card(SavannahLions)
        t = _table(Side(hand=[lions], mana={W: 1}), start=(Step.BEGIN_COMBAT, 0))
        t.act_illegal(0, lions, note="the Lions has no flash")
        t.run()

    def test_sorcery_with_nonempty_stack_raises(self):
        wave, bolt = card(Boltwave), card(BurstLightning)
        t = _table(Side(hand=[wave, bolt], mana={R: 2}))
        _cast(t, 0, bolt, player(1))
        t.act_illegal(0, wave, note="Burst Lightning is on the stack")
        t.run()

    def test_non_active_player_sorcery_raises(self):
        wave = card(Boltwave)
        t = _table(Side(), Side(hand=[wave], mana={R: 1}))
        t.pass_(0)
        t.act_illegal(1, wave, note="player 1 is not the active player")
        t.run()

    def test_non_active_player_creature_no_flash_raises(self):
        lions = card(SavannahLions)
        t = _table(Side(), Side(hand=[lions], mana={W: 1}))
        t.pass_(0)
        t.act_illegal(1, lions, note="player 1 is not the active player")
        t.run()


class TestCastSpellInstantSpeed:
    """An instant, or a spell with flash, is cast whenever its caster has
    priority (702.8a)."""

    def test_flash_creature_during_combat_succeeds(self):
        sailor = card(SpectralSailor)
        t = _table(Side(hand=[sailor], mana={U: 1}), start=(Step.BEGIN_COMBAT, 0))
        _cast(t, 0, sailor)
        _resolve(t, then=[moves(sailor, Zone.BATTLEFIELD)])
        t.run()

    def test_instant_during_upkeep_succeeds(self):
        bolt = card(BurstLightning)
        t = _table(Side(hand=[bolt], mana={R: 1}), start=(Step.UPKEEP, 0))
        _cast(t, 0, bolt, player(1))
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.run()

    def test_non_active_player_can_cast_instant(self):
        bolt = card(BurstLightning)
        t = _table(Side(), Side(hand=[bolt], mana={R: 1}))
        t.pass_(0)
        _cast(t, 1, bolt, player(0))
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(0, 18)])
        t.run()

    def test_flash_enchantment_during_combat_succeeds(self):
        blessing, lions = card(TwinbladeBlessing), card(SavannahLions)
        t = _table(Side(hand=[blessing], battlefield=[lions], mana={W: 3}), start=(Step.END_COMBAT, 0))
        _cast(t, 0, blessing, lions)
        _resolve(t, then=[moves(blessing, Zone.BATTLEFIELD)])
        t.run()


# ---------------------------------------------------------------------------
# Casting — paying the mana cost (601.2g-h)
# ---------------------------------------------------------------------------

class TestCastSpellManaPayment:
    """A spell is cast only when its mana cost can be paid, and paying it
    spends exactly that mana."""

    def test_insufficient_mana_raises(self):
        hunter, lions = card(HelpfulHunter), card(SavannahLions)
        t = _table(Side(hand=[hunter, lions], mana={W: 1}))
        t.act_illegal(0, hunter, note="{1}{W} with only {W}")
        _cast(t, 0, lions, note="the {W} pays for the Lions")
        t.run()

    def test_no_mana_at_all_raises(self):
        bolt = card(BurstLightning)
        t = _table(Side(hand=[bolt]))
        t.act_illegal(0, bolt, choices=[player(1)], note="nothing pays {R}")
        t.run()

    def test_wrong_color_mana_raises(self):
        bolt, turtle = card(BurstLightning), card(AegisTurtle)
        t = _table(Side(hand=[bolt, turtle], mana={U: 5}))
        t.act_illegal(0, bolt, choices=[player(1)], note="{U} cannot pay {R}")
        _cast(t, 0, turtle, note="the {U} pays for the Turtle")
        t.run()

    def test_mana_deducted_after_cast(self):
        first, second, flight, lions = card(HelpfulHunter), card(HelpfulHunter), card(FleetingFlight), card(SavannahLions)
        t = _table(Side(hand=[first, second, flight], battlefield=[lions], mana={W: 3}))
        _cast(t, 0, first)
        t.act_illegal(0, second, note="{1}{W} of the {W}{W}{W} is spent")
        _cast(t, 0, flight, lions, note="one {W} is left")
        t.run()

    def test_exact_mana_leaves_zero(self):
        first, second = card(BurstLightning), card(BurstLightning)
        t = _table(Side(hand=[first, second], mana={R: 1}))
        _cast(t, 0, first, player(1))
        t.act_illegal(0, second, choices=[player(1)], note="the pool is empty")
        t.run()


    def test_mana_not_deducted_on_failure(self):
        wave, bolt = card(Boltwave), card(BurstLightning)
        t = _table(Side(hand=[wave, bolt], mana={R: 1}), start=(Step.BEGIN_COMBAT, 0))
        t.act_illegal(0, wave)
        _cast(t, 0, bolt, player(1), note="the failed Boltwave spent nothing")
        t.run()


# ---------------------------------------------------------------------------
# Casting — card hooks
# ---------------------------------------------------------------------------

class TestCastSpellHooks:
    """A card's ``on_cast`` runs as it is cast, and a spell's effect happens
    only as it resolves."""


    def test_on_resolve_callback_is_called(self):
        bolt = card(BurstLightning)
        t = _table(Side(hand=[bolt], mana={R: 1}))
        _cast(t, 0, bolt, player(1), note="no damage yet")
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)], note="the damage is dealt as it resolves")
        t.run()


    def test_on_resolve_receives_game_state(self):
        wave = card(Boltwave)
        t = _table(Side(hand=[wave], mana={R: 1}), Side(life=3))
        _cast(t, 0, wave)
        t.pass_(0)
        t.pass_(1, then=[moves(wave, Zone.GRAVEYARD), life(1, 0), wins(0)], note="the resolving spell changes the game")
        t.run()


# ---------------------------------------------------------------------------
# Casting — what can be cast at all
# ---------------------------------------------------------------------------

class TestCastSpellLegality:
    """Only a card in its caster's hand is cast, a land is never cast, and a
    cast that cannot be made leaves the hand and the stack as they were."""

    def test_card_not_in_hand_raises(self):
        lions = card(SavannahLions)
        t = _table(Side(graveyard=[lions], mana={W: 1}))
        t.act_illegal(0, lions, note="the Lions is in the graveyard")
        t.run()

    def test_can_cast_returns_false_raises(self):
        played, kept = card(Plains), card(Plains)
        t = _table(Side(hand=[played, kept], mana={W: 3}))
        t.act(0, played, then=[moves(played, Zone.BATTLEFIELD)])
        t.act_illegal(0, kept, note="no land play is left, and a land is never cast")
        t.run()

    def test_hand_unchanged_on_timing_failure(self):
        lions = card(SavannahLions)
        t = _table(Side(hand=[lions], mana={W: 1}), start=(Step.BEGIN_COMBAT, 0))
        t.act_illegal(0, lions)
        final = t.run()
        assert final.where(lions) is Zone.HAND

    def test_stack_unchanged_on_failure(self):
        ceratops = card(QuakestriderCeratops)
        t = _table(Side(hand=[ceratops], mana={ManaType.GREEN: 1}))
        t.act_illegal(0, ceratops, note="{3}{G}{G}{G} with only {G}")
        final = t.run()
        assert final.stack == ()


# ---------------------------------------------------------------------------
# Playing a land — a special action (305.1-305.3, 116.2a)
# ---------------------------------------------------------------------------

class TestPlayLand:
    """A player plays one land in a main phase of their turn, with an empty
    stack, straight from their hand onto the battlefield."""

    def test_valid_land_play_moves_to_battlefield(self):
        forest = card(Forest)
        t = _table(Side(hand=[forest]))
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD)])
        t.run()

    def test_valid_land_play_removes_from_hand(self):
        forest, lions = card(Forest), card(SavannahLions)
        t = _table(Side(hand=[forest, lions]))
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD)])
        final = t.run()
        assert final.where(forest) is Zone.BATTLEFIELD and final.where(lions) is Zone.HAND

    def test_valid_land_play_decrements_remaining(self):
        first, second, third = card(Forest), card(Forest), card(Forest)
        t = _table(Side(hand=[first, second, third], battlefield=[LootExuberantExplorer]))
        t.act(0, first, then=[moves(first, Zone.BATTLEFIELD)])
        t.act(0, second, then=[moves(second, Zone.BATTLEFIELD)], note="Loot gives a second land play")
        t.act_illegal(0, third, note="both land plays are used")
        t.run()

    def test_land_play_postcombat_main_succeeds(self):
        island = card(Island)
        t = _table(Side(hand=[island]))
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.act(0, island, then=[moves(island, Zone.BATTLEFIELD)])
        t.run()

    def test_second_land_play_when_remaining_zero_raises(self):
        first, second = card(Forest), card(Forest)
        t = _table(Side(hand=[first, second]))
        t.act(0, first, then=[moves(first, Zone.BATTLEFIELD)])
        t.act_illegal(0, second)
        t.run()

    def test_remaining_already_zero_raises(self):
        first, second = card(Forest), card(Forest)
        t = _table(Side(hand=[first, second]))
        t.act(0, first, then=[moves(first, Zone.BATTLEFIELD)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.act_illegal(0, second, note="the turn's land play was used before combat")
        t.run()

    def test_land_during_combat_phase_raises(self):
        forest = card(Forest)
        t = _table(Side(hand=[forest]), start=(Step.BEGIN_COMBAT, 0))
        t.act_illegal(0, forest)
        t.run()

    def test_land_during_beginning_phase_raises(self):
        forest = card(Forest)
        t = _table(Side(hand=[forest]), start=(Step.UPKEEP, 0))
        t.act_illegal(0, forest)
        t.run()

    def test_land_by_non_active_player_raises(self):
        forest = card(Forest)
        t = _table(Side(), Side(hand=[forest]))
        t.pass_(0)
        t.act_illegal(1, forest)
        t.run()

    def test_land_with_nonempty_stack_raises(self):
        forest, bolt = card(Forest), card(BurstLightning)
        t = _table(Side(hand=[forest, bolt], mana={R: 1}))
        _cast(t, 0, bolt, player(1))
        t.act_illegal(0, forest, note="Burst Lightning is on the stack")
        t.run()

    def test_non_land_card_raises(self):
        lions = card(SavannahLions)
        t = _table(Side(hand=[lions]))
        t.act_illegal(0, lions, note="a creature card is cast, never played as a land")
        t.run()

    def test_land_not_in_hand_raises(self):
        forest = card(Forest)
        t = _table(Side(graveyard=[forest]))
        t.act_illegal(0, forest)
        t.run()

    def test_extra_land_with_increased_limit(self):
        first, second = card(Forest), card(Forest)
        t = _table(Side(hand=[first, second], battlefield=[LootExuberantExplorer]))
        t.act(0, first, then=[moves(first, Zone.BATTLEFIELD)])
        t.act(0, second, then=[moves(second, Zone.BATTLEFIELD)])
        t.run()

    def test_land_does_not_use_stack(self):
        forest, elves = card(Forest), card(LlanowarElves)
        t = _table(Side(hand=[forest, elves]))
        t.act(0, forest, then=[moves(forest, Zone.BATTLEFIELD)], note="no stack, and player 0 keeps priority")
        t.act(0, forest, then=[taps(forest)])
        _cast(t, 0, elves)
        t.run()


# ---------------------------------------------------------------------------
# Permanent type detection
# ---------------------------------------------------------------------------

class TestPermanentTypes:
    """Verify _PERMANENT_TYPES covers exactly creature, enchantment, artifact, planeswalker."""

    def test_creature_is_permanent(self):
        assert CardType.CREATURE in _PERMANENT_TYPES

    def test_enchantment_is_permanent(self):
        assert CardType.ENCHANTMENT in _PERMANENT_TYPES

    def test_artifact_is_permanent(self):
        assert CardType.ARTIFACT in _PERMANENT_TYPES

    def test_planeswalker_is_permanent(self):
        assert CardType.PLANESWALKER in _PERMANENT_TYPES

    def test_instant_is_not_permanent(self):
        assert CardType.INSTANT not in _PERMANENT_TYPES

    def test_sorcery_is_not_permanent(self):
        assert CardType.SORCERY not in _PERMANENT_TYPES

    def test_land_is_not_in_permanent_types(self):
        assert CardType.LAND not in _PERMANENT_TYPES



# ---------------------------------------------------------------------------
# Resolution — every permanent spell enters the battlefield (608.3)
# ---------------------------------------------------------------------------

class TestResolveOtherPermanents:
    """Enchantments, artifacts, planeswalkers and artifact creatures resolve
    onto the battlefield."""

    def test_enchantment_resolves_to_battlefield(self):
        authority = card(AuthorityOfTheConsuls)
        t = _table(Side(hand=[authority], mana={W: 1}))
        _cast(t, 0, authority)
        _resolve(t, then=[moves(authority, Zone.BATTLEFIELD)])
        t.run()

    def test_artifact_resolves_to_battlefield(self):
        katana = card(QuickDrawKatana)
        t = _table(Side(hand=[katana], mana={ManaType.COLORLESS: 2}))
        _cast(t, 0, katana)
        _resolve(t, then=[moves(katana, Zone.BATTLEFIELD)])
        t.run()

    def test_planeswalker_resolves_to_battlefield(self):
        ajani = card(AjaniCallerOfThePride)
        t = _table(Side(hand=[ajani], mana={W: 3}))
        _cast(t, 0, ajani)
        _resolve(t, then=[moves(ajani, Zone.BATTLEFIELD)])
        t.run()

    def test_artifact_creature_resolves_to_battlefield(self):
        barricade = card(CrystalBarricade)
        t = _table(Side(hand=[barricade], mana={W: 2}))
        _cast(t, 0, barricade)
        _resolve(t, then=[moves(barricade, Zone.BATTLEFIELD)])
        t.run()


# ---------------------------------------------------------------------------
# The stack — last in, first out, and targets chosen as a spell is cast
# ---------------------------------------------------------------------------

class TestCastResolveIntegration:
    """Spells resolve last in, first out (405.5), and a spell affects the
    targets chosen as it was cast (601.2c)."""

    def test_multiple_spells_resolve_lifo(self):
        bolt, growth, lions = card(BurstLightning), card(GiantGrowth), card(SavannahLions)
        t = _table(Side(hand=[bolt, growth], mana={R: 1, ManaType.GREEN: 1}), Side(battlefield=[lions]))
        _cast(t, 0, bolt, lions)
        _cast(t, 0, growth, lions)
        _resolve(t, then=[moves(growth, Zone.GRAVEYARD)], note="Giant Growth, cast last, resolves first")
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD)], note="the 5/4 Lions survives 2 damage")
        final = t.run()
        assert final.where(lions) is Zone.BATTLEFIELD

    def test_cast_creature_full_lifecycle(self):
        lions = card(SavannahLions)
        t = _table(Side(hand=[lions], mana={W: 1}))
        _cast(t, 0, lions, note="hand → stack")
        _resolve(t, then=[moves(lions, Zone.BATTLEFIELD)], note="stack → battlefield")
        final = t.run()
        assert final.stack == () and final.where(lions) is Zone.BATTLEFIELD

    def test_cast_with_targets_passes_to_stack_object(self):
        bolt, lions, elves = card(BurstLightning), card(SavannahLions), card(LlanowarElves)
        t = _table(Side(hand=[bolt], mana={R: 1}), Side(battlefield=[elves, lions]))
        _cast(t, 0, bolt, lions)
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)], note="the target, not the Elves")
        t.run()


# ---------------------------------------------------------------------------
# Optional targets — "up to N target X" (115.1, 601.2c)
# ---------------------------------------------------------------------------

class TestOptionalTargets:
    """Macabre Waltz returns up to two target creature cards from its
    caster's graveyard to their hand, then they discard a card: it is cast
    with fewer targets, or none, while a spell that requires a target cannot
    be cast without one."""

    @staticmethod
    def _waltz(graveyard, *, discard):
        """Player 0 holds Macabre Waltz and ``discard``, with
        ``graveyard`` in their graveyard and {B}{B} in their pool."""
        waltz = card(MacabreWaltz)
        t = _table(Side(hand=[waltz, discard], graveyard=graveyard, mana={ManaType.BLACK: 2}))
        return t, waltz

    def test_optional_empty_candidate_set_casts_without_target(self):
        plains = card(Plains)
        t, waltz = self._waltz([], discard=plains)
        _cast(t, 0, waltz)
        _resolve(t, then=[moves(waltz, Zone.GRAVEYARD), moves(plains, Zone.GRAVEYARD)])
        t.run()

    def test_required_empty_candidate_set_still_raises(self):
        stab = card(Stab)
        t = _table(Side(hand=[stab], mana={ManaType.BLACK: 1}))
        t.act_illegal(0, stab, note="no creature to target")
        t.run()

    def test_optional_declined_when_candidate_present(self):
        plains, lions = card(Plains), card(SavannahLions)
        t, waltz = self._waltz([lions], discard=plains)
        _cast(t, 0, waltz, note="it targets nothing")
        _resolve(t, then=[moves(waltz, Zone.GRAVEYARD), moves(plains, Zone.GRAVEYARD)])
        final = t.run()
        assert final.where(lions) is Zone.GRAVEYARD

    def test_optional_chosen_when_preferred(self):
        plains, lions = card(Plains), card(SavannahLions)
        t, waltz = self._waltz([lions], discard=plains)
        _cast(t, 0, waltz, lions)
        _resolve(
            t, choices=[plains], then=[moves(waltz, Zone.GRAVEYARD), moves(lions, Zone.HAND), moves(plains, Zone.GRAVEYARD)]
        )
        t.run()

    def test_up_to_two_picks_distinct_targets(self):
        plains, lions, elves = card(Plains), card(SavannahLions), card(LlanowarElves)
        t, waltz = self._waltz([lions, elves], discard=plains)
        _cast(t, 0, waltz, lions, elves)
        _resolve(
            t,
            choices=[plains],
            then=[moves(waltz, Zone.GRAVEYARD), moves(lions, Zone.HAND), moves(elves, Zone.HAND), moves(plains, Zone.GRAVEYARD)],
        )
        t.run()

    def test_up_to_two_with_one_candidate_casts_with_one(self):
        plains, lions = card(Plains), card(SavannahLions)
        t, waltz = self._waltz([lions], discard=plains)
        _cast(t, 0, waltz, lions)
        _resolve(
            t, choices=[plains], then=[moves(waltz, Zone.GRAVEYARD), moves(lions, Zone.HAND), moves(plains, Zone.GRAVEYARD)]
        )
        t.run()


class TestDependentTargetFilterArity:
    """`_safe_filter` supports both (obj) and dependent (obj, chosen) filter
    signatures, so a target's legality can depend on targets already chosen this
    cast (rule 601.2c dependent requirements) without a card-specific backdoor."""

    def test_filter_wants_chosen_detects_arity(self):
        from engine.casting import _filter_wants_chosen
        assert _filter_wants_chosen(lambda obj: True) is False
        assert _filter_wants_chosen(lambda obj, chosen: True) is True
        # The loop-binding idiom `lambda obj, _c=controller` has a DEFAULTED
        # second parameter — it is NOT a dependent filter and must be called with
        # the object alone (regression: binding `chosen` to `_c` broke ~8 cards).
        _controller = object()
        assert _filter_wants_chosen(lambda obj, _c=_controller: True) is False
        assert _filter_wants_chosen(lambda obj, g=None, ctrl=None: True) is False
        # `*rest` is not a required second positional — treated as single-arg.
        assert _filter_wants_chosen(lambda obj, *rest: True) is False

        class _C:
            def one(self, obj):
                return True

            def two(self, obj, chosen):
                return True

            def bound_default(self, obj, _c=None):
                return True

        # Bound methods: `self` is excluded from the counted parameters.
        assert _filter_wants_chosen(_C().one) is False
        assert _filter_wants_chosen(_C().two) is True
        assert _filter_wants_chosen(_C().bound_default) is False

    def test_single_arg_filter_called_with_object_only(self):
        from engine.casting import _safe_filter
        seen = {}

        def _f(obj):
            seen["obj"] = obj
            return obj == "x"

        assert _safe_filter(_f, "x", ["ignored"]) is True
        assert _safe_filter(_f, "y", []) is False
        assert seen["obj"] == "y"

    def test_dependent_filter_receives_chosen(self):
        from engine.casting import _safe_filter
        captured = {}

        def _f(obj, chosen):
            captured["chosen"] = list(chosen)
            return obj in chosen

        assert _safe_filter(_f, "a", ["a", "b"]) is True
        assert _safe_filter(_f, "z", ["a", "b"]) is False
        assert captured["chosen"] == ["a", "b"]

    def test_raising_filter_is_excluded_not_propagated(self):
        from engine.casting import _safe_filter

        def _boom(obj, chosen):
            raise RuntimeError("nope")

        assert _safe_filter(_boom, "a", []) is False



# ---------------------------------------------------------------------------
# Etali, Primal Storm — casting a spell without paying its mana cost
# ---------------------------------------------------------------------------

def _etali_attacks(spell, *, p0=(), p1=(), p0_hand=(), p1_hand=()):
    """Turn 1: player 0's Etali, Primal Storm attacks with ``spell`` on top of
    player 0's library and a Plains on top of player 1's; ``p0`` and ``p1``
    are more of each player's battlefield, ``p0_hand`` and ``p1_hand`` their
    hands. Returns the table, at the attack trigger's resolution, and player
    1's Plains."""
    etali, top = card(EtaliPrimalStorm), card(Plains)
    t = _table(
        Side(hand=list(p0_hand), battlefield=[etali, *p0], library=[spell, card(Plains)]),
        Side(hand=list(p1_hand), battlefield=list(p1), library=[top, card(Plains)]),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, etali, then=[taps(etali), on_stack(EtaliPrimalStormAbility1, 0)])
    return t, top


def _etali_resolves(t, spell, top, *choices, then=(), note: str = ""):
    """Etali's trigger resolves: it exiles both top cards and player 0 casts
    ``spell`` without paying its mana cost, answering ``choices``."""
    _resolve(
        t,
        choices=[Decision.yes(), *choices, spell],
        then=[
            off_stack(EtaliPrimalStormAbility1),
            moves(spell, Zone.EXILE),
            moves(top, Zone.EXILE),
            moves(spell, Zone.STACK),
            *then,
        ],
        note=note,
    )


class TestSpellTargetStintRevalidation:
    """A spell's target is the object chosen as it was cast: if that object
    leaves its zone and comes back before the spell resolves, it is a new
    object and no longer the target (400.7, 608.2b)."""

    def test_free_cast_marks_target_normally(self):
        bolt, sailor = card(BurstLightning), card(SpectralSailor)
        t, top = _etali_attacks(bolt, p1=[sailor])
        _etali_resolves(t, bolt, top, sailor)
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), moves(sailor, Zone.GRAVEYARD)])
        t.run()

    def test_free_cast_leave_and_return_rejected(self):
        bolt, sailor, pup, island = card(BurstLightning), card(SpectralSailor), card(MischievousPup), card(Island)
        plains = [card(Plains) for _ in range(3)]
        t, top = _etali_attacks(bolt, p1=[sailor, *plains, island], p1_hand=[pup])
        _etali_resolves(t, bolt, top, sailor)
        t.pass_(0)
        for land in plains:
            t.act(1, land, then=[taps(land)])
        _cast(t, 1, pup)
        _resolve(t, choices=[sailor], then=[moves(pup, Zone.BATTLEFIELD), on_stack(MischievousPupAbility2, 1)])
        _resolve(t, then=[off_stack(MischievousPupAbility2), moves(sailor, Zone.HAND)])
        t.pass_(0)
        t.act(1, island, then=[taps(island)])
        _cast(t, 1, sailor, note="the Sailor comes back as a new object")
        _resolve(t, then=[moves(sailor, Zone.BATTLEFIELD)])
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD)], note="Burst Lightning's target is gone, so it does nothing")
        final = t.run()
        assert final.where(sailor) is Zone.BATTLEFIELD

    def test_normal_cast_context_stored_on_stack_object(self):
        bolt, first, second = card(BurstLightning), card(SpectralSailor), card(SpectralSailor)
        t = _table(Side(hand=[bolt], mana={R: 1}), Side(battlefield=[first, second]))
        _cast(t, 0, bolt, second)
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), moves(second, Zone.GRAVEYARD)], note="the chosen Sailor, not its twin")
        final = t.run()
        assert final.where(first) is Zone.BATTLEFIELD


# ---------------------------------------------------------------------------
# Spell-cast history — authoritative per-player, per-turn record
# ---------------------------------------------------------------------------


class TestSpellCastHistoryRecord:
    """The turn-stamped record on :class:`~engine.player.Player` itself.

    This is the authoritative surface a cast-triggered ability (Thousand-Year
    Storm) reads its copy count from. It belongs to the player/turn lifecycle:
    per-player, resettable at the turn boundary, and never owned by a trigger
    source.
    """

    def test_record_and_read_round_trips_in_cast_order(self):
        p = DeterministicPlayer("Alice")
        s1, s2 = object(), object()
        p.record_instant_or_sorcery_cast(s1, 3)
        p.record_instant_or_sorcery_cast(s2, 3)
        assert p.instant_or_sorcery_casts_this_turn(3) == [s1, s2]

    def test_read_returns_a_copy_not_the_backing_list(self):
        p = DeterministicPlayer("Alice")
        s1 = object()
        p.record_instant_or_sorcery_cast(s1, 1)
        out = p.instant_or_sorcery_casts_this_turn(1)
        out.append(object())
        assert p.instant_or_sorcery_casts_this_turn(1) == [s1]

    def test_stale_turn_reads_empty(self):
        p = DeterministicPlayer("Alice")
        p.record_instant_or_sorcery_cast(object(), 1)
        assert p.instant_or_sorcery_casts_this_turn(2) == []

    def test_recording_on_a_new_turn_resets_before_appending(self):
        p = DeterministicPlayer("Alice")
        s1, s2 = object(), object()
        p.record_instant_or_sorcery_cast(s1, 1)
        p.record_instant_or_sorcery_cast(s2, 2)  # new turn — resets, then appends
        assert p.instant_or_sorcery_casts_this_turn(1) == []
        assert p.instant_or_sorcery_casts_this_turn(2) == [s2]

    def test_players_keep_separate_records(self):
        p1 = DeterministicPlayer("Alice")
        p2 = DeterministicPlayer("Bob")
        a, b = object(), object()
        p1.record_instant_or_sorcery_cast(a, 1)
        p2.record_instant_or_sorcery_cast(b, 1)
        assert p1.instant_or_sorcery_casts_this_turn(1) == [a]
        assert p2.instant_or_sorcery_casts_this_turn(1) == [b]

    def test_record_returns_prior_qualifying_cast_count(self):
        # Each recording reports how many qualifying casts came before it this
        # turn — the immutable prior-cast count for that occurrence.
        p = DeterministicPlayer("Alice")
        s1, s2, s3 = object(), object(), object()
        assert p.record_instant_or_sorcery_cast(s1, 1) == 0
        assert p.record_instant_or_sorcery_cast(s2, 1) == 1
        assert p.record_instant_or_sorcery_cast(s3, 1) == 2

    def test_record_counts_a_recast_object_as_a_new_occurrence(self):
        # The SAME object recorded twice this turn is two occurrences: the second
        # recording reports one prior cast, not zero. Excluding "the current cast"
        # by identity would instead treat both entries as the current cast.
        p = DeterministicPlayer("Alice")
        obj = object()
        assert p.record_instant_or_sorcery_cast(obj, 1) == 0
        assert p.record_instant_or_sorcery_cast(obj, 1) == 1
        assert p.instant_or_sorcery_casts_this_turn(1) == [obj, obj]

    def test_record_prior_count_restarts_at_the_turn_boundary(self):
        p = DeterministicPlayer("Alice")
        p.record_instant_or_sorcery_cast(object(), 1)
        assert p.record_instant_or_sorcery_cast(object(), 1) == 1
        # A new turn resets the record, so the count restarts from zero.
        assert p.record_instant_or_sorcery_cast(object(), 2) == 0



class TestSpellCastHistoryPipeline:
    """Each instant or sorcery a player casts is recorded once, for that
    player and that turn. Thousand-Year Storm reads the record: it copies an
    instant or sorcery once for each other one its controller cast before it
    this turn, so the copies it makes show what was recorded. Every Burst
    Lightning targets player 1."""

    @staticmethod
    def _bolt(t, bolt, *, copies=0, seat=0, note=""):
        """``seat`` casts ``bolt`` at the other player; Storm's trigger
        resolves into ``copies`` copies, each resolving for 2 damage, and then
        ``bolt`` itself."""
        foe = 1 - seat

        def hit():
            return life(foe, t.expected.players[foe].life - 2)

        _cast(t, seat, bolt, player(foe), then=[on_stack(ThousandYearStormAbility1, seat)], note=note)
        _resolve(
            t,
            choices=[NO_NEW_TARGETS] * copies,
            chooser=seat,
            then=[off_stack(ThousandYearStormAbility1), *[copied(BurstLightning, seat)] * copies],
        )
        for _ in range(copies):
            _resolve(t, then=[off_stack(BurstLightning), hit()])
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), hit()])

    def test_cast_instant_is_recorded(self):
        first, second = card(BurstLightning), card(BurstLightning)
        t = _table(Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={R: 2}))
        self._bolt(t, first)
        self._bolt(t, second, copies=1)
        t.run()

    def test_cast_sorcery_is_recorded(self):
        wave, bolt = card(Boltwave), card(BurstLightning)
        t = _table(Side(hand=[wave, bolt], battlefield=[ThousandYearStorm], mana={R: 2}))
        _cast(t, 0, wave, then=[on_stack(ThousandYearStormAbility1, 0)])
        _resolve(t, then=[off_stack(ThousandYearStormAbility1)])
        _resolve(t, then=[moves(wave, Zone.GRAVEYARD), life(1, 17)])
        self._bolt(t, bolt, copies=1)
        t.run()

    def test_instant_is_recorded_exactly_once(self):
        bolts = [card(BurstLightning) for _ in range(3)]
        t = _table(Side(hand=bolts, battlefield=[ThousandYearStorm], mana={R: 3}))
        for copies, bolt in enumerate(bolts):
            self._bolt(t, bolt, copies=copies)
        final = t.run()
        assert final.players[1].life == 8

    def test_nonqualifying_spells_do_not_record(self):
        lions, katana, authority, ajani = card(SavannahLions), card(QuickDrawKatana), card(AuthorityOfTheConsuls), card(AjaniCallerOfThePride)
        bolt, mountain = card(BurstLightning), card(Mountain)
        t = _table(
            Side(hand=[lions, katana, authority, ajani, bolt], battlefield=[ThousandYearStorm, mountain], mana={W: 7})
        )
        for permanent in (lions, katana, authority, ajani):
            _cast(t, 0, permanent, note="no Storm trigger")
            _resolve(t, then=[moves(permanent, Zone.BATTLEFIELD)])
        t.act(0, mountain, then=[taps(mountain)])
        self._bolt(t, bolt, copies=0)
        t.run()

    def test_playing_a_land_does_not_record(self):
        mountain, bolt = card(Mountain), card(BurstLightning)
        t = _table(Side(hand=[mountain, bolt], battlefield=[ThousandYearStorm]))
        t.act(0, mountain, then=[moves(mountain, Zone.BATTLEFIELD)])
        t.act(0, mountain, then=[taps(mountain)])
        self._bolt(t, bolt, copies=0)
        t.run()

    def test_two_players_get_separate_histories_through_the_pipeline(self):
        first, second, theirs = card(BurstLightning), card(BurstLightning), card(BurstLightning)
        t = _table(
            Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={R: 2}),
            Side(hand=[theirs], battlefield=[ThousandYearStorm], mana={R: 1}),
        )
        self._bolt(t, first)
        t.pass_(0)
        self._bolt(t, theirs, seat=1, note="player 0's cast is not player 1's")
        self._bolt(t, second, copies=1, note="player 1's cast is not player 0's")
        final = t.run()
        assert (final.players[0].life, final.players[1].life) == (18, 14)

    def test_free_cast_is_recorded(self):
        free, bolt, mountain = card(BurstLightning), card(BurstLightning), card(Mountain)
        t, top = _etali_attacks(free, p0=[ThousandYearStorm, mountain], p0_hand=[bolt])
        _etali_resolves(t, free, top, player(1), then=[on_stack(ThousandYearStormAbility1, 0)])
        _resolve(t, then=[off_stack(ThousandYearStormAbility1)])
        _resolve(t, then=[moves(free, Zone.GRAVEYARD), life(1, 18)])
        t.act(0, mountain, then=[taps(mountain)])
        self._bolt(t, bolt, copies=1)
        t.run()

    def test_turn_rollover_resets_through_the_pipeline(self):
        first, second, mountain = card(BurstLightning), card(BurstLightning), card(Mountain)
        t = _table(
            Side(hand=[first, second], battlefield=[ThousandYearStorm, mountain], library=[card(Plains)]),
            Side(library=[card(Plains)]),
        )
        t.act(0, mountain, then=[taps(mountain)])
        self._bolt(t, first)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act(0, mountain, then=[taps(mountain)])
        self._bolt(t, second, copies=0, note="last turn's cast no longer counts")
        t.run()

    def test_cast_stamps_prior_qualifying_count_on_the_stack_object(self):
        first, second, third = card(BurstLightning), card(BurstLightning), card(BurstLightning)
        t = _table(Side(hand=[first, second, third], battlefield=[ThousandYearStorm], mana={R: 3}))
        for bolt in (first, second, third):
            _cast(t, 0, bolt, player(1), then=[on_stack(ThousandYearStormAbility1, 0)])

        def resolve_storm(copies, bolt):
            def hit():
                return life(1, t.expected.players[1].life - 2)

            _resolve(
                t,
                choices=[NO_NEW_TARGETS] * copies,
                then=[off_stack(ThousandYearStormAbility1), *[copied(BurstLightning, 0)] * copies],
            )
            for _ in range(copies):
                _resolve(t, then=[off_stack(BurstLightning), hit()])
            _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), hit()])

        resolve_storm(2, third)
        resolve_storm(1, second)  # still one copy, though three were cast by now
        resolve_storm(0, first)
        final = t.run()
        assert final.players[1].life == 8

    def test_free_cast_stamps_prior_qualifying_count_on_the_stack_object(self):
        bolt, free = card(BurstLightning), card(BurstLightning)
        etali, top = card(EtaliPrimalStorm), card(Plains)
        t = _table(
            Side(hand=[bolt], battlefield=[etali, ThousandYearStorm], library=[free, card(Plains)], mana={R: 1}),
            Side(library=[top, card(Plains)]),
            start=(Step.BEGIN_COMBAT, 0),
        )
        self._bolt(t, bolt)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, etali, then=[taps(etali), on_stack(EtaliPrimalStormAbility1, 0)])
        _etali_resolves(t, free, top, player(1), then=[on_stack(ThousandYearStormAbility1, 0)])
        _resolve(t, choices=[NO_NEW_TARGETS], then=[off_stack(ThousandYearStormAbility1), copied(BurstLightning, 0)])
        _resolve(t, then=[off_stack(BurstLightning), life(1, 16)])
        _resolve(t, then=[moves(free, Zone.GRAVEYARD), life(1, 14)])
        t.run()

    def test_nonqualifying_cast_stamps_no_prior_count(self):
        bolt, lions = card(BurstLightning), card(SavannahLions)
        t = _table(Side(hand=[bolt, lions], battlefield=[ThousandYearStorm], mana={R: 1, W: 1}))
        self._bolt(t, bolt)
        _cast(t, 0, lions, note="a creature spell makes no Storm trigger")
        final = t.run()
        assert len(final.stack) == 1


# ---------------------------------------------------------------------------
# Flashback — cast from the graveyard, then exiled (702.34a)
# ---------------------------------------------------------------------------

class TestFlashbackDisposition:
    """Think Twice ({1}{U} instant: draw a card; flashback {2}{U}) is cast
    from its owner's graveyard by flashback and exiled as it leaves the stack;
    cast any other way it goes to the graveyard as usual."""

    def _flashback_instant(self, player):
        card = Instant(name="Recall", mana_cost=ManaCost.parse("{1}{U}"), owner=player)
        card.controller = player
        card.flashback_cost = ManaCost.parse("{2}{U}")
        return card

    def test_flashback_mode_from_graveyard_exiles(self):
        twice, drawn = card(ThinkTwice), card(Plains)
        islands = [card(Island) for _ in range(3)]
        t = _table(Side(graveyard=[twice], battlefield=islands, library=[drawn]))
        for island in islands:
            t.act(0, island, then=[taps(island)])
        _cast(t, 0, twice)
        _resolve(t, then=[moves(twice, Zone.EXILE), moves(drawn, Zone.HAND)])
        t.run()



    def test_flashback_card_from_exile_keeps_graveyard(self):
        twice = card(ThinkTwice)
        t, top = _etali_attacks(twice)
        _etali_resolves(t, twice, top, note="cast from exile, not by flashback")
        drawn = t.expected.players[0].library[0].handle
        _resolve(t, then=[moves(twice, Zone.GRAVEYARD), moves(drawn, Zone.HAND)])
        t.run()

    # -- rejected mode claims are ATOMIC: every check runs before any mutation,
    #    so controller, owner, zones, stack, cast history, and target state are
    #    byte-for-byte what they were. Each negative test snapshots that state
    #    before the claim and asserts it unchanged after the CastingError.

    @staticmethod
    def _observable_state(game, card):
        """Snapshot everything a rejected flashback claim must leave untouched."""
        from engine.types import Zone

        return {
            "controller": card.controller,
            "owner": card.owner,
            "zones": [
                (i, zone.name, tuple(id(o) for o in player.zones[zone].get_all()))
                for i, player in enumerate(game.players)
                for zone in Zone
                if zone in player.zones
            ],
            "stack": tuple(id(so) for so in game.stack._items),
            "cast_history": [
                (
                    tuple(id(s) for s in player._instant_sorcery_casts),
                    player._instant_sorcery_cast_turn,
                )
                for player in game.players
            ],
            "chosen_targets": getattr(card, "chosen_targets", None),
            "is_tapped": getattr(card, "is_tapped", None),
        }

    def _assert_rejected_claim_untouched(self, game, player, card, from_zone):
        """The FLASHBACK claim raises CastingError and mutates nothing."""
        from engine.casting import CastingError, CastMode, cast_spell_free

        before = self._observable_state(game, card)
        with pytest.raises(CastingError):
            cast_spell_free(game, player, card, from_zone, mode=CastMode.FLASHBACK)
        assert self._observable_state(game, card) == before

    def test_flashback_mode_from_exile_rejected(self):
        twice = card(ThinkTwice)
        t = _table(Side(exile=[twice], mana={U: 3}))
        t.act_illegal(0, twice, note="flashback casts only from a graveyard")
        t.run()

    def test_flashback_mode_from_hand_rejected(self):
        twice, drawn = card(ThinkTwice), card(Plains)
        t = _table(Side(hand=[twice], library=[drawn], mana={U: 2}))
        _cast(t, 0, twice)
        _resolve(t, then=[moves(twice, Zone.GRAVEYARD), moves(drawn, Zone.HAND)], note="a cast from hand is no flashback")
        t.run()

    def test_flashback_mode_without_flashback_cost_rejected(self):
        bolt = card(BurstLightning)
        t = _table(Side(graveyard=[bolt], mana={R: 5}))
        t.act_illegal(0, bolt, note="Burst Lightning has no flashback")
        t.run()

    def test_flashback_mode_from_another_players_graveyard_rejected(self):
        twice = card(ThinkTwice)
        t = _table(Side(mana={U: 3}), Side(graveyard=[twice]))
        t.act_illegal(0, twice, note="flashback casts only from its owner's graveyard")
        t.run()


    def test_flashback_mode_own_card_in_own_graveyard_accepted(self):
        twice, drawn = card(ThinkTwice), card(Plains)
        t = _table(Side(), Side(graveyard=[twice], library=[drawn], mana={U: 3}))
        t.pass_(0)
        _cast(t, 1, twice, note="an instant flashed back on the other player's turn")
        _resolve(t, then=[moves(twice, Zone.EXILE), moves(drawn, Zone.HAND)])
        t.run()


# ---------------------------------------------------------------------------
# Targeting a spell — the spell on the stack, not its card (115.1, 608.2b)
# ---------------------------------------------------------------------------

class TestStackOccurrenceTargeting:
    """A spell on the stack is targeted as that spell: an ability is not a
    spell, and a targeted spell that leaves the stack stays gone even when its
    card is cast again."""

    def test_real_pipeline_targets_exact_occurrence(self):
        bolt, offer = card(BurstLightning), card(AnOfferYouCantRefuse)
        t = _table(Side(hand=[offer], mana={U: 1}), Side(hand=[bolt], mana={R: 1}))
        t.pass_(0)
        _cast(t, 1, bolt, player(0))
        t.pass_(1)
        _cast(t, 0, offer, bolt)
        _resolve(
            t,
            then=[moves(offer, Zone.GRAVEYARD), moves(bolt, Zone.GRAVEYARD), appears(1), appears(1)],
            note="countered: player 1 gets two Treasures",
        )
        final = t.run()
        assert final.players[0].life == 20

    def test_ability_sharing_source_card_is_not_targetable(self):
        hunter, refute = card(HelpfulHunter), card(Refute)
        drawn = card(Plains)
        t = _table(Side(hand=[hunter], library=[drawn], mana={W: 2}), Side(hand=[refute], mana={U: 3}))
        _cast(t, 0, hunter)
        _resolve(t, then=[moves(hunter, Zone.BATTLEFIELD), on_stack(HelpfulHunterAbility1, 0)])
        t.pass_(0)
        t.act_illegal(1, refute, note="the Hunter's trigger is no spell")
        t.run()

    def test_copy_occurrence_targeted_distinctly_from_original(self):
        """A spell copy is a spell of its own: player 1 counters Thousand-Year
        Storm's copy of the second Burst Lightning with An Offer You Can't
        Refuse, and the original stays on the stack and resolves."""
        first, second, offer = card(BurstLightning), card(BurstLightning), card(AnOfferYouCantRefuse)
        t = _table(
            Side(hand=[first, second], battlefield=[ThousandYearStorm], mana={R: 2}),
            Side(hand=[offer], mana={U: 1}),
        )
        TestSpellCastHistoryPipeline._bolt(t, first)
        _cast(t, 0, second, player(1), then=[on_stack(ThousandYearStormAbility1, 0)])
        _resolve(t, choices=[NO_NEW_TARGETS], chooser=0,
                 then=[off_stack(ThousandYearStormAbility1), copied(BurstLightning, 0)])
        t.pass_(0)
        _cast(t, 1, offer, spell_copy(1), note="the copy, not the original")
        t.pass_(1)
        t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), off_stack(BurstLightning), appears(0), appears(0)])
        _resolve(t, then=[moves(second, Zone.GRAVEYARD), life(1, 16)], note="the original resolves")
        t.run()

    def test_departed_occurrence_fizzles_even_after_recast(self):
        twice, refute, offer = card(ThinkTwice), card(Refute), card(AnOfferYouCantRefuse)
        drawn, kept = card(Plains), card(Plains)
        t = _table(
            Side(hand=[refute, offer, kept], mana={U: 4}),
            Side(hand=[twice], library=[drawn], mana={U: 5}),
        )
        t.pass_(0)
        _cast(t, 1, twice)
        t.pass_(1)
        _cast(t, 0, refute, twice)
        _cast(t, 0, offer, twice)
        _resolve(t, then=[moves(offer, Zone.GRAVEYARD), moves(twice, Zone.GRAVEYARD), appears(1), appears(1)])
        t.pass_(0)
        _cast(t, 1, twice, note="flashed back: a new spell")
        _resolve(t, then=[moves(twice, Zone.EXILE), moves(drawn, Zone.HAND)])
        _resolve(t, then=[moves(refute, Zone.GRAVEYARD)], note="Refute's target is gone: it neither draws nor discards")
        t.run()


# ---------------------------------------------------------------------------
# Cast triggers — "whenever you cast" (601.2i, 603.2)
# ---------------------------------------------------------------------------

class TestSpellCastEventFiring:
    """Casting a spell triggers "whenever you cast" abilities once, after the
    spell is on the stack. Firebrand Archer deals 1 damage to each opponent
    whenever its controller casts a noncreature spell."""

    def test_cast_instant_fires_once_with_card_and_caster(self):
        bolt = card(BurstLightning)
        t = _table(Side(hand=[bolt], battlefield=[FirebrandArcher], mana={R: 1}))
        _cast(t, 0, bolt, player(1), then=[on_stack(FirebrandArcherAbility1, 0)])
        _resolve(t, then=[off_stack(FirebrandArcherAbility1), life(1, 19)])
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 17)])
        t.run()

    def test_event_fires_after_spell_is_on_the_stack(self):
        bolt = card(BurstLightning)
        t = _table(Side(hand=[bolt], battlefield=[FirebrandArcher], mana={R: 1}))
        _cast(t, 0, bolt, player(1), then=[on_stack(FirebrandArcherAbility1, 0)])
        final = t.run()
        assert [seen.card for seen in final.stack] == [FirebrandArcherAbility1, BurstLightning]

    def test_cast_creature_also_fires_event(self):
        whelp = card(FirespitterWhelp)
        t = _table(Side(hand=[whelp], battlefield=[FirespitterWhelp], mana={R: 3}))
        _cast(t, 0, whelp, then=[on_stack(FirespitterWhelpAbility2, 0)], note="a Dragon creature spell")
        _resolve(t, then=[off_stack(FirespitterWhelpAbility2), life(1, 19)])
        _resolve(t, then=[moves(whelp, Zone.BATTLEFIELD)])
        t.run()

    def test_cast_spell_free_fires_once(self):
        bolt = card(BurstLightning)
        t, top = _etali_attacks(bolt, p0=[FirebrandArcher])
        _etali_resolves(t, bolt, top, player(1), then=[on_stack(FirebrandArcherAbility1, 0)])
        _resolve(t, then=[off_stack(FirebrandArcherAbility1), life(1, 19)])
        _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 17)])
        t.run()

    def test_two_casts_fire_two_events_never_double(self):
        first, second = card(BurstLightning), card(BurstLightning)
        t = _table(Side(hand=[first, second], battlefield=[FirebrandArcher], mana={R: 2}))
        _cast(t, 0, first, player(1), then=[on_stack(FirebrandArcherAbility1, 0)])
        _cast(t, 0, second, player(1), then=[on_stack(FirebrandArcherAbility1, 0)])
        _resolve(t, then=[off_stack(FirebrandArcherAbility1), life(1, 19)])
        _resolve(t, then=[moves(second, Zone.GRAVEYARD), life(1, 17)])
        _resolve(t, then=[off_stack(FirebrandArcherAbility1), life(1, 16)])
        _resolve(t, then=[moves(first, Zone.GRAVEYARD), life(1, 14)])
        t.run()
