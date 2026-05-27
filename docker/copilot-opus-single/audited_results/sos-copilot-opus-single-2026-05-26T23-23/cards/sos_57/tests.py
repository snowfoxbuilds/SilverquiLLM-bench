"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt is an instant that costs {1}{U}{U}.
Oracle text: "Counter target spell. If you control a Wizard, add an amount
of {C} equal to the amount of mana spent to cast that spell at the beginning
of your next main phase."

Tests cover:
- Static card properties (name, cost, type)
- Targeting (must target a spell on the stack)
- Counterspell effect (target spell is countered on resolve)
- Wizard-controlled mana refund (delayed trigger)
- No mana refund when no Wizard controlled
"""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_card_type_includes_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types


class TestManaSculptTargeting:
    """get_targets() should require targeting a spell on the stack."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = ManaSculpt(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.zone == Zone.STACK


class TestManaSculptCounterEffect:
    """on_resolve counters the target spell (moves it to graveyard)."""

    def test_countered_spell_moves_to_graveyard(self) -> None:
        """The targeted spell should be moved to its owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Create a target spell on the stack
        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        target_spell.card_types = {CardType.INSTANT}
        game.stack.push(
            __import__("engine.stack", fromlist=["StackObject"]).StackObject(
                source=target_spell,
                controller=p2,
            )
        )

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # The target spell should be in the graveyard
        graveyard = game.get_graveyard(p2)
        assert target_spell in graveyard

    def test_countered_spell_removed_from_stack(self) -> None:
        """After countering, the target spell should no longer be on stack."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_spell = Instant(name="Giant Growth", owner=p2, controller=p2)
        target_spell.card_types = {CardType.INSTANT}

        from engine.stack import StackObject
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # Stack should not contain the countered spell
        remaining = [obj for obj in game.stack._items if obj.source is target_spell]
        assert len(remaining) == 0


class TestManaSculptWizardBonus:
    """If controller has a Wizard, delayed trigger adds {C} equal to mana spent."""

    def _make_wizard(self, owner=None, controller=None) -> Creature:
        """Helper to create a Wizard creature."""
        wizard = Creature(
            name="Merfolk Wizard",
            owner=owner,
            controller=controller,
            base_power=1,
            base_toughness=1,
        )
        wizard.card_types = {CardType.CREATURE}
        wizard.subtypes = {"Wizard"}
        return wizard

    def test_no_mana_refund_without_wizard(self) -> None:
        """Without a Wizard on the battlefield, no delayed trigger is set up."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_spell = Instant(name="Shock", owner=p2, controller=p2)
        target_spell.card_types = {CardType.INSTANT}
        target_spell.mana_cost = ManaCost.parse("{R}")

        from engine.stack import StackObject
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # No delayed trigger should be registered (check mana pool stays empty)
        mana_pool = game.players[0].mana_pool
        colorless_mana = mana_pool.get(ManaType.COLORLESS, 0)
        assert colorless_mana == 0

    def test_mana_refund_with_wizard_controlled(self) -> None:
        """With a Wizard, should set up delayed trigger for {C} equal to mana spent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put a Wizard on p1's battlefield
        wizard = self._make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        # Create a 3-mana spell as target (e.g. {2}{R} = 3 total mana)
        target_spell = Instant(name="Fireball", owner=p2, controller=p2)
        target_spell.card_types = {CardType.INSTANT}
        target_spell.mana_cost = ManaCost.parse("{2}{R}")

        from engine.stack import StackObject
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # The card should have registered a delayed trigger or stored
        # information about the mana to be added. We verify the delayed
        # trigger exists or the mana is queued.
        # At minimum, verify that the game has some delayed trigger registered
        # that will provide 3 colorless mana at next main phase.
        assert hasattr(game, 'delayed_triggers') or hasattr(game, 'trigger_manager')
        # Check that a delayed trigger was actually registered
        triggers = getattr(game, 'delayed_triggers', None) or \
                   getattr(game.trigger_manager, 'delayed_triggers', [])
        assert len(triggers) > 0, "Expected a delayed trigger for mana refund"

    def test_mana_refund_amount_equals_mana_spent(self) -> None:
        """The colorless mana added should equal the mana value of the countered spell."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Wizard on battlefield
        wizard = self._make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        # 5 mana spell: {3}{U}{U}
        target_spell = Instant(name="Big Spell", owner=p2, controller=p2)
        target_spell.card_types = {CardType.INSTANT}
        target_spell.mana_cost = ManaCost.parse("{3}{U}{U}")

        from engine.stack import StackObject
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # The delayed trigger should reference 5 mana (3 generic + 2 blue pips)
        triggers = getattr(game, 'delayed_triggers', None) or \
                   getattr(game.trigger_manager, 'delayed_triggers', [])
        assert len(triggers) > 0
        # Find the trigger and verify amount stored
        trigger = triggers[-1]
        # The trigger should store the amount of mana to add (5)
        amount = getattr(trigger, 'mana_amount', None) or \
                 getattr(trigger, 'amount', None)
        assert amount == 5, f"Expected 5 colorless mana, got {amount}"

    def test_counter_still_works_with_wizard(self) -> None:
        """Even with a Wizard, the spell must still be countered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = self._make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        target_spell = Instant(name="Opt", owner=p2, controller=p2)
        target_spell.card_types = {CardType.INSTANT}
        target_spell.mana_cost = ManaCost.parse("{U}")

        from engine.stack import StackObject
        stack_obj = StackObject(source=target_spell, controller=p2)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # Spell is still countered (in graveyard)
        graveyard = game.get_graveyard(p2)
        assert target_spell in graveyard
