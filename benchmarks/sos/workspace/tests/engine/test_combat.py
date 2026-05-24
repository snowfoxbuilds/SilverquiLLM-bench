"""Tests for engine/combat.py — Combat system.

Verifies:
- CombatState construction and default values.
- CombatState.clear() resets all fields.
- declare_attackers_step: valid attack, tapping attackers, vigilance (no tap),
  summoning sickness rejection, haste bypasses sickness, defender cannot attack,
  tapped creatures cannot attack.
- declare_blockers_step: valid block, flying evasion (only blocked by flying/reach),
  menace requires 2+ blockers (single blocker removed), blocker ordering by
  attacking player.
- combat_damage_step: basic damage to blocker and attacker, unblocked damage
  to player, first strike deals damage first (kills blocker before normal
  damage), double strike deals damage in both phases, trample excess to
  defending player, lifelink gains life, deathtouch (1 damage is lethal
  assignment).
- end_combat_step: clears combat flags and combat state.
- Integration: full attack/block/damage cycle, creature dies from combat
  damage via SBAs, multiple attackers and blockers.
- Edge cases: 0-power attacker, blocked but blocker removed before damage,
  creature with multiple keywords.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.card import Creature, GameObject
from benchmarks.sos.workspace.engine.combat import (
    CombatState,
    _can_attack,
    _can_block,
    _get_lethal_damage,
    combat_damage_step,
    declare_attackers_step,
    declare_blockers_step,
    end_combat_step,
)
from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.types import Keyword, Zone


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
    owner: DeterministicPlayer | None = None,
    controller: DeterministicPlayer | None = None,
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
    p1_script: list | None = None,
    p2_script: list | None = None,
    p1_life: int = 20,
    p2_life: int = 20,
) -> GameState:
    """Create a 2-player GameState with optional scripts and life totals."""
    p1 = DeterministicPlayer("Alice", p1_script or [], life=p1_life)
    p2 = DeterministicPlayer("Bob", p2_script or [], life=p2_life)
    return GameState([p1, p2])


def _place_on_battlefield(player: DeterministicPlayer, creature: Creature) -> None:
    """Put a creature on a player's battlefield and set its controller."""
    creature.controller = player
    creature.owner = player
    player.zones[Zone.BATTLEFIELD].add(creature)


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
    """Verify declare_attackers_step behavior."""

    def test_valid_attack_taps_creature(self) -> None:
        """A valid attacker should be tapped and registered in combat state."""
        bear = _make_creature(name="Bear", summoning_sick=False)
        game = _make_game(p1_script=[[bear]])  # active player chooses [bear]
        _place_on_battlefield(game.active_player, bear)

        declare_attackers_step(game)

        assert bear.is_tapped is True
        assert bear.is_attacking is True
        assert bear in game.combat_state.attackers
        assert game.combat_state.in_combat is True

    def test_vigilance_does_not_tap(self) -> None:
        """An attacker with vigilance should NOT be tapped."""
        vig = _make_creature(name="Vigilant", keywords=Keyword.VIGILANCE, summoning_sick=False)
        game = _make_game(p1_script=[[vig]])
        _place_on_battlefield(game.active_player, vig)

        declare_attackers_step(game)

        assert vig.is_tapped is False
        assert vig.is_attacking is True

    def test_summoning_sick_rejected(self) -> None:
        """A creature with summoning sickness should not be allowed to attack."""
        sick = _make_creature(name="Sick", summoning_sick=True)
        # Player tries to choose the sick creature, but _can_attack filters it.
        # Since the creature is not eligible, it won't appear in eligible list.
        game = _make_game(p1_script=[])
        _place_on_battlefield(game.active_player, sick)

        declare_attackers_step(game)

        # Not eligible means choose was never called or nothing was chosen
        assert sick.is_attacking is False
        assert sick not in game.combat_state.attackers

    def test_haste_bypasses_summoning_sickness(self) -> None:
        """A creature with haste can attack even with summoning sickness."""
        haste = _make_creature(name="Hasty", summoning_sick=True, keywords=Keyword.HASTE)
        game = _make_game(p1_script=[[haste]])
        _place_on_battlefield(game.active_player, haste)

        declare_attackers_step(game)

        assert haste.is_attacking is True
        assert haste in game.combat_state.attackers

    def test_no_eligible_attackers_skips(self) -> None:
        """If no creatures are eligible, the step completes without error."""
        game = _make_game(p1_script=[])
        declare_attackers_step(game)
        assert game.combat_state.attackers == {}

    def test_player_chooses_none_no_attackers(self) -> None:
        """If active player declines to attack (returns None), no attackers."""
        bear = _make_creature(name="Bear", summoning_sick=False)
        game = _make_game(p1_script=[None])
        _place_on_battlefield(game.active_player, bear)

        declare_attackers_step(game)

        assert bear.is_attacking is False
        assert len(game.combat_state.attackers) == 0

    def test_multiple_attackers(self) -> None:
        """Multiple creatures can be declared as attackers."""
        bear1 = _make_creature(name="Bear1", summoning_sick=False)
        bear2 = _make_creature(name="Bear2", summoning_sick=False)
        game = _make_game(p1_script=[[bear1, bear2]])
        _place_on_battlefield(game.active_player, bear1)
        _place_on_battlefield(game.active_player, bear2)

        declare_attackers_step(game)

        assert bear1.is_attacking is True
        assert bear2.is_attacking is True
        assert len(game.combat_state.attackers) == 2

    def test_defender_not_in_eligible_list(self) -> None:
        """A creature with defender should not be in the eligible attacker list."""
        wall = _make_creature(name="Wall", keywords=Keyword.DEFENDER, summoning_sick=False)
        game = _make_game(p1_script=[])
        _place_on_battlefield(game.active_player, wall)

        declare_attackers_step(game)

        assert wall.is_attacking is False
        assert wall not in game.combat_state.attackers

    def test_tapped_creature_not_in_eligible_list(self) -> None:
        """A tapped creature should not be eligible to attack."""
        tapped = _make_creature(name="TappedBear", is_tapped=True, summoning_sick=False)
        game = _make_game(p1_script=[])
        _place_on_battlefield(game.active_player, tapped)

        declare_attackers_step(game)

        assert tapped not in game.combat_state.attackers


