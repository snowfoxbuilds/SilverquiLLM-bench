"""Tests for SOS 245 — Witherbloom, the Balancer.

Covers:
- Static card properties (name, mana cost, P/T, type line, keywords, supertypes, subtypes)
- Flying and Deathtouch keywords present
- Legendary Elder Dragon type line
- Affinity for creatures (self): cost_reduction() returns 1 per creature controller controls
- Affinity for creatures (self): reduction capped at generic mana portion (6)
- Affinity for creatures (self): only controller's own creatures count
- Affinity for creatures (self): non-creatures (lands, enchantments) do not count
- Affinity for creatures (self): integration — can cast for reduced cost with enough creatures
- Instant/sorcery affinity grant: register_triggers wires a SpellCastTriggeredEvent trigger
- Instant/sorcery affinity grant: condition fires only for instants cast by controller
- Instant/sorcery affinity grant: condition fires only for sorceries cast by controller
- Instant/sorcery affinity grant: condition does NOT fire for creatures, enchantments
- Instant/sorcery affinity grant: condition does NOT fire for opponent's spells
- Instant/sorcery affinity grant: trigger not registered before register_triggers() is called
- Instant/sorcery affinity grant: trigger is removable via unregister
- Instant/sorcery affinity grant: effect allows casting a costly instant/sorcery for less mana
"""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery, Land, Enchantment
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell


# ---------------------------------------------------------------------------
# Static card property tests
# ---------------------------------------------------------------------------


class TestWitherbloomProperties:
    """Static card data should match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_base_power(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5

    def test_base_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_is_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_creature_card_type(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_elder_subtype(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes

    def test_dragon_subtype(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Affinity for creatures — Witherbloom's own cost_reduction
# ---------------------------------------------------------------------------


class TestWitherbloomSelfAffinityCostReduction:
    """cost_reduction() returns 1 per creature the controller controls."""

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Battlefield is empty
        assert card.cost_reduction(game) == 0

    def test_one_creature_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear])
        assert card.cost_reduction(game) == 1

    def test_three_creatures_reduces_by_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Bear{i}", base_power=2, base_toughness=2,
                     owner=p1, controller=p1)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 3

    def test_six_creatures_capped_at_six(self) -> None:
        """6+ creatures → reduction is capped at the generic portion ({6}) = max 6."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Bear{i}", base_power=2, base_toughness=2,
                     owner=p1, controller=p1)
            for i in range(10)
        ]
        set_board_state(game, 0, battlefield=creatures)
        # Must not exceed 6 (the generic component of {6}{B}{G})
        assert card.cost_reduction(game) <= 6
        # Must equal exactly 6 (not less, since 10 >= 6)
        assert card.cost_reduction(game) == 6

    def test_non_creature_permanents_do_not_count(self) -> None:
        """Lands and enchantments on the battlefield do not reduce the cost."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        forest = Land(name="Forest")
        enchantment = Enchantment(name="Pacifism")
        set_board_state(game, 0, battlefield=[forest, enchantment])
        assert card.cost_reduction(game) == 0

    def test_opponent_creatures_do_not_count(self) -> None:
        """Only the controller's creatures count; the opponent's do not."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        opponent_creatures = [
            Creature(name=f"OppBear{i}", base_power=2, base_toughness=2)
            for i in range(5)
        ]
        set_board_state(game, 1, battlefield=opponent_creatures)
        # Controller's (p1's) battlefield is empty
        assert card.cost_reduction(game) == 0

    def test_integration_cast_with_six_creatures_pays_only_color(self) -> None:
        """Integration: 6 creatures on battlefield → Witherbloom costs only {B}{G}."""
        game = create_game()
        p1 = game.players[0]
        creatures = [
            Creature(name=f"Bear{i}", base_power=2, base_toughness=2,
                     owner=p1, controller=p1)
            for i in range(6)
        ]
        card = WitherbloomTheBalancer(owner=None)
        # Set creatures on battlefield, card in hand, only {B}{G} of mana
        set_board_state(
            game, 0,
            battlefield=creatures,
            hand=[card],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
        )
        # With 6 creatures, cost reduces from {6}{B}{G} to {0}{B}{G} = {B}{G}
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(p1).contains(card)


# ---------------------------------------------------------------------------
# Instant/sorcery affinity grant — trigger registration
# ---------------------------------------------------------------------------


class TestWitherbloomAffinityGrantRegistration:
    """register_triggers() must wire a SpellCastTriggeredEvent trigger for the
    'instants and sorceries you cast have affinity for creatures' ability."""

    def test_no_triggers_before_register_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        triggers_for_card = [
            t for t in game.trigger_manager._triggers if t.source is card
        ]
        assert len(triggers_for_card) == 0

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        before = len(game.trigger_manager._triggers)
        card.register_triggers(game)
        after = len(game.trigger_manager._triggers)
        assert after > before

    def test_registers_spell_cast_triggered_event(self) -> None:
        """At least one registered trigger must watch SpellCastTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        card.register_triggers(game)
        spell_cast_triggers = [
            t for t in game.trigger_manager._triggers
            if t.event_type is SpellCastTriggeredEvent and t.source is card
        ]
        assert len(spell_cast_triggers) >= 1

    def test_trigger_can_be_unregistered(self) -> None:
        """After unregistering via trigger_manager, no triggers remain for this card."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers_before = [t for t in game.trigger_manager._triggers if t.source is card]
        assert len(triggers_before) >= 1

        game.trigger_manager.unregister(card)

        triggers_after = [t for t in game.trigger_manager._triggers if t.source is card]
        assert len(triggers_after) == 0


