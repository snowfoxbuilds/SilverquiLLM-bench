"""Tests for sos_57 — Mana Sculpt."""
from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game


class TestManaSculptProperties:
    def test_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptCounter:
    """Counters target spell (removes from stack, card goes to graveyard)."""

    def test_counter_removes_spell_from_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        sculpt = ManaSculpt(owner=p1, controller=p1)

        # Put a spell on the stack.
        target_spell = Instant(name="Lightning Bolt", mana_cost=ManaCost.parse("{R}"), owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)

        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        assert len(game.stack) == 0

    def test_counter_moves_card_to_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        sculpt = ManaSculpt(owner=p1, controller=p1)

        target_spell = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"), owner=p2, controller=p2)
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)

        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        graveyard = p2.zones[Zone.GRAVEYARD].get_all()
        assert target_spell in graveyard


class TestManaSculptNoWizard:
    """Without a Wizard, no mana is added."""

    def test_no_wizard_no_mana_registered(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        sculpt = ManaSculpt(owner=p1, controller=p1)

        target = Instant(name="Giant Growth", mana_cost=ManaCost.parse("{G}"), owner=p2, controller=p2)
        stack_obj = StackObject(source=target, controller=p2)
        game.stack.push(stack_obj)

        sculpt.chosen_targets = [stack_obj]
        before_triggers = len(game.trigger_manager._triggers)
        sculpt.on_resolve(game)
        after_triggers = len(game.trigger_manager._triggers)

        # No new main-phase trigger should be registered.
        assert after_triggers == before_triggers


class TestManaSculptWithWizard:
    """With a Wizard, adds {C} equal to countered spell's CMC at next main phase."""

    def test_with_wizard_registers_main_phase_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        sculpt = ManaSculpt(owner=p1, controller=p1)

        # p1 controls a Wizard.
        wizard = Creature(
            name="Sage Owl",
            base_power=1, base_toughness=1,
            subtypes={"Wizard"},
            owner=p1, controller=p1,
        )
        game.get_battlefield(p1).add(wizard)

        target = Instant(name="Opt", mana_cost=ManaCost.parse("{U}"), owner=p2, controller=p2)
        stack_obj = StackObject(source=target, controller=p2)
        game.stack.push(stack_obj)

        sculpt.chosen_targets = [stack_obj]
        before_triggers = len(game.trigger_manager._triggers)
        sculpt.on_resolve(game)
        after_triggers = len(game.trigger_manager._triggers)

        # One new main-phase trigger should be registered.
        assert after_triggers == before_triggers + 1

    def test_with_wizard_trigger_fires_and_adds_colorless_mana(self) -> None:
        """When main phase starts, the pending mana is added to controller's pool."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        sculpt = ManaSculpt(owner=p1, controller=p1)

        wizard = Creature(
            name="Sage Owl", base_power=1, base_toughness=1,
            subtypes={"Wizard"}, owner=p1, controller=p1,
        )
        game.get_battlefield(p1).add(wizard)

        # Target spell has CMC 3 ({1}{U}{U}).
        target = Instant(
            name="Counterspell", mana_cost=ManaCost.parse("{1}{U}{U}"), owner=p2, controller=p2
        )
        stack_obj = StackObject(source=target, controller=p2)
        game.stack.push(stack_obj)

        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # Simulate beginning of next main phase.
        before_colorless = p1.mana_pool.get(ManaType.COLORLESS)
        event = BeginningOfMainPhaseTriggeredEvent(player=p1, is_first_main=True)
        game.trigger_manager.fire_event(game, event)

        # Manually resolve any triggered abilities pushed onto stack.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Should have added 3 {C} (CMC of Counterspell).
        assert p1.mana_pool.get(ManaType.COLORLESS) == before_colorless + 3
