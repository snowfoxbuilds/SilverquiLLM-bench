"""Tests for chosen_targets refactor — targets live on StackObject, not card.

Verifies:
- card.chosen_targets is NOT set at cast time
- StackObject.targets holds targets between cast and resolve
- card.chosen_targets IS set at resolve time (backward compat)
- Targets are available to on_resolve callbacks
- Multiple spells on the stack have independent targets
- Cloned/copied cards don't inherit stale targets from the original

Targets are answered through the Player Query / Intent protocol: each test card
defines a real ``get_targets`` (a battlefield-creature ``TargetRequirement``), and
the casting player carries an Intent that prefers a specific creature for the
target query the engine raises during casting.
"""

from __future__ import annotations

import copy

import pytest

from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.casting import cast_spell, CastingError
from engine.decisions import Decision, GameRef
from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer, Intent
from engine.stack import StackObject
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Phase,
    Step,
    TargetRequirement,
    Zone,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(*, phase: Phase = Phase.PRECOMBAT_MAIN) -> GameState:
    """Create a minimal 2-player GameState at the specified phase."""
    p1 = DeterministicPlayer("Alice")
    p2 = DeterministicPlayer("Bob")
    game = GameState([p1, p2])
    game.phase = phase
    return game


def _add_to_hand(game: GameState, player_idx: int, card: CardImpl) -> None:
    game.get_hand(game.players[player_idx]).add(card)


def _add_mana(player: DeterministicPlayer, mana_type: ManaType, amount: int) -> None:
    player.mana_pool.add(mana_type, amount)


def _put_creature(game: GameState, player_idx: int, name: str, slot: int = 0) -> Creature:
    """Put a vanilla creature on a player's battlefield and return it.

    The creature is given an engine-minted ``instance_id`` so a test can
    reference it in an Intent preference, and a ``slot`` marker so multi-target
    spells can offer disjoint option sets across their target queries.
    """
    player = game.players[player_idx]
    creature = Creature(
        name=name,
        mana_cost=ManaCost(pips={ManaType.GREEN: 1}),
        base_power=2,
        base_toughness=2,
    )
    creature.owner = player
    creature.controller = player
    creature.slot = slot
    player.zones[Zone.BATTLEFIELD].add(creature)
    creature.instance_id = game.refs.instance_id(creature, Zone.BATTLEFIELD.value)
    return creature


def _target_creature_spec(slot: int | None = None) -> TargetRequirement:
    """A creature-target requirement, optionally restricted to a ``slot``.

    Restricting by ``slot`` lets a multi-target spell raise two queries with
    disjoint option sets (the engine raises one query per spec and does not
    track cross-query target distinctness).
    """
    def _ok(obj: object) -> bool:
        if CardType.CREATURE not in getattr(obj, "card_types", set()):
            return False
        return slot is None or getattr(obj, "slot", None) == slot

    return TargetRequirement(
        filter_fn=_ok,
        description="target creature",
        zone=Zone.BATTLEFIELD,
    )


def _aim(player: DeterministicPlayer, card_name: str, targets) -> None:
    """Start an Intent on *player* preferring *targets* for *card_name*'s query."""
    prefs = tuple(Decision.obj(instance=t.instance_id) for t in targets)
    player.start_intent(
        card_name,
        Intent(
            pattern=GameRef(card=frozenset({("name", card_name)})),
            preferences=prefs,
        ),
    )


# ---------------------------------------------------------------------------
# Test cards
# ---------------------------------------------------------------------------

class _TargetedBolt(Instant):
    """An instant that requires one creature target."""

    def get_targets(self, game: GameState):
        return [_target_creature_spec()]


class _TargetedSorcery(Sorcery):
    """A sorcery that requires one creature target."""

    def get_targets(self, game: GameState):
        return [_target_creature_spec()]

    def on_resolve(self, game: GameState) -> None:
        # on_resolve reads chosen_targets for backward compat
        self._resolved_targets = getattr(self, "chosen_targets", None)


class _MultiTargetSpell(Instant):
    """An instant that requires two creature targets."""

    def get_targets(self, game: GameState):
        return [_target_creature_spec(slot=0), _target_creature_spec(slot=1)]

    def on_resolve(self, game: GameState) -> None:
        self._resolved_targets = getattr(self, "chosen_targets", None)


