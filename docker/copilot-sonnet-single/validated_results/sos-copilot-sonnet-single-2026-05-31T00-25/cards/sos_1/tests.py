"""Tests for The Dawning Archaic (sos_1)."""

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Card properties
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static card data must match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_base_power(self) -> None:
        assert TheDawningArchaic(owner=None).base_power == 7

    def test_base_toughness(self) -> None:
        assert TheDawningArchaic(owner=None).base_toughness == 7

    def test_has_reach_keyword(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_is_legendary(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_avatar_subtype(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_has_creature_type(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Cost reduction
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """cost_reduction() counts instant/sorcery cards in controller's graveyard."""

    def test_zero_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Test Instant", owner=p1)
        game.get_graveyard(p1).add(instant)
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Test Sorcery", owner=p1)
        game.get_graveyard(p1).add(sorcery)
        assert card.cost_reduction(game) == 1

    def test_five_instants_reduces_by_five(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        for i in range(5):
            game.get_graveyard(p1).add(Instant(name=f"Instant {i}", owner=p1))
        assert card.cost_reduction(game) == 5

    def test_mixed_instants_and_sorceries_all_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        for i in range(3):
            game.get_graveyard(p1).add(Instant(name=f"Instant {i}", owner=p1))
        for i in range(3):
            game.get_graveyard(p1).add(Sorcery(name=f"Sorcery {i}", owner=p1))
        assert card.cost_reduction(game) == 6

    def test_cost_reduction_capped_at_ten(self) -> None:
        """With 15 instants, cost_reduction must return exactly 10 (the CMC)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        for i in range(15):
            game.get_graveyard(p1).add(Instant(name=f"Instant {i}", owner=p1))
        assert card.cost_reduction(game) == 10

    def test_exactly_ten_instants_reduces_by_ten(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        for i in range(10):
            game.get_graveyard(p1).add(Instant(name=f"Instant {i}", owner=p1))
        assert card.cost_reduction(game) == 10

    def test_non_instant_sorcery_cards_in_graveyard_do_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        game.get_graveyard(p1).add(bear)
        assert card.cost_reduction(game) == 0

    def test_opponent_graveyard_does_not_count(self) -> None:
        """Only controller's graveyard counts, not opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        for i in range(5):
            game.get_graveyard(p2).add(Instant(name=f"Instant {i}", owner=p2))
        assert card.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# Attack trigger registration
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackTrigger:
    """register_triggers must wire an AttacksTriggeredEvent trigger."""

    def test_registers_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after - before >= 1

    def test_attack_trigger_event_type_is_attacks_triggered_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(t.event_type is AttacksTriggeredEvent for t in triggers)

    def test_attack_trigger_fires_only_for_this_creature(self) -> None:
        """Trigger condition must gate on the attacking creature being this card."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is AttacksTriggeredEvent
        ]
        assert len(triggers) >= 1
        trigger = triggers[0]
        event_self = AttacksTriggeredEvent(creature=card, attacker=card)
        other_creature = Creature(
            name="Other Bear", base_power=2, base_toughness=2,
            owner=p1, controller=p1,
        )
        event_other = AttacksTriggeredEvent(creature=other_creature, attacker=other_creature)
        if trigger.condition is not None:
            assert trigger.condition(game, event_self) is True
            assert trigger.condition(game, event_other) is False

    def test_attack_trigger_pushes_onto_stack_when_fired(self) -> None:
        """Firing an AttacksTriggeredEvent for this creature should push onto stack."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        before = len(game.stack._items)
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        after = len(game.stack._items)
        assert after > before

    def test_attack_trigger_does_not_push_for_other_creature(self) -> None:
        """Firing AttacksTriggeredEvent for another creature must NOT push."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        other_creature = Creature(
            name="Other Bear", base_power=2, base_toughness=2,
            owner=p1, controller=p1,
        )
        before = len(game.stack._items)
        event = AttacksTriggeredEvent(creature=other_creature, attacker=other_creature)
        game.trigger_manager.fire_event(game, event)
        after = len(game.stack._items)
        assert after == before


# ---------------------------------------------------------------------------
# Attack trigger effect: cast from graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCastFromGraveyard:
    """When the attack trigger resolves it casts a spell from the graveyard."""

    def test_instant_in_graveyard_is_cast_when_trigger_resolves(self) -> None:
        """The instant must leave the graveyard after the trigger resolves."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        game.get_graveyard(p1).add(instant)
        card.register_triggers(game)
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)
        assert not game.get_graveyard(p1).contains(instant)

    def test_sorcery_in_graveyard_is_cast_when_trigger_resolves(self) -> None:
        """The sorcery must leave the graveyard after the trigger resolves."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        game.get_graveyard(p1).add(sorcery)
        card.register_triggers(game)
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)
        assert not game.get_graveyard(p1).contains(sorcery)

    def test_empty_graveyard_trigger_resolves_without_error(self) -> None:
        """Trigger must not raise if there are no instants/sorceries in graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)  # must not raise


# ---------------------------------------------------------------------------
# Exile replacement: spell cast via attack trigger goes to exile not graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicExileReplacement:
    """The replacement effect registers with source=self and redirects to exile."""

    def test_registers_replacement_effect_on_register_replacement_effects(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.replacement_manager._effects)
        card.register_replacement_effects(game)
        after = len(game.replacement_manager._effects)
        assert after > before

    def test_replacement_effect_source_is_card(self) -> None:
        """Replacement effect must be registered with source=TheDawningArchaic."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_replacement_effects(game)
        effects = game.replacement_manager.get_effects_for_source(card)
        assert len(effects) >= 1

    def test_exile_replacement_redirects_spell_to_exile(self) -> None:
        """End-to-end: the spell cast via the trigger ends up in exile."""
        from engine.events import SpellMovesToGraveyardReplacementEvent

        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_replacement_effects(game)

        instant = Instant(name="Fire Bolt", owner=p1, controller=p1)
        # Simulate: mark as graveyard-cast-spell
        card._graveyard_cast_spell = instant

        rep_event = SpellMovesToGraveyardReplacementEvent(
            spell=instant,
            destination="graveyard",
            controller=p1,
            owner=p1,
        )
        result = game.replacement_manager.apply(game, rep_event)
        assert result.destination == "exile"

    def test_exile_replacement_only_applies_to_marked_spell(self) -> None:
        """The replacement must NOT redirect an unmarked spell."""
        from engine.events import SpellMovesToGraveyardReplacementEvent

        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_replacement_effects(game)

        instant = Instant(name="Bolt", owner=p1, controller=p1)
        other = Instant(name="Other", owner=p1, controller=p1)

        # Mark a different spell
        card._graveyard_cast_spell = other

        rep_event = SpellMovesToGraveyardReplacementEvent(
            spell=instant,
            destination="graveyard",
            controller=p1,
            owner=p1,
        )
        result = game.replacement_manager.apply(game, rep_event)
        assert result.destination == "graveyard"
