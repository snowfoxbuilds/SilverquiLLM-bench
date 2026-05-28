"""Tests for SOS 1 — The Dawning Archaic.

Covers:
- Static card properties (name, mana cost, P/T, type line, keywords, supertypes)
- Cost reduction: {1} less per instant/sorcery in controller's graveyard
- Cost reduction counts only instants/sorceries, not other card types
- Cost reduction is capped at the generic mana component (cannot go negative)
- Attack trigger: registered on entering the battlefield via register_triggers
- Attack trigger fires only when this creature attacks (not other creatures)
- Attack trigger enables free-cast of instant/sorcery from graveyard
- Replacement: free-cast spell that would go to graveyard goes to exile instead
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery, Land, Enchantment
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, declare_attackers


# ---------------------------------------------------------------------------
# Static card property tests
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_power(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7

    def test_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_is_legendary(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_creature_card_type(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_avatar_subtype(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes


# ---------------------------------------------------------------------------
# Cost reduction tests
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """cost_reduction() returns {1} per instant/sorcery in the graveyard."""

    def test_no_graveyard_cards_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Empty graveyard → no reduction
        assert card.cost_reduction(game) == 0

    def test_one_instant_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt")
        set_board_state(game, 0, graveyard=[instant])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination")
        set_board_state(game, 0, graveyard=[sorcery])
        assert card.cost_reduction(game) == 1

    def test_multiple_instants_and_sorceries_reduce_each(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_cards = [
            Instant(name="Bolt"),
            Instant(name="Shock"),
            Sorcery(name="Wrath"),
            Sorcery(name="Divination"),
        ]
        set_board_state(game, 0, graveyard=graveyard_cards)
        assert card.cost_reduction(game) == 4

    def test_non_instant_sorcery_cards_do_not_contribute(self) -> None:
        """Creatures, lands, enchantments in graveyard don't reduce cost."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        forest = Land(name="Forest")
        ench = Enchantment(name="Pacifism")
        set_board_state(game, 0, graveyard=[bear, forest, ench])
        assert card.cost_reduction(game) == 0

    def test_mixed_graveyard_counts_only_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Bolt")
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[instant, bear])
        assert card.cost_reduction(game) == 1

    def test_ten_instants_reduces_full_cost(self) -> None:
        """10 instants/sorceries → reduce the full {10} generic cost to {0}."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_cards = [Instant(name=f"Spell{i}") for i in range(10)]
        set_board_state(game, 0, graveyard=graveyard_cards)
        # Reduction capped at the card's 10 generic mana
        assert card.cost_reduction(game) == 10

    def test_more_than_ten_instants_capped_at_ten(self) -> None:
        """Reduction cannot exceed the generic mana component (10)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_cards = [Instant(name=f"Spell{i}") for i in range(15)]
        set_board_state(game, 0, graveyard=graveyard_cards)
        # Max reduction is 10 (the generic portion of the mana cost)
        assert card.cost_reduction(game) <= 10

    def test_opponent_graveyard_does_not_contribute(self) -> None:
        """Only the controller's own graveyard counts."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Put instants in opponent's graveyard, not controller's
        set_board_state(game, 1, graveyard=[Instant(name="Bolt"), Instant(name="Shock")])
        # Controller's graveyard is empty → no reduction
        assert card.cost_reduction(game) == 0

    def test_cast_cost_reduced_by_graveyard(self) -> None:
        """Integration: with instants in graveyard, can cast for reduced cost."""
        game = create_game()
        p1 = game.players[0]
        # Put 9 instants in graveyard so the 10-cost becomes 1
        graveyard_cards = [Instant(name=f"Spell{i}") for i in range(9)]
        card = TheDawningArchaic(owner=None)
        set_board_state(game, 0,
                        hand=[card],
                        graveyard=graveyard_cards,
                        mana={ManaType.COLORLESS: 1})
        # With 9 instants in GY, cost is {10} - 9 = {1} — exactly enough mana
        from test_utils import cast_spell as test_cast_spell
        test_cast_spell(game, 0, "The Dawning Archaic")
        # Successfully resolved to battlefield
        assert game.get_battlefield(p1).contains(card)


# ---------------------------------------------------------------------------
# Attack trigger registration tests
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTriggerRegistration:
    """register_triggers() must wire an AttacksTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_registers_attacks_trigger(self) -> None:
        """At least one registered trigger must watch AttacksTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        assert len(attack_triggers) >= 1

    def test_trigger_source_is_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        assert len(attack_triggers) >= 1
        assert attack_triggers[0].source is card

    def test_trigger_condition_is_self_only(self) -> None:
        """The trigger must only fire when THIS creature attacks, not any attacker."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        assert len(attack_triggers) >= 1
        trigger = attack_triggers[0]
        if trigger.condition is not None:
            # Must match when `creature` is the card itself
            event_self = AttacksTriggeredEvent(creature=card)
            assert trigger.condition(game, event_self) is True
            # Must NOT match when a different creature attacks
            other = Creature(name="Other Creature", base_power=2, base_toughness=2)
            event_other = AttacksTriggeredEvent(creature=other)
            assert trigger.condition(game, event_other) is False