# ---------------------------------------------------------------------------
# card.chosen_targets NOT set at cast time
# ---------------------------------------------------------------------------

class TestChosenTargetsNotSetAtCastTime:
    """After cast_spell(), card.chosen_targets must NOT be set."""

    def test_targeted_instant_no_chosen_targets_after_cast(self):
        """Casting a targeted instant should NOT set card.chosen_targets."""
        game = _make_game()
        player = game.players[0]
        goblin = _put_creature(game, 1, "Goblin")
        bolt = _TargetedBolt(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "Bolt", [goblin])
        cast_spell(game, player, bolt)
        player.end_intent("Bolt")

        # chosen_targets should not exist on the card after casting
        assert not hasattr(bolt, "chosen_targets"), (
            "card.chosen_targets should not be set at cast time"
        )

    def test_targeted_sorcery_no_chosen_targets_after_cast(self):
        """Casting a targeted sorcery should NOT set card.chosen_targets."""
        game = _make_game()
        player = game.players[0]
        enemy = _put_creature(game, 1, "Enemy Creature")
        spell = _TargetedSorcery(
            name="Fireball", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "Fireball", [enemy])
        cast_spell(game, player, spell)
        player.end_intent("Fireball")

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
        game = _make_game()
        player = game.players[0]
        goblin = _put_creature(game, 1, "Target Goblin")
        bolt = _TargetedBolt(name="Bolt", mana_cost=ManaCost(pips={ManaType.RED: 1}))
        _add_to_hand(game, 0, bolt)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "Bolt", [goblin])
        cast_spell(game, player, bolt)
        player.end_intent("Bolt")

        top = game.stack.peek()
        assert top is not None
        assert top.targets == [goblin]

    def test_stack_object_targets_for_multi_target_spell(self):
        """Multi-target spells should store all targets on StackObject."""
        game = _make_game()
        player = game.players[0]
        creature_a = _put_creature(game, 1, "Creature A", slot=0)
        creature_b = _put_creature(game, 1, "Creature B", slot=1)
        spell = _MultiTargetSpell(
            name="DualStrike", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "DualStrike", [creature_a, creature_b])
        cast_spell(game, player, spell)
        player.end_intent("DualStrike")

        top = game.stack.peek()
        assert top.targets == [creature_a, creature_b]

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
        game = _make_game()
        player = game.players[0]
        enemy = _put_creature(game, 1, "Enemy Creature")
        spell = _TargetedSorcery(
            name="Fireball", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "Fireball", [enemy])
        cast_spell(game, player, spell)
        player.end_intent("Fireball")

        # Before resolve: no chosen_targets on card
        assert not hasattr(spell, "chosen_targets")

        # Resolve
        obj = game.stack.pop()
        obj.on_resolve(game)

        # After resolve: chosen_targets set on card
        assert hasattr(spell, "chosen_targets"), (
            "card.chosen_targets should be set at resolve time"
        )
        assert spell.chosen_targets == [enemy]

    def test_chosen_targets_available_inside_on_resolve_callback(self):
        """The on_resolve callback should be able to read card.chosen_targets."""
        game = _make_game()
        player = game.players[0]
        elf = _put_creature(game, 1, "Target Elf")
        spell = _TargetedSorcery(
            name="Doom", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "Doom", [elf])
        cast_spell(game, player, spell)
        player.end_intent("Doom")
        obj = game.stack.pop()
        obj.on_resolve(game)

        # The on_resolve callback stored what it saw
        assert spell._resolved_targets == [elf]

    def test_multi_target_available_in_on_resolve(self):
        """Multi-target chosen_targets should be fully available in on_resolve."""
        game = _make_game()
        player = game.players[0]
        alpha = _put_creature(game, 1, "Alpha", slot=0)
        beta = _put_creature(game, 1, "Beta", slot=1)
        spell = _MultiTargetSpell(
            name="DualStrike", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "DualStrike", [alpha, beta])
        cast_spell(game, player, spell)
        player.end_intent("DualStrike")
        obj = game.stack.pop()
        obj.on_resolve(game)

        assert spell._resolved_targets == [alpha, beta]


