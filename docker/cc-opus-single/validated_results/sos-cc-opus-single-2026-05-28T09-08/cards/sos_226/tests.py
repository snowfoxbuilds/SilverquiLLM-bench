"""Tests for SOS 226 — Silverquill, the Disputant.

Silverquill, the Disputant is a {2}{W}{B} Legendary Creature — Elder Dragon
with 4/4, flying, vigilance.

Oracle text: "Flying, vigilance
Each instant and sorcery spell you cast has casualty 1. (As you cast that
spell, you may sacrifice a creature with power 1 or greater. When you do,
copy the spell and you may choose new targets for the copy.)"

Test coverage:
- Static card properties (name, cost, types, subtypes, supertypes, P/T, keywords)
- Casualty 1 granting: triggers on controller's instant/sorcery spell cast
- Casualty optional sacrifice mechanic
- Spell copy creation on casualty payment
- Restriction: only controller's instants/sorceries
- Restriction: not opponent's spells
- Restriction: not creature/enchantment/etc. spells
- Power >= 1 requirement for sacrificed creature
"""

from __future__ import annotations

import pytest
from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_silverquill(owner=None, controller=None):
    """Create a Silverquill, the Disputant instance."""
    return SilverquillTheDisputant(owner=owner, controller=controller)


def _make_bear(name="Grizzly Bears", owner=None, controller=None, power=2, toughness=2):
    """Create a vanilla creature token for sacrifice fodder."""
    c = Creature(
        name=name,
        owner=owner,
        controller=controller,
        base_power=power,
        base_toughness=toughness,
    )
    c.is_token = False
    return c


def _make_instant(name="Test Bolt", owner=None, controller=None):
    """Create a simple instant spell."""
    return Instant(
        name=name,
        mana_cost=ManaCost.parse("{R}"),
        owner=owner,
        controller=controller,
        rules_text="Deal 3 damage to any target.",
    )


def _make_sorcery(name="Test Divination", owner=None, controller=None):
    """Create a simple sorcery spell."""
    return Sorcery(
        name=name,
        mana_cost=ManaCost.parse("{2}{U}"),
        owner=owner,
        controller=controller,
        rules_text="Draw two cards.",
    )


# ===========================================================================
# Static Properties
# ===========================================================================


class TestSilverquillProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_creature(self) -> None:
        card = _make_silverquill()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = _make_silverquill()
        assert card.name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        card = _make_silverquill()
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_mana_value_is_four(self) -> None:
        card = _make_silverquill()
        assert card.mana_cost.cmc == 4

    def test_card_type_creature(self) -> None:
        card = _make_silverquill()
        assert CardType.CREATURE in card.card_types

    def test_supertype_legendary(self) -> None:
        card = _make_silverquill()
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_elder_dragon(self) -> None:
        card = _make_silverquill()
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_power_toughness(self) -> None:
        card = _make_silverquill()
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = _make_silverquill()
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = _make_silverquill()
        assert Keyword.VIGILANCE in card.keywords


# ===========================================================================
# Trigger Registration (Casualty granting)
# ===========================================================================


class TestSilverquillTriggerRegistration:
    """Silverquill must register a triggered ability that watches for
    SpellCastTriggeredEvent to implement the casualty 1 granting."""

    def test_registers_trigger_on_battlefield(self) -> None:
        """When Silverquill enters the battlefield, it should register
        at least one trigger for spell-cast events."""
        game = create_game()
        p1 = game.players[0]
        card = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        before_count = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after_count = len(game.trigger_manager.get_triggers())
        assert after_count > before_count

    def test_registered_trigger_watches_spell_cast_event(self) -> None:
        """The trigger should watch SpellCastTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1
        spell_cast_triggers = [
            t for t in triggers
            if t.event_type is SpellCastTriggeredEvent
        ]
        assert len(spell_cast_triggers) >= 1

    def test_trigger_source_is_silverquill(self) -> None:
        """The registered trigger's source must be the Silverquill card."""
        game = create_game()
        p1 = game.players[0]
        card = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert all(t.source is card for t in triggers)

    def test_trigger_controller_is_silverquill_controller(self) -> None:
        """The registered trigger's controller must be Silverquill's controller."""
        game = create_game()
        p1 = game.players[0]
        card = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert all(t.controller is p1 for t in triggers)


