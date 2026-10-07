"""Tests for engine/combat.py — Combat system.

Verifies:
- CombatState construction and default values, and CombatState.clear().
- The attack and block eligibility helpers, lethal damage, end_combat_step.
- Declaring attackers: a valid attacker taps, vigilance does not, a creature
  that came under its controller's control this turn cannot attack unless it
  has haste, defenders and tapped creatures cannot attack.
- Declaring blockers: flying evasion (only blocked by flying/reach), menace
  requires two or more blockers, the attacker's controller divides its damage
  among several blockers (rule 510.1c).
- Combat damage: unblocked damage to the player, damage between attacker and
  blocker, first strike, double strike, trample (with deathtouch, 1 damage is
  lethal), lifelink, a blocked creature whose blocker is gone deals no damage.
- Combat damage and attack triggers fire once per creature, after the whole
  declaration (rule 508.2).

Combat is played on the Test Interface: each player's script answers the
declarations and the damage-division questions (ADR-017), and every result is
judged by what happens on the board.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_1.card_impl import SireOfSevenDeaths
from cards.fdn.fdn_3.card_impl import ArmasaurGuide, ArmasaurGuideAbility2
from cards.fdn.fdn_12.card_impl import FelidarSavior
from cards.fdn.fdn_21.card_impl import PridefulParent
from cards.fdn.fdn_49.card_impl import RuneSealedWall
from cards.fdn.fdn_59.card_impl import CryptFeaster
from cards.fdn.fdn_60.card_impl import GutlessPlunderer
from cards.fdn.fdn_68.card_impl import SanguineSyphoner, SanguineSyphonerAbility1
from cards.fdn.fdn_100.card_impl import BeastKinRanger
from cards.fdn.fdn_102.card_impl import EagerTrufflesnout, EagerTrufflesnoutAbility2
from cards.fdn.fdn_103.card_impl import ElfswornGiant
from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_115.card_impl import AleshaWhoLaughsAtFate, AleshaWhoLaughsAtFateAbility2
from cards.fdn.fdn_117.card_impl import AshrootAnimist, AshrootAnimistAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_171.card_impl import DiregrafGhoul
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_195.card_impl import FanaticalFirebrand
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_246.card_impl import SwiftbladeVindicator
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Decision, Phase, Side, Step, card, create_game
from test_utils import DeterministicPlayer

from engine.card import Creature, GameObject
from engine.combat import (
    CombatState,
    _can_attack,
    _can_block,
    _deal_damage,
    _get_lethal_damage,
)
from engine.events import DealsDamageTriggeredEvent
from engine.game_state import GameState
from engine.player import Player
from engine.triggers import TriggerRegistration
from engine.types import Keyword, Zone
from table import (
    Table,
    appears,
    first_strike_damage,
    life,
    moves,
    off_stack,
    on_stack,
    taps,
)

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_game_object_id() -> None:
    """Reset the GameObject auto-increment counter before each test."""
    GameObject.reset_id_counter()


def _make_creature(
    name: str = "Bear",
    power: int = 2,
    toughness: int = 2,
    keywords: Keyword | None = None,
    summoning_sick: bool = False,
    is_tapped: bool = False,
    owner: Player | None = None,
    controller: Player | None = None,
) -> Creature:
    """Create a creature for combat testing with sane defaults."""
    c = Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        keywords=keywords,
        owner=owner,
        controller=controller,
    )
    c.summoning_sick = summoning_sick
    c.is_tapped = is_tapped
    return c


def _make_game(
    p1_life: int = 20,
    p2_life: int = 20,
) -> GameState:
    """Create a 2-player GameState with given life totals."""
    return GameState([DeterministicPlayer("Alice", life=p1_life), DeterministicPlayer("Bob", life=p2_life)])


def _place_on_battlefield(
    player: Player,
    creature: Creature,
    game: GameState | None = None,
) -> None:
    """Put a creature on a player's battlefield and set its controller; with
    *game*, also give it its battlefield ``instance_id``."""
    creature.controller = player
    creature.owner = player
    player.zones[Zone.BATTLEFIELD].add(creature)
    if game is not None:
        creature.instance_id = game.refs.instance_id(creature, Zone.BATTLEFIELD.value)


def _attacks(p0: Side, p1: Side | None = None) -> Table:
    """Player 0's turn, from its beginning of combat to the declaration of
    attackers."""
    t = Table(create_game(p0, p1 or Side(), start=(Step.BEGIN_COMBAT, 0)))
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    return t


def _main(p0: Side, p1: Side | None = None) -> Table:
    """Player 0's first main phase."""
    return Table(create_game(p0, p1 or Side(), start=(Phase.PRECOMBAT_MAIN, 0)))


