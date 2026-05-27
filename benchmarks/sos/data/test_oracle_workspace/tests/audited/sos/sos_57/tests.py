"""Rewritten audited tests for Mana Sculpt (sos_57).

7 tests per spec:
1. test_identity — name, mana_cost {1}{U}{U}, CMC 3, Instant type, Blue color
2. test_get_targets_returns_stack_spells — cast a spell onto the stack,
   verify Mana Sculpt's targeting can target it (NOT gated on method existence)
3. test_get_targets_excludes_permanents — permanents on battlefield are NOT targets
4. test_counters_via_real_cast — opponent's spell countered (moved to GY, on_resolve
   not invoked)
5. test_refund_with_wizard — Wizard present → colorless mana refund
6. test_no_refund_without_wizard — no Wizard → no mana refund
7. test_fizzle_when_target_removed — target removed before resolution → fizzle

Bug pattern addressed: tests must verify BEHAVIOR not method existence.
No `callable(getattr(card, "get_targets", None))` pattern allowed.
"""

from __future__ import annotations

import pytest

from card_impl import ManaSculpt

from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import (
    card_colors,
    create_game,
    set_battlefield,
    set_mana_pool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wizard(name: str = "Sage of Fables") -> Creature:
    """Create a Wizard creature for testing the Wizard-conditional refund."""
    return Creature(name=name, base_power=2, base_toughness=2, subtypes={"Wizard"})


def _make_opponent_spell(name: str = "Lightning Bolt", owner=None) -> Instant:
    """Create a simple opponent spell."""
    return Instant(
        name=name,
        owner=owner,
        mana_cost=ManaCost(generic=0, pips={ManaType.RED: 1}),
    )


def _put_spell_on_stack(game, spell, controller) -> StackObject:
    """Place a spell on the game stack and return the stack object."""
    spell.owner = controller
    spell.controller = controller
    stack_obj = StackObject(source=spell, controller=controller)
    game.stack.push(stack_obj)
    controller.zones[Zone.STACK].add(spell)
    return stack_obj


# ---------------------------------------------------------------------------
# Test 1: Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    """Verify static card properties match card_spec.json."""

    def test_identity(self) -> None:
        """Mana Sculpt: name, {1}{U}{U}, CMC 3, Instant, Blue."""
        card = ManaSculpt(name="Mana Sculpt", owner=None)

        # Name
        assert card.name == "Mana Sculpt"

        # Mana cost: {1}{U}{U}
        assert card.mana_cost.generic == 1
        assert card.mana_cost.pips.get(ManaType.BLUE) == 2

        # CMC = 3
        assert card.mana_cost.cmc == 3

        # Card type: Instant
        assert CardType.INSTANT in card.card_types
        assert isinstance(card, Instant)

        # Color: Blue
        colors = card_colors(card)
        assert "U" in colors
        assert len(colors) == 1, f"Expected only Blue, got {colors}"


# ---------------------------------------------------------------------------
# Test 2: get_targets returns stack spells
# ---------------------------------------------------------------------------


class TestGetTargetsReturnsStackSpells:
    """Verify targeting finds spells on the stack — NOT gated on method existence."""

    def test_get_targets_returns_stack_spells(self) -> None:
        """Cast a spell onto the stack; Mana Sculpt's targets include it."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put opponent's spell on the stack
        enemy_spell = _make_opponent_spell("Enemy Bolt", owner=p2)
        stack_obj = _put_spell_on_stack(game, enemy_spell, p2)

        # Create Mana Sculpt and get targets
        card = ManaSculpt(name="Mana Sculpt", owner=p1)
        card.controller = p1
        targets = card.get_targets(game)

        # The opponent's spell on the stack must be a valid target
        assert stack_obj in targets, (
            f"Stack spell should be a valid target. Targets: {targets}"
        )


# ---------------------------------------------------------------------------
# Test 3: get_targets excludes permanents
# ---------------------------------------------------------------------------


class TestGetTargetsExcludesPermanents:
    """Verify permanents on the battlefield are NOT valid targets."""

    def test_get_targets_excludes_permanents(self) -> None:
        """Creatures on the battlefield must not appear in get_targets."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put creatures on the battlefield
        bear = Creature(name="Bear", owner=p1, base_power=2, base_toughness=2)
        set_battlefield(game, 0, [bear])

        enemy_creature = Creature(name="Goblin", owner=p2, base_power=1, base_toughness=1)
        set_battlefield(game, 1, [enemy_creature])

        # Mana Sculpt should have NO targets (nothing on stack)
        card = ManaSculpt(name="Mana Sculpt", owner=p1)
        card.controller = p1
        targets = card.get_targets(game)

        # Permanents must not be valid targets
        assert bear not in targets, "Battlefield creature should not be a target"
        assert enemy_creature not in targets, "Opponent's creature should not be a target"
        assert len(targets) == 0, (
            f"With empty stack and only permanents, targets should be empty. Got: {targets}"
        )


# ---------------------------------------------------------------------------
# Test 4: Counters via real cast (on_resolve not invoked on target)
# ---------------------------------------------------------------------------


class TestCountersViaRealCast:
    """Cast opponent's spell, counter with Mana Sculpt, verify counter behavior."""

    def test_counters_via_real_cast(self) -> None:
        """Opponent's spell is countered: moved to graveyard, its on_resolve NOT called."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Track whether the target's on_resolve is called
        resolve_called = []

        class TrackedSpell(Instant):
            def on_resolve(self, game):
                resolve_called.append(True)

        target_spell = TrackedSpell(
            name="Enemy Spell",
            owner=p2,
            mana_cost=ManaCost(generic=2, pips={ManaType.RED: 1}),
        )
        target_spell.controller = p2

        # Put opponent's spell on the stack
        stack_obj = _put_spell_on_stack(game, target_spell, p2)

        # Cast Mana Sculpt targeting that spell
        mana_sculpt = ManaSculpt(name="Mana Sculpt", owner=p1)
        mana_sculpt.controller = p1
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        # Target spell must be removed from the stack
        remaining_on_stack = list(game.stack.objects())
        assert stack_obj not in remaining_on_stack, (
            "Countered spell should be removed from the stack"
        )

        # Target's on_resolve must NOT have been called
        assert len(resolve_called) == 0, (
            "Countered spell's on_resolve should NOT be invoked"
        )

        # Target spell should be in owner's graveyard
        gy_cards = p2.zones[Zone.GRAVEYARD].get_all()
        assert target_spell in gy_cards, (
            f"Countered spell should be in graveyard. GY: "
            f"{[getattr(c, 'name', c) for c in gy_cards]}"
        )


# ---------------------------------------------------------------------------
# Test 5: Refund with Wizard
# ---------------------------------------------------------------------------


class TestRefundWithWizard:
    """Controller has a Wizard → gets colorless mana equal to countered spell's cost."""

    def test_refund_with_wizard(self) -> None:
        """With a Wizard on battlefield, controller gets {C} equal to countered spell's CMC."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put a Wizard on p1's battlefield
        wizard = _make_wizard("Test Wizard")
        set_battlefield(game, 0, [wizard])

        # Empty p1's mana pool to verify refund
        set_mana_pool(game, 0, {})

        # Opponent casts a 3-CMC spell
        target_spell = Instant(
            name="Expensive Spell",
            owner=p2,
            mana_cost=ManaCost(generic=2, pips={ManaType.RED: 1}),
        )
        target_spell.controller = p2
        stack_obj = _put_spell_on_stack(game, target_spell, p2)

        # Resolve Mana Sculpt
        mana_sculpt = ManaSculpt(name="Mana Sculpt", owner=p1)
        mana_sculpt.controller = p1
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        # Verify mana refund: controller should get colorless mana = countered spell's CMC (3)
        # The refund happens "at the beginning of your next main phase" per oracle text,
        # but implementations may grant it immediately or via delayed trigger.
        # We check that p1's mana pool eventually contains the refund amount.
        colorless_mana = p1.mana_pool.get(ManaType.COLORLESS)
        assert colorless_mana >= 3, (
            f"With Wizard, should refund {3} colorless mana. "
            f"Got: {colorless_mana}"
        )


# ---------------------------------------------------------------------------
# Test 6: No refund without Wizard
# ---------------------------------------------------------------------------


class TestNoRefundWithoutWizard:
    """Controller has NO Wizard → no mana refund after countering."""

    def test_no_refund_without_wizard(self) -> None:
        """Without a Wizard, no mana is refunded after countering."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # No Wizard on p1's battlefield — just a non-Wizard creature
        bear = Creature(name="Bear", owner=p1, base_power=2, base_toughness=2,
                        subtypes={"Beast"})
        set_battlefield(game, 0, [bear])

        # Empty p1's mana pool
        set_mana_pool(game, 0, {})

        # Opponent's spell
        target_spell = Instant(
            name="Expensive Spell",
            owner=p2,
            mana_cost=ManaCost(generic=2, pips={ManaType.RED: 1}),
        )
        target_spell.controller = p2
        stack_obj = _put_spell_on_stack(game, target_spell, p2)

        # Resolve Mana Sculpt
        mana_sculpt = ManaSculpt(name="Mana Sculpt", owner=p1)
        mana_sculpt.controller = p1
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        # Verify NO mana refund
        colorless_mana = p1.mana_pool.get(ManaType.COLORLESS)
        assert colorless_mana == 0, (
            f"Without Wizard, should NOT refund any mana. Got: {colorless_mana}"
        )


# ---------------------------------------------------------------------------
# Test 7: Fizzle when target removed
# ---------------------------------------------------------------------------


class TestFizzleWhenTargetRemoved:
    """If the target spell is removed from the stack before resolution, Mana Sculpt fizzles."""

    def test_fizzle_when_target_removed(self) -> None:
        """Target removed from stack before resolution → Mana Sculpt does nothing."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put a Wizard on p1's battlefield (to verify no refund on fizzle either)
        wizard = _make_wizard("Test Wizard")
        set_battlefield(game, 0, [wizard])
        set_mana_pool(game, 0, {})

        # Opponent's spell on stack
        target_spell = Instant(
            name="Vanishing Spell",
            owner=p2,
            mana_cost=ManaCost(generic=1, pips={ManaType.BLACK: 1}),
        )
        target_spell.controller = p2
        stack_obj = _put_spell_on_stack(game, target_spell, p2)

        # Mana Sculpt targets the spell
        mana_sculpt = ManaSculpt(name="Mana Sculpt", owner=p1)
        mana_sculpt.controller = p1
        mana_sculpt.chosen_targets = [stack_obj]

        # Remove target from stack BEFORE resolution (simulating another counter)
        game.stack._items.remove(stack_obj)

        # Resolve Mana Sculpt — should fizzle (no effect)
        mana_sculpt.on_resolve(game)

        # Graveyard should NOT have the target (it was already removed elsewhere)
        gy_cards = p2.zones[Zone.GRAVEYARD].get_all()
        target_in_gy = any(
            getattr(c, "name", None) == "Vanishing Spell" for c in gy_cards
        )
        # The spell was removed from the stack by other means — Mana Sculpt
        # should not move it to graveyard again or have any effect
        assert not target_in_gy, (
            "Fizzled Mana Sculpt should not move already-removed spell to graveyard"
        )

        # No mana refund on fizzle (even with Wizard)
        colorless_mana = p1.mana_pool.get(ManaType.COLORLESS)
        assert colorless_mana == 0, (
            f"Fizzled spell should not grant mana refund. Got: {colorless_mana}"
        )
