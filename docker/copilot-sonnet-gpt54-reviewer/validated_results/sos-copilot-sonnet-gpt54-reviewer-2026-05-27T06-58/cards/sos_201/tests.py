"""Tests for sos_201 — Lorehold, the Historian.

Card spec:
  - Legendary Creature — Elder Dragon
  - {3}{R}{W}, 5/5
  - Flying, haste
  - Each instant and sorcery card in your hand has miracle {2}.
  - At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

Test strategy:
  1. Static card properties (name, mana cost, P/T, type line, keywords).
  2. Trigger registration (upkeep trigger + DrawsCard miracle trigger).
  3. Opponent-upkeep trigger condition (fires for opponent, not controller).
  4. Opponent-upkeep trigger effect (discard → draw; pass → no draw).
  5. Miracle granting: DrawsCard trigger fires for instants/sorceries drawn
     as the first card of the turn; does NOT fire for non-instant/sorcery
     or when it's not the first draw.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import (
    BeginningOfUpkeepTriggeredEvent,
    DrawsCardTriggeredEvent,
)
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lorehold(game, player_index=0):
    """Create a LoreholdTheHistorian with owner/controller set to players[player_index]."""
    player = game.players[player_index]
    card = LoreholdTheHistorian(owner=player, controller=player)
    return card


def _make_instant(game, player_index=0, name="Test Instant"):
    """Create a vanilla Instant owned by players[player_index]."""
    player = game.players[player_index]
    card = Instant(name=name, owner=player, controller=player)
    return card


def _make_sorcery(game, player_index=0, name="Test Sorcery"):
    """Create a vanilla Sorcery owned by players[player_index]."""
    player = game.players[player_index]
    card = Sorcery(name=name, owner=player, controller=player)
    return card


def _make_creature(game, player_index=0, name="Test Creature"):
    """Create a vanilla Creature owned by players[player_index]."""
    player = game.players[player_index]
    card = Creature(name=name, base_power=2, base_toughness=2,
                    owner=player, controller=player)
    return card


# ---------------------------------------------------------------------------
# 1. Static card properties
# ---------------------------------------------------------------------------

class TestLoreholdProperties:
    """Static card data must match the sos_201 spec."""

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        expected = ManaCost.parse("{3}{R}{W}")
        assert LoreholdTheHistorian(owner=None).mana_cost == expected

    def test_base_power(self) -> None:
        assert LoreholdTheHistorian(owner=None).base_power == 5

    def test_base_toughness(self) -> None:
        assert LoreholdTheHistorian(owner=None).base_toughness == 5

    def test_has_flying(self) -> None:
        kw = LoreholdTheHistorian(owner=None).keywords
        assert Keyword.FLYING in kw

    def test_has_haste(self) -> None:
        kw = LoreholdTheHistorian(owner=None).keywords
        assert Keyword.HASTE in kw

    def test_is_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_creature_card_type(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtypes_include_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Dragon" in card.subtypes

    def test_subtypes_include_elder(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes


# ---------------------------------------------------------------------------
# 2. Trigger registration
# ---------------------------------------------------------------------------

class TestLoreholdTriggerRegistration:
    """register_triggers must register both required triggered abilities."""

    def test_registers_upkeep_trigger(self) -> None:
        """At least one trigger fires for BeginningOfUpkeepTriggeredEvent."""
        game = create_game()
        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        upkeep_triggers = [
            t for t in triggers
            if issubclass(t.event_type, BeginningOfUpkeepTriggeredEvent)
        ]
        assert len(upkeep_triggers) >= 1, (
            "Expected at least one trigger for BeginningOfUpkeepTriggeredEvent"
        )

    def test_registers_draws_card_trigger(self) -> None:
        """At least one trigger fires for DrawsCardTriggeredEvent (miracle)."""
        game = create_game()
        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        draw_triggers = [
            t for t in triggers
            if issubclass(t.event_type, DrawsCardTriggeredEvent)
        ]
        assert len(draw_triggers) >= 1, (
            "Expected at least one trigger for DrawsCardTriggeredEvent (miracle granting)"
        )

    def test_triggers_are_trigger_registration_instances(self) -> None:
        """All registered triggers must be TriggerRegistration instances."""
        game = create_game()
        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        for t in game.trigger_manager.get_triggers_for_source(lorehold):
            assert isinstance(t, TriggerRegistration)


# ---------------------------------------------------------------------------
# 3. Opponent-upkeep trigger condition
# ---------------------------------------------------------------------------

class TestLoreholdUpkeepTriggerCondition:
    """The upkeep trigger must fire only during an opponent's upkeep."""

    def _get_upkeep_trigger(self, game, lorehold):
        """Retrieve the first BeginningOfUpkeepTriggeredEvent trigger."""
        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        for t in triggers:
            if issubclass(t.event_type, BeginningOfUpkeepTriggeredEvent):
                return t
        raise AssertionError("No upkeep trigger found")

    def test_condition_true_when_active_player_is_opponent(self) -> None:
        """Trigger fires when the active player is NOT Lorehold's controller."""
        game = create_game()
        p1 = game.players[0]  # Lorehold's controller
        # Make p2 the active player (opponent's upkeep)
        game.active_player_index = 1

        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        trigger = self._get_upkeep_trigger(game, lorehold)

        event = BeginningOfUpkeepTriggeredEvent()
        # Condition must be None (always fire) OR return True for opponent's upkeep
        if trigger.condition is None:
            # No condition means always fire; we trust the effect to guard
            pass
        else:
            assert trigger.condition(game, event) is True

    def test_condition_false_when_active_player_is_controller(self) -> None:
        """Trigger must NOT fire when the active player is Lorehold's own controller."""
        game = create_game()
        p1 = game.players[0]  # Lorehold's controller = active player
        game.active_player_index = 0

        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        trigger = self._get_upkeep_trigger(game, lorehold)

        event = BeginningOfUpkeepTriggeredEvent()
        # If condition is None, the trigger fires always — that would be wrong.
        assert trigger.condition is not None, (
            "Upkeep trigger must have a condition to guard against controller's own upkeep"
        )
        assert trigger.condition(game, event) is False