def _cast(t: Table, land, spell, *, choices=(), then=()) -> None:
    """Player 0 taps ``land`` and casts ``spell``, and both players pass."""
    t.act(0, land, then=[taps(land)])
    t.act(0, spell, choices=list(choices), then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=list(then))


def _attack(t: Table, *attackers, tapping=None, then=()) -> None:
    """Player 0 declares ``attackers``, which tap — all of them unless
    ``tapping`` names the ones that do — and both players pass."""
    tapped = attackers if tapping is None else tapping
    t.act(0, *attackers, then=[*(taps(a) for a in tapped), *then])


def _to_blockers(t: Table) -> None:
    """Both players pass in the declare attackers step."""
    t.pass_(0)
    t.pass_(1)


def _no_blocks(t: Table, *, then=(), first_strike=None) -> None:
    """Player 1 declares no blockers and both players pass to combat damage,
    whose results are ``then``; with ``first_strike``, a first-strike combat
    damage step with those results comes first (rule 510.4)."""
    t.pass_(1, then=[first_strike_damage()] if first_strike is not None else [])
    t.pass_(0)
    if first_strike is not None:
        t.pass_(1, then=list(first_strike))
        t.pass_(0)
    t.pass_(1, then=list(then))


def _blocks(t: Table, blocks: dict, *, shares=None, then=(), first_strike=None) -> None:
    """Player 1 blocks as ``blocks`` says (blocker to attacker), and both
    players pass to combat damage, whose results are ``then``; ``shares``
    divides an attacker's damage, blocker to amount; with ``first_strike``,
    a first-strike combat damage step with those results comes first (rule
    510.4)."""
    t.act(1, *blocks, scoped=blocks, then=[first_strike_damage()] if first_strike is not None else [])
    per_query = {b: [Decision.number(n)] for b, n in (shares or {}).items()}
    t.pass_(0, per_query=per_query or None)
    if first_strike is not None:
        t.pass_(1, then=list(first_strike))
        t.pass_(0)
    t.pass_(1, then=list(then))


def _no_attack(t: Table) -> None:
    """Player 0 declares no attackers, so the declare blockers and combat
    damage steps are skipped (rule 508.8); play stops at end of combat."""
    t.pass_(0)
    t.pass_(0)
    t.pass_(1)


# ---------------------------------------------------------------------------
# CombatState — construction and clear
# ---------------------------------------------------------------------------

class TestCombatState:
    """Verify CombatState dataclass defaults and clear() method."""

    def test_default_construction(self) -> None:
        """A newly created CombatState should have empty dicts and in_combat=False."""
        cs = CombatState()
        assert cs.attackers == {}
        assert cs.blockers == {}
        assert cs.attacker_blockers == {}
        assert cs.damage_assignments == {}
        assert cs.was_blocked == set()
        assert cs.in_combat is False

    def test_clear_resets_all_fields(self) -> None:
        """CombatState.clear() should empty all mappings and set in_combat to False."""
        cs = CombatState()
        cs.in_combat = True
        cs.attackers["a"] = "p"
        cs.blockers["b"] = ["a"]
        cs.attacker_blockers["a"] = ["b"]
        cs.damage_assignments["a"] = [("b", 2)]
        cs.was_blocked.add("a")
        cs.clear()
        assert cs.attackers == {}
        assert cs.blockers == {}
        assert cs.attacker_blockers == {}
        assert cs.damage_assignments == {}
        assert cs.was_blocked == set()
        assert cs.in_combat is False

    def test_game_state_has_combat_state(self) -> None:
        """GameState should have a CombatState instance."""
        game = _make_game()
        assert isinstance(game.combat_state, CombatState)
        assert game.combat_state.in_combat is False


