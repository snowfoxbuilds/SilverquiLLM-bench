"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt is an instant costing {1}{U}{U} that reads:
  "Counter target spell. If you control a Wizard, add an amount of {C}
   equal to the amount of mana spent to cast that spell at the beginning
   of your next main phase."

Requirements tested:
  - Static properties (name, mana cost, card type)
  - Targeting: targets a spell on the stack
  - Counter effect: removes the targeted spell from the stack to graveyard
  - Wizard check: delayed mana trigger only fires when a Wizard is controlled
  - Delayed trigger adds {C} equal to mana spent on the countered spell
  - No mana added if no Wizard is controlled
  - Fizzle behavior when target is missing
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper to create a Wizard creature
# ---------------------------------------------------------------------------

def _make_wizard(name: str = "Test Wizard", owner: Any = None) -> Creature:
    """Create a simple Wizard creature for testing."""
    c = Creature(
        name=name,
        owner=owner,
        base_power=1,
        base_toughness=1,
        subtypes={"Human", "Wizard"},
    )
    return c


def _make_dummy_spell(name: str = "Dummy Spell", mana_cost_str: str = "{2}{R}",
                      owner: Any = None) -> Instant:
    """Create a dummy instant to serve as the target spell on the stack."""
    spell = Instant(
        name=name,
        owner=owner,
        mana_cost=ManaCost.parse(mana_cost_str),
    )
    return spell


def _put_spell_on_stack(game: Any, player_index: int, spell: Any) -> StackObject:
    """Place a spell onto the stack and return its StackObject.

    This simulates the casting pipeline without paying mana.
    """
    player = game.players[player_index]
    spell.owner = player
    spell.controller = player

    # Add the card to the player's stack zone
    player.zones[Zone.STACK].add(spell)

    # Create and push a StackObject
    stack_obj = StackObject(
        source=spell,
        controller=player,
        targets=[],
        on_resolve=lambda g: spell.on_resolve(g),
    )
    game.stack.push(stack_obj)
    return stack_obj


# ===========================================================================
# Tests
# ===========================================================================


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_card_type_includes_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types


class TestManaSculptTargeting:
    """get_targets() should advertise a single spell target on the stack."""

    def test_returns_target_requirement_when_spell_on_stack(self) -> None:
        game = create_game()
        p2 = game.players[1]

        dummy = _make_dummy_spell(owner=p2)
        _put_spell_on_stack(game, 1, dummy)

        card = ManaSculpt(owner=game.players[0])
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        game = create_game()
        p2 = game.players[1]

        dummy = _make_dummy_spell(owner=p2)
        _put_spell_on_stack(game, 1, dummy)

        card = ManaSculpt(owner=game.players[0])
        reqs = card.get_targets(game)
        assert reqs[0].zone == Zone.STACK

    def test_cannot_cast_with_empty_stack(self) -> None:
        """can_cast should return False when there are no spells to counter."""
        game = create_game()
        card = ManaSculpt(owner=game.players[0])
        assert card.can_cast(game) is False

    def test_can_cast_with_spell_on_stack(self) -> None:
        """can_cast should return True when there is a spell on the stack."""
        game = create_game()
        dummy = _make_dummy_spell(owner=game.players[1])
        _put_spell_on_stack(game, 1, dummy)

        card = ManaSculpt(owner=game.players[0])
        # Mana Sculpt itself should not be on the stack for this check
        assert card.can_cast(game) is True


class TestManaSculptCounterEffect:
    """on_resolve should counter the targeted spell."""

    def test_countered_spell_goes_to_graveyard(self) -> None:
        """The countered spell's card should end up in its owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        dummy = _make_dummy_spell(name="Lightning Bolt", mana_cost_str="{R}", owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # The countered spell should be in the owner's graveyard
        gy = game.get_graveyard(p2)
        gy_cards = gy.get_all()
        assert any(c is dummy for c in gy_cards), (
            "Countered spell should be in owner's graveyard"
        )

    def test_countered_spell_removed_from_stack(self) -> None:
        """After countering, the targeted spell should no longer be on the stack."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        dummy = _make_dummy_spell(owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # The stack should no longer contain the countered spell
        for item in game.stack._items:
            assert item is not stack_obj, (
                "Countered StackObject should be removed from the stack"
            )

    def test_no_target_is_a_noop(self) -> None:
        """If chosen_targets is empty or unset, resolution should not raise."""
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        # No chosen_targets set — should be safe
        sculpt.on_resolve(game)