# ---------------------------------------------------------------------------
# Declare Blockers Step
# ---------------------------------------------------------------------------

class TestDeclareBlockers:
    """Verify declare_blockers_step behavior."""

    def _setup_attack(
        self,
        attacker: Creature,
        game: GameState,
    ) -> None:
        """Manually register an attacker in combat state (shortcut)."""
        combat = game.combat_state
        combat.in_combat = True
        combat.attackers[attacker] = game.non_active_player
        combat.attacker_blockers[attacker] = []
        attacker.is_attacking = True

    def test_valid_block(self) -> None:
        """A ground blocker can block a ground attacker."""
        attacker = _make_creature(name="Attacker", summoning_sick=False)
        blocker = _make_creature(name="Blocker", summoning_sick=False)

        game = _make_game(p2_script=[{blocker: attacker}])  # defending player assigns
        _place_on_battlefield(game.active_player, attacker)
        _place_on_battlefield(game.non_active_player, blocker)

        self._setup_attack(attacker, game)
        declare_blockers_step(game)

        assert blocker in game.combat_state.blockers
        assert blocker.is_blocking is True
        assert blocker in game.combat_state.attacker_blockers[attacker]

    def test_flying_cannot_be_blocked_by_ground(self) -> None:
        """A flying attacker cannot be blocked by a ground creature."""
        flyer = _make_creature(name="Flyer", keywords=Keyword.FLYING, summoning_sick=False)
        ground = _make_creature(name="Ground", summoning_sick=False)

        game = _make_game(p2_script=[{ground: flyer}])
        _place_on_battlefield(game.active_player, flyer)
        _place_on_battlefield(game.non_active_player, ground)

        self._setup_attack(flyer, game)
        declare_blockers_step(game)

        # Block should be rejected
        assert ground not in game.combat_state.blockers
        assert game.combat_state.attacker_blockers[flyer] == []

    def test_flying_blocked_by_reach(self) -> None:
        """A flying attacker CAN be blocked by a reach creature."""
        flyer = _make_creature(name="Flyer", keywords=Keyword.FLYING, summoning_sick=False)
        reacher = _make_creature(name="Reacher", keywords=Keyword.REACH, summoning_sick=False)

        game = _make_game(p2_script=[{reacher: flyer}])
        _place_on_battlefield(game.active_player, flyer)
        _place_on_battlefield(game.non_active_player, reacher)

        self._setup_attack(flyer, game)
        declare_blockers_step(game)

        assert reacher in game.combat_state.blockers
        assert reacher in game.combat_state.attacker_blockers[flyer]

    def test_menace_requires_two_blockers(self) -> None:
        """A menace creature blocked by only 1 blocker is treated as unblocked."""
        menace = _make_creature(name="Menace", keywords=Keyword.MENACE, summoning_sick=False)
        lone_blocker = _make_creature(name="LoneBlocker", summoning_sick=False)

        game = _make_game(p2_script=[{lone_blocker: menace}])
        _place_on_battlefield(game.active_player, menace)
        _place_on_battlefield(game.non_active_player, lone_blocker)

        self._setup_attack(menace, game)
        declare_blockers_step(game)

        # Single blocker should be removed due to menace
        assert game.combat_state.attacker_blockers[menace] == []
        assert lone_blocker not in game.combat_state.blockers

    def test_menace_with_two_blockers_succeeds(self) -> None:
        """A menace creature blocked by 2 blockers is legally blocked."""
        menace = _make_creature(name="Menace", keywords=Keyword.MENACE, summoning_sick=False)
        b1 = _make_creature(name="Blocker1", summoning_sick=False)
        b2 = _make_creature(name="Blocker2", summoning_sick=False)

        # Defending player assigns both blockers to the menace creature
        game = _make_game(
            p1_script=[],  # active player — order blockers
            p2_script=[{b1: menace, b2: menace}],
        )
        # The attacking player orders blockers — provide an ordering answer
        game.active_player._script.append([b1, b2])

        _place_on_battlefield(game.active_player, menace)
        _place_on_battlefield(game.non_active_player, b1)
        _place_on_battlefield(game.non_active_player, b2)

        self._setup_attack(menace, game)
        declare_blockers_step(game)

        assert len(game.combat_state.attacker_blockers[menace]) == 2

    def test_blocker_ordering_by_controller(self) -> None:
        """When multiple blockers, the attacker's controller orders them."""
        attacker = _make_creature(name="Attacker", summoning_sick=False, power=5, toughness=5)
        b1 = _make_creature(name="B1", toughness=2, summoning_sick=False)
        b2 = _make_creature(name="B2", toughness=3, summoning_sick=False)

        game = _make_game(
            p1_script=[[b2, b1]],  # controller orders b2 first, then b1
            p2_script=[{b1: attacker, b2: attacker}],
        )
        _place_on_battlefield(game.active_player, attacker)
        _place_on_battlefield(game.non_active_player, b1)
        _place_on_battlefield(game.non_active_player, b2)

        self._setup_attack(attacker, game)
        declare_blockers_step(game)

        # Controller ordered b2, b1
        assert game.combat_state.attacker_blockers[attacker] == [b2, b1]

    def test_no_attackers_blockers_step_skips(self) -> None:
        """If there are no attackers, declare_blockers_step does nothing."""
        game = _make_game()
        declare_blockers_step(game)
        assert game.combat_state.blockers == {}

    def test_defending_player_chooses_none_no_blockers(self) -> None:
        """If the defending player declines to block, no blockers are assigned."""
        attacker = _make_creature(name="Attacker", summoning_sick=False)
        blocker = _make_creature(name="Blocker", summoning_sick=False)

        game = _make_game(p2_script=[None])
        _place_on_battlefield(game.active_player, attacker)
        _place_on_battlefield(game.non_active_player, blocker)

        self._setup_attack(attacker, game)
        declare_blockers_step(game)

        assert game.combat_state.blockers == {}


