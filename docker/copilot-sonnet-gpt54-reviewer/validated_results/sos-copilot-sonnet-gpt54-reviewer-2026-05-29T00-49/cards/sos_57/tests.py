"""Tests for sos_57 — Mana Sculpt.

Counter-spell instant with conditional mana refund.

oracle_text:
  "Counter target spell. If you control a Wizard, add an amount of {C}
   equal to the amount of mana spent to cast that spell at the beginning
   of your next main phase."

Test coverage:
- Static card properties (name, mana cost, Instant type)
- get_targets() returns one TargetRequirement targeting the stack
- on_resolve counters the targeted spell (removes from stack)
- Countered card goes to its owner's graveyard
- No-target no-op (no Wizard logic applied)
- Without a Wizard: no colorless mana tracked
- With a Wizard: pending mana amount equals CMC of countered spell
- Mana is NOT added to pool immediately on resolution
- With a Wizard: mana is delivered at beginning of caster's next main phase
- Edge: 0-cost spell countered with Wizard → no mana added
- Edge: high-CMC spell gives correct colorless mana amount
- Wizard identification uses creature subtype ("Wizard")
- Non-Wizard creature does not trigger the mana bonus
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.stack import StackObject
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wizard(game: Any, player: Any, name: str = "Test Wizard") -> Creature:
    """Create a Wizard creature and place it on player's battlefield."""
    wizard = Creature(
        name=name,
        owner=player,
        controller=player,
        base_power=2,
        base_toughness=2,
        subtypes={"Wizard"},
    )
    wizard.card_types = {CardType.CREATURE}
    game.get_battlefield(player).add(wizard)
    return wizard


def _make_sorcery_on_stack(
    game: Any,
    controller: Any,
    name: str = "Dummy Sorcery",
    mana_cost: str = "{3}",
) -> tuple[StackObject, Sorcery]:
    """Create a sorcery card and push a StackObject for it onto the game stack."""
    card = Sorcery(
        name=name,
        mana_cost=ManaCost.parse(mana_cost),
        owner=controller,
        controller=controller,
    )
    stack_obj = StackObject(
        source=card,
        controller=controller,
    )
    game.stack.push(stack_obj)
    return stack_obj, card


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestManaSculptProperties:
    """Static card data must match the sos_57 spec."""

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_has_instant_card_type(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types


# ---------------------------------------------------------------------------
# Targeting — get_targets()
# ---------------------------------------------------------------------------

class TestManaSculptTargeting:
    """get_targets() must advertise exactly one stack-zone TargetRequirement."""

    def test_get_targets_returns_list(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        result = card.get_targets(game)
        assert isinstance(result, list)

    def test_get_targets_returns_one_requirement(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        assert len(reqs) == 1

    def test_get_targets_returns_target_requirement(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        req = card.get_targets(game)[0]
        assert isinstance(req, TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        """Counterspells target spells on the stack."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_target_filter_accepts_stack_object(self) -> None:
        """The filter must accept StackObjects (spells on the stack)."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        p1 = game.players[0]
        stack_obj, _ = _make_sorcery_on_stack(game, p1)
        assert req.filter_fn(stack_obj) is True


# ---------------------------------------------------------------------------
# Countering behavior
# ---------------------------------------------------------------------------

class TestManaSculptCountering:
    """on_resolve must counter (remove) the targeted spell from the stack."""

    def test_countered_spell_removed_from_stack(self) -> None:
        """The targeted spell must be gone from the stack after resolution."""
        game = create_game()
        p1 = game.players[0]
        stack_obj, _ = _make_sorcery_on_stack(game, p1)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # The targeted StackObject must no longer be on the stack.
        assert stack_obj not in game.stack._items

    def test_countered_spell_card_goes_to_graveyard(self) -> None:
        """The countered card must move to its owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        stack_obj, card = _make_sorcery_on_stack(game, p1)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        graveyard_cards = game.get_graveyard(p1).get_all()
        assert card in graveyard_cards

    def test_no_target_is_noop(self) -> None:
        """Resolving without chosen_targets must not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = ManaSculpt(owner=p1, controller=p1)
        # chosen_targets unset — must not crash.
        spell.on_resolve(game)

    def test_no_target_leaves_stack_unchanged(self) -> None:
        """Without a target, no stack manipulation occurs."""
        game = create_game()
        p1 = game.players[0]
        stack_obj, _ = _make_sorcery_on_stack(game, p1)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = []  # explicit empty list
        spell.on_resolve(game)

        # Existing stack object must remain untouched.
        assert stack_obj in game.stack._items


# ---------------------------------------------------------------------------
# No Wizard — no mana bonus
# ---------------------------------------------------------------------------

class TestManaSculptNoWizard:
    """Without a Wizard on the battlefield, no colorless mana should be tracked."""

    def test_no_wizard_no_colorless_in_pool_immediately(self) -> None:
        """Pool must have no colorless mana immediately after resolution."""
        game = create_game()
        p1 = game.players[0]
        # Place a non-Wizard creature to confirm subtype check is specific.
        non_wizard = Creature(
            name="Goblin Scout",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
            subtypes={"Goblin"},
        )
        game.get_battlefield(p1).add(non_wizard)

        stack_obj, _ = _make_sorcery_on_stack(game, p1, mana_cost="{4}")
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_wizard_no_pending_mana_stored(self) -> None:
        """Without a Wizard, no pending colorless mana attribute should be set."""
        game = create_game()
        p1 = game.players[0]
        stack_obj, _ = _make_sorcery_on_stack(game, p1, mana_cost="{3}")
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # The pending amount — if tracked — must be 0 or absent.
        pending = getattr(p1, "pending_colorless_for_main", 0)
        assert pending == 0


# ---------------------------------------------------------------------------
# With Wizard — mana amount tracked and deferred
# ---------------------------------------------------------------------------

class TestManaSculptWithWizard:
    """With a Wizard controlled, CMC-worth of {C} must be stored for main phase."""

    def test_with_wizard_mana_not_immediately_in_pool(self) -> None:
        """Mana must NOT be added to the pool at the moment of resolution."""
        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)
        stack_obj, _ = _make_sorcery_on_stack(game, p1, mana_cost="{3}")
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # The mana must be deferred, not immediate.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_with_wizard_pending_mana_amount_is_cmc(self) -> None:
        """Pending colorless amount must equal the countered spell's CMC."""
        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)
        # CMC = 3 (one generic {3})
        stack_obj, card = _make_sorcery_on_stack(game, p1, mana_cost="{3}")
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        pending = getattr(p1, "pending_colorless_for_main", None)
        assert pending == 3  # CMC of {3} is 3

    def test_with_wizard_pending_mana_matches_colored_cmc(self) -> None:
        """CMC counting includes colored pips (e.g. {2}{R}{R} → CMC 4)."""
        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)
        stack_obj, _ = _make_sorcery_on_stack(game, p1, mana_cost="{2}{R}{R}")
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        pending = getattr(p1, "pending_colorless_for_main", None)
        assert pending == 4  # {2} + {R} + {R} = 4

    def test_with_wizard_zero_cost_spell_no_pending_mana(self) -> None:
        """Countering a 0-cost spell gives 0 mana (nothing to refund)."""
        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)
        # {0} is not a standard cost; use a 0-CMC card by giving it no cost
        card = Sorcery(
            name="Free Spell",
            mana_cost=ManaCost(),  # 0 CMC
            owner=p1,
            controller=p1,
        )
        stack_obj = StackObject(source=card, controller=p1)
        game.stack.push(stack_obj)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        pending = getattr(p1, "pending_colorless_for_main", 0)
        assert pending == 0

    def test_with_wizard_high_cost_spell_correct_amount(self) -> None:
        """Countering a 7-CMC spell gives 7 colorless pending mana."""
        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)
        stack_obj, _ = _make_sorcery_on_stack(game, p1, mana_cost="{4}{U}{U}{U}")
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        pending = getattr(p1, "pending_colorless_for_main", None)
        assert pending == 7  # {4} + {U} + {U} + {U} = 7

    def test_non_wizard_creature_does_not_trigger_bonus(self) -> None:
        """A creature without 'Wizard' subtype must not grant the mana bonus."""
        game = create_game()
        p1 = game.players[0]
        # Add a non-Wizard creature
        cleric = Creature(
            name="Healing Cleric",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
            subtypes={"Cleric"},
        )
        game.get_battlefield(p1).add(cleric)

        stack_obj, _ = _make_sorcery_on_stack(game, p1, mana_cost="{3}")
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        pending = getattr(p1, "pending_colorless_for_main", 0)
        assert pending == 0


