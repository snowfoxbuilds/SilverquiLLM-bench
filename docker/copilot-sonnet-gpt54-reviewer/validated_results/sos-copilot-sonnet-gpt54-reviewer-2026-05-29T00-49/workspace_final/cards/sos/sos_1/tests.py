"""Tests for sos_1 — The Dawning Archaic.

Covers:
- Static properties (name, mana cost, power/toughness, type)
- Reach keyword
- Cost reduction: {1} less for each instant/sorcery in graveyard
- Attack trigger: cast instant/sorcery from graveyard without paying mana cost
- Replacement effect: if the cast spell would go to graveyard, exile it instead
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import (
    AttacksTriggeredEvent,
    MoveToGraveyardReplacementEvent,
    CreatureDiesReplacementEvent,
)
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state, declare_attackers


class TestTheDawningArchaicProperties:
    """Static card data should match the sos_1 spec."""

    def test_name(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_base_power(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7

    def test_base_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_toughness == 7

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_is_legendary(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords


class TestTheDawningArchaicCostReduction:
    """cost_reduction() returns 1 per instant/sorcery card in controller's graveyard."""

    def test_no_graveyard_cards_gives_zero_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_in_graveyard_gives_reduction_of_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        instant.card_types = {CardType.INSTANT}
        set_board_state(game, 0, graveyard=[instant])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_in_graveyard_gives_reduction_of_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        sorcery.card_types = {CardType.SORCERY}
        set_board_state(game, 0, graveyard=[sorcery])
        assert card.cost_reduction(game) == 1

    def test_three_instants_and_sorceries_give_reduction_of_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant1 = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        instant1.card_types = {CardType.INSTANT}
        instant2 = Instant(name="Counterspell", owner=p1, controller=p1)
        instant2.card_types = {CardType.INSTANT}
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        sorcery.card_types = {CardType.SORCERY}
        set_board_state(game, 0, graveyard=[instant1, instant2, sorcery])
        assert card.cost_reduction(game) == 3

    def test_creature_in_graveyard_does_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(name="Grizzly Bears", owner=p1, controller=p1)
        creature.card_types = {CardType.CREATURE}
        set_board_state(game, 0, graveyard=[creature])
        assert card.cost_reduction(game) == 0

    def test_opponent_graveyard_instants_do_not_count(self) -> None:
        """Only controller's graveyard counts for cost reduction."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        instant.card_types = {CardType.INSTANT}
        set_board_state(game, 1, graveyard=[instant])
        assert card.cost_reduction(game) == 0

    def test_cost_reduction_capped_at_ten(self) -> None:
        """Reduction cannot exceed the base cost of {10}."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Create 15 instants in the graveyard
        graveyard_cards = []
        for i in range(15):
            instant = Instant(name=f"Instant {i}", owner=p1, controller=p1)
            instant.card_types = {CardType.INSTANT}
            graveyard_cards.append(instant)
        set_board_state(game, 0, graveyard=graveyard_cards)
        # Reduction should not exceed the total mana value
        assert card.cost_reduction(game) <= 10


class TestTheDawningArchaicAttackTrigger:
    """When The Dawning Archaic attacks, register an attack trigger."""

    def test_register_triggers_registers_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_attack_trigger_fires_on_attacks_event(self) -> None:
        """The trigger must watch AttacksTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1
        attack_triggers = [
            t for t in triggers
            if t.event_type is AttacksTriggeredEvent
        ]
        assert len(attack_triggers) == 1

    def test_attack_trigger_only_fires_for_this_creature(self) -> None:
        """Trigger condition should verify it's this creature attacking."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = next(
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is AttacksTriggeredEvent
        )
        # Event for this card — should fire
        event_self = AttacksTriggeredEvent(creature=card, attacker=card)
        # Event for another creature — should NOT fire
        other = Creature(name="Grizzly Bears", owner=p1, controller=p1)
        event_other = AttacksTriggeredEvent(creature=other, attacker=other)
        if trigger.condition is not None:
            assert trigger.condition(game, event_self) is True
            assert trigger.condition(game, event_other) is False

    def test_attack_trigger_pushes_to_stack_when_card_attacks(self) -> None:
        """Fire the AttacksTriggeredEvent and confirm the stack has an entry."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        before = len(game.stack._objects)
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        after = len(game.stack._objects)
        assert after > before


class TestTheDawningArchaicGraveyardCast:
    """Attack trigger effect: cast instant/sorcery from graveyard for free."""

    def test_trigger_effect_casts_instant_from_graveyard(self) -> None:
        """The trigger effect should move an instant from graveyard onto the stack."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Put an instant in the graveyard
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        instant.card_types = {CardType.INSTANT}
        set_board_state(game, 0, graveyard=[instant])
        card.register_triggers(game)
        # Fire the attack trigger
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        # Resolve the trigger (top of stack)
        stack_obj = game.stack._objects[-1]
        stack_obj.on_resolve(game)
        # The instant should no longer be in the graveyard
        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(instant)

    def test_trigger_effect_noop_with_empty_graveyard(self) -> None:
        """If no instant/sorcery in graveyard, trigger effect is a no-op."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Empty graveyard — no instants/sorceries
        creature = Creature(name="Grizzly Bears", owner=p1, controller=p1)
        creature.card_types = {CardType.CREATURE}
        set_board_state(game, 0, graveyard=[creature])
        card.register_triggers(game)
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        stack_obj = game.stack._objects[-1]
        # Should not raise — it's a no-op when no valid targets exist
        try:
            stack_obj.on_resolve(game)
        except Exception:
            pytest.fail("on_resolve raised unexpectedly with no valid graveyard targets")


class TestTheDawningArchaicExileReplacement:
    """If the graveyard-cast spell would go to graveyard, exile it instead."""

    def test_registers_replacement_effect_on_enter_battlefield(self) -> None:
        """register_replacement_effects should register a replacement that exiles the spell."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.replacement_manager._effects)
        card.register_replacement_effects(game)
        after = len(game.replacement_manager._effects)
        assert after > before

    def test_graveyard_cast_spell_exiled_not_back_to_graveyard(self) -> None:
        """After the free-cast spell resolves, it goes to exile, not graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Create a sorcery that will be cast from graveyard
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        sorcery.card_types = {CardType.SORCERY}
        # Mark it as "graveyard-cast" so the replacement knows to exile it
        sorcery.cast_from_graveyard_by_dawning_archaic = True
        card.register_replacement_effects(game)
        # Simulate it moving to graveyard
        event = MoveToGraveyardReplacementEvent(
            destination="graveyard",
            controller=p1,
            owner=p1,
        )
        # Attach the card reference to the event for the replacement to read
        event.card_obj = sorcery
        result = game.replacement_manager.apply(game, event)
        # The replacement should redirect to exile (prevented or destination changed)
        exile_zone = game.get_exile(p1)
        graveyard_zone = game.get_graveyard(p1)
        # Either the event is prevented (card moved to exile by the replacement),
        # or the destination was changed to "exile"
        exile_or_prevented = (
            result.prevented is True
            or result.destination == "exile"
            or exile_zone.contains(sorcery)
        )
        assert exile_or_prevented, (
            f"Expected exile or prevented, got destination={result.destination!r}, "
            f"prevented={result.prevented!r}, exile_contains={exile_zone.contains(sorcery)!r}"
        )
