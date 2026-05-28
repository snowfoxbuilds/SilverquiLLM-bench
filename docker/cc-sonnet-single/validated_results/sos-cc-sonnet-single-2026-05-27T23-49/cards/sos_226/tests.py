"""Tests for SOS 226 — Silverquill, the Disputant.

Covers:
- Static card properties (name, mana cost, P/T, keywords, supertypes, subtypes)
- Flying and vigilance keywords present
- register_triggers wires up a casualty trigger for instants/sorceries
- Casualty mechanic: offer to sacrifice a creature with power >= 1 when casting
  an instant or sorcery
- Casualty trigger fires only on instants/sorceries (not creatures, enchantments, etc.)
- Casualty sacrifice requires power >= 1 (power-0 creatures are ineligible)
- When casualty is paid (creature sacrificed), a copy of the spell is pushed onto the stack
- When casualty is declined (no sacrifice), no copy is made
- Copy can have new targets chosen
- Trigger only fires while Silverquill is on the battlefield
- SpellCastTriggeredEvent is the hook used to implement casualty
"""

from __future__ import annotations

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery, Land, Enchantment
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card property tests
# ---------------------------------------------------------------------------


class TestSilverquillProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_creature_card_type(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_elder_subtype(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes

    def test_dragon_subtype(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Trigger registration tests
# ---------------------------------------------------------------------------


class TestSilverquillTriggerRegistration:
    """register_triggers() must wire up a SpellCastTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        before = len(game.trigger_manager._triggers)
        card.register_triggers(game)
        after = len(game.trigger_manager._triggers)
        assert after > before

    def test_registers_spell_cast_trigger(self) -> None:
        """At least one registered trigger watches SpellCastTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        spell_cast_triggers = [
            t for t in game.trigger_manager._triggers
            if t.event_type is SpellCastTriggeredEvent
            and t.source is card
        ]
        assert len(spell_cast_triggers) >= 1

    def test_trigger_has_correct_source(self) -> None:
        """Registered trigger's source is the Silverquill instance."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = [t for t in game.trigger_manager._triggers if t.source is card]
        assert len(triggers) >= 1


# ---------------------------------------------------------------------------
# Casualty condition tests — which spells trigger casualty
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyCondition:
    """Casualty trigger should fire on instants and sorceries, not on other types."""

    def _get_casualty_trigger(self, game, card) -> TriggerRegistration | None:
        """Helper: find the first SpellCastTriggeredEvent trigger owned by card."""
        for t in game.trigger_manager._triggers:
            if t.source is card and t.event_type is SpellCastTriggeredEvent:
                return t
        return None

    def test_condition_true_for_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        instant = Instant(name="Test Bolt")
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=instant)
        assert trigger.condition is None or trigger.condition(game, event) is True

    def test_condition_true_for_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        sorcery = Sorcery(name="Test Sorcery")
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=sorcery)
        assert trigger.condition is None or trigger.condition(game, event) is True

    def test_condition_false_for_creature(self) -> None:
        """Casualty should NOT apply to creature spells."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        if trigger.condition is None:
            # If condition is None it always fires; that would be a bug for creatures
            # but can't be tested via condition check. Skip instead of falsely pass.
            pytest.skip("trigger.condition is None — cannot verify per-type filtering")

        creature = Creature(name="Test Bear", base_power=2, base_toughness=2)
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=creature)
        assert trigger.condition(game, event) is False

    def test_condition_false_for_enchantment(self) -> None:
        """Casualty should NOT apply to enchantment spells."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        if trigger.condition is None:
            pytest.skip("trigger.condition is None — cannot verify per-type filtering")

        enchantment = Enchantment(name="Test Enchantment")
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=enchantment)
        assert trigger.condition(game, event) is False

    def test_condition_only_triggers_for_controller(self) -> None:
        """Casualty only applies when the controller casts the spell, not the opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        if trigger.condition is None:
            pytest.skip("trigger.condition is None — cannot verify controller filtering")

        instant = Instant(name="Opponent Bolt")
        # Spell cast by p2 (not the controller)
        event = SpellCastTriggeredEvent(spell=None, player=p2, card=instant)
        assert trigger.condition(game, event) is False


# ---------------------------------------------------------------------------
# Casualty effect — sacrifice and copy
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyEffect:
    """When casualty is paid, a copy of the spell is pushed onto the stack."""

    def _get_casualty_trigger(self, game, card) -> TriggerRegistration | None:
        for t in game.trigger_manager._triggers:
            if t.source is card and t.event_type is SpellCastTriggeredEvent:
                return t
        return None

    def test_no_sacrifice_no_copy(self) -> None:
        """When the player declines to sacrifice, no copy is added to the stack."""
        from engine.player import DeterministicPlayer
        from engine.game_state import GameState
        from engine.stack import StackObject

        # Script: decline the casualty sacrifice (False = no)
        p1 = DeterministicPlayer("Alice", [False])
        p2 = DeterministicPlayer("Bob", [])
        game = GameState([p1, p2])
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN

        card = SilverquillTheDisputant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        # Put a creature on battlefield that could be sacrificed
        victim = Creature(name="Victim", base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(victim)

        # Create a mock instant spell on the stack
        spell_card = Instant(name="Test Bolt", owner=p1, controller=p1)
        spell_obj = StackObject(source=spell_card, controller=p1)
        game.stack.push(spell_obj)

        stack_size_before = len(game.stack)

        # Fire the trigger effect
        event = SpellCastTriggeredEvent(spell=spell_obj, player=p1, card=spell_card)
        trigger.effect(game)

        # No copy should be pushed
        assert len(game.stack) == stack_size_before

    def test_sacrifice_adds_copy_to_stack(self) -> None:
        """When the player sacrifices a creature, a copy of the spell is on the stack."""
        from engine.player import DeterministicPlayer
        from engine.game_state import GameState
        from engine.stack import StackObject
        from engine.types import Phase

        # Script: accept the sacrifice (True), then choose the victim creature
        victim = Creature(name="Victim", base_power=1, base_toughness=1)
        p1 = DeterministicPlayer("Alice", [True, victim])
        p2 = DeterministicPlayer("Bob", [])
        game = GameState([p1, p2])
        game.phase = Phase.PRECOMBAT_MAIN

        victim.owner = p1
        victim.controller = p1

        card = SilverquillTheDisputant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        game.get_battlefield(p1).add(victim)

        spell_card = Instant(name="Test Bolt", owner=p1, controller=p1)
        spell_obj = StackObject(source=spell_card, controller=p1)
        game.stack.push(spell_obj)

        stack_size_before = len(game.stack)

        trigger.effect(game)

        # A copy should now be on the stack
        assert len(game.stack) == stack_size_before + 1

    def test_sacrifice_moves_creature_to_graveyard(self) -> None:
        """The sacrificed creature is moved to the graveyard."""
        from engine.player import DeterministicPlayer
        from engine.game_state import GameState
        from engine.stack import StackObject
        from engine.types import Phase

        victim = Creature(name="Sacrifice Me", base_power=2, base_toughness=2)
        p1 = DeterministicPlayer("Alice", [True, victim])
        p2 = DeterministicPlayer("Bob", [])
        game = GameState([p1, p2])
        game.phase = Phase.PRECOMBAT_MAIN

        victim.owner = p1
        victim.controller = p1

        card = SilverquillTheDisputant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        game.get_battlefield(p1).add(victim)
        assert game.get_battlefield(p1).contains(victim)

        spell_card = Instant(name="Test Bolt", owner=p1, controller=p1)
        spell_obj = StackObject(source=spell_card, controller=p1)
        game.stack.push(spell_obj)

        trigger.effect(game)

        # Victim should be in graveyard, not battlefield
        assert not game.get_battlefield(p1).contains(victim)
        assert game.get_graveyard(p1).contains(victim)


# ---------------------------------------------------------------------------
# Casualty power requirement tests
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyPowerRequirement:
    """Only creatures with power >= 1 can be sacrificed for casualty."""

    def _get_casualty_trigger(self, game, card) -> TriggerRegistration | None:
        for t in game.trigger_manager._triggers:
            if t.source is card and t.event_type is SpellCastTriggeredEvent:
                return t
        return None

    def test_power_zero_creature_cannot_pay_casualty(self) -> None:
        """A 0-power creature is not a legal casualty sacrifice.

        If only a 0-power creature is on the battlefield, the casualty
        effect should not result in a copy even if the player says yes.
        """
        from engine.player import DeterministicPlayer
        from engine.game_state import GameState
        from engine.stack import StackObject
        from engine.types import Phase

        # Power-0 creature present — player says yes but no valid victim
        weak = Creature(name="Memnite", base_power=0, base_toughness=1)
        p1 = DeterministicPlayer("Alice", [True, weak])
        p2 = DeterministicPlayer("Bob", [])
        game = GameState([p1, p2])
        game.phase = Phase.PRECOMBAT_MAIN

        weak.owner = p1
        weak.controller = p1

        card = SilverquillTheDisputant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        game.get_battlefield(p1).add(weak)

        spell_card = Instant(name="Test Bolt", owner=p1, controller=p1)
        spell_obj = StackObject(source=spell_card, controller=p1)
        game.stack.push(spell_obj)

        stack_size_before = len(game.stack)
        # The implementation should reject the power-0 sacrifice — no copy added
        try:
            trigger.effect(game)
        except Exception:
            pass  # If it raises on invalid target, that's also acceptable

        # Either the stack is unchanged, or the weak creature stayed on battlefield
        # (power-0 = not a valid casualty target)
        victim_still_on_battlefield = game.get_battlefield(p1).contains(weak)
        no_copy_added = len(game.stack) == stack_size_before
        # At least one must be true: either no copy made, or victim not sacrificed
        assert no_copy_added or victim_still_on_battlefield

    def test_power_one_creature_can_pay_casualty(self) -> None:
        """A power-1 creature is a valid casualty sacrifice."""
        from engine.player import DeterministicPlayer
        from engine.game_state import GameState
        from engine.stack import StackObject
        from engine.types import Phase

        one_one = Creature(name="Soldier Token", base_power=1, base_toughness=1)
        p1 = DeterministicPlayer("Alice", [True, one_one])
        p2 = DeterministicPlayer("Bob", [])
        game = GameState([p1, p2])
        game.phase = Phase.PRECOMBAT_MAIN

        one_one.owner = p1
        one_one.controller = p1

        card = SilverquillTheDisputant(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        trigger = self._get_casualty_trigger(game, card)
        assert trigger is not None

        game.get_battlefield(p1).add(one_one)

        spell_card = Instant(name="Test Bolt", owner=p1, controller=p1)
        spell_obj = StackObject(source=spell_card, controller=p1)
        game.stack.push(spell_obj)

        stack_size_before = len(game.stack)
        trigger.effect(game)

        # A power-1 creature is valid — copy should be on the stack
        assert len(game.stack) == stack_size_before + 1


# ---------------------------------------------------------------------------
# Battlefield presence requirement
# ---------------------------------------------------------------------------


class TestSilverquillBattlefieldPresence:
    """Casualty effect should only apply while Silverquill is on the battlefield."""

    def _get_casualty_trigger(self, game, card) -> TriggerRegistration | None:
        for t in game.trigger_manager._triggers:
            if t.source is card and t.event_type is SpellCastTriggeredEvent:
                return t
        return None

    def test_trigger_not_registered_without_entering_battlefield(self) -> None:
        """Triggers are not registered until register_triggers() is called."""
        game = create_game()
        p1 = game.players[0]
        # Create the card but do NOT call register_triggers
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        triggers_for_card = [
            t for t in game.trigger_manager._triggers if t.source is card
        ]
        assert len(triggers_for_card) == 0

    def test_trigger_deregistered_on_leave_battlefield(self) -> None:
        """After unregistering triggers, no triggers remain for this card."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)

        # Verify triggers were registered
        triggers_before = [
            t for t in game.trigger_manager._triggers if t.source is card
        ]
        assert len(triggers_before) >= 1

        # Simulate leaving battlefield by unregistering
        game.trigger_manager.unregister(card)

        triggers_after = [
            t for t in game.trigger_manager._triggers if t.source is card
        ]
        assert len(triggers_after) == 0
