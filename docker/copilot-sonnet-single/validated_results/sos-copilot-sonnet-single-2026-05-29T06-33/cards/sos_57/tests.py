"""Tests for SOS 57 — Mana Sculpt.

Covers:
- Static properties: name, mana_cost, card type (Instant), no keywords.
- Targeting: targets a spell on the stack (Zone.STACK, TargetRequirement).
- Counter effect: chosen target spell is removed from stack, put in graveyard.
- No-wizard case: no mana is generated (no trigger registered).
- Wizard-present case: a trigger fires at beginning of next main phase that
  adds colorless mana equal to the CMC of the countered spell.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state, advance_to_phase


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_no_keywords(self) -> None:
        assert ManaSculpt(owner=None).keywords == Keyword(0)

    def test_card_type_is_instant(self) -> None:
        assert CardType.INSTANT in ManaSculpt(owner=None).card_types


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------

class TestManaSculptTargeting:
    """get_targets() advertises one target requirement for a spell on the stack."""

    def test_returns_one_target_requirement(self) -> None:
        game = create_game()
        reqs = ManaSculpt(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_target_filter_accepts_instant_spell(self) -> None:
        """Filter must accept a StackObject wrapping an Instant."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        p2 = game.players[1]
        target_card = Instant(
            name="Lightning Bolt",
            mana_cost=ManaCost.parse("{R}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        assert req.filter_fn(stack_obj) is True

    def test_target_filter_accepts_sorcery_spell(self) -> None:
        """Filter must accept a StackObject wrapping a Sorcery."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        p2 = game.players[1]
        target_card = Sorcery(
            name="Divination",
            mana_cost=ManaCost.parse("{2}{U}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        assert req.filter_fn(stack_obj) is True

    def test_target_filter_rejects_mana_ability(self) -> None:
        """Filter must not accept a mana ability (non-counterable)."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        p2 = game.players[1]
        target_card = Instant(
            name="Some Mana",
            mana_cost=ManaCost.parse("{0}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2, is_mana_ability=True)
        assert req.filter_fn(stack_obj) is False


# ---------------------------------------------------------------------------
# Counter spell effect
# ---------------------------------------------------------------------------

class TestManaSculptCounterEffect:
    """on_resolve counters the target spell: removes from stack, goes to graveyard."""

    def _setup_stack_target(self, game, cmc_cost: str = "{3}{R}"):
        """Push an opponent's spell onto the stack and return (stack_obj, source_card)."""
        p2 = game.players[1]
        target_card = Instant(
            name="Big Spell",
            mana_cost=ManaCost.parse(cmc_cost),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)
        return stack_obj, target_card

    def test_countered_spell_removed_from_stack(self) -> None:
        """After resolution, the targeted spell is no longer on the stack."""
        game = create_game()
        p1 = game.players[0]
        stack_obj, target_card = self._setup_stack_target(game)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # Stack should be empty (or at least not contain the countered spell)
        stack_items = game.stack.objects()
        assert stack_obj not in stack_items

    def test_countered_spell_goes_to_owners_graveyard(self) -> None:
        """The source card of the countered spell ends up in its owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        stack_obj, target_card = self._setup_stack_target(game)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        graveyard = game.get_graveyard(p2).get_all()
        assert target_card in graveyard

    def test_no_target_is_a_noop(self) -> None:
        """Resolution with no chosen targets must not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = ManaSculpt(owner=p1, controller=p1)
        # chosen_targets not set — should be a no-op
        spell.on_resolve(game)


# ---------------------------------------------------------------------------
# No Wizard — no mana generation
# ---------------------------------------------------------------------------

class TestManaSculptNoWizard:
    """Without a Wizard, no mana is generated after countering."""

    def test_no_wizard_no_trigger_for_mana(self) -> None:
        """When controller has no Wizard, no mana trigger is registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Place a non-Wizard creature on p1's battlefield
        non_wizard = Creature(
            name="Grizzly Bears",
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[non_wizard])

        # Put a spell on the stack
        target_card = Instant(
            name="Some Spell",
            mana_cost=ManaCost.parse("{3}{U}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        initial_trigger_count = len(game.trigger_manager.get_triggers())

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # No new mana-related triggers should be registered
        final_trigger_count = len(game.trigger_manager.get_triggers())
        assert final_trigger_count == initial_trigger_count

    def test_no_wizard_no_mana_added_immediately(self) -> None:
        """When controller has no Wizard, no colorless mana is added right away."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Battlefield has no wizards for p1
        target_card = Instant(
            name="Some Spell",
            mana_cost=ManaCost.parse("{4}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


# ---------------------------------------------------------------------------
# Wizard present — mana generation at beginning of next main phase
# ---------------------------------------------------------------------------

class TestManaSculptWithWizard:
    """With a Wizard on the battlefield, mana is added at beginning of next main phase."""

    def _put_wizard_on_battlefield(self, game, player_index: int) -> Creature:
        """Create a Wizard creature and put it on the given player's battlefield."""
        player = game.players[player_index]
        wizard = Creature(
            name="Test Wizard",
            base_power=1,
            base_toughness=1,
            subtypes={"Wizard"},
            owner=player,
            controller=player,
        )
        set_board_state(game, player_index, battlefield=[wizard])
        return wizard

    def test_wizard_present_trigger_registered(self) -> None:
        """When controller has a Wizard, a trigger is registered after countering."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self._put_wizard_on_battlefield(game, 0)

        target_card = Instant(
            name="Some Spell",
            mana_cost=ManaCost.parse("{3}{R}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        initial_trigger_count = len(game.trigger_manager.get_triggers())

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # A new trigger should be registered for the beginning of next main phase
        final_trigger_count = len(game.trigger_manager.get_triggers())
        assert final_trigger_count > initial_trigger_count

    def test_wizard_mana_equals_countered_cmc_4(self) -> None:
        """Trigger fires and adds 4 colorless mana for a CMC-4 countered spell."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent  # added by implementer

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self._put_wizard_on_battlefield(game, 0)

        # CMC = 3 + 1 (R) = 4
        target_card = Instant(
            name="Big Spell",
            mana_cost=ManaCost.parse("{3}{R}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # Fire the beginning of main phase event
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        # Resolve the pending trigger
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Should have 4 colorless mana (CMC of {3}{R})
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_wizard_mana_equals_countered_cmc_1(self) -> None:
        """Trigger fires and adds 1 colorless mana for a CMC-1 countered spell."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent  # added by implementer

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self._put_wizard_on_battlefield(game, 0)

        # CMC = 1
        target_card = Sorcery(
            name="Small Spell",
            mana_cost=ManaCost.parse("{G}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_wizard_mana_not_added_immediately(self) -> None:
        """Mana should NOT be added to the pool immediately on resolution."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self._put_wizard_on_battlefield(game, 0)

        target_card = Instant(
            name="Big Spell",
            mana_cost=ManaCost.parse("{3}{R}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # Mana should NOT be in the pool yet (deferred until main phase)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_wizard_mana_only_fires_once_next_main_phase(self) -> None:
        """The mana trigger should fire only once — at the NEXT main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent  # added by implementer

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        self._put_wizard_on_battlefield(game, 0)

        target_card = Instant(
            name="Test Spell",
            mana_cost=ManaCost.parse("{2}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # Fire the beginning of main phase event
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        mana_after_first_trigger = p1.mana_pool.get(ManaType.COLORLESS)

        # Fire again — mana should not increase (trigger is one-shot)
        p1.mana_pool.empty()
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # CMC of {2} is 2; should have gotten exactly 2 the first time
        assert mana_after_first_trigger == 2
        # Second firing should not add mana (trigger consumed)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_opponent_wizard_does_not_trigger_mana(self) -> None:
        """Only controller's Wizard matters — opponent's Wizard does not trigger."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Wizard is on p2's side (opponent), not p1's
        self._put_wizard_on_battlefield(game, 1)

        target_card = Instant(
            name="Opponent Spell",
            mana_cost=ManaCost.parse("{3}{R}"),
            owner=p2,
            controller=p2,
        )
        stack_obj = StackObject(source=target_card, controller=p2)
        game.stack.push(stack_obj)

        initial_trigger_count = len(game.trigger_manager.get_triggers())

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # No new triggers should be registered (wizard is opponent's)
        final_trigger_count = len(game.trigger_manager.get_triggers())
        assert final_trigger_count == initial_trigger_count