# ---------------------------------------------------------------------------
# Helper: _can_attack
# ---------------------------------------------------------------------------

class TestCanAttack:
    """Verify the _can_attack helper function."""

    def test_normal_creature_can_attack(self) -> None:
        """An untapped creature without summoning sickness can attack."""
        c = _make_creature(summoning_sick=False)
        assert _can_attack(c) is True

    def test_tapped_creature_cannot_attack(self) -> None:
        """A tapped creature cannot attack."""
        c = _make_creature(is_tapped=True)
        assert _can_attack(c) is False

    def test_summoning_sick_creature_cannot_attack(self) -> None:
        """A creature with summoning sickness cannot attack."""
        c = _make_creature(summoning_sick=True)
        assert _can_attack(c) is False

    def test_summoning_sick_with_haste_can_attack(self) -> None:
        """A creature with summoning sickness but haste CAN attack."""
        c = _make_creature(summoning_sick=True, keywords=Keyword.HASTE)
        assert _can_attack(c) is True

    def test_defender_cannot_attack(self) -> None:
        """A creature with defender cannot attack."""
        c = _make_creature(keywords=Keyword.DEFENDER)
        assert _can_attack(c) is False


# ---------------------------------------------------------------------------
# Helper: _can_block
# ---------------------------------------------------------------------------

class TestCanBlock:
    """Verify the _can_block helper function."""

    def test_normal_block(self) -> None:
        """A ground creature can block a ground attacker."""
        blocker = _make_creature(name="Blocker")
        attacker = _make_creature(name="Attacker")
        assert _can_block(blocker, attacker) is True

    def test_tapped_cannot_block(self) -> None:
        """A tapped creature cannot block."""
        blocker = _make_creature(name="Blocker", is_tapped=True)
        attacker = _make_creature(name="Attacker")
        assert _can_block(blocker, attacker) is False

    def test_flying_not_blocked_by_ground(self) -> None:
        """A flying attacker cannot be blocked by a ground creature."""
        blocker = _make_creature(name="Blocker")
        attacker = _make_creature(name="Flyer", keywords=Keyword.FLYING)
        assert _can_block(blocker, attacker) is False

    def test_flying_blocked_by_flying(self) -> None:
        """A flying attacker CAN be blocked by a flying creature."""
        blocker = _make_creature(name="FlyBlocker", keywords=Keyword.FLYING)
        attacker = _make_creature(name="Flyer", keywords=Keyword.FLYING)
        assert _can_block(blocker, attacker) is True

    def test_flying_blocked_by_reach(self) -> None:
        """A flying attacker CAN be blocked by a creature with reach."""
        blocker = _make_creature(name="Reacher", keywords=Keyword.REACH)
        attacker = _make_creature(name="Flyer", keywords=Keyword.FLYING)
        assert _can_block(blocker, attacker) is True


# ---------------------------------------------------------------------------
# Helper: _get_lethal_damage
# ---------------------------------------------------------------------------

class TestGetLethalDamage:
    """Verify the _get_lethal_damage helper function."""

    def test_lethal_is_toughness_minus_damage(self) -> None:
        """Lethal damage equals toughness - damage_marked."""
        c = _make_creature(toughness=4)
        c.damage_marked = 1
        assert _get_lethal_damage(c) == 3

    def test_lethal_at_least_one(self) -> None:
        """Lethal damage is at least 1 even if damage_marked >= toughness."""
        c = _make_creature(toughness=2)
        c.damage_marked = 5
        assert _get_lethal_damage(c) >= 1

    def test_deathtouch_makes_lethal_one(self) -> None:
        """If the attacker has deathtouch, lethal damage is always 1."""
        c = _make_creature(toughness=10)
        attacker = _make_creature(keywords=Keyword.DEATHTOUCH)
        assert _get_lethal_damage(c, attacker) == 1


# ---------------------------------------------------------------------------
# Declare Attackers Step
# ---------------------------------------------------------------------------

