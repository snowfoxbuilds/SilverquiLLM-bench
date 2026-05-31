"""Tests for sos_1 — The Dawning Archaic.

Coverage:
- Static properties: name, mana cost ({10}), type, subtypes, supertypes, P/T, Reach keyword
- Cost reduction: 1 less per instant/sorcery in controller's graveyard
- Attack trigger: registers for AttacksTriggeredEvent on the attacker
- Attack trigger: condition fires only for this card attacking, not others
- Attack trigger effect: instant/sorcery leaves graveyard when trigger resolves
- Exile replacement: cast spell from graveyard goes to exile, not graveyard
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.combat import _can_block
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------

class TestTheDawningArchaicProperties:
    """Static card data should match the sos_1 spec."""

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtype_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_legendary_supertype(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_power_seven(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7

    def test_toughness_seven(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_toughness == 7

    def test_has_reach_keyword(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords


# ---------------------------------------------------------------------------
# Cost reduction tests
# ---------------------------------------------------------------------------

class TestTheDawningArchaicCostReduction:
    """cost_reduction() returns 1 per instant/sorcery in controller's graveyard."""

    def test_cost_reduction_zero_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_cost_reduction_one_instant_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        assert card.cost_reduction(game) == 1

    def test_cost_reduction_one_sorcery_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        assert card.cost_reduction(game) == 1

    def test_cost_reduction_three_instants_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        gy_cards = [
            Instant(name="Bolt", owner=p1, controller=p1),
            Sorcery(name="Draw Two", owner=p1, controller=p1),
            Instant(name="Counterspell", owner=p1, controller=p1),
        ]
        set_board_state(game, 0, graveyard=gy_cards)
        assert card.cost_reduction(game) == 3

    def test_cost_reduction_ignores_creatures_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(name="Bear", base_power=2, base_toughness=2,
                            owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[creature])
        assert card.cost_reduction(game) == 0

    def test_cost_reduction_counts_only_controller_graveyard(self) -> None:
        """Opponent's graveyard instants/sorceries must NOT contribute."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        opponent_instant = Instant(name="Bolt", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[opponent_instant])
        assert card.cost_reduction(game) == 0

    def test_cost_reduction_mixed_counts_only_instants_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        gy_cards = [
            Instant(name="Bolt", owner=p1, controller=p1),       # counts
            Sorcery(name="Ramp", owner=p1, controller=p1),       # counts
            Creature(name="Bear", base_power=2, base_toughness=2,
                     owner=p1, controller=p1),                    # does NOT count
        ]
        set_board_state(game, 0, graveyard=gy_cards)
        assert card.cost_reduction(game) == 2


# ---------------------------------------------------------------------------
# Reach: behavioral blocking test
# ---------------------------------------------------------------------------

class TestTheDawningArchaicReach:
    """Reach keyword: the Archaic can block flying creatures."""

    def test_reach_allows_blocking_flying_attacker(self) -> None:
        """Behavioral test: Reach enables blocking a flying creature."""
        archaic = TheDawningArchaic(owner=None)
        archaic.is_tapped = False
        flying_attacker = Creature(name="Dragon", base_power=5, base_toughness=5)
        flying_attacker.keywords = Keyword.FLYING
        assert _can_block(archaic, flying_attacker) is True


# ---------------------------------------------------------------------------
# Attack trigger registration tests
# ---------------------------------------------------------------------------

class TestTheDawningArchaicTriggerRegistration:
    """register_triggers must register exactly one AttacksTriggeredEvent trigger."""

    def test_register_triggers_adds_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after - before == 1

    def test_registered_trigger_is_for_attacks_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_registered_trigger_source_is_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert triggers[0].source is card

    def test_registered_trigger_controller_is_card_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert triggers[0].controller is p1


# ---------------------------------------------------------------------------
# Attack trigger condition tests
# ---------------------------------------------------------------------------

class TestTheDawningArchaicTriggerCondition:
    """Trigger condition: fires only when THIS card is the attacker."""

    def test_trigger_condition_true_for_this_card_attacking(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        event = AttacksTriggeredEvent(attacker=card, creature=card)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True

    def test_trigger_condition_false_for_other_creature_attacking(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        other = Creature(name="Other Attacker", base_power=2, base_toughness=2)
        event = AttacksTriggeredEvent(attacker=other, creature=other)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False

    def test_firing_attack_event_for_this_card_pushes_to_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        event = AttacksTriggeredEvent(attacker=card, creature=card)
        before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) > before

    def test_firing_attack_event_for_other_card_does_not_push_to_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        other = Creature(name="Other", base_power=2, base_toughness=2)
        event = AttacksTriggeredEvent(attacker=other, creature=other)
        before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) == before


# ---------------------------------------------------------------------------
# Attack trigger effect: instant/sorcery cast from graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackEffect:
    """When the attack trigger resolves, an instant/sorcery from the
    controller's graveyard is cast for free."""

    def test_trigger_effect_removes_instant_from_graveyard(self) -> None:
        """Resolving the trigger moves an instant out of the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        assert not game.get_graveyard(p1).contains(instant)

    def test_trigger_effect_removes_sorcery_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        assert not game.get_graveyard(p1).contains(sorcery)

    def test_trigger_effect_is_noop_with_only_creatures_in_graveyard(self) -> None:
        """No valid targets → trigger resolves as a no-op, does not raise."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(name="Bear", base_power=2, base_toughness=2,
                            owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[creature])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)  # must not raise

    def test_trigger_effect_is_noop_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)  # must not raise


# ---------------------------------------------------------------------------
# Exile replacement effect tests
# ---------------------------------------------------------------------------

class TestTheDawningArchaicExileReplacement:
    """Spell cast via the attack trigger is exiled instead of going to graveyard."""

    def test_instant_cast_via_trigger_ends_in_exile_not_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        assert game.get_exile(p1).contains(instant), \
            "Spell cast via trigger must end in exile"
        assert not game.get_graveyard(p1).contains(instant), \
            "Spell cast via trigger must NOT be in graveyard"

    def test_sorcery_cast_via_trigger_ends_in_exile_not_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        trigger.effect(game)
        assert game.get_exile(p1).contains(sorcery), \
            "Sorcery cast via trigger must end in exile"
        assert not game.get_graveyard(p1).contains(sorcery), \
            "Sorcery cast via trigger must NOT be in graveyard"
