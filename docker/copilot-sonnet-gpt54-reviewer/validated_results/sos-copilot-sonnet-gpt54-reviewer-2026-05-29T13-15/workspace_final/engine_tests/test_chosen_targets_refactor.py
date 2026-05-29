"""Tests for chosen_targets refactor — targets live on StackObject, not card.

Verifies:
- card.chosen_targets is NOT set at cast time
- StackObject.targets holds targets between cast and resolve
- card.chosen_targets IS set at resolve time (backward compat)
- Targets are available to on_resolve callbacks
- Multiple spells on the stack have independent targets
- Cloned/copied cards don't inherit stale targets from the original
"""

from __future__ import annotations

import copy

import pytest

from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.casting import cast_spell, CastingError
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, Step


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


def _add_to_hand(game: GameState, player_idx: int, card: CardImpl) -> None:
    game.get_hand(game.players[player_idx]).add(card)


def _add_mana(player: DeterministicPlayer, mana_type: ManaType, amount: int) -> None:
    player.mana_pool.add(mana_type, amount)


# ---------------------------------------------------------------------------
# Test cards
# ---------------------------------------------------------------------------

class _TargetedBolt(Instant):
    """An instant that requires one target."""

    def get_targets(self, game: GameState):
        return ["any_target"]


class _TargetedSorcery(Sorcery):
    """A sorcery that requires one target."""

    def get_targets(self, game: GameState):
        return ["any_target"]

    def on_resolve(self, game: GameState) -> None:
        # on_resolve reads chosen_targets for backward compat
        self._resolved_targets = getattr(self, "chosen_targets", None)


class _MultiTargetSpell(Instant):
    """An instant that requires two targets."""

    def get_targets(self, game: GameState):
        return ["target_spec_a", "target_spec_b"]

    def on_resolve(self, game: GameState) -> None:
        self._resolved_targets = getattr(self, "chosen_targets", None)


# ---------------------------------------------------------------------------
# card.chosen_targets NOT set at cast time
# ---------------------------------------------------------------------------

class TestChosenTargetsNotSetAtCastTime:
    """After cast_spell(), card.chosen_targets must NOT be set."""

    def test_targeted_instant_no_chosen_targets_after_cast(self):
        """Casting a targeted instant should NOT set card.chosen_targets."""
        game = _make_game(p1_script=["goblin"])
        player = game.players[0]
        bolt = _TargetedBolt(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, bolt)

        # chosen_targets should not exist on the card after casting
        assert not hasattr(bolt, "chosen_targets"), (
            "card.chosen_targets should not be set at cast time"
        )

    def test_targeted_sorcery_no_chosen_targets_after_cast(self):
        """Casting a targeted sorcery should NOT set card.chosen_targets."""
        game = _make_game(p1_script=["enemy_creature"])
        player = game.players[0]
        spell = _TargetedSorcery(
            name="Fireball", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, spell)

        assert not hasattr(spell, "chosen_targets"), (
            "card.chosen_targets should not be set at cast time"
        )

    def test_no_targets_spell_no_chosen_targets_after_cast(self):
        """A spell with no targets should also not set chosen_targets at cast."""
        game = _make_game()
        player = game.players[0]
        spell = Instant(name="Opt", mana_cost=ManaCost(pips={ManaType.BLUE: 1}))
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.BLUE, 1)

        cast_spell(game, player, spell)

        assert not hasattr(spell, "chosen_targets"), (
            "card.chosen_targets should not be set at cast time for targetless spells"
        )


# ---------------------------------------------------------------------------
# StackObject.targets holds targets between cast and resolve
# ---------------------------------------------------------------------------

class TestStackObjectTargets:
    """StackObject.targets is the single source of truth between cast and resolve."""

    def test_stack_object_stores_chosen_targets(self):
        """After cast_spell, StackObject.targets should contain the chosen targets."""
        game = _make_game(p1_script=["target_goblin"])
        player = game.players[0]
        bolt = _TargetedBolt(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, bolt)

        top = game.stack.peek()
        assert top is not None
        assert top.targets == ["target_goblin"]

    def test_stack_object_targets_for_multi_target_spell(self):
        """Multi-target spells should store all targets on StackObject."""
        game = _make_game(p1_script=["creature_a", "creature_b"])
        player = game.players[0]
        spell = _MultiTargetSpell(
            name="DualStrike", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, spell)

        top = game.stack.peek()
        assert top.targets == ["creature_a", "creature_b"]

    def test_no_targets_spell_has_empty_targets_on_stack(self):
        """A spell with no targets should have empty list on StackObject."""
        game = _make_game()
        player = game.players[0]
        spell = Instant(name="Opt", mana_cost=ManaCost(pips={ManaType.BLUE: 1}))
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.BLUE, 1)

        cast_spell(game, player, spell)

        top = game.stack.peek()
        assert top.targets == []