class TestDeclareAttackers:
    """Declaring attackers."""

    def test_valid_attack_taps_creature(self) -> None:
        lions = card(SavannahLions)
        t = _attacks(Side(battlefield=[lions]))
        _attack(t, lions)
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 18)])
        t.run()

    def test_vigilance_does_not_tap(self) -> None:
        parent = card(PridefulParent)
        t = _attacks(Side(battlefield=[parent]))
        _attack(t, parent, tapping=())
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 18)])
        t.run()

    def test_summoning_sick_rejected(self) -> None:
        lions, plains = card(SavannahLions), card(Plains)
        t = _main(Side(hand=[lions], battlefield=[plains]))
        _cast(t, plains, lions, then=[moves(lions, Zone.BATTLEFIELD)])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act_illegal(0, lions, note="the Lions came under player 0's control this turn")
        _no_attack(t)
        t.run()

    def test_haste_bypasses_summoning_sickness(self) -> None:
        firebrand, mountain = card(FanaticalFirebrand), card(Mountain)
        t = _main(Side(hand=[firebrand], battlefield=[mountain]))
        _cast(t, mountain, firebrand, then=[moves(firebrand, Zone.BATTLEFIELD)])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        _attack(t, firebrand)
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 19)])
        t.run()

    def test_no_eligible_attackers_skips(self) -> None:
        """With no creatures, the declaration is still asked, and nothing
        attacks."""
        t = _attacks(Side(), Side(battlefield=[card(SavannahLions)]))
        _no_attack(t)
        t.run()

    def test_player_chooses_none_no_attackers(self) -> None:
        lions = card(SavannahLions)
        t = _attacks(Side(battlefield=[lions]))
        _no_attack(t)
        t.run()

    def test_multiple_attackers(self) -> None:
        lions, elves = card(SavannahLions), card(LlanowarElves)
        t = _attacks(Side(battlefield=[lions, elves]))
        _attack(t, lions, elves)
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 17)])
        t.run()

    def test_defender_not_in_eligible_list(self) -> None:
        wall = card(RuneSealedWall)
        t = _attacks(Side(battlefield=[wall]))
        t.act_illegal(0, wall, note="a creature with defender can't attack")
        _no_attack(t)
        t.run()

    def test_tapped_creature_not_in_eligible_list(self) -> None:
        lions = card(SavannahLions, tapped=True)
        t = _attacks(Side(battlefield=[lions]))
        t.act_illegal(0, lions, note="a tapped creature can't attack")
        _no_attack(t)
        t.run()


# ---------------------------------------------------------------------------
# Declare Blockers Step
# ---------------------------------------------------------------------------