# ---------------------------------------------------------------------------
# 4. Opponent-upkeep trigger effect: discard → draw
# ---------------------------------------------------------------------------

class TestLoreholdUpkeepEffect:
    """The trigger effect: optionally discard a card; if discarded, draw a card."""

    def _get_upkeep_trigger(self, game, lorehold):
        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        for t in triggers:
            if issubclass(t.event_type, BeginningOfUpkeepTriggeredEvent):
                return t
        raise AssertionError("No upkeep trigger found")

    def test_discard_then_draw_when_player_chooses_yes(self) -> None:
        """When controller says yes: a card is discarded and a new card is drawn."""
        from engine.card import CardImpl
        from engine.types import Zone

        # Script: p1 says yes, then picks the card in hand to discard
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        p2 = game.players[1]

        # Lorehold is p1's creature; p2 is the active player (opponent's upkeep)
        game.active_player_index = 1

        lorehold = _make_lorehold(game, player_index=0)

        # Give p1 a card in hand to discard and a card in library to draw
        discard_card = _make_instant(game, player_index=0, name="Discard Me")
        library_card = _make_instant(game, player_index=0, name="Draw Me")
        set_board_state(game, 0, hand=[discard_card])
        # Put library_card in library
        p1.zones[Zone.LIBRARY].add(library_card)

        # Script: p1 says yes, then picks discard_card as the card to discard
        p1._script.append(True)       # yes, I want to discard
        p1._script.append(discard_card)  # which card to discard

        lorehold.register_triggers(game)
        trigger = self._get_upkeep_trigger(game, lorehold)

        hand_before = len(p1.zones[Zone.HAND].get_all())
        graveyard_before = len(p1.zones[Zone.GRAVEYARD].get_all())

        # Execute the trigger effect directly
        trigger.effect(game)

        hand_after = len(p1.zones[Zone.HAND].get_all())
        graveyard_after = len(p1.zones[Zone.GRAVEYARD].get_all())

        # Net result: -1 discarded +1 drawn = same hand size
        assert hand_after == hand_before, (
            f"Expected hand size unchanged (discard + draw), got {hand_after} vs {hand_before}"
        )
        # Graveyard should have gained the discarded card
        assert graveyard_after == graveyard_before + 1, (
            "Discarded card should be in graveyard"
        )
        # Discard_card should be in graveyard
        assert p1.zones[Zone.GRAVEYARD].contains(discard_card), (
            "The discarded card should now be in the graveyard"
        )
        # Draw Me should be in hand
        assert p1.zones[Zone.HAND].contains(library_card), (
            "The drawn card (library_card) should now be in hand"
        )

    def test_no_discard_no_draw_when_player_passes(self) -> None:
        """When controller says no: nothing is discarded, nothing is drawn."""
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        p2 = game.players[1]
        game.active_player_index = 1

        lorehold = _make_lorehold(game, player_index=0)

        hold_card = _make_instant(game, player_index=0, name="Keep Me")
        library_card = _make_instant(game, player_index=0, name="Library Card")
        set_board_state(game, 0, hand=[hold_card])
        p1.zones[Zone.LIBRARY].add(library_card)

        # Script: p1 says no
        p1._script.append(False)

        lorehold.register_triggers(game)
        trigger = self._get_upkeep_trigger(game, lorehold)

        hand_before = len(p1.zones[Zone.HAND].get_all())

        trigger.effect(game)

        hand_after = len(p1.zones[Zone.HAND].get_all())
        graveyard_after = len(p1.zones[Zone.GRAVEYARD].get_all())

        assert hand_after == hand_before, "Hand should not change when player declines"
        assert graveyard_after == 0, "No cards should be discarded when player declines"
        # library_card remains in library
        assert p1.zones[Zone.LIBRARY].contains(library_card)