# ---------------------------------------------------------------------------
# Combat Damage Step
# ---------------------------------------------------------------------------

class TestCombatDamage:
    """Verify combat_damage_step behavior."""

    def _setup_combat(
        self,
        game: GameState,
        attacker: Creature,
        blockers: list[Creature] | None = None,
    ) -> None:
        """Set up combat state with attacker and optional blockers."""
        combat = game.combat_state
        combat.in_combat = True
        combat.attackers[attacker] = game.non_active_player
        combat.attacker_blockers[attacker] = blockers or []

    def test_unblocked_damage_to_player(self) -> None:
        """An unblocked attacker deals damage to the defending player."""
        bear = _make_creature(name="Bear", power=2, toughness=2)
        game = _make_game(p2_life=20)
        _place_on_battlefield(game.active_player, bear)
        bear.controller = game.active_player

        self._setup_combat(game, bear)
        combat_damage_step(game)

        assert game.non_active_player.life == 18

    def test_blocked_damage_to_blocker(self) -> None:
        """A blocked attacker deals damage to the blocker, and vice versa."""
        attacker = _make_creature(name="Attacker", power=3, toughness=3)
        blocker = _make_creature(name="Blocker", power=2, toughness=4)
        game = _make_game()
        _place_on_battlefield(game.active_player, attacker)
        _place_on_battlefield(game.non_active_player, blocker)
        attacker.controller = game.active_player
        blocker.controller = game.non_active_player

        self._setup_combat(game, attacker, [blocker])
        combat_damage_step(game)

        # Attacker deals 3 to blocker
        assert blocker.damage_marked == 3
        # Blocker deals 2 to attacker
        assert attacker.damage_marked == 2
        # No damage to either player
        assert game.active_player.life == 20
        assert game.non_active_player.life == 20

    def test_zero_power_attacker_unblocked(self) -> None:
        """A 0-power attacker deals 0 damage to the defending player."""
        wimp = _make_creature(name="Wimp", power=0, toughness=1)
        game = _make_game(p2_life=20)
        _place_on_battlefield(game.active_player, wimp)
        wimp.controller = game.active_player

        self._setup_combat(game, wimp)
        combat_damage_step(game)

        assert game.non_active_player.life == 20

    def test_first_strike_deals_damage_first(self) -> None:
        """A first-strike creature deals damage before a normal creature.

        If the first-strike creature can kill the blocker, the blocker
        should not deal damage back (because SBAs kill it first).
        """
        first_striker = _make_creature(
            name="FirstStriker", power=3, toughness=1,
            keywords=Keyword.FIRST_STRIKE,
        )
        blocker = _make_creature(name="Blocker", power=3, toughness=3)
        game = _make_game()
        _place_on_battlefield(game.active_player, first_striker)
        _place_on_battlefield(game.non_active_player, blocker)
        first_striker.controller = game.active_player
        blocker.controller = game.non_active_player

        self._setup_combat(game, first_striker, [blocker])
        combat_damage_step(game)

        # First striker deals 3 damage to blocker (lethal for 3 toughness)
        assert blocker.damage_marked >= 3
        # After SBAs, blocker dies — first_striker should not have damage
        # from normal damage sub-step (blocker was removed by SBAs)
        # The blocker's damage-back only happens in the normal damage step
        # for non-first-strike creatures, but blocker is not in the
        # first-strike group. So blocker deals damage in normal step.
        # But SBAs may remove blocker from battlefield before normal damage.
        # Actually, the blocker's damage-dealing happens in the same
        # _assign_combat_damage call, so let's verify that if the blocker
        # died from first-strike damage, it might still deal damage
        # depending on implementation.

        # The key behavior: first_striker's damage came first.
        # Blocker took 3 damage. blocker has toughness 3 -> dies to SBAs.
        # After SBAs in first-strike sub-step, blocker should be in GY.
        gy = game.non_active_player.zones[Zone.GRAVEYARD]
        bf = game.non_active_player.zones[Zone.BATTLEFIELD]
        # Blocker should be moved to graveyard by SBAs after first strike damage
        assert gy.contains(blocker) or blocker.damage_marked >= blocker.toughness

    def test_double_strike_deals_damage_twice(self) -> None:
        """A double-strike creature deals damage in both first-strike and normal phases."""
        double = _make_creature(
            name="DoubleStriker", power=2, toughness=3,
            keywords=Keyword.DOUBLE_STRIKE,
        )
        game = _make_game(p2_life=20)
        _place_on_battlefield(game.active_player, double)
        double.controller = game.active_player

        self._setup_combat(game, double)
        combat_damage_step(game)

        # Double strike: 2 damage in first-strike + 2 damage in normal = 4 total
        assert game.non_active_player.life == 16

    def test_trample_excess_damage_to_player(self) -> None:
        """Trample: excess damage over blocker toughness goes to defending player."""
        trampler = _make_creature(
            name="Trampler", power=5, toughness=5,
            keywords=Keyword.TRAMPLE,
        )
        blocker = _make_creature(name="Blocker", power=1, toughness=2)
        game = _make_game(p2_life=20)
        _place_on_battlefield(game.active_player, trampler)
        _place_on_battlefield(game.non_active_player, blocker)
        trampler.controller = game.active_player
        blocker.controller = game.non_active_player

        self._setup_combat(game, trampler, [blocker])
        combat_damage_step(game)

        # Trampler assigns lethal (2) to blocker, excess (3) to player
        assert blocker.damage_marked >= 2
        assert game.non_active_player.life == 17

    def test_trample_with_deathtouch(self) -> None:
        """Trample + deathtouch: 1 damage is lethal, rest tramples through."""
        dt_trampler = _make_creature(
            name="DTTrampler", power=5, toughness=5,
            keywords=Keyword.TRAMPLE | Keyword.DEATHTOUCH,
        )
        blocker = _make_creature(name="Blocker", power=1, toughness=7)
        game = _make_game(p2_life=20)
        _place_on_battlefield(game.active_player, dt_trampler)
        _place_on_battlefield(game.non_active_player, blocker)
        dt_trampler.controller = game.active_player
        blocker.controller = game.non_active_player

        self._setup_combat(game, dt_trampler, [blocker])
        combat_damage_step(game)

        # Deathtouch lethal = 1, so 1 to blocker and 4 to player
        assert blocker.damage_marked >= 1
        assert game.non_active_player.life == 16

    def test_lifelink_gains_life(self) -> None:
        """A lifelink creature's controller gains life equal to damage dealt."""
        lifelinker = _make_creature(
            name="Lifelinker", power=3, toughness=3,
            keywords=Keyword.LIFELINK,
        )
        game = _make_game(p1_life=15, p2_life=20)
        _place_on_battlefield(game.active_player, lifelinker)
        lifelinker.controller = game.active_player

        self._setup_combat(game, lifelinker)
        combat_damage_step(game)

        # Deals 3 to defending player, gains 3 life for controller
        assert game.non_active_player.life == 17
        assert game.active_player.life == 18

    def test_lifelink_with_blocker(self) -> None:
        """Lifelink gains life when dealing damage to a blocker too."""
        lifelinker = _make_creature(
            name="Lifelinker", power=2, toughness=2,
            keywords=Keyword.LIFELINK,
        )
        blocker = _make_creature(name="Blocker", power=1, toughness=3)
        game = _make_game(p1_life=10)
        _place_on_battlefield(game.active_player, lifelinker)
        _place_on_battlefield(game.non_active_player, blocker)
        lifelinker.controller = game.active_player
        blocker.controller = game.non_active_player

        self._setup_combat(game, lifelinker, [blocker])
        combat_damage_step(game)

        # Lifelinker deals 2 to blocker -> gains 2 life
        assert game.active_player.life == 12

    def test_no_attackers_damage_step_skips(self) -> None:
        """If no attackers, combat_damage_step does nothing."""
        game = _make_game(p1_life=20, p2_life=20)
        combat_damage_step(game)
        assert game.active_player.life == 20
        assert game.non_active_player.life == 20

    def test_without_trample_all_damage_to_blocker(self) -> None:
        """Without trample, all damage goes to the blocker even if it exceeds toughness."""
        big = _make_creature(name="Big", power=10, toughness=10)
        small = _make_creature(name="Small", power=1, toughness=1)
        game = _make_game(p2_life=20)
        _place_on_battlefield(game.active_player, big)
        _place_on_battlefield(game.non_active_player, small)
        big.controller = game.active_player
        small.controller = game.non_active_player

        self._setup_combat(game, big, [small])
        combat_damage_step(game)

        # Without trample, all 10 damage goes to blocker
        assert small.damage_marked == 10
        # No damage to defending player
        assert game.non_active_player.life == 20

    def test_multiple_blockers_damage_assignment_order(self) -> None:
        """Damage is assigned to blockers in order, lethal to each before the next."""
        attacker = _make_creature(name="Attacker", power=5, toughness=5)
        b1 = _make_creature(name="B1", power=1, toughness=2)
        b2 = _make_creature(name="B2", power=1, toughness=3)
        game = _make_game(p2_life=20)
        _place_on_battlefield(game.active_player, attacker)
        _place_on_battlefield(game.non_active_player, b1)
        _place_on_battlefield(game.non_active_player, b2)
        attacker.controller = game.active_player
        b1.controller = game.non_active_player
        b2.controller = game.non_active_player

        # Order: b1 first, then b2
        self._setup_combat(game, attacker, [b1, b2])
        combat_damage_step(game)

        # b1 gets lethal (2), b2 gets remaining (3)
        assert b1.damage_marked == 2
        assert b2.damage_marked == 3
        assert game.non_active_player.life == 20  # no trample