class TestDeclareBlockers:
    """Declaring blockers."""

    def test_valid_block(self) -> None:
        lions, turtle = card(SavannahLions), card(AegisTurtle)
        t = _attacks(Side(battlefield=[lions]), Side(battlefield=[turtle]))
        _attack(t, lions)
        _to_blockers(t)
        _blocks(t, {turtle: lions})
        t.run()

    def test_flying_cannot_be_blocked_by_ground(self) -> None:
        sailor, lions = card(SpectralSailor), card(SavannahLions)
        t = _attacks(Side(battlefield=[sailor]), Side(battlefield=[lions]))
        _attack(t, sailor)
        _to_blockers(t)
        t.act_illegal(1, lions, scoped={lions: sailor}, note="flying")
        _no_blocks(t, then=[life(1, 19)])
        t.run()

    def test_flying_blocked_by_reach(self) -> None:
        sailor, giant = card(SpectralSailor), card(ElfswornGiant)
        t = _attacks(Side(battlefield=[sailor]), Side(battlefield=[giant]))
        _attack(t, sailor)
        _to_blockers(t)
        _blocks(t, {giant: sailor}, then=[moves(sailor, Zone.GRAVEYARD)])
        t.run()

    def test_menace_requires_two_blockers(self) -> None:
        feaster, turtle = card(CryptFeaster), card(AegisTurtle)
        t = _attacks(Side(battlefield=[feaster]), Side(battlefield=[turtle]))
        _attack(t, feaster)
        _to_blockers(t)
        t.act_illegal(1, turtle, scoped={turtle: feaster}, note="menace")
        _no_blocks(t, then=[life(1, 17)])
        t.run()

    def test_menace_with_two_blockers_succeeds(self) -> None:
        feaster, turtle, lions = card(CryptFeaster), card(AegisTurtle), card(SavannahLions)
        t = _attacks(Side(battlefield=[feaster]), Side(battlefield=[turtle, lions]))
        _attack(t, feaster)
        _to_blockers(t)
        _blocks(
            t, {turtle: feaster, lions: feaster}, shares={lions: 3, turtle: 0},
            then=[moves(lions, Zone.GRAVEYARD)],
        )
        t.run()

    def test_attackers_controller_divides_damage_among_blockers(self) -> None:
        """The 12 damage is divided 1 to the Brazen Scourge, which survives,
        and 11 to the Aegis Turtle, which dies."""
        ceratops, scourge, turtle = card(QuakestriderCeratops), card(BrazenScourge), card(AegisTurtle)
        t = _attacks(Side(battlefield=[ceratops]), Side(battlefield=[scourge, turtle]))
        _attack(t, ceratops)
        _to_blockers(t)
        _blocks(
            t, {scourge: ceratops, turtle: ceratops}, shares={scourge: 1, turtle: 11},
            then=[moves(turtle, Zone.GRAVEYARD)],
        )
        t.run()

    def test_no_attackers_blockers_step_skips(self) -> None:
        """Player 1, who could block, is never asked to declare blockers."""
        t = _attacks(Side(battlefield=[card(SavannahLions)]), Side(battlefield=[card(AegisTurtle)]))
        _no_attack(t)
        t.run()

    def test_defending_player_chooses_none_no_blockers(self) -> None:
        lions, turtle = card(SavannahLions), card(AegisTurtle)
        t = _attacks(Side(battlefield=[lions]), Side(battlefield=[turtle]))
        _attack(t, lions)
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 18)])
        t.run()


# ---------------------------------------------------------------------------
# Combat Damage Step
# ---------------------------------------------------------------------------

