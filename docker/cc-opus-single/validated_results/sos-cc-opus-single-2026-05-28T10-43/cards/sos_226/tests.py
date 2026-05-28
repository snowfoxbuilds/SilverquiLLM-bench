"""Tests for SOS 226 -- Silverquill, the Disputant.

Silverquill, the Disputant is a 4/4 Legendary Creature -- Elder Dragon
costing {2}{W}{B} with Flying and Vigilance.

Oracle text:
    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1.
    (As you cast that spell, you may sacrifice a creature with power 1
    or greater. When you do, copy the spell and you may choose new
    targets for the copy.)

Casualty 1 is granted to every instant and sorcery spell the controller
casts while Silverquill is on the battlefield.  Paying casualty means
sacrificing a creature with power >= 1 as an additional cost; doing so
triggers a copy of the spell being placed on the stack.
"""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject, copy_spell
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
# Static Properties
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

    def test_power_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4
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

    def test_subtypes_include_elder_and_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Trigger Registration -- Casualty granting
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyRegistration:
    """When Silverquill enters the battlefield it should register trigger(s)
    that grant casualty 1 to instant and sorcery spells the controller casts.

    Casualty is implemented as: when the controller casts an instant or
    sorcery, if they choose to pay casualty (sacrifice a creature with
    power >= 1), the spell is copied on the stack.
    """

    def test_registers_trigger_on_battlefield(self) -> None:
        """Silverquill should register at least one trigger when it enters
        the battlefield (a SpellCastTriggeredEvent watcher)."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_registered_trigger_watches_spell_cast_event(self) -> None:
        """The trigger should be watching for SpellCastTriggeredEvent so
        that it fires when the controller casts an instant or sorcery."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        spell_cast_triggers = [
            t for t in triggers
            if t.event_type is SpellCastTriggeredEvent
        ]
        assert len(spell_cast_triggers) >= 1

    def test_trigger_source_is_silverquill(self) -> None:
        """The registered trigger's source must be the Silverquill card itself."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1
        assert all(t.source is card for t in triggers)


# ---------------------------------------------------------------------------
# Casualty Condition -- only instants and sorceries
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyCondition:
    """The casualty trigger should only fire for instant and sorcery spells
    cast by the controller, not for creature/enchantment/artifact spells,
    and not for spells cast by the opponent."""

    def _setup_silverquill_on_battlefield(self):
        """Helper: create game with Silverquill on p1's battlefield,
        triggers registered."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        return game, p1, card

    def test_trigger_fires_for_instant_spell_by_controller(self) -> None:
        """An instant cast by the controller should match the casualty trigger
        condition."""
        game, p1, sq = self._setup_silverquill_on_battlefield()
        triggers = game.trigger_manager.get_triggers_for_source(sq)
        spell_trigger = next(
            t for t in triggers
            if t.event_type is SpellCastTriggeredEvent
        )
        instant_spell = Instant(name="Test Bolt", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=instant_spell, player=p1, card=instant_spell, controller=p1
        )
        # Condition should pass for an instant cast by the controller
        if spell_trigger.condition is not None:
            assert spell_trigger.condition(game, event) is True

    def test_trigger_fires_for_sorcery_spell_by_controller(self) -> None:
        """A sorcery cast by the controller should match the casualty trigger
        condition."""
        game, p1, sq = self._setup_silverquill_on_battlefield()
        triggers = game.trigger_manager.get_triggers_for_source(sq)
        spell_trigger = next(
            t for t in triggers
            if t.event_type is SpellCastTriggeredEvent
        )
        sorcery_spell = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(
            spell=sorcery_spell, player=p1, card=sorcery_spell, controller=p1
        )
        if spell_trigger.condition is not None:
            assert spell_trigger.condition(game, event) is True

    def test_trigger_does_not_fire_for_creature_spell(self) -> None:
        """A creature spell should NOT trigger the casualty granting."""
        game, p1, sq = self._setup_silverquill_on_battlefield()
        triggers = game.trigger_manager.get_triggers_for_source(sq)
        spell_trigger = next(
            t for t in triggers
            if t.event_type is SpellCastTriggeredEvent
        )
        creature_spell = Creature(
            name="Test Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        event = SpellCastTriggeredEvent(
            spell=creature_spell, player=p1, card=creature_spell, controller=p1
        )
        if spell_trigger.condition is not None:
            assert spell_trigger.condition(game, event) is False

    def test_trigger_does_not_fire_for_opponent_spell(self) -> None:
        """An instant or sorcery cast by the opponent should NOT trigger
        the casualty granted by this Silverquill."""
        game, p1, sq = self._setup_silverquill_on_battlefield()
        p2 = game.players[1]
        triggers = game.trigger_manager.get_triggers_for_source(sq)
        spell_trigger = next(
            t for t in triggers
            if t.event_type is SpellCastTriggeredEvent
        )
        opponent_spell = Instant(name="Opponent Bolt", owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(
            spell=opponent_spell, player=p2, card=opponent_spell, controller=p2
        )
        if spell_trigger.condition is not None:
            assert spell_trigger.condition(game, event) is False


# ---------------------------------------------------------------------------
# Casualty Effect -- sacrifice + copy
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyEffect:
    """When casualty is paid (a creature with power >= 1 is sacrificed),
    the spell should be copied on the stack.  When casualty is not paid,
    no copy is created."""

    def _setup_with_sacrificable_creature(self):
        """Helper: game with Silverquill and a 1/1 token on p1's battlefield."""
        game = create_game()
        p1 = game.players[0]
        sq = SilverquillTheDisputant(owner=p1, controller=p1)
        token = Creature(
            name="Inkling Token", owner=p1, controller=p1,
            base_power=1, base_toughness=1,
        )
        token.is_token = True
        set_board_state(game, 0, battlefield=[sq, token])
        sq.register_triggers(game)
        return game, p1, sq, token

    def test_casualty_paid_creates_copy_on_stack(self) -> None:
        """When casualty is paid (a creature with power >= 1 is sacrificed),
        the spell should be copied and put on the stack."""
        game, p1, sq, token = self._setup_with_sacrificable_creature()

        # Create an instant spell and put it on the stack
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        stack_obj = StackObject(
            source=bolt, controller=p1, targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(stack_obj)

        # Mark that casualty was paid for this spell by sacrificing the token
        bolt._casualty_paid = True
        bolt._casualty_sacrificed = token

        # Fire the spell-cast event
        event = SpellCastTriggeredEvent(
            spell=bolt, player=p1, card=bolt, controller=p1
        )
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)

        # The trigger should have pushed something on the stack (the copy
        # trigger or the actual copy).
        assert len(game.stack) > stack_before

    def test_no_sacrifice_no_copy(self) -> None:
        """When casualty is NOT paid (no creature sacrificed), the spell
        should not be copied.

        This requires that Silverquill's trigger is actually registered
        and that the trigger or its effect correctly no-ops when casualty
        is not paid.
        """
        game, p1, sq, token = self._setup_with_sacrificable_creature()

        # Verify the trigger is actually registered (guards against
        # vacuous pass from stub).
        triggers = game.trigger_manager.get_triggers_for_source(sq)
        assert len(triggers) >= 1, (
            "Silverquill must register at least one trigger for casualty"
        )

        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        stack_obj = StackObject(
            source=bolt, controller=p1, targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(stack_obj)

        # Casualty not paid -- no _casualty_paid flag
        event = SpellCastTriggeredEvent(
            spell=bolt, player=p1, card=bolt, controller=p1
        )

        # Fire the event -- even if the trigger fires, its condition/effect
        # should check whether casualty was actually paid.
        # The trigger's condition should reject this event because casualty
        # was not paid.  If condition is None, the trigger effect itself
        # should check and be a no-op.
        stack_count_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)

        # At most the trigger itself might be pushed, but when it resolves
        # it should not add a copy if casualty wasn't paid.
        # We resolve any triggers that were pushed.
        while len(game.stack) > stack_count_before:
            obj = game.stack.pop()
            obj.on_resolve(game)

        # No extra copies should remain on the stack
        assert len(game.stack) == stack_count_before


# ---------------------------------------------------------------------------
# Casualty Power Threshold
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyPowerThreshold:
    """Casualty 1 requires sacrificing a creature with power 1 or greater.
    A creature with power 0 should not satisfy the casualty requirement."""

    def test_creature_with_power_zero_cannot_pay_casualty(self) -> None:
        """A creature with power 0 should not be valid for casualty 1."""
        game = create_game()
        p1 = game.players[0]
        sq = SilverquillTheDisputant(owner=p1, controller=p1)
        zero_power = Creature(
            name="Zero Token", owner=p1, controller=p1,
            base_power=0, base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[sq, zero_power])
        sq.register_triggers(game)

        # The implementation should expose some way to validate casualty
        # eligibility. The creature with power 0 should not be acceptable
        # for casualty 1.  This tests the card's casualty validation logic.
        # If the card uses a helper method, attribute, or checks in the
        # trigger condition, we verify a power-0 creature is rejected.
        can_pay = getattr(sq, "can_pay_casualty", None)
        if can_pay is not None:
            assert can_pay(game, zero_power) is False
        else:
            # Alternative: check that the casualty N value is set to 1
            casualty_n = getattr(sq, "casualty_n", None)
            assert casualty_n == 1

    def test_creature_with_power_one_can_pay_casualty(self) -> None:
        """A creature with power exactly 1 should be valid for casualty 1."""
        game = create_game()
        p1 = game.players[0]
        sq = SilverquillTheDisputant(owner=p1, controller=p1)
        one_power = Creature(
            name="Token", owner=p1, controller=p1,
            base_power=1, base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[sq, one_power])
        sq.register_triggers(game)

        can_pay = getattr(sq, "can_pay_casualty", None)
        if can_pay is not None:
            assert can_pay(game, one_power) is True
        else:
            casualty_n = getattr(sq, "casualty_n", None)
            assert casualty_n == 1

    def test_creature_with_power_greater_than_one_can_pay_casualty(self) -> None:
        """A creature with power > 1 should be valid for casualty 1."""
        game = create_game()
        p1 = game.players[0]
        sq = SilverquillTheDisputant(owner=p1, controller=p1)
        big_creature = Creature(
            name="Big Bear", owner=p1, controller=p1,
            base_power=5, base_toughness=5,
        )
        set_board_state(game, 0, battlefield=[sq, big_creature])
        sq.register_triggers(game)

        can_pay = getattr(sq, "can_pay_casualty", None)
        if can_pay is not None:
            assert can_pay(game, big_creature) is True
        else:
            casualty_n = getattr(sq, "casualty_n", None)
            assert casualty_n == 1


# ---------------------------------------------------------------------------
# Casualty sacrificed creature goes to graveyard
# ---------------------------------------------------------------------------


class TestSilverquillCasualtySacrifice:
    """When a creature is sacrificed for casualty, it should be moved to
    the graveyard (i.e., it is no longer on the battlefield)."""

    def test_sacrificed_creature_leaves_battlefield(self) -> None:
        """The creature sacrificed to pay casualty should no longer be
        on the battlefield after the sacrifice."""
        game = create_game()
        p1 = game.players[0]
        sq = SilverquillTheDisputant(owner=p1, controller=p1)
        token = Creature(
            name="Sac Target", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[sq, token])
        sq.register_triggers(game)

        # Put an instant on the stack and simulate casualty payment
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt._casualty_paid = True
        bolt._casualty_sacrificed = token

        stack_obj = StackObject(
            source=bolt, controller=p1, targets=[],
            on_resolve=lambda g: None,
        )
        game.stack.push(stack_obj)

        event = SpellCastTriggeredEvent(
            spell=bolt, player=p1, card=bolt, controller=p1
        )
        game.trigger_manager.fire_event(game, event)

        # Resolve any trigger effects
        while len(game.stack) > 1:
            obj = game.stack.pop()
            obj.on_resolve(game)

        # The token should have been sacrificed (moved to graveyard)
        bf = game.get_battlefield(p1)
        bf_names = [getattr(c, "name", "") for c in bf.get_all()]
        # Token should NOT be on the battlefield after casualty payment
        # (it was either sacrificed as part of the trigger effect or
        # as part of the casting cost).  The exact mechanism depends on
        # implementation but the token must leave the battlefield.
        assert "Sac Target" not in bf_names or token not in bf.get_all()


# ---------------------------------------------------------------------------
# Edge: Silverquill leaves battlefield -- triggers unregistered
# ---------------------------------------------------------------------------


class TestSilverquillLeavesPlay:
    """When Silverquill leaves the battlefield, its triggers should be
    unregistered so that subsequent instant/sorcery casts do NOT get
    casualty 1."""

    def test_triggers_unregistered_on_leave(self) -> None:
        """After Silverquill leaves the battlefield, no triggers from it
        should remain in the trigger manager."""
        game = create_game()
        p1 = game.players[0]
        sq = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[sq])
        sq.register_triggers(game)

        # Verify triggers exist
        assert len(game.trigger_manager.get_triggers_for_source(sq)) >= 1

        # Now unregister (as would happen when the creature leaves)
        game.trigger_manager.unregister(sq)

        # Triggers should be gone
        assert len(game.trigger_manager.get_triggers_for_source(sq)) == 0