# ---------------------------------------------------------------------------
# Attack trigger effect — free-cast from graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackTriggerEffect:
    """The attack trigger allows free-casting an instant/sorcery from the graveyard."""

    def test_attack_trigger_casts_instant_from_graveyard(self) -> None:
        """When the attack trigger fires, it casts an instant from the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Put a cheap instant in the graveyard as the target
        instant = Instant(name="Lightning Bolt")
        set_board_state(game, 0, graveyard=[instant])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        assert len(attack_triggers) >= 1
        trigger = attack_triggers[0]

        # Fire the effect directly — simulates the trigger resolving
        trigger.effect(game)

        # The instant should no longer be in the graveyard
        assert not game.get_graveyard(p1).contains(instant)

    def test_attack_trigger_no_op_with_empty_graveyard(self) -> None:
        """If the graveyard has no instants/sorceries, the trigger resolves gracefully."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        assert len(attack_triggers) >= 1
        trigger = attack_triggers[0]

        # Should not raise even with empty graveyard
        trigger.effect(game)

    def test_attack_trigger_fires_on_attacking(self) -> None:
        """Declaring this creature as an attacker fires the attack trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Prevent summoning sickness so it can attack
        card.summoning_sick = False
        card.is_tapped = False
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        before_stack_size = len(game.stack.objects())
        # Fire the trigger manager with an AttacksTriggeredEvent for this card
        from engine.events import AttacksTriggeredEvent as ATE
        game.trigger_manager.fire_event(game, ATE(creature=card))

        # A trigger should have been pushed to the stack
        assert len(game.stack.objects()) > before_stack_size

    def test_other_creature_attack_does_not_fire_trigger(self) -> None:
        """An AttacksTriggeredEvent for a different creature does NOT fire the trigger."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        other = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        before_stack_size = len(game.stack.objects())
        from engine.events import AttacksTriggeredEvent as ATE
        game.trigger_manager.fire_event(game, ATE(creature=other))

        # Trigger should NOT have fired — stack unchanged
        assert len(game.stack.objects()) == before_stack_size


# ---------------------------------------------------------------------------
# Exile replacement effect
# ---------------------------------------------------------------------------


class TestTheDawningArchaicExileReplacement:
    """Instants/sorceries cast via the attack trigger go to exile, not graveyard."""

    def test_free_cast_spell_goes_to_exile_not_graveyard(self) -> None:
        """A spell cast via the attack trigger and resolved goes to exile instead of graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # The sorcery starts in the graveyard; after free-cast + resolve it should go to exile
        sorcery = Sorcery(name="Divination", owner=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        assert len(attack_triggers) >= 1
        trigger = attack_triggers[0]

        # Fire the trigger effect
        trigger.effect(game)
        # Resolve any items pushed onto the stack by the free-cast
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # The spell must NOT be in the graveyard
        assert not game.get_graveyard(p1).contains(sorcery)

    def test_free_cast_spell_is_in_exile_after_resolution(self) -> None:
        """The spell cast via the trigger ends up in exile after resolving."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p1)
        set_board_state(game, 0, graveyard=[instant])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_triggers = [
            t for t in triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        assert len(attack_triggers) >= 1
        trigger = attack_triggers[0]

        trigger.effect(game)
        # Resolve the free cast
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Spell must be in exile
        exile_zone = p1.zones[Zone.EXILE]
        assert exile_zone.contains(instant)
