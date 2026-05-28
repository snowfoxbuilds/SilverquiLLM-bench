"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt is an Instant ({1}{U}{U}) with two effects:
1. Counter target spell.
2. If you control a Wizard, add an amount of {C} equal to the countered
   spell's mana value at the beginning of your next main phase.

Test philosophy:
- Static properties are checked directly from the card object.
- Counterspell effect is exercised by placing a StackObject manually on
  the stack and calling on_resolve with the StackObject as the chosen target.
- The Wizard conditional is checked by examining the battlefield for Wizard
  subtypes; tests run in both the with-Wizard and without-Wizard branches.
- Mana amount tests inspect the controller's mana pool after the delayed
  effect fires, or inspect trigger registration details.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import CardImpl, Creature, Instant
from engine.stack import Stack, StackObject
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wizard(game, player, name: str = "Test Wizard") -> Creature:
    """Return a tapped-in Wizard creature in player's battlefield."""
    wizard = Creature(
        name=name,
        owner=player,
        controller=player,
        base_power=1,
        base_toughness=1,
    )
    wizard.subtypes = {"Wizard"}
    game.get_battlefield(player).add(wizard)
    return wizard


def _make_stack_spell(player, mana_cost_str: str, name: str = "Target Spell") -> StackObject:
    """Return a StackObject on the stack representing a target spell."""
    source_card = CardImpl(
        name=name,
        mana_cost=ManaCost.parse(mana_cost_str),
        card_types={CardType.INSTANT},
        owner=player,
        controller=player,
    )
    return StackObject(
        source=source_card,
        controller=player,
        on_resolve=lambda _game: None,
    )


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestManaSculptProperties:
    """Static card data must match the SOS 57 spec."""

    def test_name(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"

    def test_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)

    def test_has_instant_card_type(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_mana_cost_cmc(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.mana_cost.cmc == 3


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------

class TestManaSculptTargeting:
    """get_targets() must declare exactly one target on the stack."""

    def test_returns_one_target_requirement(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1

    def test_target_requirement_is_correct_type(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        req = card.get_targets(game)[0]
        assert isinstance(req, TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        req = card.get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_target_filter_accepts_stack_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        # A spell on the stack should pass the filter.
        target_spell = _make_stack_spell(p1, "{2}{R}")
        game.stack.push(target_spell)
        assert req.filter_fn(target_spell) is True


# ---------------------------------------------------------------------------
# Counterspell effect — removes target from stack
# ---------------------------------------------------------------------------

class TestManaSculptCounterspell:
    """on_resolve with a chosen target must remove that StackObject from the stack."""

    def test_counters_target_spell_removes_from_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = _make_stack_spell(p1, "{2}{R}", "Fireball")
        game.stack.push(target)
        assert len(game.stack) == 1

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert len(game.stack) == 0

    def test_countered_spell_no_longer_in_stack_items(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = _make_stack_spell(p1, "{3}", "Giant Growth")
        game.stack.push(target)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        remaining = game.stack.objects()
        assert target not in remaining

    def test_counters_only_target_spell_leaves_other_spells(self) -> None:
        """Only the chosen target is removed; other stack items remain."""
        game = create_game()
        p1 = game.players[0]
        other = _make_stack_spell(p1, "{1}{W}", "Other Spell")
        target = _make_stack_spell(p1, "{2}{R}", "Fireball")
        game.stack.push(other)
        game.stack.push(target)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        remaining = game.stack.objects()
        assert target not in remaining
        assert other in remaining

    def test_no_target_is_a_noop(self) -> None:
        """With no chosen_targets, on_resolve must not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)  # Should not raise


# ---------------------------------------------------------------------------
# Without a Wizard — no delayed mana
# ---------------------------------------------------------------------------

class TestManaSculptNoWizard:
    """Without a Wizard on the battlefield, no delayed mana trigger is registered."""

    def test_no_trigger_registered_without_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # No Wizard on battlefield.
        target = _make_stack_spell(p1, "{2}{R}", "Fireball")
        game.stack.push(target)

        before = len(game.trigger_manager.get_triggers())
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        after = len(game.trigger_manager.get_triggers())
        assert after == before

    def test_no_mana_added_without_wizard(self) -> None:
        """No mana is added to the pool immediately on resolve without a Wizard."""
        game = create_game()
        p1 = game.players[0]
        target = _make_stack_spell(p1, "{2}{R}", "Fireball")
        game.stack.push(target)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


# ---------------------------------------------------------------------------
# With a Wizard — delayed mana trigger registered
# ---------------------------------------------------------------------------

class TestManaSculptWithWizard:
    """With a Wizard on the battlefield, a delayed trigger for main-phase mana is registered."""

    def test_trigger_registered_when_wizard_present(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)

        target = _make_stack_spell(p1, "{2}{R}", "Fireball")
        game.stack.push(target)

        before = len(game.trigger_manager.get_triggers())
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_trigger_registered_exactly_one_when_wizard_present(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)

        target = _make_stack_spell(p1, "{2}{R}", "Fireball")
        game.stack.push(target)

        before = len(game.trigger_manager.get_triggers())
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        after = len(game.trigger_manager.get_triggers())
        assert after - before == 1

    def test_trigger_is_controlled_by_caster(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _make_wizard(game, p1)

        target = _make_stack_spell(p1, "{2}{R}", "Fireball")
        game.stack.push(target)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        assert any(t.controller is p1 for t in triggers)

    def test_no_trigger_when_opponent_has_wizard_not_controller(self) -> None:
        """The Wizard condition checks the controller's battlefield, not the opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _make_wizard(game, p2)  # opponent has Wizard, not the caster

        target = _make_stack_spell(p1, "{2}{R}", "Fireball")
        game.stack.push(target)

        before = len(game.trigger_manager.get_triggers())
        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        after = len(game.trigger_manager.get_triggers())
        assert after == before


# ---------------------------------------------------------------------------
# Mana amount equals mana value of countered spell
# ---------------------------------------------------------------------------

class TestManaSculptManaAmount:
    """The amount of {C} added must equal the mana value of the countered spell."""

    def _resolve_and_fire(self, game, p1, countered_cmc: int, mana_cost_str: str) -> None:
        """Helper: resolve Mana Sculpt countering a spell, then fire the delayed trigger."""
        _make_wizard(game, p1)
        target = _make_stack_spell(p1, mana_cost_str)
        game.stack.push(target)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        # The delayed trigger should now be registered.
        # Fire it by directly invoking the registered trigger's effect.
        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) >= 1
        # Invoke the most recently registered trigger's effect (the delayed mana one).
        trigger = triggers[-1]
        trigger.effect(game)

    def test_mana_added_equals_cmc_of_countered_spell_cmc3(self) -> None:
        """Countering a 3-CMC spell with Wizard → 3 {C} added."""
        game = create_game()
        p1 = game.players[0]
        self._resolve_and_fire(game, p1, 3, "{2}{R}")
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_mana_added_equals_cmc_of_countered_spell_cmc5(self) -> None:
        """Countering a 5-CMC spell with Wizard → 5 {C} added."""
        game = create_game()
        p1 = game.players[0]
        self._resolve_and_fire(game, p1, 5, "{3}{G}{G}")
        assert p1.mana_pool.get(ManaType.COLORLESS) == 5

    def test_mana_added_equals_cmc_of_countered_spell_cmc1(self) -> None:
        """Countering a 1-CMC spell with Wizard → 1 {C} added."""
        game = create_game()
        p1 = game.players[0]
        self._resolve_and_fire(game, p1, 1, "{U}")
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_mana_added_is_colorless_not_colored(self) -> None:
        """The mana added must be colorless ({C}), not any colored type."""
        game = create_game()
        p1 = game.players[0]
        self._resolve_and_fire(game, p1, 3, "{2}{R}")
        # Colorless pool is 3.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
        # No blue, white, black, red, or green mana is added.
        assert p1.mana_pool.get(ManaType.BLUE) == 0
        assert p1.mana_pool.get(ManaType.RED) == 0
        assert p1.mana_pool.get(ManaType.GREEN) == 0
        assert p1.mana_pool.get(ManaType.WHITE) == 0
        assert p1.mana_pool.get(ManaType.BLACK) == 0

    def test_mana_amount_zero_cmc_spell(self) -> None:
        """Countering a 0-CMC spell → 0 mana added (no {C} produced)."""
        game = create_game()
        p1 = game.players[0]

        _make_wizard(game, p1)
        # Build a 0-CMC card manually (no standard parse for empty cost,
        # so use a ManaCost with generic=0 and no pips).
        source_card = CardImpl(
            name="Free Spell",
            mana_cost=ManaCost(generic=0),
            card_types={CardType.INSTANT},
            owner=p1,
            controller=p1,
        )
        target = StackObject(
            source=source_card,
            controller=p1,
            on_resolve=lambda _game: None,
        )
        game.stack.push(target)

        spell = ManaSculpt(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) >= 1
        trigger = triggers[-1]
        trigger.effect(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