# ---------------------------------------------------------------------------
# card.chosen_targets IS set at resolve time
# ---------------------------------------------------------------------------

class TestChosenTargetsSetAtResolveTime:
    """card.chosen_targets must be set at resolve time for backward compat."""

    def test_chosen_targets_set_on_card_during_resolution(self):
        """After on_resolve, card.chosen_targets should be set."""
        game = _make_game(p1_script=["enemy_creature"])
        player = game.players[0]
        spell = _TargetedSorcery(
            name="Fireball", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, spell)

        # Before resolve: no chosen_targets on card
        assert not hasattr(spell, "chosen_targets")

        # Resolve
        obj = game.stack.pop()
        obj.on_resolve(game)

        # After resolve: chosen_targets set on card
        assert hasattr(spell, "chosen_targets"), (
            "card.chosen_targets should be set at resolve time"
        )
        assert spell.chosen_targets == ["enemy_creature"]

    def test_chosen_targets_available_inside_on_resolve_callback(self):
        """The on_resolve callback should be able to read card.chosen_targets."""
        game = _make_game(p1_script=["target_elf"])
        player = game.players[0]
        spell = _TargetedSorcery(
            name="Doom", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, spell)
        obj = game.stack.pop()
        obj.on_resolve(game)

        # The on_resolve callback stored what it saw
        assert spell._resolved_targets == ["target_elf"]

    def test_multi_target_available_in_on_resolve(self):
        """Multi-target chosen_targets should be fully available in on_resolve."""
        game = _make_game(p1_script=["alpha", "beta"])
        player = game.players[0]
        spell = _MultiTargetSpell(
            name="DualStrike", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, spell)
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert spell._resolved_targets == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# Multiple spells on the stack have independent targets
# ---------------------------------------------------------------------------

class TestMultipleSpellsIndependentTargets:
    """Each StackObject maintains its own independent targets list."""

    def test_two_spells_different_targets_on_stack(self):
        """Two spells on the stack should have different, independent targets."""
        game = _make_game(p1_script=["target_a", "target_b"])
        player = game.players[0]

        bolt1 = _TargetedBolt(
            name="Bolt1", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        bolt2 = _TargetedBolt(
            name="Bolt2", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )

        _add_to_hand(game, 0, bolt1)
        _add_to_hand(game, 0, bolt2)
        _add_mana(player, ManaType.RED, 2)

        cast_spell(game, player, bolt1)
        cast_spell(game, player, bolt2)

        objects = game.stack.objects()  # top to bottom
        assert len(objects) == 2
        # bolt2 is on top (LIFO)
        assert objects[0].targets == ["target_b"]
        assert objects[1].targets == ["target_a"]

    def test_resolving_first_does_not_affect_second_targets(self):
        """Resolving one spell doesn't change the other's StackObject targets."""
        game = _make_game(p1_script=["victim_a", "victim_b"])
        player = game.players[0]

        spell1 = _TargetedBolt(
            name="Spell1", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        spell2 = _TargetedBolt(
            name="Spell2", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )

        _add_to_hand(game, 0, spell1)
        _add_to_hand(game, 0, spell2)
        _add_mana(player, ManaType.RED, 2)

        cast_spell(game, player, spell1)
        cast_spell(game, player, spell2)

        # Resolve top (spell2)
        top = game.stack.pop()
        top.on_resolve(game)

        # The remaining stack object still has its own targets
        remaining = game.stack.peek()
        assert remaining.targets == ["victim_a"]


# ---------------------------------------------------------------------------
# Cloned/copied cards don't inherit stale targets
# ---------------------------------------------------------------------------

class TestNoStaleTargetLeakage:
    """Cloned or shallow-copied cards should not carry stale chosen_targets."""

    def test_copy_before_resolve_has_no_chosen_targets(self):
        """Copying a card between cast and resolve: copy has no chosen_targets."""
        game = _make_game(p1_script=["some_target"])
        player = game.players[0]
        spell = _TargetedSorcery(
            name="Original", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, spell)

        # Copy the card before resolution
        clone = copy.copy(spell)

        # Neither original nor clone should have chosen_targets before resolve
        assert not hasattr(spell, "chosen_targets")
        assert not hasattr(clone, "chosen_targets")

    def test_resolve_original_does_not_affect_clone(self):
        """After resolving the original, a pre-resolve clone stays clean."""
        game = _make_game(p1_script=["the_target"])
        player = game.players[0]
        spell = _TargetedSorcery(
            name="Original", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        cast_spell(game, player, spell)

        # Clone before resolve
        clone = copy.copy(spell)

        # Resolve the original
        obj = game.stack.pop()
        obj.on_resolve(game)

        # Original gets chosen_targets from resolution
        assert hasattr(spell, "chosen_targets")
        assert spell.chosen_targets == ["the_target"]

        # Clone should NOT have chosen_targets (it was copied before resolve)
        assert not hasattr(clone, "chosen_targets")