# ---------------------------------------------------------------------------
# Multiple spells on the stack have independent targets
# ---------------------------------------------------------------------------

class TestMultipleSpellsIndependentTargets:
    """Each StackObject maintains its own independent targets list."""

    def test_two_spells_different_targets_on_stack(self):
        """Two spells on the stack should have different, independent targets."""
        game = _make_game()
        player = game.players[0]
        target_a = _put_creature(game, 1, "Target A")
        target_b = _put_creature(game, 1, "Target B")

        bolt1 = _TargetedBolt(
            name="Bolt1", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        bolt2 = _TargetedBolt(
            name="Bolt2", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )

        _add_to_hand(game, 0, bolt1)
        _add_to_hand(game, 0, bolt2)
        _add_mana(player, ManaType.RED, 2)

        _aim(player, "Bolt1", [target_a])
        cast_spell(game, player, bolt1)
        player.end_intent("Bolt1")

        _aim(player, "Bolt2", [target_b])
        cast_spell(game, player, bolt2)
        player.end_intent("Bolt2")

        objects = game.stack.objects()  # top to bottom
        assert len(objects) == 2
        # bolt2 is on top (LIFO)
        assert objects[0].targets == [target_b]
        assert objects[1].targets == [target_a]

    def test_resolving_first_does_not_affect_second_targets(self):
        """Resolving one spell doesn't change the other's StackObject targets."""
        game = _make_game()
        player = game.players[0]
        victim_a = _put_creature(game, 1, "Victim A")
        victim_b = _put_creature(game, 1, "Victim B")

        spell1 = _TargetedBolt(
            name="Spell1", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        spell2 = _TargetedBolt(
            name="Spell2", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )

        _add_to_hand(game, 0, spell1)
        _add_to_hand(game, 0, spell2)
        _add_mana(player, ManaType.RED, 2)

        _aim(player, "Spell1", [victim_a])
        cast_spell(game, player, spell1)
        player.end_intent("Spell1")

        _aim(player, "Spell2", [victim_b])
        cast_spell(game, player, spell2)
        player.end_intent("Spell2")

        # Resolve top (spell2)
        top = game.stack.pop()
        top.on_resolve(game)

        # The remaining stack object still has its own targets
        remaining = game.stack.peek()
        assert remaining.targets == [victim_a]


# ---------------------------------------------------------------------------
# Cloned/copied cards don't inherit stale targets
# ---------------------------------------------------------------------------

class TestNoStaleTargetLeakage:
    """Cloned or shallow-copied cards should not carry stale chosen_targets."""

    def test_copy_before_resolve_has_no_chosen_targets(self):
        """Copying a card between cast and resolve: copy has no chosen_targets."""
        game = _make_game()
        player = game.players[0]
        some_target = _put_creature(game, 1, "Some Target")
        spell = _TargetedSorcery(
            name="Original", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "Original", [some_target])
        cast_spell(game, player, spell)
        player.end_intent("Original")

        # Copy the card before resolution
        clone = copy.copy(spell)

        # Neither original nor clone should have chosen_targets before resolve
        assert not hasattr(spell, "chosen_targets")
        assert not hasattr(clone, "chosen_targets")

    def test_resolve_original_does_not_affect_clone(self):
        """After resolving the original, a pre-resolve clone stays clean."""
        game = _make_game()
        player = game.players[0]
        the_target = _put_creature(game, 1, "The Target")
        spell = _TargetedSorcery(
            name="Original", mana_cost=ManaCost(pips={ManaType.RED: 1})
        )
        _add_to_hand(game, 0, spell)
        _add_mana(player, ManaType.RED, 1)

        _aim(player, "Original", [the_target])
        cast_spell(game, player, spell)
        player.end_intent("Original")

        # Clone before resolve
        clone = copy.copy(spell)

        # Resolve the original
        obj = game.stack.pop()
        obj.on_resolve(game)

        # Original gets chosen_targets from resolution
        assert hasattr(spell, "chosen_targets")
        assert spell.chosen_targets == [the_target]

        # Clone should NOT have chosen_targets (it was copied before resolve)
        assert not hasattr(clone, "chosen_targets")