class TestCombatDamage:
    """Combat damage."""

    def test_unblocked_damage_to_player(self) -> None:
        scourge = card(BrazenScourge)
        t = _attacks(Side(battlefield=[scourge]))
        _attack(t, scourge)
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 17)])
        t.run()

    def test_blocked_damage_to_blocker(self) -> None:
        """Two 3/3s trade: each deals its damage to the other."""
        attacker, blocker = card(BrazenScourge), card(BrazenScourge)
        t = _attacks(Side(battlefield=[attacker]), Side(battlefield=[blocker]))
        _attack(t, attacker)
        _to_blockers(t)
        _blocks(t, {blocker: attacker}, then=[moves(attacker, Zone.GRAVEYARD), moves(blocker, Zone.GRAVEYARD)])
        t.run()

    def test_zero_power_attacker_unblocked(self) -> None:
        turtle = card(AegisTurtle)
        t = _attacks(Side(battlefield=[turtle]))
        _attack(t, turtle)
        _to_blockers(t)
        _no_blocks(t)
        t.run()

    def test_first_strike_deals_damage_first(self) -> None:
        """Alesha's first-strike damage kills the blocked Lions before it
        deals its own."""
        lions, alesha = card(SavannahLions), card(AleshaWhoLaughsAtFate)
        t = _attacks(Side(battlefield=[lions]), Side(battlefield=[alesha]))
        _attack(t, lions)
        _to_blockers(t)
        _blocks(t, {alesha: lions}, first_strike=[moves(lions, Zone.GRAVEYARD)])
        t.run()

    def test_double_strike_deals_damage_twice(self) -> None:
        vindicator = card(SwiftbladeVindicator)
        t = _attacks(Side(battlefield=[vindicator]))
        _attack(t, vindicator, tapping=())
        _to_blockers(t)
        _no_blocks(t, first_strike=[life(1, 19)], then=[life(1, 18)])
        t.run()

    def test_trample_excess_damage_to_player(self) -> None:
        ranger, elves = card(BeastKinRanger), card(LlanowarElves)
        t = _attacks(Side(battlefield=[ranger]), Side(battlefield=[elves]))
        _attack(t, ranger)
        _to_blockers(t)
        _blocks(t, {elves: ranger}, shares={elves: 1}, then=[moves(elves, Zone.GRAVEYARD), life(1, 18)])
        t.run()

    def test_trample_with_deathtouch(self) -> None:
        """Ashroot Animist gives the deathtouch Gutless Plunderer trample and
        +4/+4; 1 damage is lethal to the Aegis Turtle blocking it, so 5
        tramples over, beside the Animist's 4."""
        animist, plunderer, turtle = card(AshrootAnimist), card(GutlessPlunderer), card(AegisTurtle)
        t = _attacks(Side(battlefield=[animist, plunderer]), Side(battlefield=[turtle]))
        _attack(t, plunderer, animist, then=[on_stack(AshrootAnimistAbility2, 0)])
        t.pass_(0, choices=[plunderer])
        t.pass_(1, then=[off_stack(AshrootAnimistAbility2)])
        _to_blockers(t)
        _blocks(t, {turtle: plunderer}, shares={turtle: 1}, then=[moves(turtle, Zone.GRAVEYARD), life(1, 11)])
        t.run()

    def test_lifelink_gains_life(self) -> None:
        savior = card(FelidarSavior)
        t = _attacks(Side(battlefield=[savior], life=15))
        _attack(t, savior)
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 18), life(0, 17)])
        t.run()

    def test_lifelink_with_blocker(self) -> None:
        savior, turtle = card(FelidarSavior), card(AegisTurtle)
        t = _attacks(Side(battlefield=[savior], life=10), Side(battlefield=[turtle]))
        _attack(t, savior)
        _to_blockers(t)
        _blocks(t, {turtle: savior}, then=[life(0, 12)])
        t.run()

    def test_no_attackers_damage_step_skips(self) -> None:
        t = _attacks(Side(battlefield=[card(FelidarSavior)], life=15))
        _no_attack(t)
        t.run()

    def test_without_trample_all_damage_to_blocker(self) -> None:
        ceratops, lions = card(QuakestriderCeratops), card(SavannahLions)
        t = _attacks(Side(battlefield=[ceratops]), Side(battlefield=[lions]))
        _attack(t, ceratops)
        _to_blockers(t)
        _blocks(t, {lions: ceratops}, then=[moves(lions, Zone.GRAVEYARD)])
        t.run()

    def test_multiple_blockers_damage_division(self) -> None:
        """The 3 damage is divided as lethal damage to both blockers; with no
        trample none reaches player 1."""
        scourge, lions, ghoul = card(BrazenScourge), card(SavannahLions), card(DiregrafGhoul)
        t = _attacks(Side(battlefield=[scourge]), Side(battlefield=[lions, ghoul]))
        _attack(t, scourge)
        _to_blockers(t)
        _blocks(
            t, {lions: scourge, ghoul: scourge}, shares={lions: 1, ghoul: 2},
            then=[moves(scourge, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD), moves(ghoul, Zone.GRAVEYARD)],
        )
        t.run()



# ---------------------------------------------------------------------------
# End Combat Step
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Integration Scenarios
# ---------------------------------------------------------------------------

