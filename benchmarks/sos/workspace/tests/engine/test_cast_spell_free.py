"""Tests for cast_spell_free — casting without paying mana costs via the stack.

Verifies:
- cast_spell_free places the spell on the stack (not directly resolving it)
- The spell can be countered while on the stack
- On resolution, permanents go to battlefield, non-permanents to graveyard
- No mana payment is required
- The card's source zone (e.g., exile) is handled correctly
- on_resolve is called only when the spell actually resolves from the stack
"""

from __future__ import annotations

import pytest

from engine.card import (
    Creature,
    Instant,
    Sorcery,
)
from engine.casting import cast_spell_free
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    *,
    p1_script: list | None = None,
    p2_script: list | None = None,
    phase: Phase = Phase.PRECOMBAT_MAIN,
) -> GameState:
    """Create a minimal 2-player GameState at the specified phase."""
    p1 = DeterministicPlayer("Alice", p1_script or [])
    p2 = DeterministicPlayer("Bob", p2_script or [])
    game = GameState([p1, p2])
    game.phase = phase
    return game


def _put_in_exile(game: GameState, player_idx: int, card) -> None:
    """Place a card in the player's exile zone."""
    player = game.players[player_idx]
    player.zones[Zone.EXILE].add(card)


# ---------------------------------------------------------------------------
# Tests: cast_spell_free puts spell on the stack
# ---------------------------------------------------------------------------

class TestCastSpellFreePutsOnStack:
    """cast_spell_free must place the spell on the stack, not resolve immediately."""

    def test_creature_goes_on_stack(self):
        """A creature cast for free should appear on the stack."""
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Grizzly Bears",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _put_in_exile(game, 0, bear)

        cast_spell_free(game, player, bear, from_zone=Zone.EXILE)

        assert not game.stack.is_empty()
        top = game.stack.peek()
        assert top is not None
        assert top.source is bear
        assert top.controller is player

    def test_sorcery_goes_on_stack(self):
        """A sorcery cast for free should appear on the stack."""
        game = _make_game()
        player = game.players[0]
        spell = Sorcery(
            name="Divination",
            mana_cost=ManaCost(generic=2, pips={ManaType.BLUE: 1}),
        )
        _put_in_exile(game, 0, spell)

        cast_spell_free(game, player, spell, from_zone=Zone.EXILE)

        assert not game.stack.is_empty()
        top = game.stack.peek()
        assert top.source is spell

    def test_instant_goes_on_stack(self):
        """An instant cast for free should appear on the stack."""
        game = _make_game()
        player = game.players[0]
        bolt = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost(pips={ManaType.RED: 1}),
        )
        _put_in_exile(game, 0, bolt)

        cast_spell_free(game, player, bolt, from_zone=Zone.EXILE)

        assert not game.stack.is_empty()
        top = game.stack.peek()
        assert top.source is bolt


# ---------------------------------------------------------------------------
# Tests: No mana required
# ---------------------------------------------------------------------------

class TestCastSpellFreeNoManaRequired:
    """cast_spell_free should not require or consume mana."""

    def test_expensive_creature_cast_with_empty_mana_pool(self):
        """A 6-mana creature can be cast for free with zero mana available."""
        game = _make_game()
        player = game.players[0]
        # Player has no mana in pool
        big_creature = Creature(
            name="Colossal Dreadmaw",
            mana_cost=ManaCost(generic=4, pips={ManaType.GREEN: 2}),
            base_power=6, base_toughness=6,
        )
        _put_in_exile(game, 0, big_creature)

        # Should not raise — no mana needed
        cast_spell_free(game, player, big_creature, from_zone=Zone.EXILE)

        assert not game.stack.is_empty()
        assert game.stack.peek().source is big_creature


# ---------------------------------------------------------------------------
# Tests: Resolution behavior
# ---------------------------------------------------------------------------

