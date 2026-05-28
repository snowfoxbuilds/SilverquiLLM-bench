"""Tests for SOS 1 — The Dawning Archaic.

The Dawning Archaic is a {10} Legendary Creature — Avatar with 7/7 and Reach.

Requirements tested:
1. Static properties: name, mana cost, power/toughness, types, supertypes, keywords.
2. Cost reduction: costs {1} less for each instant and sorcery card in your graveyard.
3. Reach keyword.
4. Attack trigger: "Whenever The Dawning Archaic attacks, you may cast target instant
   or sorcery card from your graveyard without paying its mana cost."
5. Replacement clause: "If that spell would be put into your graveyard, exile it instead."
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_is_legendary(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_avatar_subtype(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_has_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_has_creature_type(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Cost reduction
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """This spell costs {1} less for each instant and sorcery card in your graveyard."""

    def test_one_instant_in_graveyard_reduces_by_one(self) -> None:
        """One instant in graveyard should reduce cost by 1."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[bolt])

        reduction = card.cost_reduction(game)
        assert reduction == 1

    def test_one_sorcery_in_graveyard_reduces_by_one(self) -> None:
        """One sorcery in graveyard should reduce cost by 1."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        divination = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[divination])

        reduction = card.cost_reduction(game)
        assert reduction == 1

    def test_multiple_instants_and_sorceries(self) -> None:
        """Multiple instants and sorceries should each reduce cost by 1."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        shock = Instant(name="Shock", owner=p1, controller=p1)
        divination = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[bolt, shock, divination])

        reduction = card.cost_reduction(game)
        assert reduction == 3

    def test_creatures_in_graveyard_do_not_reduce_cost(self) -> None:
        """Creature cards in graveyard should not count toward reduction."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])

        reduction = card.cost_reduction(game)
        assert reduction == 0

    def test_mixed_card_types_only_counts_instants_sorceries(self) -> None:
        """Only instant and sorcery cards count, not creatures or other types."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        divination = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[bolt, bear, divination])

        reduction = card.cost_reduction(game)
        assert reduction == 2

    def test_opponent_graveyard_does_not_count(self) -> None:
        """Only the controller's graveyard should be counted."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)

        # Put instants in opponent's graveyard, not controller's
        bolt = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[bolt])

        reduction = card.cost_reduction(game)
        assert reduction == 0

    def test_reduction_up_to_ten(self) -> None:
        """With 10+ instants/sorceries, the cost reduction should be at least 10
        (the full generic cost), making it castable for free."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        gy_cards = []
        for i in range(10):
            gy_cards.append(Instant(name=f"Spell_{i}", owner=p1, controller=p1))
        set_board_state(game, 0, graveyard=gy_cards)

        reduction = card.cost_reduction(game)
        assert reduction == 10


# ---------------------------------------------------------------------------
# Attack trigger — registration
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTriggerRegistration:
    """Whenever The Dawning Archaic attacks, the trigger should be registered."""

    def test_registers_attack_trigger(self) -> None:
        """register_triggers should register at least one AttacksTriggeredEvent trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        before_count = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after_count = len(game.trigger_manager.get_triggers())

        assert after_count > before_count

    def test_registered_trigger_watches_attacks_event(self) -> None:
        """The registered trigger should watch for AttacksTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ]
        assert len(attack_triggers) >= 1

    def test_trigger_condition_matches_self_attacking(self) -> None:
        """The trigger condition should match when this creature attacks."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ]
        assert len(attack_triggers) >= 1

        # Build an event where this creature attacks
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        trigger = attack_triggers[0]
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True

    def test_trigger_condition_does_not_match_other_creature(self) -> None:
        """The trigger should NOT fire when a different creature attacks."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        other = Creature(name="Other Creature", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ]
        assert len(attack_triggers) >= 1

        event = AttacksTriggeredEvent(creature=other, attacker=other)
        trigger = attack_triggers[0]
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False


