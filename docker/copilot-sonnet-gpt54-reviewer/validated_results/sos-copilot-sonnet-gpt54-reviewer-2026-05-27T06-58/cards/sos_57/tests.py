"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt is a {1}{U}{U} instant that:
1. Counters the target spell (removes it from the stack).
2. If the controller controls a Wizard: at the beginning of controller's
   next main phase, adds {C} equal to the mana value of the countered spell.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import CardImpl, Creature, Instant
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _wizard(name: str = "Test Wizard", owner=None, controller=None) -> Creature:
    """A 1/1 Wizard creature."""
    c = Creature(
        name=name,
        owner=owner,
        controller=controller,
        base_power=1,
        base_toughness=1,
    )
    c.subtypes = {"Wizard"}
    return c


def _non_wizard(name: str = "Test Bear", owner=None, controller=None) -> Creature:
    """A 2/2 non-Wizard creature."""
    c = Creature(
        name=name,
        owner=owner,
        controller=controller,
        base_power=2,
        base_toughness=2,
    )
    c.subtypes = {"Bear"}
    return c


def _dummy_spell(mana_value: int = 3, owner=None, controller=None) -> CardImpl:
    """A dummy spell with the given converted mana cost."""
    card = CardImpl(
        name=f"Dummy Spell {mana_value}",
        mana_cost=ManaCost(generic=mana_value),
        card_types={CardType.INSTANT},
        owner=owner,
        controller=controller,
    )
    return card


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestManaSculptProperties:
    """Static card data must match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_card_type_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types

    def test_cmc_is_three(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.mana_cost.cmc == 3


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------

class TestManaSculptTargeting:
    """get_targets() must return a requirement for spells on the stack."""

    def test_returns_target_requirement_list(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1

    def test_target_filter_accepts_stack_spell(self) -> None:
        """A spell on the stack is a legal target."""
        game = create_game()
        p2 = game.players[1]
        spell = _dummy_spell(owner=p2, controller=p2)
        stack_obj = StackObject(source=spell, controller=p2)
        game.stack.push(stack_obj)

        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.filter_fn(stack_obj) is True

    def test_target_filter_rejects_non_spell_object(self) -> None:
        """Non-spell objects are not legal counter targets."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        bear = _non_wizard()
        assert req.filter_fn(bear) is False


# ---------------------------------------------------------------------------
# Counter effect (spell removed from stack)
# ---------------------------------------------------------------------------

class TestManaSculptCounterEffect:
    """on_resolve removes the target spell from the stack."""

    def test_countered_spell_is_removed_from_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put a spell on the stack for p2
        target_card = _dummy_spell(mana_value=3, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        assert game.stack.is_empty()

    def test_countered_spell_goes_to_graveyard(self) -> None:
        """After being countered, the spell card should be in its owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_card = _dummy_spell(mana_value=2, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        graveyard = game.get_graveyard(p2)
        assert target_card in graveyard.get_all()

    def test_no_target_is_noop(self) -> None:
        """If chosen_targets is empty/unset, resolution does not raise."""
        game = create_game()
        p1 = game.players[0]
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        # No chosen_targets set — should not raise
        mana_sculpt.on_resolve(game)

    def test_counter_leaves_other_stack_objects_intact(self) -> None:
        """Only the targeted spell is removed; other stack objects remain."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Two spells on the stack
        other_card = _dummy_spell(mana_value=1, owner=p1, controller=p1)
        other_obj = StackObject(source=other_card, controller=p1)
        game.stack.push(other_obj)

        target_card = _dummy_spell(mana_value=4, owner=p2, controller=p2)
        target_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(target_obj)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [target_obj]
        mana_sculpt.on_resolve(game)

        # Only the target was countered
        assert len(game.stack) == 1
        remaining = game.stack.peek()
        assert remaining is other_obj


# ---------------------------------------------------------------------------
# Wizard condition — mana reward at beginning of next main phase
# ---------------------------------------------------------------------------

class TestManaSculptWizardReward:
    """If controller has a Wizard, {C} equal to countered spell's CMC is added
    at the beginning of the controller's next main phase."""

    def test_wizard_present_registers_delayed_trigger(self) -> None:
        """After countering with a Wizard on board, a trigger should be pending
        for the next main phase (trigger manager or pending action registered)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _wizard(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])

        target_card = _dummy_spell(mana_value=4, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        # Track trigger count before
        trigger_count_before = len(game.trigger_manager._triggers)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        # After resolution with a Wizard, a delayed trigger should be registered
        trigger_count_after = len(game.trigger_manager._triggers)
        assert trigger_count_after > trigger_count_before, (
            "Expected a delayed trigger to be registered for next main phase mana reward"
        )

    def test_no_wizard_no_trigger_registered(self) -> None:
        """Without a Wizard, no delayed trigger is registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        non_wiz = _non_wizard(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[non_wiz])

        target_card = _dummy_spell(mana_value=4, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        trigger_count_before = len(game.trigger_manager._triggers)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        trigger_count_after = len(game.trigger_manager._triggers)
        assert trigger_count_after == trigger_count_before, (
            "No trigger should be registered without a Wizard"
        )

    def test_wizard_reward_adds_colorless_mana_equal_to_countered_cmc(self) -> None:
        """The mana reward produces {C} equal to countered spell's CMC."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _wizard(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])

        # Countered spell has mana value 5
        target_card = _dummy_spell(mana_value=5, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        # Simulate beginning of controller's next main phase by firing trigger
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        p1.mana_pool.empty()
        game.active_player_index = 0  # P1 is active
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent(player=p1))

        # Resolve any triggered stack objects
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 5

    def test_wizard_reward_amount_matches_mana_value_of_countered_spell(self) -> None:
        """Different mana values produce different amounts of {C}."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _wizard(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])

        # Countered spell has mana value 2
        target_card = _dummy_spell(mana_value=2, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        from engine.events import BeginningOfMainPhaseTriggeredEvent
        p1.mana_pool.empty()
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent(player=p1))

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_wizard_reward_does_not_fire_for_opponents_main_phase(self) -> None:
        """The mana reward triggers at the CONTROLLER's next main phase, not opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _wizard(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])

        target_card = _dummy_spell(mana_value=3, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        # Fire beginning-of-main-phase for opponent (p2), not for p1
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        p1.mana_pool.empty()
        game.active_player_index = 1  # p2 is active
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent(player=p2))

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # p1 should NOT have received mana on opponent's main phase
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_wizard_check_is_at_resolution_time(self) -> None:
        """The Wizard check happens when Mana Sculpt resolves (controller
        must control a Wizard at that point)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # No wizard on battlefield at resolve time
        set_board_state(game, 0, battlefield=[])

        target_card = _dummy_spell(mana_value=3, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        trigger_count_before = len(game.trigger_manager._triggers)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        # No wizard = no trigger
        trigger_count_after = len(game.trigger_manager._triggers)
        assert trigger_count_after == trigger_count_before

    def test_empty_battlefield_no_wizard_no_mana(self) -> None:
        """With empty battlefield, no mana is added next main phase."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_card = _dummy_spell(mana_value=6, owner=p2, controller=p2)
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        mana_sculpt.chosen_targets = [stack_obj]
        mana_sculpt.on_resolve(game)

        from engine.events import BeginningOfMainPhaseTriggeredEvent
        p1.mana_pool.empty()
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent(player=p1))

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
