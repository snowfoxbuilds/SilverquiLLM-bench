"""Rewritten audited tests for Great Hall of the Biblioplex (sos_257).

17 tests covering three sub-mechanics:
  (a) Mana abilities: colorless tap, any-color restricted tap
  (b) Persistent animation: 2/4 Wizard creature, no auto-cleanup
  (c) Prowess-like trigger: +1/+0 until end of turn on instant/sorcery cast

Tests:
  1.  test_identity — Land type, correct name
  2.  test_mana_adds_colorless — {T}: Add {C}
  3.  test_mana_adds_any_color — {T}, Pay 1 life: Add one mana of any color
  4.  test_restricted_spend_legal — restricted mana can pay for instant via cast_spell
  5.  test_restricted_spend_illegal — restricted mana cannot pay for creature via cast_spell
  6.  test_animation_persists_across_turns — stays a creature after engine cleanup step
  7.  test_no_op_when_already_creature — re-animation gated by "if not a creature"
  8.  test_animation_cleared_on_leaves_play — state resets via move_to_zone
  9.  test_activation_cost_payment — requires 5 mana to animate
  10. test_animated_can_attack — creature can attack (summoning sickness permitting)
  11. test_boost_on_instant — +1/+0 when controller casts instant
  12. test_boost_on_sorcery — +1/+0 when controller casts sorcery
  13. test_opponent_cast_filter — opponent's spell doesn't trigger boost
  14. test_end_of_turn_revert — +1/+0 reverts via engine cleanup but animation persists
  15. test_trigger_inactive_when_unanimated — no trigger when not a creature
  16. test_animation_gives_creature_type — creature type Wizard, P/T 2/4
  17. test_multiple_triggers_stack — two spells give +2/+0
"""

from __future__ import annotations

import pytest

from card_impl import GreatHallOfTheBiblioplex