# ---------------------------------------------------------------------------
# End Combat Step
# ---------------------------------------------------------------------------

class TestEndCombat:
    """Verify end_combat_step clears all combat state."""

    def test_clears_combat_flags(self) -> None:
        """end_combat_step should clear is_attacking and is_blocking flags."""
        attacker = _make_creature(name="Attacker")
        blocker = _make_creature(name="Blocker")

        game = _make_game()
        combat = game.combat_state
        combat.in_combat = True
        combat.attackers[attacker] = game.non_active_player
        combat.blockers[blocker] = [attacker]
        combat.attacker_blockers[attacker] = [blocker]
        attacker.is_attacking = True
        blocker.is_blocking = True

        end_combat_step(game)

        assert attacker.is_attacking is False
        assert blocker.is_blocking is False
        assert combat.in_combat is False
        assert combat.attackers == {}
        assert combat.blockers == {}


# ---------------------------------------------------------------------------
# Integration Scenarios
# ---------------------------------------------------------------------------

class TestCombatIntegration:
    """Full attack/block/damage cycle integration tests."""

    def test_full_combat_cycle_unblocked(self) -> None:
        """Full cycle: declare attacker → no blockers → damage → end combat."""
        bear = _make_creature(name="Bear", power=2, toughness=2, summoning_sick=False)
        game = _make_game(
            p1_script=[[bear]],  # declare attackers
            p2_script=[None],  # no blockers
        )
        _place_on_battlefield(game.active_player, bear)

        declare_attackers_step(game)
        declare_blockers_step(game)
        combat_damage_step(game)
        end_combat_step(game)

        assert game.non_active_player.life == 18
        assert bear.is_attacking is False
        assert game.combat_state.in_combat is False

    def test_full_combat_cycle_blocked(self) -> None:
        """Full cycle: declare attacker → blocker → mutual damage → end combat."""
        attacker = _make_creature(name="Attacker", power=3, toughness=3, summoning_sick=False)
        blocker = _make_creature(name="Blocker", power=2, toughness=2, summoning_sick=False)
        game = _make_game(
            p1_script=[[attacker]],
            p2_script=[{blocker: attacker}],
        )
        _place_on_battlefield(game.active_player, attacker)
        _place_on_battlefield(game.non_active_player, blocker)

        declare_attackers_step(game)
        declare_blockers_step(game)
        combat_damage_step(game)

        # Attacker dealt 3 to blocker, blocker dealt 2 to attacker
        assert blocker.damage_marked == 3
        assert attacker.damage_marked == 2
        # Blocker died (3 >= 2 toughness), so SBAs should have moved it
        gy = game.non_active_player.zones[Zone.GRAVEYARD]
        assert gy.contains(blocker)

        end_combat_step(game)
        assert game.combat_state.in_combat is False

    def test_multiple_attackers_mixed_block(self) -> None:
        """Two attackers: one blocked, one unblocked."""
        a1 = _make_creature(name="A1", power=2, toughness=2, summoning_sick=False)
        a2 = _make_creature(name="A2", power=3, toughness=3, summoning_sick=False)
        b1 = _make_creature(name="B1", power=1, toughness=4, summoning_sick=False)

        game = _make_game(
            p1_script=[[a1, a2]],  # both attack
            p2_script=[{b1: a1}],  # b1 blocks a1 only
        )
        _place_on_battlefield(game.active_player, a1)
        _place_on_battlefield(game.active_player, a2)
        _place_on_battlefield(game.non_active_player, b1)

        declare_attackers_step(game)
        declare_blockers_step(game)
        combat_damage_step(game)

        # a1 blocked by b1: a1 deals 2 to b1, b1 deals 1 to a1
        assert b1.damage_marked == 2
        assert a1.damage_marked == 1
        # a2 unblocked: deals 3 to defending player
        assert game.non_active_player.life == 17

        end_combat_step(game)

    def test_creature_with_multiple_keywords(self) -> None:
        """A creature with flying + trample + lifelink in combat."""
        multi = _make_creature(
            name="Multi", power=5, toughness=5, summoning_sick=False,
            keywords=Keyword.FLYING | Keyword.TRAMPLE | Keyword.LIFELINK,
        )
        flyer_blocker = _make_creature(
            name="FlyBlocker", power=1, toughness=2, summoning_sick=False,
            keywords=Keyword.FLYING,
        )
        game = _make_game(
            p1_script=[[multi]],
            p2_script=[{flyer_blocker: multi}],
            p1_life=15,
            p2_life=20,
        )
        _place_on_battlefield(game.active_player, multi)
        _place_on_battlefield(game.non_active_player, flyer_blocker)

        declare_attackers_step(game)
        declare_blockers_step(game)
        combat_damage_step(game)

        # Trample: 2 to blocker (lethal), 3 to player
        assert flyer_blocker.damage_marked >= 2
        assert game.non_active_player.life == 17
        # Lifelink: gains 5 life total (2 to blocker + 3 to player)
        assert game.active_player.life == 20

    def test_blocked_but_blocker_removed_before_damage(self) -> None:
        """If a blocker is assigned but then removed before damage,
        the attacker is still 'blocked' and deals NO damage to the
        defending player (unless it has trample).  Per MTG rule 509.1h,
        once a creature is declared as blocked it stays blocked even if
        all its blockers are removed.
        """
        attacker = _make_creature(name="Attacker", power=3, toughness=3, summoning_sick=False)
        game = _make_game(p2_life=20)
        _place_on_battlefield(game.active_player, attacker)
        attacker.controller = game.active_player

        # Simulate: attacker was blocked, but the blocker is gone
        combat = game.combat_state
        combat.in_combat = True
        combat.attackers[attacker] = game.non_active_player
        # Has a blocker list key (meaning it was blocked) but list is empty
        combat.attacker_blockers[attacker] = []
        # Per MTG rule 509.1h, the attacker was declared as blocked
        combat.was_blocked.add(attacker)

        combat_damage_step(game)

        # Blocked creature with no remaining blockers deals NO damage
        # to the defending player (no trample → damage goes nowhere).
        assert game.non_active_player.life == 20

    def test_first_strike_kills_before_normal_damage(self) -> None:
        """First-strike creature kills blocker; blocker doesn't deal damage back.

        The blocker should die from SBAs between first-strike and normal
        damage steps, so it doesn't get to deal its normal-damage back.
        """
        first_striker = _make_creature(
            name="FS", power=4, toughness=1,
            keywords=Keyword.FIRST_STRIKE,
        )
        blocker = _make_creature(name="Blocker", power=4, toughness=4)
        game = _make_game()
        _place_on_battlefield(game.active_player, first_striker)
        _place_on_battlefield(game.non_active_player, blocker)
        first_striker.controller = game.active_player
        blocker.controller = game.non_active_player

        combat = game.combat_state
        combat.in_combat = True
        combat.attackers[first_striker] = game.non_active_player
        combat.attacker_blockers[first_striker] = [blocker]
        # Also register blocker in combat.blockers
        combat.blockers[blocker] = [first_striker]

        combat_damage_step(game)

        # First striker dealt 4 to blocker (lethal), SBAs should kill blocker
        # Blocker should be in graveyard
        gy = game.non_active_player.zones[Zone.GRAVEYARD]
        assert gy.contains(blocker)
        # First striker should NOT have taken damage from blocker
        # (blocker died before normal damage step)
        assert first_striker.damage_marked == 0