# ---------------------------------------------------------------------------
# Mana delivery timing — beginning of caster's next main phase
# ---------------------------------------------------------------------------

class TestManaSculptManaDelivery:
    """Pending colorless mana must appear in the pool at the beginning of main phase."""

    def test_mana_delivered_when_main_phase_begins(self) -> None:
        """After on_resolve with a Wizard, pending colorless mana must be
        delivered at the beginning of the caster's next main phase.

        This test advances the game state to the precombat main phase and
        resolves any triggers queued during on_resolve.
        """
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)
        stack_obj, _ = _make_sorcery_on_stack(game, p1, mana_cost="{3}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # Advance to the caster's precombat main phase.
        game.active_player_index = 0  # p1 is the active player
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        # Invoke any delivery callbacks the implementation registered.
        if hasattr(p1, "_deliver_main_phase_mana"):
            p1._deliver_main_phase_mana(game)

        # Also drain any stack triggers that were queued on_resolve.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        colorless_in_pool = p1.mana_pool.get(ManaType.COLORLESS)
        assert colorless_in_pool == 3

    def test_mana_delivered_at_correct_amount_via_trigger(self) -> None:
        """Trigger resolution should add exactly CMC colorless mana to the pool."""
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)
        # Counterspell a 5-mana spell
        stack_obj, _ = _make_sorcery_on_stack(game, p1, mana_cost="{3}{G}{G}")

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [stack_obj]
        spell.on_resolve(game)

        # Resolve any triggers that were put on the stack during on_resolve.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            # Manually set active player/phase to main phase before resolving
            # so that "beginning of main phase" condition is met.
            game.active_player_index = 0
            game.phase = Phase.PRECOMBAT_MAIN
            game.step = None
            obj.on_resolve(game)

        colorless_in_pool = p1.mana_pool.get(ManaType.COLORLESS)
        assert colorless_in_pool == 5  # {3}{G}{G} CMC = 5