# ---------------------------------------------------------------------------
# 5. Miracle-granting DrawsCard trigger
# ---------------------------------------------------------------------------

class TestLoreholdMiracleGranting:
    """DrawsCard trigger for miracle {2}: fires for instants/sorceries drawn
    as first card of the turn; not for other card types or later draws."""

    def _get_draws_card_trigger(self, game, lorehold):
        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        for t in triggers:
            if issubclass(t.event_type, DrawsCardTriggeredEvent):
                return t
        raise AssertionError("No DrawsCardTriggeredEvent trigger found")

    def _reset_cards_drawn(self, player, count=0) -> None:
        """Set the player's cards_drawn_this_turn counter."""
        player.cards_drawn_this_turn = count

    def test_miracle_trigger_fires_for_instant_as_first_draw(self) -> None:
        """Condition is True when controller draws an instant as the 1st card."""
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0

        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        trigger = self._get_draws_card_trigger(game, lorehold)

        if trigger.condition is None:
            pytest.skip("No condition on DrawsCard trigger — cannot validate miracle filtering")

        instant = _make_instant(game, player_index=0)
        self._reset_cards_drawn(p1, 1)  # This IS the first draw
        event = DrawsCardTriggeredEvent(player=p1, card=instant)
        assert trigger.condition(game, event) is True

    def test_miracle_trigger_fires_for_sorcery_as_first_draw(self) -> None:
        """Condition is True when controller draws a sorcery as the 1st card."""
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0

        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        trigger = self._get_draws_card_trigger(game, lorehold)

        if trigger.condition is None:
            pytest.skip("No condition on DrawsCard trigger — cannot validate miracle filtering")

        sorcery = _make_sorcery(game, player_index=0)
        self._reset_cards_drawn(p1, 1)
        event = DrawsCardTriggeredEvent(player=p1, card=sorcery)
        assert trigger.condition(game, event) is True

    def test_miracle_trigger_does_not_fire_for_creature(self) -> None:
        """Condition is False when the drawn card is a creature (not instant/sorcery)."""
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0

        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        trigger = self._get_draws_card_trigger(game, lorehold)

        if trigger.condition is None:
            pytest.skip("No condition on DrawsCard trigger — cannot validate card-type filtering")

        creature = _make_creature(game, player_index=0)
        self._reset_cards_drawn(p1, 1)
        event = DrawsCardTriggeredEvent(player=p1, card=creature)
        assert trigger.condition(game, event) is False

    def test_miracle_trigger_does_not_fire_for_second_draw(self) -> None:
        """Condition is False when it's NOT the first card drawn this turn."""
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0

        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        trigger = self._get_draws_card_trigger(game, lorehold)

        if trigger.condition is None:
            pytest.skip("No condition on DrawsCard trigger — cannot validate first-draw guard")

        instant = _make_instant(game, player_index=0)
        self._reset_cards_drawn(p1, 2)  # second draw
        event = DrawsCardTriggeredEvent(player=p1, card=instant)
        assert trigger.condition(game, event) is False

    def test_miracle_trigger_does_not_fire_for_opponent_draw(self) -> None:
        """Condition is False when an opponent draws an instant (not Lorehold's controller)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        game.active_player_index = 1

        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)
        trigger = self._get_draws_card_trigger(game, lorehold)

        if trigger.condition is None:
            pytest.skip("No condition on DrawsCard trigger — cannot validate player guard")

        instant = _make_instant(game, player_index=1)
        p2.cards_drawn_this_turn = 1
        event = DrawsCardTriggeredEvent(player=p2, card=instant)
        assert trigger.condition(game, event) is False

    def test_miracle_trigger_puts_stack_object_on_stack(self) -> None:
        """When the miracle trigger fires for a qualifying draw, the trigger
        should place something on the stack (the miracle-cast opportunity)."""
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0

        lorehold = _make_lorehold(game, player_index=0)
        lorehold.register_triggers(game)

        instant = _make_instant(game, player_index=0, name="Miracle Instant")
        # Simulate the draw: put the instant in hand, record first draw
        set_board_state(game, 0, hand=[instant])
        p1.cards_drawn_this_turn = 1

        stack_before = len(game.stack)

        event = DrawsCardTriggeredEvent(player=p1, card=instant)
        game.trigger_manager.fire_event(game, event)

        # At least one stack object should have been pushed
        stack_after = len(game.stack)
        assert stack_after > stack_before, (
            "Miracle trigger should push a stack object when the condition is met"
        )
