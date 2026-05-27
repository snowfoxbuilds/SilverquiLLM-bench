"""Tests for sos_57 — Mana Sculpt.

Card spec:
  Mana cost: {1}{U}{U}
  Type: Instant
  Oracle text:
    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.
"""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestManaSculptProperties:
    """Static card data must match the sos_57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_mana_cost_cmc(self) -> None:
        """CMC of {1}{U}{U} is 3."""
        assert ManaSculpt(owner=None).mana_cost.cmc == 3


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestManaSculptTargeting:
    """get_targets() must advertise a single spell target on the stack."""

    def test_returns_one_target_requirement(self) -> None:
        game = create_game()
        reqs = ManaSculpt(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        """The target requirement zone must be Zone.STACK (spells on the stack)."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_target_filter_accepts_stack_object(self) -> None:
        """The filter must accept a StackObject representing a spell on the stack."""
        game = create_game()
        p1 = game.players[0]
        req = ManaSculpt(owner=None).get_targets(game)[0]

        dummy_card = Instant(
            name="Dummy Spell",
            mana_cost=ManaCost.parse("{2}{U}"),
            owner=p1,
            controller=p1,
        )
        stack_obj = StackObject(source=dummy_card, controller=p1)

        assert req.filter_fn(stack_obj) is True


# ---------------------------------------------------------------------------
# Resolution — countering behavior
# ---------------------------------------------------------------------------