from engine.card import Instant, Land, Sorcery, Creature
from engine.events import SpellCastTriggeredEvent
from engine.turn import _do_cleanup_step
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from engine.zones import move_to_zone
from test_utils import (
    advance_to_phase,
    assert_casting_error,
    card_colors,
    cast_spell,
    create_game,
    resolve_top,
    set_battlefield,
    set_hand,
    set_mana_pool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hall_on_battlefield(mana_amount: int = 0):
    """Create a game with Great Hall on player 0's battlefield.

    Returns (game, hall, player).
    """
    game = create_game()
    player = game.players[0]
    hall = GreatHallOfTheBiblioplex(owner=player)
    hall.controller = player
    set_battlefield(game, 0, [hall])
    if mana_amount > 0:
        set_mana_pool(game, 0, {ManaType.COLORLESS: mana_amount})
    return game, hall, player


def _animate_hall(game, hall, player):
    """Give player enough mana and activate animation (ability_index=2)."""
    set_mana_pool(game, 0, {ManaType.COLORLESS: 5})
    result = hall.activate(game, ability_index=2)
    assert result is True, "Animation activation should succeed"
    return result


def _fire_spell_cast_trigger(game, caster, spell):
    """Fire a SpellCastTriggeredEvent and resolve the resulting trigger."""
    event = SpellCastTriggeredEvent(
        spell=spell,
        player=caster,
        card=spell,
        controller=caster,
    )
    game.trigger_manager.fire_event(game, event)
    # Resolve the trigger that was pushed to the stack
    if not game.stack.is_empty():
        resolve_top(game)


# ---------------------------------------------------------------------------
# Test 1: Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    """Verify card is a Land type with correct name."""

    def test_identity(self) -> None:
        """Great Hall of the Biblioplex is a Land with CMC 0, colorless."""
        card = GreatHallOfTheBiblioplex(owner=None)

        assert card.name == "Great Hall of the Biblioplex"
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types
        assert card.mana_cost.cmc == 0
        assert len(card_colors(card)) == 0


# ---------------------------------------------------------------------------
# Sub-mechanic (a): Mana abilities
# ---------------------------------------------------------------------------


class TestManaAbilities:
    """Two mana abilities including restricted spend."""

    def test_mana_adds_colorless(self) -> None:
        """First tap ability adds {C} to controller's mana pool."""
        game, hall, player = _make_hall_on_battlefield()

        assert player.mana_pool.total() == 0
        result = hall.activate(game, ability_index=0)
        assert result is True
        assert hall.is_tapped is True
        assert player.mana_pool.get(ManaType.COLORLESS) >= 1

    def test_mana_adds_any_color(self) -> None:
        """Second tap ability adds one mana (pays 1 life) — restricted."""
        game, hall, player = _make_hall_on_battlefield()
        initial_life = player.life

        result = hall.activate(game, ability_index=1)
        assert result is True
        assert hall.is_tapped is True
        assert player.life == initial_life - 1
        # Mana was added to the pool
        assert player.mana_pool.total() >= 1

    def test_restricted_spend_legal(self) -> None:
        """Restricted mana can successfully pay for an instant spell via cast_spell.

        Activate the restricted mana ability, put an instant in hand with
        cost {1}, then cast it. The cast should succeed — restricted mana
        is legal for instants.
        """
        game, hall, player = _make_hall_on_battlefield()

        # Activate restricted mana ability (produces 1 mana)
        hall.activate(game, ability_index=1)
        assert player.mana_pool.total() >= 1

        # Put an instant with cost {1} in hand
        bolt = Instant(name="Lightning Bolt", owner=player, mana_cost=ManaCost(generic=1))
        bolt.controller = player
        set_hand(game, 0, [bolt])

        # Ensure we are at sorcery speed for the cast (main phase, active player)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0

        # Cast should succeed — restricted mana is valid for instant/sorcery
        cast_spell(game, 0, "Lightning Bolt")

    def test_restricted_spend_illegal(self) -> None:
        """Restricted mana cannot pay for a creature spell via cast_spell.

        Activate the restricted mana ability (only source of mana), put a
        creature with cost {1} in hand, then attempt to cast it. The cast
        should fail because restricted mana cannot be spent on creatures.
        """
        game, hall, player = _make_hall_on_battlefield()

        # Activate restricted mana ability (produces 1 mana)
        hall.activate(game, ability_index=1)
        assert player.mana_pool.total() >= 1

        # Put a creature with cost {1} in hand
        bear = Creature(name="Grizzly Bears", owner=player, mana_cost=ManaCost(generic=1))
        bear.controller = player
        set_hand(game, 0, [bear])

        # Ensure we are at sorcery speed for the cast
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0

        # Cast should FAIL — restricted mana cannot be spent on creatures
        with assert_casting_error():
            cast_spell(game, 0, "Grizzly Bears")


# ---------------------------------------------------------------------------
# Sub-mechanic (b): Persistent animation
# ---------------------------------------------------------------------------


class TestPersistentAnimation:
    """Animation persists, gated, clears on leave."""

    def test_animation_persists_across_turns(self) -> None:
        """Once animated, the engine's cleanup step does NOT remove creature type.

        Uses _do_cleanup_step (the engine's turn cleanup path) rather than
        calling hall.end_of_turn_cleanup() directly, verifying the engine
        lifecycle integration.
        """
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        assert CardType.CREATURE in hall.card_types

        # Advance game state to cleanup step and execute it via engine path
        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        _do_cleanup_step(game)

        # Animation persists through the engine's end-of-turn cleanup
        assert CardType.CREATURE in hall.card_types
        assert hall.power == 2
        assert hall.toughness == 4

    def test_no_op_when_already_creature(self) -> None:
        """Activating animation when already a creature returns False (no-op)."""
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        assert CardType.CREATURE in hall.card_types
        # Try to animate again with fresh mana
        set_mana_pool(game, 0, {ManaType.COLORLESS: 5})
        result = hall.activate(game, ability_index=2)
        assert result is False, "Should be no-op when already a creature"

    def test_animation_cleared_on_leaves_play(self) -> None:
        """Animation state resets when card leaves the battlefield via move_to_zone.

        Uses the engine's move_to_zone (which calls on_leave_battlefield
        internally) rather than calling hall.on_leave_battlefield() directly.
        """
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        assert CardType.CREATURE in hall.card_types

        # Move the card off the battlefield via engine zone-move path
        move_to_zone(game, hall, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        # Animation should be cleared by the engine's leave-battlefield hook
        assert CardType.CREATURE not in hall.card_types
        assert hall.power == 0
        assert hall.toughness == 0

    def test_activation_cost_payment(self) -> None:
        """Animation requires 5 mana — fails with insufficient mana."""
        game, hall, player = _make_hall_on_battlefield()
        # Only 4 mana available
        set_mana_pool(game, 0, {ManaType.COLORLESS: 4})
        result = hall.activate(game, ability_index=2)
        assert result is False
        assert CardType.CREATURE not in hall.card_types

    def test_animated_can_attack(self) -> None:
        """Once animated (and summoning sickness cleared), it's a valid attacker."""
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        # Verify it's a creature (attackable)
        assert CardType.CREATURE in hall.card_types
        # Clear summoning sickness (simulating a turn passing)
        hall.summoning_sick = False
        # It should be a valid attacker: is a creature, untapped, no summoning sickness
        assert not hall.is_tapped
        assert not hall.summoning_sick

    def test_animation_gives_creature_type(self) -> None:
        """After animation, has Wizard subtype and 2/4 P/T."""
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        assert "Wizard" in hall.subtypes
        assert hall.power == 2
        assert hall.toughness == 4
        # Still a land
        assert CardType.LAND in hall.card_types


# ---------------------------------------------------------------------------
# Sub-mechanic (c): Spell-cast trigger (+1/+0)
# ---------------------------------------------------------------------------


class TestSpellCastTrigger:
    """Prowess-like trigger granting +1/+0 until end of turn."""

    def test_boost_on_instant(self) -> None:
        """When controller casts an instant, animated Great Hall gets +1/+0."""
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        assert hall.power == 2
        spell = Instant(name="Lightning Bolt", owner=player)
        _fire_spell_cast_trigger(game, player, spell)
        assert hall.power == 3

    def test_boost_on_sorcery(self) -> None:
        """When controller casts a sorcery, animated Great Hall gets +1/+0."""
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        assert hall.power == 2
        spell = Sorcery(name="Divination", owner=player)
        _fire_spell_cast_trigger(game, player, spell)
        assert hall.power == 3

    def test_opponent_cast_filter(self) -> None:
        """Opponent casting instant/sorcery does NOT trigger the boost."""
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        opponent = game.players[1]
        spell = Instant(name="Counterspell", owner=opponent)
        _fire_spell_cast_trigger(game, opponent, spell)
        assert hall.power == 2, "Opponent's spell should not boost"

    def test_end_of_turn_revert(self) -> None:
        """At end of turn, +1/+0 boost reverts via engine cleanup but animation persists.

        Uses _do_cleanup_step (the engine's cleanup path) rather than
        calling hall.end_of_turn_cleanup() directly.
        """
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        spell = Instant(name="Bolt", owner=player)
        _fire_spell_cast_trigger(game, player, spell)
        assert hall.power == 3

        # Run engine cleanup step
        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        _do_cleanup_step(game)

        assert hall.power == 2, "Boost should revert after engine cleanup"
        assert CardType.CREATURE in hall.card_types, "Animation should persist"

    def test_trigger_inactive_when_unanimated(self) -> None:
        """If Great Hall is not animated, trigger doesn't fire."""
        game, hall, player = _make_hall_on_battlefield()
        # Do NOT animate
        assert CardType.CREATURE not in hall.card_types

        spell = Instant(name="Bolt", owner=player)
        _fire_spell_cast_trigger(game, player, spell)
        # Power should remain 0 (not animated)
        assert hall.power == 0

    def test_multiple_triggers_stack(self) -> None:
        """Casting 2 spells gives +2/+0 total."""
        game, hall, player = _make_hall_on_battlefield()
        _animate_hall(game, hall, player)

        assert hall.power == 2
        spell1 = Instant(name="Bolt", owner=player)
        spell2 = Sorcery(name="Divination", owner=player)
        _fire_spell_cast_trigger(game, player, spell1)
        _fire_spell_cast_trigger(game, player, spell2)
        assert hall.power == 4, "Two spells should give +2/+0"