# ===========================================================================
# Casualty Condition — Only controller's instants/sorceries
# ===========================================================================


class TestSilverquillCasualtyCondition:
    """The casualty trigger should only fire for the controller's
    instant and sorcery spells, not for opponent's spells or
    non-instant/sorcery spells."""

    def _setup_with_trigger(self):
        """Set up a game with Silverquill on the battlefield and its
        trigger registered. Returns (game, p1, p2, silverquill, trigger)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        spell_cast_triggers = [
            t for t in triggers
            if t.event_type is SpellCastTriggeredEvent
        ]
        assert len(spell_cast_triggers) >= 1
        trigger = spell_cast_triggers[0]
        return game, p1, p2, card, trigger

    def test_condition_true_for_controller_instant(self) -> None:
        """Casualty trigger should match controller's instant spells."""
        game, p1, p2, silverquill, trigger = self._setup_with_trigger()
        instant = _make_instant(owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )
        # Condition should be true (or None meaning always fires)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True
        # If condition is None, it always fires, which is still valid

    def test_condition_true_for_controller_sorcery(self) -> None:
        """Casualty trigger should match controller's sorcery spells."""
        game, p1, p2, silverquill, trigger = self._setup_with_trigger()
        sorcery = _make_sorcery(owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=sorcery, player=p1, card=sorcery, controller=p1,
        )
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True

    def test_condition_false_for_opponent_instant(self) -> None:
        """Casualty trigger should NOT match opponent's spells."""
        game, p1, p2, silverquill, trigger = self._setup_with_trigger()
        instant = _make_instant(owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(
            spell=instant, player=p2, card=instant, controller=p2,
        )
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False
        else:
            # If condition is None, the trigger fires for everything,
            # which is wrong -- it should only fire for controller's spells.
            pytest.fail(
                "Casualty trigger has no condition — it would fire for "
                "opponent's spells, which violates the card's text."
            )

    def test_condition_false_for_controller_creature_spell(self) -> None:
        """Casualty trigger should NOT match non-instant/sorcery spells."""
        game, p1, p2, silverquill, trigger = self._setup_with_trigger()
        creature = Creature(
            name="Test Creature",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        event = SpellCastTriggeredEvent(
            spell=creature, player=p1, card=creature, controller=p1,
        )
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False
        else:
            pytest.fail(
                "Casualty trigger has no condition — it would fire for "
                "creature spells, which violates the card's text."
            )


# ===========================================================================
# Casualty Mechanic — Sacrifice and Copy
# ===========================================================================


class TestSilverquillCasualtyEffect:
    """When casualty is paid (a creature with power >= 1 is sacrificed),
    the spell on the stack should be copied."""

    def test_casualty_paid_creates_copy_on_stack(self) -> None:
        """When the casualty trigger resolves and a creature was
        sacrificed, a copy of the spell should be pushed onto the stack."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)

        # Place a sacrifice fodder creature on the battlefield
        fodder = _make_bear(name="Sac Fodder", owner=p1, controller=p1)
        game.get_battlefield(p1).add(fodder)

        # Create an instant spell and simulate it being on the stack
        instant = _make_instant(name="Lightning Bolt", owner=p1, controller=p1)
        from engine.stack import StackObject
        spell_stack_obj = StackObject(
            source=instant,
            controller=p1,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(spell_stack_obj)

        # Fire the SpellCastTriggeredEvent — the trigger effect should
        # offer casualty and, if paid, push a copy on the stack.
        # For testing, we script the player to choose to pay casualty
        # (choose "yes" and then choose the creature to sacrifice).
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            # Script: yes to pay casualty, select the fodder creature,
            # and optionally "no" to choosing new targets
            p1._script.extend([True, fodder, False])

        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # The trigger should have been pushed onto the stack. Resolve it.
        initial_stack_size = len(game.stack)
        # There should be the original spell + the trigger on the stack
        assert len(game.stack) >= 2, (
            f"Expected at least 2 items on stack (original spell + trigger), "
            f"but found {len(game.stack)}"
        )

        # Pop and resolve the trigger (top of stack)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        # After resolving the trigger, if casualty was paid:
        # - The fodder creature should have been sacrificed (not on battlefield)
        # - A copy of the spell should be on the stack
        bf_creatures = [
            c for c in game.get_battlefield(p1).get_all()
            if c is fodder
        ]
        assert len(bf_creatures) == 0, (
            "Sacrificed creature should no longer be on the battlefield"
        )

        # The stack should have at least the original spell plus the copy
        stack_items = game.stack.objects()
        # At least 2 items: the original spell and the copy
        assert len(stack_items) >= 2, (
            f"Expected at least 2 items on stack (original + copy), "
            f"found {len(stack_items)}"
        )

    def test_casualty_declined_no_copy(self) -> None:
        """When the player declines to pay casualty, no copy is created
        and no creature is sacrificed."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)

        fodder = _make_bear(name="Sac Fodder", owner=p1, controller=p1)
        game.get_battlefield(p1).add(fodder)

        instant = _make_instant(name="Lightning Bolt", owner=p1, controller=p1)
        from engine.stack import StackObject
        spell_stack_obj = StackObject(
            source=instant,
            controller=p1,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(spell_stack_obj)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            # Script: no, decline to pay casualty
            p1._script.extend([False])

        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve the trigger
        if len(game.stack) >= 2:
            trigger_obj = game.stack.pop()
            trigger_obj.on_resolve(game)

        # The fodder creature should still be on the battlefield
        bf_creatures = [
            c for c in game.get_battlefield(p1).get_all()
            if c is fodder
        ]
        assert len(bf_creatures) == 1, (
            "Creature should NOT be sacrificed when casualty is declined"
        )

        # Stack should only have the original spell
        assert len(game.stack) == 1, (
            f"No copy should be on the stack when casualty is declined, "
            f"but stack has {len(game.stack)} items"
        )

    def test_sacrificed_creature_goes_to_graveyard(self) -> None:
        """The creature sacrificed for casualty should end up in its
        owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)

        fodder = _make_bear(name="Sac Fodder", owner=p1, controller=p1)
        game.get_battlefield(p1).add(fodder)

        instant = _make_instant(name="Lightning Bolt", owner=p1, controller=p1)
        from engine.stack import StackObject
        spell_stack_obj = StackObject(
            source=instant,
            controller=p1,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(spell_stack_obj)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.extend([True, fodder, False])

        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve the trigger
        if len(game.stack) >= 2:
            trigger_obj = game.stack.pop()
            trigger_obj.on_resolve(game)

        # Sacrificed creature should be in the graveyard
        gy = game.get_graveyard(p1)
        assert gy.contains(fodder), (
            "Sacrificed creature should be in the owner's graveyard"
        )


# ===========================================================================
# Casualty power requirement
# ===========================================================================


class TestSilverquillCasualtyPowerRequirement:
    """Casualty 1 requires sacrificing a creature with power >= 1.
    A creature with power 0 should not be a valid sacrifice target."""

    def test_creature_with_zero_power_not_valid_sacrifice(self) -> None:
        """A creature with power 0 cannot be sacrificed for casualty 1."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)

        # Zero-power creature should not be a valid casualty sacrifice
        zero_power = _make_bear(
            name="Wall",
            owner=p1,
            controller=p1,
            power=0,
            toughness=3,
        )
        game.get_battlefield(p1).add(zero_power)

        instant = _make_instant(name="Lightning Bolt", owner=p1, controller=p1)
        from engine.stack import StackObject
        spell_stack_obj = StackObject(
            source=instant,
            controller=p1,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(spell_stack_obj)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            # Script: yes to pay casualty, but the only creature
            # available has power 0. Depending on implementation,
            # either the sacrifice is rejected or the wall is not offered.
            # We attempt to sacrifice it; the implementation should
            # either skip the wall or reject the payment.
            p1._script.extend([True, zero_power, False])

        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve trigger if pushed
        stack_count_before = len(game.stack)
        while len(game.stack) > 1:
            top = game.stack.pop()
            top.on_resolve(game)

        # The zero-power creature should still be on the battlefield
        # (not sacrificed) because it doesn't meet the power requirement
        bf_creatures = [
            c for c in game.get_battlefield(p1).get_all()
            if c is zero_power
        ]
        assert len(bf_creatures) == 1, (
            "Zero-power creature should NOT be sacrificed for casualty 1"
        )

    def test_creature_with_power_one_valid_sacrifice(self) -> None:
        """A creature with power exactly 1 meets the casualty 1 requirement."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)

        one_power = _make_bear(
            name="Soldier Token",
            owner=p1,
            controller=p1,
            power=1,
            toughness=1,
        )
        game.get_battlefield(p1).add(one_power)

        instant = _make_instant(name="Lightning Bolt", owner=p1, controller=p1)
        from engine.stack import StackObject
        spell_stack_obj = StackObject(
            source=instant,
            controller=p1,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(spell_stack_obj)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.extend([True, one_power, False])

        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve trigger
        while len(game.stack) > 1:
            top = game.stack.pop()
            top.on_resolve(game)

        # The power-1 creature should have been sacrificed
        bf_creatures = [
            c for c in game.get_battlefield(p1).get_all()
            if c is one_power
        ]
        assert len(bf_creatures) == 0, (
            "Power-1 creature should be sacrificed for casualty 1"
        )


# ===========================================================================
# Silverquill itself can be sacrificed for casualty
# ===========================================================================


class TestSilverquillSelfSacrifice:
    """Silverquill (power 4) can itself be a valid sacrifice target for
    casualty 1 if the controller chooses it."""

    def test_silverquill_is_valid_sacrifice_target(self) -> None:
        """Silverquill has power 4 >= 1, so it meets casualty 1 requirement."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)

        instant = _make_instant(name="Lightning Bolt", owner=p1, controller=p1)
        from engine.stack import StackObject
        spell_stack_obj = StackObject(
            source=instant,
            controller=p1,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(spell_stack_obj)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            # Choose to sacrifice Silverquill itself
            p1._script.extend([True, silverquill, False])

        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve trigger
        while len(game.stack) > 1:
            top = game.stack.pop()
            top.on_resolve(game)

        # Silverquill should have been sacrificed
        bf_cards = [
            c for c in game.get_battlefield(p1).get_all()
            if c is silverquill
        ]
        assert len(bf_cards) == 0, (
            "Silverquill should be sacrificed when chosen as casualty target"
        )


# ===========================================================================
# No creatures to sacrifice — casualty cannot be paid
# ===========================================================================


class TestSilverquillNoCasualtyCandidates:
    """When the controller has no eligible creatures to sacrifice,
    casualty cannot be paid and no copy is made."""

    def test_no_creatures_to_sacrifice_no_copy(self) -> None:
        """When no eligible creatures exist, no copy should be created."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)
        # Note: Silverquill itself could be sacrificed. But we test with
        # only zero-power creatures available.
        zero_power = _make_bear(
            name="Wall",
            owner=p1,
            controller=p1,
            power=0,
            toughness=4,
        )
        # Remove silverquill from BF to have only zero-power creatures
        game.get_battlefield(p1).remove(silverquill)
        game.get_battlefield(p1).add(zero_power)

        instant = _make_instant(name="Lightning Bolt", owner=p1, controller=p1)
        from engine.stack import StackObject
        spell_stack_obj = StackObject(
            source=instant,
            controller=p1,
            targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(spell_stack_obj)

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            # Even if the player wants to sacrifice, there's no valid target
            # Script: try to pay but fail
            p1._script.extend([True, False])

        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1,
        )

        # Since Silverquill is not on the battlefield, the trigger should
        # not even be registered. Let's re-register with it on the bf.
        game.get_battlefield(p1).add(silverquill)
        silverquill.register_triggers(game)

        game.trigger_manager.fire_event(game, event)

        # Resolve all triggers
        while len(game.stack) > 1:
            top = game.stack.pop()
            top.on_resolve(game)

        # Stack should only have the original spell (no copy)
        assert len(game.stack) == 1, (
            f"No copy should exist when no valid creature can be sacrificed, "
            f"stack has {len(game.stack)} items"
        )