class TestCombatIntegration:
    """Full attack/block/damage cycles."""

    def test_full_combat_cycle_unblocked(self) -> None:
        """Declare an attacker, no blockers, damage, then on to the second main phase."""
        lions = card(SavannahLions)
        t = _attacks(Side(battlefield=[lions]))
        _attack(t, lions)
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 18)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.run()

    def test_full_combat_cycle_blocked(self) -> None:
        """The 3/3 kills its 2/2 blocker and survives its 2 damage."""
        scourge, parent = card(BrazenScourge), card(PridefulParent)
        t = _attacks(Side(battlefield=[scourge]), Side(battlefield=[parent]))
        _attack(t, scourge)
        _to_blockers(t)
        _blocks(t, {parent: scourge}, then=[moves(parent, Zone.GRAVEYARD)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.run()

    def test_multiple_attackers_mixed_block(self) -> None:
        lions, scourge, turtle = card(SavannahLions), card(BrazenScourge), card(AegisTurtle)
        t = _attacks(Side(battlefield=[lions, scourge]), Side(battlefield=[turtle]))
        _attack(t, lions, scourge)
        _to_blockers(t)
        _blocks(t, {turtle: lions}, then=[life(1, 17)])
        t.run()

    def test_creature_with_multiple_keywords(self) -> None:
        """Sire of Seven Deaths — first strike, vigilance, menace, trample,
        reach, lifelink — attacks without tapping, needs two blockers, kills
        both with first-strike damage before they deal theirs, tramples 5 over
        and gains its controller 7 life."""
        sire, lions, elves = card(SireOfSevenDeaths), card(SavannahLions), card(LlanowarElves)
        t = _attacks(Side(battlefield=[sire]), Side(battlefield=[lions, elves]))
        _attack(t, sire, tapping=())
        _to_blockers(t)
        t.act_illegal(1, lions, scoped={lions: sire}, note="menace")
        _blocks(
            t, {lions: sire, elves: sire}, shares={lions: 1, elves: 1},
            first_strike=[moves(lions, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD), life(1, 15), life(0, 27)],
        )
        t.run()

    def test_blocked_but_blocker_removed_before_damage(self) -> None:
        """The Lions stays blocked after its blocker dies, so it deals no
        damage (rule 509.1h)."""
        lions, mountain, bolt = card(SavannahLions), card(Mountain), card(BurstLightning)
        elves = card(LlanowarElves)
        t = _attacks(Side(battlefield=[lions, mountain], hand=[bolt]), Side(battlefield=[elves]))
        _attack(t, lions)
        _to_blockers(t)
        t.act(1, elves, scoped={elves: lions})
        _cast(t, mountain, bolt, choices=[elves], then=[moves(bolt, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1)
        t.run()

    def test_first_strike_kills_before_normal_damage(self) -> None:
        """Alesha attacks, gets a +1/+1 counter from her attack trigger, and
        her 3 first-strike damage kills the 3/3 blocking her before it deals
        its own."""
        alesha, scourge = card(AleshaWhoLaughsAtFate), card(BrazenScourge)
        t = _attacks(Side(battlefield=[alesha]), Side(battlefield=[scourge]))
        _attack(t, alesha, then=[on_stack(AleshaWhoLaughsAtFateAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(AleshaWhoLaughsAtFateAbility2)])
        _to_blockers(t)
        _blocks(t, {scourge: alesha}, first_strike=[moves(scourge, Zone.GRAVEYARD)])
        t.run()



# ---------------------------------------------------------------------------
# Dormant-event firing (Phase I, issue #44): combat damage and attacks
# ---------------------------------------------------------------------------

def _record_events(game: GameState, event_type: type) -> list:
    """Register a spy trigger recording every fired *event_type*.

    The spy's condition appends the event and returns ``False`` so the event's
    facts are observed at the firing site without the trigger going on the
    stack — keeping these tests focused on *whether/what* fires, not resolution.
    Returns the list the spy appends to.
    """
    events: list = []

    def _cond(_g: GameState, event: object) -> bool:
        events.append(event)
        return False

    game.trigger_manager.register(
        TriggerRegistration(
            event_type=event_type,
            condition=_cond,
            effect=lambda _g: None,
            source=object(),
            controller=game.active_player,
        )
    )
    return events


class TestCombatDamageFiresEvent:
    """engine/combat.py::_deal_damage fires DealsDamageTriggeredEvent (Phase I).

    Before Phase I combat damage fired no event, so every combat-damage trigger
    (Drake Hatcher's incubation, Goldvein Pick's Treasure, prowess-of-combat)
    was dormant. It now fires with ``is_combat``/``combat`` both True, so a
    subscriber can distinguish combat from the non-combat damage that
    engine.game.deal_damage fires with those flags False.
    """

    def test_damage_to_player_fires_combat_flagged_event(self) -> None:
        game = _make_game()
        attacker = _make_creature("Raider", 3, 3)
        _place_on_battlefield(game.players[0], attacker, game)
        events = _record_events(game, DealsDamageTriggeredEvent)
        _deal_damage(attacker, game.players[1], 3, game, game.combat_state)
        assert len(events) == 1
        (e,) = events
        assert e.source is attacker
        assert e.target is game.players[1]
        assert e.amount == 3
        assert e.is_combat is True
        assert e.combat is True

    def test_damage_to_creature_fires_combat_flagged_event(self) -> None:
        game = _make_game()
        attacker = _make_creature("Raider", 3, 3)
        blocker = _make_creature("Wall", 0, 4)
        _place_on_battlefield(game.players[0], attacker, game)
        _place_on_battlefield(game.players[1], blocker, game)
        events = _record_events(game, DealsDamageTriggeredEvent)
        _deal_damage(attacker, blocker, 3, game, game.combat_state)
        assert len(events) == 1
        assert events[0].target is blocker
        assert events[0].is_combat is True and events[0].combat is True

    def test_zero_and_prevented_damage_fires_nothing(self) -> None:
        game = _make_game()
        attacker = _make_creature("Raider", 2, 2)
        _place_on_battlefield(game.players[0], attacker, game)
        events = _record_events(game, DealsDamageTriggeredEvent)
        # amount <= 0 short-circuits before the event
        _deal_damage(attacker, game.players[1], 0, game, game.combat_state)
        assert events == []


    def test_combat_damage_step_fires_for_unblocked_attacker(self) -> None:
        """Eager Trufflesnout's combat-damage trigger makes a Food when it
        deals combat damage to player 1."""
        snout = card(EagerTrufflesnout)
        t = _attacks(Side(battlefield=[snout]))
        _attack(t, snout)
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 16), on_stack(EagerTrufflesnoutAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(EagerTrufflesnoutAbility2), appears(0)])
        t.run()


class TestAttacksFiresEvent:
    """Attack triggers fire once per declared attacker, after the whole
    declaration is made (rule 508.2)."""

    def test_fires_once_per_attacker_with_both_fields(self) -> None:
        """Each Sanguine Syphoner's attack trigger drains 1."""
        s1, s2 = card(SanguineSyphoner), card(SanguineSyphoner)
        t = _attacks(Side(battlefield=[s1, s2]))
        _attack(t, s1, s2, then=[on_stack(SanguineSyphonerAbility1, 0), on_stack(SanguineSyphonerAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(SanguineSyphonerAbility1), life(1, 19), life(0, 21)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(SanguineSyphonerAbility1), life(1, 18), life(0, 22)])
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 16)])
        t.run()

    def test_fires_after_full_declaration(self) -> None:
        """Armasaur Guide's trigger needs three attackers, so it fires only
        when it sees the whole declaration; its +1/+1 counter on the Lions
        adds 1 to the damage."""
        guide, lions, elves = card(ArmasaurGuide), card(SavannahLions), card(LlanowarElves)
        t = _attacks(Side(battlefield=[guide, lions, elves]))
        _attack(t, lions, guide, elves, tapping=(lions, elves), then=[on_stack(ArmasaurGuideAbility2, 0)])
        t.pass_(0, choices=[lions])
        t.pass_(1, then=[off_stack(ArmasaurGuideAbility2)])
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 12)])
        t.run()

    def test_no_attackers_declared_fires_nothing(self) -> None:
        t = _attacks(Side(battlefield=[card(SanguineSyphoner)]))
        _no_attack(t)
        t.run()

    def test_ineligible_creature_does_not_fire(self) -> None:
        """A declaration naming a tapped Syphoner never takes effect, so it
        drains nothing; declaring the untapped one alone drains 1."""
        syphoner, tapped = card(SanguineSyphoner), card(SanguineSyphoner, tapped=True)
        t = _attacks(Side(battlefield=[syphoner, tapped]))
        t.act_illegal(0, syphoner, tapped, note="a tapped creature can't attack")
        _attack(t, syphoner, then=[on_stack(SanguineSyphonerAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(SanguineSyphonerAbility1), life(1, 19), life(0, 21)])
        _to_blockers(t)
        _no_blocks(t, then=[life(1, 18)])
        t.run()
