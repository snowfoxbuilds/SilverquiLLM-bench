"""Tests for SOS 57 — Mana Sculpt.

Covers:
- Static card properties (name, mana cost, type)
- Targeting API: get_targets returns a TargetRequirement for any spell on the stack
- can_cast: returns False when no valid target on the stack
- on_resolve: counters target spell (removes from stack, moves card to owner's graveyard)
- on_resolve without a Wizard: no mana bonus
- on_resolve with a Wizard: registers/schedules {C} equal to countered spell's CMC
- Mana amount equals the mana value (CMC) of the countered spell
- No chosen target: on_resolve is a graceful no-op
- Wizard check: only creatures with subtype "Wizard" on controller's battlefield count
"""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone, TargetRequirement
from engine.stack import StackObject
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_wizard(name: str = "Test Wizard") -> Creature:
    """Create a simple creature with the Wizard subtype."""
    c = Creature(name=name, base_power=2, base_toughness=2)
    c.subtypes = {"Wizard"}
    return c


def _push_spell(game, player, card) -> StackObject:
    """Put card on the stack so it can be targeted."""
    stack_obj = StackObject(source=card, controller=player)
    # Also place it in the player's stack zone so _counter_spell can find it.
    player.zones[Zone.STACK].add(card)
    game.stack.push(stack_obj)
    return stack_obj


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

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

    def test_card_type_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------

