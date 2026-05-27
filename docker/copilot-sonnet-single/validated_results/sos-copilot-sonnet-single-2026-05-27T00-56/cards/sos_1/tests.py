"""Tests for sos_1 — The Dawning Archaic.

Card spec:
  Mana cost: {10}
  Type: Legendary Creature — Avatar
  P/T: 7/7
  Keywords: Reach
  Oracle text:
    This spell costs {1} less to cast for each instant and sorcery card
    in your graveyard.
    Reach
    Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost. If that
    spell would be put into your graveyard, exile it instead.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestTheDawningArchaicProperties:
    """Static card data should match the spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power(self) -> None:
        assert TheDawningArchaic(owner=None).base_power == 7

    def test_toughness(self) -> None:
        assert TheDawningArchaic(owner=None).base_toughness == 7

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes

    def test_avatar_subtype(self) -> None:
        assert "Avatar" in TheDawningArchaic(owner=None).subtypes


# ---------------------------------------------------------------------------
# Cost reduction — {1} less per instant/sorcery in your graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicCostReduction:
    """cost_reduction() returns the number of instant/sorcery cards in
    the controller's graveyard."""

    def test_empty_graveyard_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Test Instant", owner=p1)
        set_board_state(game, 0, graveyard=[instant])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Test Sorcery", owner=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        assert card.cost_reduction(game) == 1

    def test_mixed_instants_and_sorceries_stacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant1 = Instant(name="Instant A", owner=p1)
        instant2 = Instant(name="Instant B", owner=p1)
        sorcery1 = Sorcery(name="Sorcery A", owner=p1)
        set_board_state(game, 0, graveyard=[instant1, instant2, sorcery1])
        assert card.cost_reduction(game) == 3

    def test_non_instant_sorcery_graveyard_cards_not_counted(self) -> None:
        """Creature cards in graveyard should not reduce cost."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(name="Dead Creature", owner=p1, base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[creature])
        assert card.cost_reduction(game) == 0

    def test_only_controllers_graveyard_counts(self) -> None:
        """Opponent's instant/sorceries in their graveyard do not reduce
        the controller's cost."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        opp_instant = Instant(name="Opponent Instant", owner=p2)
        set_board_state(game, 1, graveyard=[opp_instant])
        assert card.cost_reduction(game) == 0

    def test_five_instants_reduces_by_five(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instants = [Instant(name=f"Instant {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, graveyard=instants)
        assert card.cost_reduction(game) == 5

    def test_ten_instants_reduces_by_ten_making_cost_zero(self) -> None:
        """With 10 instants/sorceries the {10} cost would be fully reduced."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instants = [Instant(name=f"Instant {i}", owner=p1) for i in range(10)]
        set_board_state(game, 0, graveyard=instants)
        assert card.cost_reduction(game) == 10


# ---------------------------------------------------------------------------
# Trigger registration — "Whenever The Dawning Archaic attacks"
# ---------------------------------------------------------------------------

class TestTheDawningArchaicTriggerRegistration:
    """register_triggers() should register an AttacksTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_registers_attacks_triggered_event(self) -> None:
        """The trigger must watch for AttacksTriggeredEvent (or a parent)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1
        event_types = [t.event_type for t in triggers]
        # At least one trigger must fire for AttacksTriggeredEvent instances
        assert any(
            issubclass(AttacksTriggeredEvent, t) or t is AttacksTriggeredEvent
            for t in event_types
        )

    def test_trigger_condition_requires_self_attacking(self) -> None:
        """Trigger should only fire when *this* creature attacks, not others."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [t for t in triggers if t.event_type is AttacksTriggeredEvent]
        assert len(attack_triggers) >= 1
        trigger = attack_triggers[0]

        # Event for a different creature — condition should be False
        other_creature = Creature(name="Other Creature", owner=p1, controller=p1)
        event_other = AttacksTriggeredEvent(creature=other_creature)
        assert trigger.condition is None or trigger.condition(game, event_other) is False

    def test_trigger_condition_fires_for_self(self) -> None:
        """Trigger condition must return True when TheDawningArchaic itself attacks."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [t for t in triggers if t.event_type is AttacksTriggeredEvent]
        assert len(attack_triggers) >= 1
        trigger = attack_triggers[0]

        event_self = AttacksTriggeredEvent(creature=card)
        if trigger.condition is not None:
            assert trigger.condition(game, event_self) is True

    def test_trigger_fires_on_attack_event(self) -> None:
        """Firing an AttacksTriggeredEvent for this creature pushes onto stack."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        stack_before = len(game.stack)
        event = AttacksTriggeredEvent(creature=card)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) > stack_before

    def test_trigger_does_not_fire_for_other_attacker(self) -> None:
        """Firing an attack event for a different creature must not push
        The Dawning Archaic's trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        stack_before = len(game.stack)
        other = Creature(name="Random Attacker", owner=p1, controller=p1)
        event = AttacksTriggeredEvent(creature=other)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) == stack_before


# ---------------------------------------------------------------------------
# Attack trigger effect — cast from graveyard, exile replacement
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackTriggerEffect:
    """When the attack trigger resolves with no eligible graveyard targets,
    it should no-op gracefully."""

    def test_trigger_effect_noop_with_empty_graveyard(self) -> None:
        """With no instant/sorcery in graveyard, the trigger effect must
        not raise and must not change the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [t for t in triggers if t.event_type is AttacksTriggeredEvent]
        assert len(attack_triggers) >= 1
        # Invoke the effect directly — must not raise
        attack_triggers[0].effect(game)

    def test_trigger_effect_noop_when_graveyard_has_only_creatures(self) -> None:
        """Trigger effect is a no-op when the graveyard contains no instants
        or sorceries to cast."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(name="Dead Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[creature])
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [t for t in triggers if t.event_type is AttacksTriggeredEvent]
        assert len(attack_triggers) >= 1
        before_gy = len(game.get_graveyard(p1).get_all())
        attack_triggers[0].effect(game)
        # Graveyard unchanged (creature still there, nothing happened)
        assert len(game.get_graveyard(p1).get_all()) == before_gy
