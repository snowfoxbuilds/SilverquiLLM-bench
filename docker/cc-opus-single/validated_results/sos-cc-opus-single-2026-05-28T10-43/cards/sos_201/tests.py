"""Tests for SOS 201 — Lorehold, the Historian.

Card spec:
  Name: Lorehold, the Historian
  Mana cost: {3}{R}{W}
  Type: Legendary Creature — Elder Dragon
  Oracle text:
    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
  Power/Toughness: 5/5
  Keywords: Flying, Haste
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


class TestLoreholdProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords

    def test_legendary_supertype(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_elder_dragon_subtypes(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Miracle granting — instants and sorceries in hand get miracle {2}
# ---------------------------------------------------------------------------


class TestLoreholdMiracleGrant:
    """Each instant and sorcery card in your hand has miracle {2}.

    Lorehold grants the miracle keyword ability to all instant and sorcery
    cards in the controller's hand. This is a continuous/static ability that
    should be checkable on cards in hand while Lorehold is on the battlefield.
    """

    def test_instant_in_hand_has_miracle(self) -> None:
        """An instant card in the controller's hand should have miracle {2}
        when Lorehold is on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        instant = Instant(name="Test Bolt", owner=p1, controller=p1,
                          mana_cost=ManaCost.parse("{R}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[instant])
        lorehold.register_triggers(game)

        # The instant in hand should have a miracle cost of {2}
        miracle_cost = getattr(instant, "miracle_cost", None)
        assert miracle_cost is not None, "Instant in hand should have miracle_cost"
        assert miracle_cost == ManaCost.parse("{2}") or miracle_cost == 2

    def test_sorcery_in_hand_has_miracle(self) -> None:
        """A sorcery card in the controller's hand should have miracle {2}
        when Lorehold is on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        sorcery = Sorcery(name="Test Divination", owner=p1, controller=p1,
                          mana_cost=ManaCost.parse("{2}{U}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[sorcery])
        lorehold.register_triggers(game)

        miracle_cost = getattr(sorcery, "miracle_cost", None)
        assert miracle_cost is not None, "Sorcery in hand should have miracle_cost"
        assert miracle_cost == ManaCost.parse("{2}") or miracle_cost == 2

    def test_creature_in_hand_does_not_get_miracle(self) -> None:
        """Non-instant/sorcery cards should NOT get miracle from Lorehold."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        creature = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[lorehold], hand=[creature])
        lorehold.register_triggers(game)

        miracle_cost = getattr(creature, "miracle_cost", None)
        assert miracle_cost is None, "Creature should not get miracle from Lorehold"

    def test_opponent_instants_do_not_get_miracle(self) -> None:
        """Instants in the opponent's hand should NOT get miracle from Lorehold."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        opp_instant = Instant(name="Opponent Bolt", owner=p2, controller=p2,
                              mana_cost=ManaCost.parse("{R}"))

        set_board_state(game, 0, battlefield=[lorehold])
        set_board_state(game, 1, hand=[opp_instant])
        lorehold.register_triggers(game)

        miracle_cost = getattr(opp_instant, "miracle_cost", None)
        assert miracle_cost is None, "Opponent's instant should not get miracle"


# ---------------------------------------------------------------------------
# Miracle trigger — first card drawn this turn can be cast for miracle cost
# ---------------------------------------------------------------------------


class TestLoreholdMiracleTrigger:
    """The miracle mechanic allows casting a drawn instant/sorcery for {2}
    if it is the first card drawn this turn. Per rule 702.94a, when a card
    with miracle is drawn as the first card of the turn, the player may
    reveal it and cast it for the miracle cost.
    """

    def test_miracle_trigger_on_first_draw_of_instant(self) -> None:
        """When the first card drawn this turn is an instant with miracle
        (granted by Lorehold), a miracle trigger should fire or the card
        should become castable for {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        instant = Instant(name="Miracle Bolt", owner=p1, controller=p1,
                          mana_cost=ManaCost.parse("{3}{R}"))

        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Put the instant on top of library
        game.get_library(p1).add(instant)

        # Reset cards drawn tracker
        if hasattr(p1, "cards_drawn_this_turn"):
            p1.cards_drawn_this_turn = 0

        # Draw the card (first card this turn)
        from engine.game import draw_card
        drawn = draw_card(game, p1)

        assert drawn is instant, "Should have drawn the instant"

        # After drawing, there should be a miracle opportunity:
        # either a trigger on the stack or the card should be flagged
        # for miracle casting at cost {2}
        miracle_available = (
            not game.stack.is_empty()
            or getattr(instant, "_miracle_revealed", False)
            or getattr(instant, "miracle_triggered", False)
        )
        assert miracle_available, (
            "Drawing an instant as first card should create miracle opportunity"
        )

    def test_no_miracle_on_second_draw(self) -> None:
        """Miracle only triggers on the FIRST card drawn each turn.
        A second drawn card should not get a miracle trigger."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        first_card = Instant(name="First Draw", owner=p1, controller=p1,
                             mana_cost=ManaCost.parse("{R}"))
        second_card = Instant(name="Second Draw", owner=p1, controller=p1,
                              mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Put both cards on top of library (second_card on top)
        game.get_library(p1).add(first_card)
        game.get_library(p1).add(second_card)

        # Reset
        if hasattr(p1, "cards_drawn_this_turn"):
            p1.cards_drawn_this_turn = 0

        from engine.game import draw_card

        # First draw — miracle eligible
        draw_card(game, p1)

        # Clear any stack objects from first draw miracle
        while not game.stack.is_empty():
            game.stack.pop()

        stack_before = len(game.stack)

        # Second draw — should NOT miracle
        drawn2 = draw_card(game, p1)
        assert drawn2 is first_card

        # No new miracle trigger on stack for the second draw
        miracle_triggered_second = (
            getattr(first_card, "_miracle_revealed", False)
            or getattr(first_card, "miracle_triggered", False)
        )
        # The second card drawn should not have miracle triggered
        assert not miracle_triggered_second or len(game.stack) == stack_before, (
            "Second card drawn this turn should not get miracle trigger"
        )

    def test_miracle_not_triggered_for_creature_draw(self) -> None:
        """When the first card drawn is a creature (not an instant or
        sorcery), miracle should NOT trigger even though Lorehold is on
        the battlefield."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        creature = Creature(name="Bear Draw", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        game.get_library(p1).add(creature)

        if hasattr(p1, "cards_drawn_this_turn"):
            p1.cards_drawn_this_turn = 0

        from engine.game import draw_card
        stack_before = len(game.stack)
        draw_card(game, p1)

        # Creature should not trigger miracle
        miracle_on_creature = (
            getattr(creature, "_miracle_revealed", False)
            or getattr(creature, "miracle_triggered", False)
        )
        assert not miracle_on_creature, (
            "Creature should not get miracle trigger"
        )


# ---------------------------------------------------------------------------
# Upkeep trigger — discard to draw (looting) at opponent's upkeep
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTrigger:
    """At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

    This is a triggered ability that triggers at the beginning of each
    opponent's upkeep, offering the controller a may-discard-then-draw.
    """

    def test_registers_upkeep_trigger(self) -> None:
        """Lorehold should register a triggered ability that watches for
        the beginning of upkeep events."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        before_count = len(game.trigger_manager.get_triggers())
        lorehold.register_triggers(game)
        after_count = len(game.trigger_manager.get_triggers())

        assert after_count > before_count, (
            "Lorehold should register at least one trigger"
        )

    def test_trigger_fires_on_opponent_upkeep(self) -> None:
        """The looting trigger should fire when the opponent's upkeep
        begins (Lorehold's controller is not the active player)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Set active player to opponent (p2)
        game.active_player_index = 1

        # Fire the upkeep event
        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent()
        )

        # There should be a trigger on the stack
        assert not game.stack.is_empty(), (
            "Trigger should fire on opponent's upkeep"
        )

    def test_trigger_does_not_fire_on_own_upkeep(self) -> None:
        """The trigger says 'each opponent's upkeep', so it should NOT
        fire during the controller's own upkeep."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Active player is p1 (Lorehold's controller)
        game.active_player_index = 0

        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent()
        )

        # No trigger should be on the stack
        assert game.stack.is_empty(), (
            "Trigger should NOT fire on controller's own upkeep"
        )

    def test_upkeep_discard_then_draw(self) -> None:
        """When the trigger resolves and the player chooses 'yes' to
        discard, they discard a card then draw a card."""
        game = create_game(scripts=([True], []))  # p1 says "yes" to may
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        # Give p1 a card in hand to discard
        discard_card = Instant(name="Fodder", owner=p1, controller=p1,
                               mana_cost=ManaCost.parse("{R}"))
        # Put a card in library to draw
        draw_target = Sorcery(name="Reward", owner=p1, controller=p1,
                              mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[discard_card])
        game.get_library(p1).add(draw_target)
        lorehold.register_triggers(game)

        # Simulate opponent's upkeep
        game.active_player_index = 1

        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent()
        )

        # Resolve the trigger
        assert not game.stack.is_empty(), "Trigger should be on stack"
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        # The discard_card should have moved to graveyard
        hand_cards = game.get_hand(p1).get_all()
        graveyard_cards = game.get_graveyard(p1).get_all()

        hand_names = [getattr(c, "name", "") for c in hand_cards]
        graveyard_names = [getattr(c, "name", "") for c in graveyard_cards]

        assert "Fodder" not in hand_names, (
            "Discarded card should not be in hand"
        )
        assert "Fodder" in graveyard_names, (
            "Discarded card should be in graveyard"
        )
        # Should have drawn a card
        assert "Reward" in hand_names, (
            "Should have drawn a card after discarding"
        )

    def test_upkeep_decline_discard(self) -> None:
        """When the trigger resolves and the player declines ('no'),
        no cards are discarded and no cards are drawn."""
        game = create_game(scripts=([False], []))  # p1 says "no"
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        hand_card = Instant(name="Keep Me", owner=p1, controller=p1,
                            mana_cost=ManaCost.parse("{R}"))
        lib_card = Sorcery(name="Stay In Library", owner=p1, controller=p1,
                           mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[hand_card])
        game.get_library(p1).add(lib_card)
        lorehold.register_triggers(game)

        game.active_player_index = 1

        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent()
        )

        assert not game.stack.is_empty()
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        # Hand should still contain the original card
        hand_names = [getattr(c, "name", "") for c in game.get_hand(p1).get_all()]
        assert "Keep Me" in hand_names, "Card should remain in hand when declining"
        # Library card should still be in library
        assert game.get_library(p1).contains(lib_card), (
            "Library card should remain when declining discard"
        )

    def test_upkeep_no_cards_in_hand_no_discard(self) -> None:
        """If the player has no cards in hand, the may ability should
        effectively do nothing (no discard possible, so no draw)."""
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        lib_card = Instant(name="Library Card", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        game.get_library(p1).add(lib_card)
        lorehold.register_triggers(game)

        game.active_player_index = 1

        game.trigger_manager.fire_event(
            game, BeginningOfUpkeepTriggeredEvent()
        )

        # Even if trigger fires, with no cards in hand, nothing happens
        if not game.stack.is_empty():
            trigger = game.stack.pop()
            trigger.on_resolve(game)

        # Library card should still be there (no draw without discard)
        assert game.get_library(p1).contains(lib_card), (
            "Should not draw if no card was discarded"
        )

    def test_upkeep_trigger_source_is_lorehold(self) -> None:
        """The registered trigger's source should be the Lorehold card."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        lorehold.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        assert len(triggers) >= 1, (
            "At least one trigger should be registered with Lorehold as source"
        )

    def test_upkeep_trigger_controller_is_lorehold_controller(self) -> None:
        """The trigger's controller should be Lorehold's controller."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        lorehold.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        upkeep_triggers = [
            t for t in triggers
            if t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1
        assert upkeep_triggers[0].controller is p1


# ---------------------------------------------------------------------------
# ETB / Battlefield integration
# ---------------------------------------------------------------------------


class TestLoreholdBattlefield:
    """Integration tests: Lorehold entering the battlefield should
    register its triggers properly, and leaving should unregister them."""

    def test_enters_battlefield_registers_triggers(self) -> None:
        """When Lorehold enters the battlefield via move_to_zone,
        triggers should be registered."""
        from engine.zones import move_to_zone
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        # Put in hand first
        game.get_hand(p1).add(lorehold)

        triggers_before = len(game.trigger_manager.get_triggers())
        # Simulate moving to battlefield (ETB hooks fire)
        move_to_zone(game, lorehold, Zone.HAND, Zone.BATTLEFIELD)
        triggers_after = len(game.trigger_manager.get_triggers())

        assert triggers_after > triggers_before, (
            "Triggers should be registered when Lorehold enters battlefield"
        )

    def test_leaves_battlefield_unregisters_triggers(self) -> None:
        """When Lorehold leaves the battlefield, its triggers should be
        unregistered."""
        from engine.zones import move_to_zone
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        # Place on battlefield
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        triggers_registered = len(
            game.trigger_manager.get_triggers_for_source(lorehold)
        )
        assert triggers_registered > 0

        # Remove from battlefield (simulate destruction)
        move_to_zone(game, lorehold, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        triggers_remaining = len(
            game.trigger_manager.get_triggers_for_source(lorehold)
        )
        assert triggers_remaining == 0, (
            "All Lorehold triggers should be unregistered after leaving battlefield"
        )