class TestManaSculptTargeting:
    """get_targets returns a single TargetRequirement for any spell on the stack."""

    def test_get_targets_returns_list(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        result = card.get_targets(game)
        assert isinstance(result, list)

    def test_get_targets_returns_one_requirement(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        result = card.get_targets(game)
        assert len(result) == 1

    def test_get_targets_requirement_is_target_requirement(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        req = card.get_targets(game)[0]
        assert isinstance(req, TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        req = card.get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_target_filter_accepts_spell_stack_object(self) -> None:
        """The filter should accept a StackObject whose source is a spell."""
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        req = card.get_targets(game)[0]

        spell = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"))
        stack_obj = StackObject(source=spell, controller=p1)
        assert req.filter_fn(stack_obj) is True

    def test_target_filter_rejects_self(self) -> None:
        """The filter must reject the ManaSculpt spell itself from targeting itself."""
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        self_obj = StackObject(source=card, controller=p1)
        assert req.filter_fn(self_obj) is False


# ---------------------------------------------------------------------------
# Countering the spell
# ---------------------------------------------------------------------------

class TestManaSculptCountersSpell:
    """on_resolve removes the target spell from the stack and puts it in graveyard."""

    def test_on_resolve_removes_target_from_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Opponent's spell on the stack.
        opp_spell = Sorcery(name="Wrath", mana_cost=ManaCost.parse("{2}{W}{W}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]
        counterspell.on_resolve(game)

        assert game.stack.is_empty()

    def test_on_resolve_moves_countered_spell_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        opp_spell = Sorcery(name="Wrath", mana_cost=ManaCost.parse("{2}{W}{W}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]
        counterspell.on_resolve(game)

        assert game.get_graveyard(p2).contains(opp_spell)

    def test_on_resolve_no_target_is_noop(self) -> None:
        """If there's no chosen target, on_resolve must not raise."""
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        # chosen_targets is empty or not set
        card.chosen_targets = []
        card.on_resolve(game)  # must not raise

    def test_on_resolve_without_chosen_targets_attribute_is_noop(self) -> None:
        """If chosen_targets attr is absent, on_resolve must not raise."""
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        card.on_resolve(game)  # must not raise


# ---------------------------------------------------------------------------
# No-Wizard: no mana bonus
# ---------------------------------------------------------------------------

class TestManaSculptNoWizardNoBonusMana:
    """Without a Wizard on the battlefield, no mana is added."""

    def test_no_wizard_no_pending_mana(self) -> None:
        """With no Wizard controlled, no mana should be pending or added."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Ensure no Wizards on p1's battlefield.
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        bear.subtypes = {"Bear"}
        set_board_state(game, 0, battlefield=[bear])

        opp_spell = Sorcery(name="Inferno", mana_cost=ManaCost.parse("{4}{R}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]
        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        counterspell.on_resolve(game)

        # Mana pool should not have increased immediately.
        mana_after = p1.mana_pool.get(ManaType.COLORLESS)
        assert mana_after == mana_before

    def test_no_wizard_no_trigger_registered(self) -> None:
        """Without a Wizard, no trigger should be registered for main-phase mana."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        opp_spell = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]

        triggers_before = len(game.trigger_manager.get_triggers())
        counterspell.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        assert triggers_after == triggers_before


# ---------------------------------------------------------------------------
# Wizard present: mana bonus scheduled
# ---------------------------------------------------------------------------

class TestManaSculptWizardBonusMana:
    """With a Wizard controlled, {C} equal to countered spell's CMC is scheduled."""

    def test_wizard_triggers_mana_registration(self) -> None:
        """With a Wizard present, a trigger or pending state is registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = p1
        wizard.controller = p1
        set_board_state(game, 0, battlefield=[wizard])

        opp_spell = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]

        triggers_before = len(game.trigger_manager.get_triggers())
        counterspell.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        # A trigger (for the mana-at-main-phase effect) should have been registered.
        assert triggers_after > triggers_before

    def test_mana_amount_equals_countered_spell_cmc(self) -> None:
        """The mana added equals the CMC of the countered spell."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = p1
        wizard.controller = p1
        set_board_state(game, 0, battlefield=[wizard])

        # Spell with CMC 5 (3 generic + 1R + 1G = 5)
        opp_spell = Creature(
            name="Big Bear",
            mana_cost=ManaCost.parse("{3}{R}{G}"),
            base_power=5, base_toughness=5,
        )
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]
        counterspell.on_resolve(game)

        # The pending mana attribute should record the CMC (5).
        pending = getattr(counterspell, "pending_mana_amount", None)
        assert pending == 5, (
            f"Expected pending_mana_amount == 5 (CMC of countered spell), got {pending!r}"
        )

    def test_mana_amount_equals_zero_for_free_spell(self) -> None:
        """For a zero-cost spell, the mana bonus is 0 {C}."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = p1
        wizard.controller = p1
        set_board_state(game, 0, battlefield=[wizard])

        free_spell = Instant(name="Ancestral Vision", mana_cost=ManaCost())
        free_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, free_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]
        counterspell.on_resolve(game)

        pending = getattr(counterspell, "pending_mana_amount", None)
        assert pending == 0 or pending is None, (
            f"Expected pending_mana_amount == 0 for a free spell, got {pending!r}"
        )

    def test_wizard_check_uses_controller_battlefield(self) -> None:
        """Only the caster's battlefield is checked for a Wizard, not the opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Wizard on OPPONENT's battlefield, not p1's.
        opp_wizard = _make_wizard("Opponent's Wizard")
        opp_wizard.owner = p2
        opp_wizard.controller = p2
        set_board_state(game, 1, battlefield=[opp_wizard])

        opp_spell = Sorcery(name="Shock", mana_cost=ManaCost.parse("{R}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]

        triggers_before = len(game.trigger_manager.get_triggers())
        counterspell.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        # No trigger should have been registered because p1 doesn't control a Wizard.
        assert triggers_after == triggers_before

    def test_non_wizard_creature_does_not_trigger_bonus(self) -> None:
        """A creature without the Wizard subtype should not enable the bonus."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        non_wizard = Creature(name="Soldier", base_power=2, base_toughness=2)
        non_wizard.subtypes = {"Human", "Soldier"}
        non_wizard.owner = p1
        non_wizard.controller = p1
        set_board_state(game, 0, battlefield=[non_wizard])

        opp_spell = Sorcery(name="Brainstorm", mana_cost=ManaCost.parse("{U}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]

        triggers_before = len(game.trigger_manager.get_triggers())
        counterspell.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        assert triggers_after == triggers_before

    def test_wizard_present_trigger_fires_at_main_phase(self) -> None:
        """The registered trigger fires at beginning of next main phase and adds mana."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent  # Added by implementer

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = p1
        wizard.controller = p1
        set_board_state(game, 0, battlefield=[wizard])

        # CMC of the spell = 3 (1 generic + 1U + 1U = 3)
        opp_spell = Instant(name="Counterspell", mana_cost=ManaCost.parse("{U}{U}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]
        counterspell.on_resolve(game)

        # Simulate beginning of main phase event
        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1)
        )
        # Resolve the triggered ability from the stack
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        mana_after = p1.mana_pool.get(ManaType.COLORLESS)
        # Spell CMC is 2 ({U}{U}), so 2 colorless should be added.
        assert mana_after - mana_before == 2

    def test_trigger_is_one_shot(self) -> None:
        """The main-phase mana trigger fires only once and then unregisters."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent  # Added by implementer

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = p1
        wizard.controller = p1
        set_board_state(game, 0, battlefield=[wizard])

        opp_spell = Sorcery(name="Terror", mana_cost=ManaCost.parse("{1}{B}"))
        opp_spell.owner = p2
        target_stack_obj = _push_spell(game, p2, opp_spell)

        counterspell = ManaSculpt(owner=p1, controller=p1)
        counterspell.chosen_targets = [target_stack_obj]
        counterspell.on_resolve(game)

        # Fire first main-phase event.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        mana_after_first = p1.mana_pool.get(ManaType.COLORLESS)

        # Fire second main-phase event — trigger should not fire again.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        mana_after_second = p1.mana_pool.get(ManaType.COLORLESS)
        # Mana should not have increased on the second firing.
        assert mana_after_second == mana_after_first