class TestCastSpellFreeResolution:
    """When the stack object resolves, it should behave like a normal spell."""

    def test_creature_resolves_to_battlefield(self):
        """A creature that resolves from cast_spell_free goes to battlefield."""
        game = _make_game()
        player = game.players[0]
        bear = Creature(
            name="Grizzly Bears",
            mana_cost=ManaCost(generic=1, pips={ManaType.GREEN: 1}),
            base_power=2, base_toughness=2,
        )
        _put_in_exile(game, 0, bear)

        cast_spell_free(game, player, bear, from_zone=Zone.EXILE)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_battlefield(player).contains(bear)

    def test_sorcery_resolves_to_graveyard(self):
        """A sorcery that resolves from cast_spell_free goes to graveyard."""
        game = _make_game()
        player = game.players[0]
        spell = Sorcery(
            name="Lava Axe",
            mana_cost=ManaCost(generic=4, pips={ManaType.RED: 1}),
        )
        _put_in_exile(game, 0, spell)

        cast_spell_free(game, player, spell, from_zone=Zone.EXILE)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert game.get_graveyard(player).contains(spell)

    def test_on_resolve_hook_called(self):
        """The card's on_resolve method should be called during resolution."""
        game = _make_game()
        player = game.players[0]
        resolved_flag = []

        class TrackerSorcery(Sorcery):
            def on_resolve(self, game):
                resolved_flag.append(True)

        spell = TrackerSorcery(
            name="Tracker",
            mana_cost=ManaCost(pips={ManaType.BLUE: 1}),
        )
        _put_in_exile(game, 0, spell)

        cast_spell_free(game, player, spell, from_zone=Zone.EXILE)

        # on_resolve should NOT have been called yet (spell is on stack)
        assert resolved_flag == []

        obj = game.stack.pop()
        obj.on_resolve(game)

        # Now on_resolve should have been called
        assert resolved_flag == [True]


# ---------------------------------------------------------------------------
# Tests: Counterspell interaction (the key requirement)
# ---------------------------------------------------------------------------

class TestCastSpellFreeCounterable:
    """A spell cast via cast_spell_free must be counterable on the stack.

    This is the primary requirement from the TODO: the spell goes through
    the stack so effects like Counterspell can target it.
    """

    def test_spell_is_on_stack_and_can_be_removed_before_resolving(self):
        """Simulates countering: pop the spell off the stack without resolving.

        If the spell bypassed the stack (old behavior), it would never be
        visible on the stack and could not be interacted with.
        """
        game = _make_game()
        player = game.players[0]
        spell = Sorcery(
            name="Explosive Vegetation",
            mana_cost=ManaCost(generic=3, pips={ManaType.GREEN: 1}),
        )
        _put_in_exile(game, 0, spell)

        cast_spell_free(game, player, spell, from_zone=Zone.EXILE)

        # The spell is on the stack — an opponent could counter it
        assert not game.stack.is_empty()
        stack_obj = game.stack.peek()
        assert stack_obj.source is spell

        # Simulate counter: remove from stack, move to graveyard
        countered_obj = game.stack.pop()
        assert countered_obj.source is spell
        # After countering, the spell should NOT be on the battlefield
        assert not game.get_battlefield(player).contains(spell)

    def test_multiple_free_casts_all_go_on_stack(self):
        """When multiple spells are cast for free, all should be on the stack.

        This allows an opponent to counter any of them individually.
        """
        game = _make_game()
        player = game.players[0]
        spell_a = Sorcery(name="Spell A", mana_cost=ManaCost(generic=1))
        spell_b = Creature(
            name="Spell B",
            mana_cost=ManaCost(generic=2),
            base_power=2, base_toughness=2,
        )
        _put_in_exile(game, 0, spell_a)
        _put_in_exile(game, 0, spell_b)

        cast_spell_free(game, player, spell_a, from_zone=Zone.EXILE)
        cast_spell_free(game, player, spell_b, from_zone=Zone.EXILE)

        assert len(game.stack) == 2

    def test_countered_spell_does_not_resolve(self):
        """A spell removed from the stack (countered) should not call on_resolve."""
        game = _make_game()
        player = game.players[0]
        resolved_flag = []

        class TrackerCreature(Creature):
            def on_resolve(self, game):
                resolved_flag.append(True)

        critter = TrackerCreature(
            name="Tracker Beast",
            mana_cost=ManaCost(generic=3, pips={ManaType.GREEN: 1}),
            base_power=4, base_toughness=4,
        )
        _put_in_exile(game, 0, critter)

        cast_spell_free(game, player, critter, from_zone=Zone.EXILE)

        # Counter it — just pop without calling on_resolve
        game.stack.pop()

        assert resolved_flag == []
        assert not game.get_battlefield(player).contains(critter)