class TestManaSculptWizardCheck:
    """The Wizard condition determines whether the delayed mana trigger fires."""

    def test_no_wizard_no_mana_added(self) -> None:
        """Without a Wizard on the battlefield, no colorless mana should be added."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # No Wizard on p1's battlefield
        dummy = _make_dummy_spell(name="Big Spell", mana_cost_str="{4}{R}", owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # Advance to next main phase — no mana should appear
        initial_colorless = p1.mana_pool.get(ManaType.COLORLESS)
        # Try to trigger any delayed triggers by advancing phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        # Even after going to a main phase, no mana should be added since
        # no Wizard was controlled
        # The mana pool should not have increased
        assert p1.mana_pool.get(ManaType.COLORLESS) == initial_colorless

    def test_with_wizard_triggers_mana_production(self) -> None:
        """With a Wizard controlled, resolution should set up a delayed trigger
        that adds colorless mana equal to the countered spell's mana cost."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put a Wizard on p1's battlefield
        wizard = _make_wizard(owner=p1)
        set_board_state(game, 0, battlefield=[wizard])

        # Put a spell costing {2}{R} (CMC=3 / total mana spent = 3) on the stack
        dummy = _make_dummy_spell(name="Expensive Spell", mana_cost_str="{2}{R}", owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # The delayed trigger should have been created. We need to check that
        # either: (a) a trigger was registered that will fire at next main phase,
        # or (b) the mana gets added when we advance to the next main phase.
        # We verify by checking that something changed (trigger registered or
        # mana was directly queued).
        triggers_before = len(game.trigger_manager.get_triggers())
        # There should be at least one trigger registered or some delayed
        # mechanism stored.
        # This test verifies the implementation creates a delayed mechanism.
        # Since the implementation doesn't exist yet, this will fail (TDD red).
        assert (
            triggers_before > 0
            or hasattr(sculpt, "_delayed_mana")
            or hasattr(p1, "_delayed_mana_sculpt")
        ), "A delayed trigger or mana mechanism should be set up when Wizard is controlled"


class TestManaSculptDelayedMana:
    """The delayed trigger should add {C} equal to the mana spent on the
    countered spell at the beginning of the controller's next main phase."""

    def test_mana_amount_equals_countered_spell_cmc(self) -> None:
        """Colorless mana added should equal the mana spent to cast the
        countered spell. We approximate 'mana spent' as the spell's CMC."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1)
        set_board_state(game, 0, battlefield=[wizard])

        # Spell costs {3}{U}{U} — CMC = 5
        dummy = _make_dummy_spell(name="Big Blue", mana_cost_str="{3}{U}{U}", owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        initial_colorless = p1.mana_pool.get(ManaType.COLORLESS)
        sculpt.on_resolve(game)

        # Now simulate the beginning of p1's next main phase.
        # Set up so p1 is the active player at precombat main.
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        # Fire any registered triggers for the main phase beginning.
        # The implementation should register a delayed trigger that fires here.
        from engine.events import TriggeredEvent

        # Try firing a generic phase-beginning event or check directly.
        # Process any triggers on the stack.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # After the delayed trigger resolves, colorless mana should increase by 5
        final_colorless = p1.mana_pool.get(ManaType.COLORLESS)
        assert final_colorless == initial_colorless + 5, (
            f"Expected {initial_colorless + 5} colorless mana, got {final_colorless}"
        )

    def test_mana_amount_for_cheap_spell(self) -> None:
        """A one-mana spell should yield 1 colorless mana."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1)
        set_board_state(game, 0, battlefield=[wizard])

        # Spell costs {R} — CMC = 1
        dummy = _make_dummy_spell(name="Shock", mana_cost_str="{R}", owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        initial_colorless = p1.mana_pool.get(ManaType.COLORLESS)
        sculpt.on_resolve(game)

        # Advance to next main phase
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        final_colorless = p1.mana_pool.get(ManaType.COLORLESS)
        assert final_colorless == initial_colorless + 1

    def test_mana_is_colorless(self) -> None:
        """The mana added should be specifically colorless ({C}), not any color."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1)
        set_board_state(game, 0, battlefield=[wizard])

        dummy = _make_dummy_spell(name="Test", mana_cost_str="{1}{G}", owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        # Record all mana types before resolution
        mana_before = {mt: p1.mana_pool.get(mt) for mt in ManaType}
        sculpt.on_resolve(game)

        # Advance to main phase
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Only colorless should have changed
        for mt in ManaType:
            if mt == ManaType.COLORLESS:
                assert p1.mana_pool.get(mt) == mana_before[mt] + 2, (
                    f"Expected colorless mana to increase by 2 (CMC of {{1}}{{G}})"
                )
            else:
                assert p1.mana_pool.get(mt) == mana_before[mt], (
                    f"Non-colorless mana type {mt} should not change"
                )


class TestManaSculptEdgeCases:
    """Edge cases and special interactions."""

    def test_wizard_leaves_before_resolve_no_mana(self) -> None:
        """If the Wizard leaves the battlefield before Mana Sculpt resolves,
        no delayed mana trigger should be created (condition checked on resolve)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Wizard exists on battlefield for setup
        wizard = _make_wizard(owner=p1)
        set_board_state(game, 0, battlefield=[wizard])

        dummy = _make_dummy_spell(name="Target", mana_cost_str="{3}", owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        # Remove wizard before resolve
        bf = game.get_battlefield(p1)
        bf.remove(wizard)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # No delayed trigger should fire — no mana at next main phase
        initial_colorless = p1.mana_pool.get(ManaType.COLORLESS)
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == initial_colorless

    def test_spell_still_countered_even_without_wizard(self) -> None:
        """The spell should be countered regardless of whether a Wizard is controlled.
        The Wizard only matters for the mana bonus."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # No Wizard on battlefield
        dummy = _make_dummy_spell(name="Target Spell", mana_cost_str="{2}{B}", owner=p2)
        stack_obj = _put_spell_on_stack(game, 1, dummy)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # Spell should be countered (in graveyard)
        gy = game.get_graveyard(p2)
        assert any(c is dummy for c in gy.get_all()), (
            "Spell should be countered even without a Wizard"
        )

    def test_counter_creature_spell(self) -> None:
        """Mana Sculpt can counter any spell, not just instants/sorceries.
        Verify it works on a creature spell."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
            mana_cost=ManaCost.parse("{1}{G}"),
        )
        stack_obj = _put_spell_on_stack(game, 1, bear)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # Bear should be countered — in graveyard, not on battlefield
        gy = game.get_graveyard(p2)
        assert any(c is bear for c in gy.get_all()), (
            "Creature spell should be countered"
        )
        bf = game.get_battlefield(p2)
        assert not any(c is bear for c in bf.get_all()), (
            "Creature should not be on the battlefield after being countered"
        )

    def test_zero_cost_spell_yields_zero_mana(self) -> None:
        """If the countered spell costs {0}, the delayed mana amount is 0."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1)
        set_board_state(game, 0, battlefield=[wizard])

        # A zero-cost spell (like Ornithopter as an instant for testing)
        zero_spell = Instant(
            name="Zero Cost",
            owner=p2,
            mana_cost=ManaCost(generic=0, pips={}),
        )
        stack_obj = _put_spell_on_stack(game, 1, zero_spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        initial_colorless = p1.mana_pool.get(ManaType.COLORLESS)
        sculpt.on_resolve(game)

        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Should still be the same — zero mana produced
        assert p1.mana_pool.get(ManaType.COLORLESS) == initial_colorless