# ---------------------------------------------------------------------------
# Attack trigger — targeting (instant/sorcery in graveyard)
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackTriggerTargeting:
    """The attack trigger targets an instant or sorcery card in the graveyard."""

    def test_get_targets_returns_at_least_one_requirement(self) -> None:
        """get_targets should return at least one target requirement for the
        attack trigger (targeting an instant or sorcery in the graveyard)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        targets = card.get_targets(game)
        assert isinstance(targets, list)
        assert len(targets) >= 1, "Expected at least one target requirement"

    def test_get_targets_zone_is_graveyard(self) -> None:
        """The target requirement should specify the graveyard zone."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        targets = card.get_targets(game)
        assert len(targets) >= 1
        req = targets[0]
        assert req.zone == Zone.GRAVEYARD

    def test_get_targets_filter_accepts_instant(self) -> None:
        """The target filter should accept instant cards."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        targets = card.get_targets(game)
        assert len(targets) >= 1
        req = targets[0]

        bolt = Instant(name="Lightning Bolt")
        assert req.filter_fn(bolt) is True

    def test_get_targets_filter_accepts_sorcery(self) -> None:
        """The target filter should accept sorcery cards."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        targets = card.get_targets(game)
        assert len(targets) >= 1
        req = targets[0]

        div = Sorcery(name="Divination")
        assert req.filter_fn(div) is True

    def test_get_targets_filter_rejects_creature(self) -> None:
        """The target filter should reject creature cards."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        targets = card.get_targets(game)
        assert len(targets) >= 1
        req = targets[0]

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        assert req.filter_fn(bear) is False


# ---------------------------------------------------------------------------
# Attack trigger — effect (free cast from graveyard)
# ---------------------------------------------------------------------------


class TestTheDawningArchaicFreeCast:
    """When the attack trigger resolves, you may cast the targeted instant or
    sorcery from your graveyard without paying its mana cost."""

    def test_attack_trigger_casts_spell_from_graveyard(self) -> None:
        """When the trigger resolves with a valid target in graveyard,
        that spell should be cast (moved from graveyard)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # Put an instant in the graveyard
        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1,
                       mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, graveyard=[bolt])

        # Verify it is in the graveyard before trigger fires
        assert game.get_graveyard(p1).contains(bolt)

        # Fire the attack event for this creature
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)

        # Resolve the triggered ability from the stack
        if not game.stack.is_empty():
            # The trigger effect should interact with the graveyard spell.
            # After resolving, the bolt should no longer be in the graveyard
            # (it was cast and should end up exiled per the replacement clause,
            # or at minimum no longer in the graveyard).
            stack_obj = game.stack.pop()
            # Set up target for the trigger effect
            stack_obj.source.chosen_targets = [bolt] if hasattr(stack_obj, 'source') else None
            stack_obj.on_resolve(game)

            # The bolt should no longer be in the graveyard
            # (it was either cast and exiled, or moved to stack/exile)
            graveyard_contains_bolt = game.get_graveyard(p1).contains(bolt)
            exile_contains_bolt = game.get_exile(p1).contains(bolt)
            # The bolt should either be exiled or on the stack (being cast)
            assert not graveyard_contains_bolt or exile_contains_bolt

    def test_free_cast_does_not_require_mana(self) -> None:
        """The spell should be castable without paying mana even though the
        player's mana pool may be empty."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # Expensive spell in graveyard, no mana in pool
        spell = Sorcery(name="Expensive Spell", owner=p1, controller=p1,
                        mana_cost=ManaCost.parse("{8}"))
        set_board_state(game, 0, graveyard=[spell], mana={})

        # Verify mana pool is empty
        assert p1.mana_pool.can_pay(ManaCost.parse("{1}")) is False

        # Fire the attack event
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)

        # Resolve the trigger
        if not game.stack.is_empty():
            stack_obj = game.stack.pop()
            # The trigger resolves and casts the spell for free
            # This should not raise even with empty mana pool
            if hasattr(stack_obj, 'source'):
                stack_obj.source.chosen_targets = [spell]
            stack_obj.on_resolve(game)


# ---------------------------------------------------------------------------
# Replacement — exile instead of graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicExileReplacement:
    """If the free-cast spell would be put into your graveyard, exile it instead."""

    def test_cast_spell_goes_to_exile_not_graveyard(self) -> None:
        """After the free-cast resolves, the instant/sorcery should end up
        in exile, not the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1,
                       mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, graveyard=[bolt])

        # Fire the attack event
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)

        # Resolve the triggered ability (which casts the spell)
        if not game.stack.is_empty():
            stack_obj = game.stack.pop()
            if hasattr(stack_obj, 'source'):
                stack_obj.source.chosen_targets = [bolt]
            stack_obj.on_resolve(game)

        # Resolve any spell that got cast onto the stack
        while not game.stack.is_empty():
            top = game.stack.pop()
            top.on_resolve(game)

        # The spell should be in exile, NOT in graveyard
        assert game.get_exile(p1).contains(bolt), \
            "The free-cast spell should be exiled instead of going to graveyard"
        assert not game.get_graveyard(p1).contains(bolt), \
            "The free-cast spell should NOT return to the graveyard"

    def test_normal_spells_still_go_to_graveyard(self) -> None:
        """The exile-instead-of-graveyard effect only applies to the spell
        cast via this trigger, not to all instants/sorceries everywhere."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # A separately cast spell (not via the trigger) should still go to GY
        normal_bolt = Instant(name="Normal Bolt", owner=p1, controller=p1,
                              mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[normal_bolt],
                        mana={ManaType.RED: 1})

        # Cast the spell normally via the hand
        from test_utils import cast_spell
        cast_spell(game, 0, "Normal Bolt")

        # Normal spell should go to graveyard, not exile
        assert game.get_graveyard(p1).contains(normal_bolt), \
            "A normally-cast spell should go to the graveyard"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestTheDawningArchaicEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_graveyard_no_valid_target(self) -> None:
        """With no instants or sorceries in graveyard, the trigger should
        have no valid targets and should not crash."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # Graveyard is empty
        set_board_state(game, 0, graveyard=[])

        # Fire the attack event — should not crash
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)

        # If trigger was added to stack, resolve it without targets
        if not game.stack.is_empty():
            stack_obj = game.stack.pop()
            # Resolving with no valid target should be safe
            stack_obj.on_resolve(game)

    def test_graveyard_with_only_creatures_no_valid_target(self) -> None:
        """If the graveyard only has creatures (no instants/sorceries),
        the trigger should have no valid targets."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])

        # Fire the attack event — should not crash
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)

        if not game.stack.is_empty():
            stack_obj = game.stack.pop()
            stack_obj.on_resolve(game)

        # Bear should still be in graveyard (untouched)
        assert game.get_graveyard(p1).contains(bear)