# ---------------------------------------------------------------------------
# Tests: Real counterspell integration
# ---------------------------------------------------------------------------

class TestCastSpellFreeCounteredByRealCounter:
    """Integration tests using the engine's _counter_spell mechanic.

    These prove that a Counterspell-style effect can properly target and
    counter a spell placed on the stack via cast_spell_free.
    """

    def test_counter_spell_removes_free_cast_from_stack_to_graveyard(self):
        """_counter_spell targeting a free-cast spell removes it and moves card to graveyard."""
        from cards.fdn.fdn_160.card_impl import _counter_spell

        game = _make_game()
        player = game.players[0]
        spell = Sorcery(
            name="Explosive Vegetation",
            mana_cost=ManaCost(generic=3, pips={ManaType.GREEN: 1}),
        )
        spell.owner = player
        _put_in_exile(game, 0, spell)

        cast_spell_free(game, player, spell, from_zone=Zone.EXILE)

        # The spell is on the stack
        assert not game.stack.is_empty()
        stack_obj = game.stack.peek()
        assert stack_obj.source is spell

        # Use the real _counter_spell function to counter it
        _counter_spell(game, stack_obj)

        # After countering: stack is empty, spell is in owner's graveyard
        assert game.stack.is_empty()
        assert game.get_graveyard(player).contains(spell)
        assert not game.get_battlefield(player).contains(spell)

    def test_counter_spell_prevents_on_resolve_from_firing(self):
        """A countered free-cast spell's on_resolve never executes."""
        from cards.fdn.fdn_160.card_impl import _counter_spell

        game = _make_game()
        player = game.players[0]
        resolved_flag = []

        class TrackerSorcery(Sorcery):
            def on_resolve(self, game):
                resolved_flag.append(True)

        spell = TrackerSorcery(
            name="Tracked Spell",
            mana_cost=ManaCost(generic=2, pips={ManaType.BLUE: 1}),
        )
        spell.owner = player
        _put_in_exile(game, 0, spell)

        cast_spell_free(game, player, spell, from_zone=Zone.EXILE)
        stack_obj = game.stack.peek()

        # Counter it using the real counter mechanic
        _counter_spell(game, stack_obj)

        # on_resolve should never have been called
        assert resolved_flag == []

    def test_counter_creature_free_cast_prevents_battlefield_entry(self):
        """A creature countered after cast_spell_free never enters the battlefield."""
        from cards.fdn.fdn_160.card_impl import _counter_spell

        game = _make_game()
        player = game.players[0]
        creature = Creature(
            name="Colossal Dreadmaw",
            mana_cost=ManaCost(generic=4, pips={ManaType.GREEN: 2}),
            base_power=6, base_toughness=6,
        )
        creature.owner = player
        _put_in_exile(game, 0, creature)

        cast_spell_free(game, player, creature, from_zone=Zone.EXILE)
        stack_obj = game.stack.peek()

        _counter_spell(game, stack_obj)

        # Creature should be in graveyard, not battlefield
        assert game.stack.is_empty()
        assert game.get_graveyard(player).contains(creature)
        assert not game.get_battlefield(player).contains(creature)

    def test_counter_targets_specific_spell_among_multiple_on_stack(self):
        """When multiple free-cast spells are on the stack, counter targets only one."""
        from cards.fdn.fdn_160.card_impl import _counter_spell

        game = _make_game()
        player = game.players[0]

        spell_a = Sorcery(name="Spell A", mana_cost=ManaCost(generic=1))
        spell_a.owner = player
        spell_b = Sorcery(name="Spell B", mana_cost=ManaCost(generic=2))
        spell_b.owner = player

        _put_in_exile(game, 0, spell_a)
        _put_in_exile(game, 0, spell_b)

        cast_spell_free(game, player, spell_a, from_zone=Zone.EXILE)
        cast_spell_free(game, player, spell_b, from_zone=Zone.EXILE)

        assert len(game.stack) == 2

        # Counter only spell_a (the bottom spell)
        # Find its stack object
        all_objs = game.stack.objects()
        spell_a_obj = next(obj for obj in all_objs if obj.source is spell_a)

        _counter_spell(game, spell_a_obj)

        # Only spell_a countered; spell_b remains on stack
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell_b
        assert game.get_graveyard(player).contains(spell_a)
        assert not game.get_graveyard(player).contains(spell_b)