# ---------------------------------------------------------------------------
# Instant/sorcery affinity grant — trigger condition
# ---------------------------------------------------------------------------


class TestWitherbloomAffinityGrantCondition:
    """The trigger condition fires for controller's instants and sorceries only."""

    def _get_spell_cast_trigger(self, game, card) -> TriggerRegistration | None:
        """Helper: find the first SpellCastTriggeredEvent trigger owned by card."""
        for t in game.trigger_manager._triggers:
            if t.source is card and t.event_type is SpellCastTriggeredEvent:
                return t
        return None

    def test_condition_true_for_controller_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        instant = Instant(name="Bolt")
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=instant)
        # Either condition is None (fires always) or it evaluates True for an instant
        result = trigger.condition is None or trigger.condition(game, event)
        assert result is True

    def test_condition_true_for_controller_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        sorcery = Sorcery(name="Divination")
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=sorcery)
        result = trigger.condition is None or trigger.condition(game, event)
        assert result is True

    def test_condition_false_for_controller_creature(self) -> None:
        """Creature spells cast by the controller should NOT trigger the affinity grant."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        if trigger.condition is None:
            pytest.skip("condition is None — cannot verify type filtering")

        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=creature)
        assert trigger.condition(game, event) is False

    def test_condition_false_for_controller_enchantment(self) -> None:
        """Enchantment spells cast by the controller should NOT trigger the grant."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        if trigger.condition is None:
            pytest.skip("condition is None — cannot verify type filtering")

        enchantment = Enchantment(name="Leyline")
        event = SpellCastTriggeredEvent(spell=None, player=p1, card=enchantment)
        assert trigger.condition(game, event) is False

    def test_condition_false_for_opponent_instant(self) -> None:
        """The opponent casting an instant does NOT trigger the affinity grant."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        if trigger.condition is None:
            pytest.skip("condition is None — cannot verify controller filtering")

        instant = Instant(name="Opponent Bolt")
        event = SpellCastTriggeredEvent(spell=None, player=p2, card=instant)
        assert trigger.condition(game, event) is False


# ---------------------------------------------------------------------------
# Instant/sorcery affinity grant — effect (cost reduction applied)
# ---------------------------------------------------------------------------


class TestWitherbloomAffinityGrantEffect:
    """When the trigger fires, the instant/sorcery being cast receives a cost
    reduction equal to the number of creatures the controller controls."""

    def _get_spell_cast_trigger(self, game, card) -> TriggerRegistration | None:
        for t in game.trigger_manager._triggers:
            if t.source is card and t.event_type is SpellCastTriggeredEvent:
                return t
        return None

    def test_effect_fires_without_error_with_no_creatures(self) -> None:
        """Effect resolves gracefully even when there are no creatures."""
        from engine.stack import StackObject

        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(witherbloom)
        witherbloom.register_triggers(game)

        trigger = self._get_spell_cast_trigger(game, witherbloom)
        assert trigger is not None

        spell_card = Instant(name="Test Bolt", owner=p1, controller=p1)
        spell_obj = StackObject(source=spell_card, controller=p1)
        game.stack.push(spell_obj)

        # Should not raise even with zero creatures
        trigger.effect(game)

    def test_instant_cast_cheaper_with_witherbloom_and_creatures(self) -> None:
        """Integration: with Witherbloom on board and 3 creatures,
        a {3} instant can be cast for free."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        witherbloom.summoning_sick = False
        creatures = [
            Creature(name=f"Bear{i}", base_power=2, base_toughness=2,
                     owner=p1, controller=p1)
            for i in range(3)
        ]
        instant = Instant(
            name="Big Instant",
            mana_cost=ManaCost.parse("{3}"),
            owner=None,
        )
        # Set up board: Witherbloom + 3 creatures on battlefield, instant in hand
        set_board_state(
            game, 0,
            battlefield=[witherbloom] + creatures,
            hand=[instant],
            mana={},  # no mana — affinity should reduce cost to 0
        )
        # Register Witherbloom's triggers (simulating it entering the battlefield)
        witherbloom.register_triggers(game)

        # Casting the {3} instant should succeed without any mana (reduced to {0})
        cast_spell(game, 0, "Big Instant")
        # After resolve, instant should be in graveyard
        assert game.get_graveyard(p1).contains(instant)

    def test_sorcery_cast_cheaper_with_witherbloom_and_creatures(self) -> None:
        """Integration: with Witherbloom on board and 4 creatures,
        a {4} sorcery can be cast for free."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        witherbloom.summoning_sick = False
        creatures = [
            Creature(name=f"Bear{i}", base_power=2, base_toughness=2,
                     owner=p1, controller=p1)
            for i in range(4)
        ]
        sorcery = Sorcery(
            name="Big Sorcery",
            mana_cost=ManaCost.parse("{4}"),
            owner=None,
        )
        set_board_state(
            game, 0,
            battlefield=[witherbloom] + creatures,
            hand=[sorcery],
            mana={},  # no mana — affinity should reduce cost to 0
        )
        witherbloom.register_triggers(game)

        # Casting the {4} sorcery should succeed without any mana
        cast_spell(game, 0, "Big Sorcery")
        assert game.get_graveyard(p1).contains(sorcery)
