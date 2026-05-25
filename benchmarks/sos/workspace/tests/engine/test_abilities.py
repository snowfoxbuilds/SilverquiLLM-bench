"""Tests for engine/abilities.py — Activated abilities system.

Covers:
- ActivatedAbilityInstance dataclass construction and fields.
- LoyaltyAbilityInstance dataclass construction and fields.
- activate_ability: mana ability → resolves immediately (no stack), effect applied.
- activate_ability: non-mana ability → pushes StackObject to stack.
- tap_cost: succeeds when untapped, fails when already tapped, sets is_tapped.
- Timing checks: regular activated abilities work at instant speed (no sorcery restriction).
- Mana abilities bypass timing checks entirely (resolve immediately).
- Only loyalty abilities have sorcery-speed restriction.
- LoyaltyAbility: loyalty counter adjustment (+N, −N).
- LoyaltyAbility: once-per-turn restriction.
- LoyaltyAbility: once-per-turn resets after clear_loyalty_tracking.
- LoyaltyAbility: insufficient loyalty for −N cost → AbilityError.
- Cost payment failure → AbilityError, no stack entry.
- Integration: land tap-for-mana → mana added and card tapped.
- Multiple abilities on the same source.
- Edge cases: unknown ability type, zero loyalty cost, etc.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.abilities import (
    AbilityError,
    ActivatedAbilityInstance,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
    tap_cost,
)
from benchmarks.sos.workspace.engine.card import Land, Planeswalker
from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.types import ManaType, Phase, Step


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker():
    """Ensure the module-level loyalty tracker is clean for every test."""
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _make_game(
    *,
    p1_script: list | None = None,
    p2_script: list | None = None,
    phase: Phase = Phase.PRECOMBAT_MAIN,
    step: Step | None = None,
) -> GameState:
    """Create a minimal 2-player GameState at the specified phase/step."""
    p1 = DeterministicPlayer("Alice", p1_script or [])
    p2 = DeterministicPlayer("Bob", p2_script or [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = step
    return game


def _sorcery_speed_game() -> GameState:
    """Return a game where sorcery-speed timing is met for the active player."""
    return _make_game(phase=Phase.PRECOMBAT_MAIN, step=None)


def _instant_speed_game() -> GameState:
    """Return a game where sorcery-speed timing is NOT met (combat phase)."""
    return _make_game(phase=Phase.COMBAT, step=Step.DECLARE_ATTACKERS)


# ---------------------------------------------------------------------------
# ActivatedAbilityInstance — construction
# ---------------------------------------------------------------------------


class TestActivatedAbilityInstanceConstruction:
    """ActivatedAbilityInstance dataclass stores all expected fields."""

    def test_fields_assigned(self):
        source = object()
        controller = DeterministicPlayer("Alice", [])
        cost = lambda g, s: True
        effect = lambda g: None
        ability = ActivatedAbilityInstance(
            source=source,
            controller=controller,
            cost=cost,
            effect=effect,
            is_mana_ability=True,
            description="Tap for mana",
        )
        assert ability.source is source
        assert ability.controller is controller
        assert ability.cost is cost
        assert ability.effect is effect
        assert ability.is_mana_ability is True
        assert ability.description == "Tap for mana"

    def test_defaults(self):
        source = object()
        controller = DeterministicPlayer("Alice", [])
        ability = ActivatedAbilityInstance(
            source=source,
            controller=controller,
            cost=lambda g, s: True,
            effect=lambda g: None,
        )
        assert ability.is_mana_ability is False
        assert ability.description == ""


# ---------------------------------------------------------------------------
# LoyaltyAbilityInstance — construction
# ---------------------------------------------------------------------------


class TestLoyaltyAbilityInstanceConstruction:
    """LoyaltyAbilityInstance dataclass stores all expected fields."""

    def test_fields_assigned(self):
        source = object()
        controller = DeterministicPlayer("Alice", [])
        effect = lambda g: None
        ability = LoyaltyAbilityInstance(
            source=source,
            controller=controller,
            loyalty_cost=-3,
            effect=effect,
            description="Destroy target creature",
        )
        assert ability.source is source
        assert ability.controller is controller
        assert ability.loyalty_cost == -3
        assert ability.effect is effect
        assert ability.description == "Destroy target creature"

    def test_defaults(self):
        source = object()
        controller = DeterministicPlayer("Alice", [])
        ability = LoyaltyAbilityInstance(
            source=source,
            controller=controller,
        )
        assert ability.loyalty_cost == 0
        assert ability.description == ""
        # default effect should be callable
        ability.effect(None)  # should not raise


# ---------------------------------------------------------------------------
# tap_cost helper
# ---------------------------------------------------------------------------


class TestTapCost:
    """tap_cost checks untapped state and sets is_tapped = True."""

    def test_untapped_source_returns_true(self):
        game = _sorcery_speed_game()
        source = Land(name="Forest")
        assert source.is_tapped is False
        result = tap_cost(game, source)
        assert result is True

    def test_untapped_source_becomes_tapped(self):
        game = _sorcery_speed_game()
        source = Land(name="Forest")
        tap_cost(game, source)
        assert source.is_tapped is True

    def test_already_tapped_source_returns_false(self):
        game = _sorcery_speed_game()
        source = Land(name="Forest")
        source.is_tapped = True
        result = tap_cost(game, source)
        assert result is False

    def test_already_tapped_source_stays_tapped(self):
        game = _sorcery_speed_game()
        source = Land(name="Forest")
        source.is_tapped = True
        tap_cost(game, source)
        assert source.is_tapped is True

    def test_source_without_is_tapped_attribute(self):
        """Source with no is_tapped attribute is treated as untapped."""
        game = _sorcery_speed_game()

        class Bare:
            pass

        source = Bare()
        result = tap_cost(game, source)
        assert result is True
        assert source.is_tapped is True


# ---------------------------------------------------------------------------
# activate_ability — mana ability (resolves immediately)
# ---------------------------------------------------------------------------


class TestActivateManaAbility:
    """Mana abilities resolve immediately without using the stack."""

    def test_mana_ability_does_not_push_to_stack(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        source = Land(name="Forest")
        effect_called = []
        ability = ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: effect_called.append(True),
            is_mana_ability=True,
        )
        activate_ability(game, player, ability)
        assert game.stack.is_empty()

    def test_mana_ability_effect_is_called_immediately(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        source = Land(name="Forest")
        effect_called = []
        ability = ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: effect_called.append(True),
            is_mana_ability=True,
        )
        activate_ability(game, player, ability)
        assert len(effect_called) == 1

    def test_mana_ability_bypasses_timing_check(self):
        """Mana abilities can be activated even at non-sorcery-speed timing."""
        game = _instant_speed_game()
        player = game.players[0]
        source = Land(name="Forest")
        effect_called = []
        ability = ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: effect_called.append(True),
            is_mana_ability=True,
        )
        # Should not raise — mana abilities ignore sorcery-speed timing.
        activate_ability(game, player, ability)
        assert len(effect_called) == 1

    def test_mana_ability_during_non_active_player_turn(self):
        """Mana abilities can be activated even by non-active player."""
        game = _instant_speed_game()
        non_active = game.players[1]
        effect_called = []
        source = Land(name="Island")
        ability = ActivatedAbilityInstance(
            source=source,
            controller=non_active,
            cost=lambda g, s: True,
            effect=lambda g: effect_called.append(True),
            is_mana_ability=True,
        )
        # Should not raise — mana abilities can be activated at any time.
        activate_ability(game, non_active, ability)
        assert len(effect_called) == 1

    def test_mana_ability_cost_failure_raises(self):
        """If the cost of a mana ability cannot be paid, AbilityError is raised."""
        game = _sorcery_speed_game()
        player = game.players[0]
        source = Land(name="Forest")
        source.is_tapped = True
        ability = ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=tap_cost,
            effect=lambda g: None,
            is_mana_ability=True,
        )
        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, player, ability)


# ---------------------------------------------------------------------------
# activate_ability — non-mana ability (pushes to stack)
# ---------------------------------------------------------------------------


class TestActivateNonManaAbility:
    """Non-mana activated abilities go on the stack."""

    def test_pushes_stack_object(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        source = object()
        ability = ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: None,
            is_mana_ability=False,
        )
        activate_ability(game, player, ability)
        assert not game.stack.is_empty()

    def test_stack_object_has_correct_source(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        source = object()
        ability = ActivatedAbilityInstance(
            source=source,
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        top = game.stack.peek()
        assert top is not None
        assert top.source is source

    def test_stack_object_has_correct_controller(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        top = game.stack.peek()
        assert top.controller is player

    def test_stack_object_on_resolve_is_ability_effect(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        resolved = []
        effect = lambda g: resolved.append("resolved")
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: True,
            effect=effect,
        )
        activate_ability(game, player, ability)
        top = game.stack.peek()
        top.on_resolve(game)
        assert resolved == ["resolved"]

    def test_stack_object_is_not_mana_ability(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        top = game.stack.peek()
        assert top.is_mana_ability is False

    def test_effect_not_called_on_activation(self):
        """Non-mana abilities effect should NOT be called immediately."""
        game = _sorcery_speed_game()
        player = game.players[0]
        effect_called = []
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: effect_called.append(True),
        )
        activate_ability(game, player, ability)
        assert len(effect_called) == 0


# ---------------------------------------------------------------------------
# Timing checks for non-mana abilities
# ---------------------------------------------------------------------------


class TestNonManaAbilityTiming:
    """Regular (non-mana) activated abilities work at instant speed.

    They can be activated whenever a player has priority — during any
    phase/step, even with items on the stack.  Priority enforcement is
    handled externally by ``priority_loop``, not by ``activate_ability``.
    Only *loyalty* abilities carry a sorcery-speed restriction.
    """

    def test_allowed_during_combat(self):
        """Regular abilities can be activated during combat (instant speed)."""
        game = _instant_speed_game()
        player = game.players[0]
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: None,
            is_mana_ability=False,
        )
        # Should not raise — regular abilities are instant speed.
        activate_ability(game, player, ability)
        assert not game.stack.is_empty()

    def test_allowed_when_stack_not_empty(self):
        """Regular abilities can be activated even when the stack has items."""
        game = _sorcery_speed_game()
        player = game.players[0]
        # Put something on the stack.
        game.stack.push(StackObject(source=object(), controller=player))
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: None,
            is_mana_ability=False,
        )
        # Should not raise — regular abilities work at instant speed.
        activate_ability(game, player, ability)
        # Stack should now have 2 items (the existing one + the new ability).
        assert game.stack.peek() is not None

    def test_allowed_for_non_active_player(self):
        """Regular abilities can be activated by non-active player (with priority)."""
        game = _sorcery_speed_game()
        non_active = game.players[1]
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=non_active,
            cost=lambda g, s: True,
            effect=lambda g: None,
            is_mana_ability=False,
        )
        # Should not raise — priority enforcement is external.
        activate_ability(game, non_active, ability)
        assert not game.stack.is_empty()

    def test_allowed_during_end_step(self):
        """Regular abilities can be activated during the end step."""
        game = _make_game(phase=Phase.ENDING, step=Step.END)
        player = game.players[0]
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: True,
            effect=lambda g: None,
            is_mana_ability=False,
        )
        activate_ability(game, player, ability)
        assert not game.stack.is_empty()


# ---------------------------------------------------------------------------
# Cost payment failure
# ---------------------------------------------------------------------------


class TestCostPaymentFailure:
    """If cost returns False, AbilityError is raised and nothing is pushed."""

    def test_cost_failure_raises_ability_error(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: False,
            effect=lambda g: None,
        )
        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, player, ability)

    def test_cost_failure_leaves_stack_empty(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: False,
            effect=lambda g: None,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, player, ability)
        assert game.stack.is_empty()

    def test_cost_failure_effect_not_called(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        effect_called = []
        ability = ActivatedAbilityInstance(
            source=object(),
            controller=player,
            cost=lambda g, s: False,
            effect=lambda g: effect_called.append(True),
        )
        with pytest.raises(AbilityError):
            activate_ability(game, player, ability)
        assert len(effect_called) == 0


# ---------------------------------------------------------------------------
# LoyaltyAbility — positive cost (+N)
# ---------------------------------------------------------------------------


class TestLoyaltyAbilityPositiveCost:
    """Loyalty ability with positive cost increases loyalty counters."""

    def test_positive_loyalty_cost_increases_loyalty(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=3)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=2,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        assert pw.loyalty == 5

    def test_positive_cost_pushes_to_stack(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=3)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        assert not game.stack.is_empty()


# ---------------------------------------------------------------------------
# LoyaltyAbility — negative cost (−N)
# ---------------------------------------------------------------------------


class TestLoyaltyAbilityNegativeCost:
    """Loyalty ability with negative cost decreases loyalty counters."""

    def test_negative_loyalty_cost_decreases_loyalty(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=5)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=-3,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        assert pw.loyalty == 2

    def test_negative_cost_exact_loyalty(self):
        """Using -N when loyalty == N should succeed and set loyalty to 0."""
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=4)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=-4,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        assert pw.loyalty == 0

    def test_insufficient_loyalty_raises(self):
        """Cannot activate −N if source loyalty < N."""
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=2)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=-5,
            effect=lambda g: None,
        )
        with pytest.raises(AbilityError, match="insufficient loyalty"):
            activate_ability(game, player, ability)

    def test_insufficient_loyalty_no_stack_entry(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=1)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=-3,
            effect=lambda g: None,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, player, ability)
        assert game.stack.is_empty()

    def test_insufficient_loyalty_does_not_change_loyalty(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=2)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=-5,
            effect=lambda g: None,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, player, ability)
        assert pw.loyalty == 2  # unchanged


# ---------------------------------------------------------------------------
# LoyaltyAbility — zero cost
# ---------------------------------------------------------------------------


class TestLoyaltyAbilityZeroCost:
    """Loyalty ability with zero cost leaves loyalty unchanged."""

    def test_zero_loyalty_cost_does_not_change_loyalty(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=3)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=0,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        assert pw.loyalty == 3


# ---------------------------------------------------------------------------
# LoyaltyAbility — once-per-turn restriction
# ---------------------------------------------------------------------------


class TestLoyaltyOncePerTurn:
    """Only one loyalty ability per source per turn."""

    def test_second_activation_same_turn_raises(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=10)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        # First activation succeeds.
        activate_ability(game, player, ability)
        # Clear the stack so sorcery-speed check still passes.
        game.stack.pop()
        # Second activation should fail.
        with pytest.raises(AbilityError, match="already activated this turn"):
            activate_ability(game, player, ability)

    def test_second_activation_no_stack_entry(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=10)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        game.stack.pop()
        with pytest.raises(AbilityError):
            activate_ability(game, player, ability)
        assert game.stack.is_empty()

    def test_clear_loyalty_tracking_allows_reactivation(self):
        """Simulates a new turn by calling clear_loyalty_tracking."""
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=10)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        game.stack.pop()  # clear stack for sorcery-speed
        # Clearing the tracking simulates a new turn starting.
        clear_loyalty_tracking()
        # Now activation should succeed again.
        activate_ability(game, player, ability)
        assert not game.stack.is_empty()

    def test_different_turn_number_allows_reactivation(self):
        """Different turn number means the once-per-turn has reset."""
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=10)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        game.turn_number = 1
        activate_ability(game, player, ability)
        game.stack.pop()
        # Advance to turn 2.
        game.turn_number = 2
        activate_ability(game, player, ability)
        assert not game.stack.is_empty()

    def test_different_sources_allowed_same_turn(self):
        """Two different planeswalkers can each activate once per turn."""
        game = _sorcery_speed_game()
        player = game.players[0]
        pw1 = Planeswalker(name="Walker1", starting_loyalty=5)
        pw2 = Planeswalker(name="Walker2", starting_loyalty=5)
        ability1 = LoyaltyAbilityInstance(
            source=pw1,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        ability2 = LoyaltyAbilityInstance(
            source=pw2,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability1)
        game.stack.pop()  # clear stack
        activate_ability(game, player, ability2)
        assert not game.stack.is_empty()


# ---------------------------------------------------------------------------
# LoyaltyAbility — timing
# ---------------------------------------------------------------------------


class TestLoyaltyAbilityTiming:
    """Loyalty abilities require sorcery-speed timing."""

    def test_rejected_during_combat(self):
        game = _instant_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=5)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        with pytest.raises(AbilityError, match="sorcery-speed"):
            activate_ability(game, player, ability)

    def test_rejected_for_non_active_player(self):
        game = _sorcery_speed_game()
        non_active = game.players[1]
        pw = Planeswalker(name="TestWalker", starting_loyalty=5)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=non_active,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        with pytest.raises(AbilityError, match="sorcery-speed"):
            activate_ability(game, non_active, ability)


# ---------------------------------------------------------------------------
# Integration: land tap-for-mana
# ---------------------------------------------------------------------------


class TestLandTapForMana:
    """End-to-end: tap a land for mana → mana added and card tapped."""

    def test_land_tap_for_mana_adds_mana_and_taps(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        forest = Land(name="Forest")
        forest.is_tapped = False

        def forest_effect(g: GameState) -> None:
            player.mana_pool.add(ManaType.GREEN, 1)

        ability = ActivatedAbilityInstance(
            source=forest,
            controller=player,
            cost=tap_cost,
            effect=forest_effect,
            is_mana_ability=True,
            description="{T}: Add {G}",
        )
        activate_ability(game, player, ability)
        assert forest.is_tapped is True
        assert player.mana_pool.get(ManaType.GREEN) == 1

    def test_land_tap_for_mana_stack_remains_empty(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        forest = Land(name="Forest")

        ability = ActivatedAbilityInstance(
            source=forest,
            controller=player,
            cost=tap_cost,
            effect=lambda g: player.mana_pool.add(ManaType.GREEN, 1),
            is_mana_ability=True,
        )
        activate_ability(game, player, ability)
        assert game.stack.is_empty()

    def test_tapped_land_cannot_tap_for_mana(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        forest = Land(name="Forest")
        forest.is_tapped = True

        ability = ActivatedAbilityInstance(
            source=forest,
            controller=player,
            cost=tap_cost,
            effect=lambda g: player.mana_pool.add(ManaType.GREEN, 1),
            is_mana_ability=True,
        )
        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, player, ability)
        # Mana pool should be unchanged.
        assert player.mana_pool.get(ManaType.GREEN) == 0

    def test_land_tap_for_mana_at_instant_speed(self):
        """Mana abilities can be activated during combat, etc."""
        game = _instant_speed_game()
        player = game.players[0]
        island = Land(name="Island")

        ability = ActivatedAbilityInstance(
            source=island,
            controller=player,
            cost=tap_cost,
            effect=lambda g: player.mana_pool.add(ManaType.BLUE, 1),
            is_mana_ability=True,
        )
        activate_ability(game, player, ability)
        assert island.is_tapped is True
        assert player.mana_pool.get(ManaType.BLUE) == 1


# ---------------------------------------------------------------------------
# Multiple abilities on the same source
# ---------------------------------------------------------------------------


class TestMultipleAbilitiesSameSource:
    """Multiple abilities on a single permanent."""

    def test_activate_two_different_mana_abilities_on_same_source(self):
        """Example: a dual land with two mana abilities (but requires two taps
        in real MTG — here we test that both abilities are independent)."""
        game = _sorcery_speed_game()
        player = game.players[0]
        dual_land = Land(name="DualLand")

        ability_green = ActivatedAbilityInstance(
            source=dual_land,
            controller=player,
            cost=tap_cost,
            effect=lambda g: player.mana_pool.add(ManaType.GREEN, 1),
            is_mana_ability=True,
        )
        ability_white = ActivatedAbilityInstance(
            source=dual_land,
            controller=player,
            cost=tap_cost,
            effect=lambda g: player.mana_pool.add(ManaType.WHITE, 1),
            is_mana_ability=True,
        )
        # First activation taps the land.
        activate_ability(game, player, ability_green)
        assert dual_land.is_tapped is True
        assert player.mana_pool.get(ManaType.GREEN) == 1

        # Second activation fails because the land is already tapped.
        with pytest.raises(AbilityError, match="cost could not be paid"):
            activate_ability(game, player, ability_white)
        # White mana should not have been added.
        assert player.mana_pool.get(ManaType.WHITE) == 0


# ---------------------------------------------------------------------------
# Unknown ability type
# ---------------------------------------------------------------------------


class TestUnknownAbilityType:
    """activate_ability rejects unknown ability types."""

    def test_unknown_type_raises(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        with pytest.raises(AbilityError, match="Unknown ability type"):
            activate_ability(game, player, "not an ability")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Loyalty stack object properties
# ---------------------------------------------------------------------------


class TestLoyaltyStackObject:
    """Verify the StackObject pushed by loyalty ability has correct properties."""

    def test_stack_object_source_is_planeswalker(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=5)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        top = game.stack.peek()
        assert top.source is pw

    def test_stack_object_controller_is_player(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=5)
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: None,
        )
        activate_ability(game, player, ability)
        top = game.stack.peek()
        assert top.controller is player

    def test_stack_object_on_resolve_invokes_effect(self):
        game = _sorcery_speed_game()
        player = game.players[0]
        pw = Planeswalker(name="TestWalker", starting_loyalty=5)
        resolved = []
        ability = LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=1,
            effect=lambda g: resolved.append("done"),
        )
        activate_ability(game, player, ability)
        top = game.stack.peek()
        top.on_resolve(game)
        assert resolved == ["done"]