class TestManaSculptResolution:
    """on_resolve must counter the targeted spell."""

    def test_no_target_is_noop(self) -> None:
        """If chosen_targets is unset, on_resolve must not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.on_resolve(game)  # must not raise

    def test_empty_chosen_targets_is_noop(self) -> None:
        """If chosen_targets is an empty list, on_resolve must not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)  # must not raise

    def test_countered_spell_removed_from_stack(self) -> None:
        """The targeted StackObject must be removed from the stack on resolve."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Create a spell on the stack (card in p2's stack zone, StackObject on game stack)
        target_card = Instant(
            name="Counterable Spell",
            mana_cost=ManaCost.parse("{3}{U}"),
            owner=p2,
            controller=p2,
        )
        p2.zones[Zone.STACK].add(target_card)
        target_stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(target_stack_obj)

        assert len(game.stack) == 1

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        # The targeted spell's StackObject should be gone
        assert len(game.stack) == 0

    def test_countered_spell_card_moves_to_graveyard(self) -> None:
        """The source card of the countered spell must move to the owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_card = Instant(
            name="Counterable Spell",
            mana_cost=ManaCost.parse("{2}{U}"),
            owner=p2,
            controller=p2,
        )
        p2.zones[Zone.STACK].add(target_card)
        target_stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(target_stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        graveyard = game.get_graveyard(p2)
        assert graveyard.contains(target_card)

    def test_countered_spell_not_on_stack_after_resolve(self) -> None:
        """Confirm the countered spell's card is no longer in p2's stack zone."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_card = Instant(
            name="Counterable Spell",
            mana_cost=ManaCost.parse("{1}{U}"),
            owner=p2,
            controller=p2,
        )
        p2.zones[Zone.STACK].add(target_card)
        target_stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(target_stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        # Card must no longer be in the stack zone
        assert not p2.zones[Zone.STACK].contains(target_card)


# ---------------------------------------------------------------------------
# Wizard condition — conditional mana effect
# ---------------------------------------------------------------------------


class _WizardHelpers:
    """Shared helpers for wizard-condition tests."""

    @staticmethod
    def make_wizard(game, player) -> Creature:
        """Create a Wizard creature and place it on the player's battlefield."""
        wizard = Creature(
            name="Test Wizard",
            base_power=1,
            base_toughness=2,
            owner=player,
            controller=player,
        )
        wizard.subtypes = {"Wizard"}
        wizard.card_types = {CardType.CREATURE}
        game.get_battlefield(player).add(wizard)
        return wizard

    @staticmethod
    def push_target_spell(game, owner, mana_cost_str: str) -> tuple:
        """Push an Instant onto the stack and return (card, stack_obj)."""
        target_card = Instant(
            name="Target Spell",
            mana_cost=ManaCost.parse(mana_cost_str),
            owner=owner,
            controller=owner,
        )
        owner.zones[Zone.STACK].add(target_card)
        target_stack_obj = StackObject(source=target_card, controller=owner)
        game.stack.push(target_stack_obj)
        return target_card, target_stack_obj


class TestManaSculptWizardCondition(_WizardHelpers):
    """The bonus effect only fires when the controller controls a Wizard."""

    def test_no_wizard_no_delayed_trigger(self) -> None:
        """With no Wizard on the battlefield, no delayed trigger should be registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _, target_stack_obj = self.push_target_spell(game, p2, "{3}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]

        trigger_count_before = len(game.trigger_manager.get_triggers())
        spell.on_resolve(game)
        trigger_count_after = len(game.trigger_manager.get_triggers())

        # No additional trigger should be registered when no wizard is present
        assert trigger_count_after == trigger_count_before

    def test_wizard_on_battlefield_registers_delayed_trigger(self) -> None:
        """With a Wizard on the battlefield, a delayed mana trigger must be registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{3}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]

        trigger_count_before = len(game.trigger_manager.get_triggers())
        spell.on_resolve(game)
        trigger_count_after = len(game.trigger_manager.get_triggers())

        # At least one new trigger should be registered for the mana effect
        assert trigger_count_after > trigger_count_before

    def test_wizard_in_graveyard_does_not_satisfy_condition(self) -> None:
        """A Wizard in the graveyard does not count as 'controlling a Wizard'."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Place a Wizard in the graveyard (not battlefield)
        wizard = Creature(
            name="Graveyard Wizard",
            base_power=1,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        wizard.subtypes = {"Wizard"}
        wizard.card_types = {CardType.CREATURE}
        game.get_graveyard(p1).add(wizard)

        _, target_stack_obj = self.push_target_spell(game, p2, "{3}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]

        trigger_count_before = len(game.trigger_manager.get_triggers())
        spell.on_resolve(game)
        trigger_count_after = len(game.trigger_manager.get_triggers())

        assert trigger_count_after == trigger_count_before

    def test_opponent_wizard_does_not_satisfy_condition(self) -> None:
        """A Wizard controlled by the opponent does not satisfy the condition."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Place a Wizard on the opponent's battlefield
        self.make_wizard(game, p2)

        _, target_stack_obj = self.push_target_spell(game, p2, "{3}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]

        trigger_count_before = len(game.trigger_manager.get_triggers())
        spell.on_resolve(game)
        trigger_count_after = len(game.trigger_manager.get_triggers())

        assert trigger_count_after == trigger_count_before

    def test_wizard_in_hand_does_not_satisfy_condition(self) -> None:
        """A Wizard in the hand does not count as 'controlling a Wizard'."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Place a Wizard in p1's hand
        wizard = Creature(
            name="Hand Wizard",
            base_power=1,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        wizard.subtypes = {"Wizard"}
        wizard.card_types = {CardType.CREATURE}
        game.get_hand(p1).add(wizard)

        _, target_stack_obj = self.push_target_spell(game, p2, "{3}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]

        trigger_count_before = len(game.trigger_manager.get_triggers())
        spell.on_resolve(game)
        trigger_count_after = len(game.trigger_manager.get_triggers())

        assert trigger_count_after == trigger_count_before


# ---------------------------------------------------------------------------
# Mana amount — equal to CMC of the countered spell
# ---------------------------------------------------------------------------


class TestManaSculptManaAmount(_WizardHelpers):
    """The bonus colorless mana must equal the mana value of the countered spell."""

    def test_trigger_effect_adds_colorless_mana_equal_to_cmc(self) -> None:
        """Triggering the delayed effect adds colorless mana equal to the CMC of the
        countered spell ({3}{U} = CMC 4, so 4 colorless mana)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{3}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) >= 1, "A delayed trigger should be registered"

        # Fire the most recently registered trigger's effect directly
        # (simulates the trigger resolving at the beginning of the next main phase)
        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        triggers[-1].effect(game)
        mana_after = p1.mana_pool.get(ManaType.COLORLESS)

        # CMC of {3}{U} is 4 — should add 4 colorless mana
        assert mana_after - mana_before == 4

    def test_trigger_effect_adds_mana_for_five_cmc_spell(self) -> None:
        """Countering a 5-CMC spell ({2}{U}{U}{U}) with wizard adds 5 colorless mana."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{2}{U}{U}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) >= 1

        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        triggers[-1].effect(game)
        mana_after = p1.mana_pool.get(ManaType.COLORLESS)

        assert mana_after - mana_before == 5

    def test_trigger_adds_colorless_not_blue_mana(self) -> None:
        """The added mana must be colorless ({C}), not blue or any other color."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{3}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) >= 1

        blue_before = p1.mana_pool.get(ManaType.BLUE)
        triggers[-1].effect(game)
        blue_after = p1.mana_pool.get(ManaType.BLUE)

        # No blue mana should be added — only colorless
        assert blue_after == blue_before

    def test_trigger_is_associated_with_controller(self) -> None:
        """The delayed trigger must be registered to the controller (p1), not the opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{2}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) >= 1

        # The last registered trigger should be controlled by p1
        assert triggers[-1].controller is p1


# ---------------------------------------------------------------------------
# Timing — mana added at beginning of NEXT main phase, not immediately
# ---------------------------------------------------------------------------


class TestManaSculptTiming(_WizardHelpers):
    """The mana must be added at the beginning of the next main phase,
    NOT immediately upon resolving Mana Sculpt."""

    def test_mana_not_added_immediately_on_resolve(self) -> None:
        """Mana must NOT appear in the pool the moment on_resolve finishes;
        it should only be scheduled as a delayed trigger."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{3}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]

        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        spell.on_resolve(game)
        mana_after = p1.mana_pool.get(ManaType.COLORLESS)

        # Mana must not have been added immediately — it is a delayed trigger
        assert mana_after == mana_before

    def test_trigger_registered_for_beginning_of_main_phase_event(self) -> None:
        """The registered trigger must fire on BeginningOfMainPhaseTriggeredEvent."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{2}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) >= 1

        # The newly registered trigger must watch BeginningOfMainPhaseTriggeredEvent
        last_trigger = triggers[-1]
        assert last_trigger.event_type is BeginningOfMainPhaseTriggeredEvent

    def test_fire_main_phase_event_pushes_trigger_to_stack(self) -> None:
        """When BeginningOfMainPhaseTriggeredEvent fires, the trigger must be
        pushed onto the game stack (standard triggered-ability flow)."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{3}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        # Stack is now empty (the countered spell and Mana Sculpt itself are gone)
        stack_size_before = len(game.stack)

        # Fire the main-phase event — the delayed trigger should be queued
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        # The trigger should now appear on the stack as a StackObject
        assert len(game.stack) > stack_size_before

    def test_mana_added_after_main_phase_event_resolves(self) -> None:
        """After BeginningOfMainPhaseTriggeredEvent fires and the triggered
        ability resolves, the correct amount of colorless mana is added."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        # CMC 4 ({3}{U}) → should add 4 colorless
        _, target_stack_obj = self.push_target_spell(game, p2, "{3}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        # Fire the event to push the triggered ability onto the stack
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        # Resolve the top of the stack (the triggered ability)
        assert len(game.stack) >= 1
        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        triggered_obj = game.stack.pop()
        triggered_obj.on_resolve(game)
        mana_after = p1.mana_pool.get(ManaType.COLORLESS)

        assert mana_after - mana_before == 4

    def test_mana_not_added_on_unrelated_event(self) -> None:
        """The trigger must NOT fire on other events (e.g., another turn's
        BeginningOfMainPhaseTriggeredEvent should only fire once — one-shot)."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self.make_wizard(game, p1)
        _, target_stack_obj = self.push_target_spell(game, p2, "{3}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        # Fire and resolve once (the intended main phase)
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())
        assert len(game.stack) >= 1
        triggered_obj = game.stack.pop()
        triggered_obj.on_resolve(game)  # this also unregisters the one-shot trigger

        # Fire the event again (a subsequent main phase) — trigger should NOT fire
        mana_after_first = p1.mana_pool.get(ManaType.COLORLESS)
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        # Nothing new on the stack (trigger was unregistered after first fire)
        new_stack_objects = len(game.stack)
        assert new_stack_objects == 0

        # Mana pool unchanged
        assert p1.mana_pool.get(ManaType.COLORLESS) == mana_after_first

    def test_mana_not_added_when_no_wizard_and_main_phase_fires(self) -> None:
        """Without a Wizard, BeginningOfMainPhaseTriggeredEvent must not add
        any colorless mana — no trigger should have been registered at all."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # No Wizard on p1's battlefield
        _, target_stack_obj = self.push_target_spell(game, p2, "{3}{U}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_stack_obj]
        spell.on_resolve(game)

        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        # Nothing on stack, mana unchanged
        assert len(game.stack) == 0
        assert p1.mana_pool.get(ManaType.COLORLESS) == mana_before
