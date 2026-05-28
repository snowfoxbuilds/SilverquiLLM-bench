"""Tests for SOS 201 — Lorehold, the Historian.

Lorehold, the Historian is a {3}{R}{W} Legendary Creature — Elder Dragon (5/5)
with Flying, Haste.

Requirements tested:
1. Static properties: name, mana cost, power/toughness, types, supertypes,
   subtypes, keywords.
2. Miracle granting: "Each instant and sorcery card in your hand has miracle {2}."
   Instants and sorceries in the controller's hand should gain miracle with
   cost {2}. Creatures and other card types should not gain miracle.
3. Opponent's upkeep trigger: "At the beginning of each opponent's upkeep,
   you may discard a card. If you do, draw a card." This is a looting trigger
   that fires at the beginning of each opponent's upkeep.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery, Enchantment
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


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_elder_dragon_subtypes(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords

    def test_has_creature_type(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Miracle granting — instants and sorceries in hand get miracle {2}
# ---------------------------------------------------------------------------


class TestLoreholdMiracleGranting:
    """Each instant and sorcery card in your hand has miracle {2}.

    This is a static ability on Lorehold. While Lorehold is on the
    battlefield, every instant and sorcery card in the controller's hand
    should have miracle with cost {2}. Non-instant/sorcery cards should
    not gain miracle.
    """

    def test_instant_in_hand_gains_miracle(self) -> None:
        """An instant card in the controller's hand should have miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1,
                       mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[bolt])

        # The instant should now have a miracle cost attribute
        miracle_cost = getattr(bolt, "miracle_cost", None)
        assert miracle_cost is not None, (
            "Instant in hand should have miracle_cost when Lorehold is on battlefield"
        )
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Miracle cost should be {{2}}, got {miracle_cost}"
        )

    def test_sorcery_in_hand_gains_miracle(self) -> None:
        """A sorcery card in the controller's hand should have miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        div = Sorcery(name="Divination", owner=p1, controller=p1,
                      mana_cost=ManaCost.parse("{2}{U}"))
        set_board_state(game, 0, hand=[div])

        miracle_cost = getattr(div, "miracle_cost", None)
        assert miracle_cost is not None, (
            "Sorcery in hand should have miracle_cost when Lorehold is on battlefield"
        )
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Miracle cost should be {{2}}, got {miracle_cost}"
        )

    def test_creature_in_hand_does_not_gain_miracle(self) -> None:
        """A creature card in the controller's hand should NOT have miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[bear])

        miracle_cost = getattr(bear, "miracle_cost", None)
        assert miracle_cost is None, (
            "Creature in hand should NOT have miracle_cost"
        )

    def test_enchantment_in_hand_does_not_gain_miracle(self) -> None:
        """An enchantment card in hand should NOT have miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        ench = Enchantment(name="Pacifism", owner=p1, controller=p1,
                           mana_cost=ManaCost.parse("{1}{W}"))
        set_board_state(game, 0, hand=[ench])

        miracle_cost = getattr(ench, "miracle_cost", None)
        assert miracle_cost is None, (
            "Enchantment in hand should NOT have miracle_cost"
        )

    def test_miracle_cost_is_two_generic(self) -> None:
        """The miracle cost should be exactly {2} (two generic mana)."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        expensive = Instant(name="Expensive Spell", owner=p1, controller=p1,
                            mana_cost=ManaCost.parse("{5}{U}{U}"))
        set_board_state(game, 0, hand=[expensive])

        miracle_cost = getattr(expensive, "miracle_cost", None)
        assert miracle_cost is not None
        expected = ManaCost.parse("{2}")
        assert miracle_cost == expected, (
            f"Miracle cost should be {{2}} (generic 2), got {miracle_cost}"
        )

    def test_opponent_instants_do_not_gain_miracle(self) -> None:
        """Only the Lorehold controller's hand should gain miracle, not
        the opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Put an instant in the opponent's hand
        opp_bolt = Instant(name="Opponent Bolt", owner=p2, controller=p2,
                           mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 1, hand=[opp_bolt])

        miracle_cost = getattr(opp_bolt, "miracle_cost", None)
        assert miracle_cost is None, (
            "Opponent's instant should NOT gain miracle from Lorehold"
        )


# ---------------------------------------------------------------------------
# Opponent's upkeep trigger — registration
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTriggerRegistration:
    """At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

    The trigger should be registered when Lorehold enters the battlefield.
    """

    def test_registers_trigger(self) -> None:
        """register_triggers should register at least one trigger."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)

        before_count = len(game.trigger_manager.get_triggers())
        lorehold.register_triggers(game)
        after_count = len(game.trigger_manager.get_triggers())

        assert after_count > before_count, (
            "register_triggers should add at least one trigger"
        )

    def test_registered_trigger_watches_upkeep_event(self) -> None:
        """The registered trigger should watch for BeginningOfUpkeepTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        upkeep_triggers = [
            t for t in triggers
            if t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1, (
            "Should have at least one trigger watching BeginningOfUpkeepTriggeredEvent"
        )


# ---------------------------------------------------------------------------
# Opponent's upkeep trigger — condition
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTriggerCondition:
    """The upkeep trigger should fire only at the beginning of an opponent's
    upkeep, not the controller's own upkeep."""

    def test_trigger_fires_on_opponent_upkeep(self) -> None:
        """The trigger should fire when the active player is the opponent
        (i.e. it's the opponent's upkeep)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Set p2 (opponent) as the active player
        game.active_player_index = 1

        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        upkeep_triggers = [
            t for t in triggers
            if t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1

        event = BeginningOfUpkeepTriggeredEvent()
        trigger = upkeep_triggers[0]
        if trigger.condition is not None:
            result = trigger.condition(game, event)
            assert result is True, (
                "Trigger should fire on opponent's upkeep"
            )

    def test_trigger_does_not_fire_on_own_upkeep(self) -> None:
        """The trigger should NOT fire when the active player is the
        Lorehold controller (own upkeep, not opponent's)."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Set p1 (controller) as the active player — it's p1's own upkeep
        game.active_player_index = 0

        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        upkeep_triggers = [
            t for t in triggers
            if t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1

        event = BeginningOfUpkeepTriggeredEvent()
        trigger = upkeep_triggers[0]
        if trigger.condition is not None:
            result = trigger.condition(game, event)
            assert result is False, (
                "Trigger should NOT fire on the controller's own upkeep"
            )
        else:
            # If there's no condition, the trigger fires on every upkeep,
            # which is incorrect for "each opponent's upkeep"
            assert False, (
                "Trigger should have a condition to restrict to opponent's upkeep"
            )


# ---------------------------------------------------------------------------
# Opponent's upkeep trigger — effect (looting: discard then draw)
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTriggerEffect:
    """When the upkeep trigger resolves, the Lorehold controller may discard
    a card. If they do, they draw a card. This is a 'you may' (optional)
    discard-then-draw (looting) effect."""

    def test_looting_discards_a_card(self) -> None:
        """When choosing to discard, a card should move from hand to graveyard."""
        game = create_game(scripts=([True, None], []))
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Give p1 a card in hand to discard and a card in library to draw
        discard_card = Instant(name="Discard Me", owner=p1, controller=p1)
        draw_card = Instant(name="Draw Me", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[discard_card])
        game.get_library(p1).add(draw_card)

        # Set opponent as active player
        game.active_player_index = 1

        # Fire the upkeep event
        event = BeginningOfUpkeepTriggeredEvent()
        game.trigger_manager.fire_event(game, event)

        # Resolve the triggered ability
        if not game.stack.is_empty():
            stack_obj = game.stack.pop()
            stack_obj.on_resolve(game)

        # The discarded card should be in the graveyard
        assert game.get_graveyard(p1).contains(discard_card), (
            "Discarded card should be in the graveyard"
        )

    def test_looting_draws_a_card_after_discard(self) -> None:
        """After discarding, the controller should draw a card."""
        game = create_game(scripts=([True, None], []))
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Give p1 a card in hand to discard
        discard_card = Instant(name="Discard Me", owner=p1, controller=p1)
        draw_card = Instant(name="Draw Me", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[discard_card])
        game.get_library(p1).add(draw_card)

        # Set opponent as active player
        game.active_player_index = 1

        # Fire the upkeep event
        event = BeginningOfUpkeepTriggeredEvent()
        game.trigger_manager.fire_event(game, event)

        # Resolve the triggered ability
        if not game.stack.is_empty():
            stack_obj = game.stack.pop()
            stack_obj.on_resolve(game)

        # p1 should have drawn a card (the draw card should be in hand)
        assert game.get_hand(p1).contains(draw_card), (
            "Controller should have drawn a card after discarding"
        )

    def test_may_choose_not_to_discard(self) -> None:
        """The discard is optional ('you may'). If the controller chooses
        not to discard, no discard or draw occurs."""
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        hand_card = Instant(name="Keep Me", owner=p1, controller=p1)
        draw_card = Instant(name="Library Card", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[hand_card])
        game.get_library(p1).add(draw_card)

        # Set opponent as active player
        game.active_player_index = 1

        # Fire the upkeep event
        event = BeginningOfUpkeepTriggeredEvent()
        game.trigger_manager.fire_event(game, event)

        # Resolve the triggered ability (player says "no")
        if not game.stack.is_empty():
            stack_obj = game.stack.pop()
            stack_obj.on_resolve(game)

        # Hand should still contain the original card (not discarded)
        assert game.get_hand(p1).contains(hand_card), (
            "Card should remain in hand when choosing not to discard"
        )
        # Should NOT have drawn a card
        assert not game.get_hand(p1).contains(draw_card), (
            "Should not draw a card when declining to discard"
        )

    def test_empty_hand_no_discard_no_draw(self) -> None:
        """With an empty hand, the controller cannot discard, so no draw
        should occur either. The trigger should resolve without error."""
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        draw_card = Instant(name="Library Card", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[])
        game.get_library(p1).add(draw_card)

        # Set opponent as active player
        game.active_player_index = 1

        # Fire the upkeep event
        event = BeginningOfUpkeepTriggeredEvent()
        game.trigger_manager.fire_event(game, event)

        # Resolve the triggered ability — should not crash
        if not game.stack.is_empty():
            stack_obj = game.stack.pop()
            stack_obj.on_resolve(game)

        # Library card should still be in library (no draw happened)
        assert game.get_library(p1).contains(draw_card), (
            "Should not draw when hand is empty and no discard can occur"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestLoreholdEdgeCases:
    """Edge cases and boundary conditions for Lorehold, the Historian."""

    def test_multiple_instants_all_gain_miracle(self) -> None:
        """All instant/sorcery cards in hand should gain miracle, not just one."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1,
                       mana_cost=ManaCost.parse("{R}"))
        shock = Instant(name="Shock", owner=p1, controller=p1,
                        mana_cost=ManaCost.parse("{R}"))
        divination = Sorcery(name="Divination", owner=p1, controller=p1,
                             mana_cost=ManaCost.parse("{2}{U}"))
        set_board_state(game, 0, hand=[bolt, shock, divination])

        for card in [bolt, shock, divination]:
            miracle_cost = getattr(card, "miracle_cost", None)
            assert miracle_cost is not None, (
                f"{card.name} should have miracle_cost"
            )
            assert miracle_cost == ManaCost.parse("{2}"), (
                f"{card.name} miracle cost should be {{2}}, got {miracle_cost}"
            )

    def test_mixed_hand_only_instants_sorceries_gain_miracle(self) -> None:
        """In a mixed hand, only instants/sorceries should gain miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1,
                       mana_cost=ManaCost.parse("{R}"))
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        div = Sorcery(name="Divination", owner=p1, controller=p1,
                      mana_cost=ManaCost.parse("{2}{U}"))
        set_board_state(game, 0, hand=[bolt, bear, div])

        # Instants/sorceries get miracle
        assert getattr(bolt, "miracle_cost", None) is not None
        assert getattr(div, "miracle_cost", None) is not None
        # Creatures do not
        assert getattr(bear, "miracle_cost", None) is None

    def test_trigger_fires_event_onto_stack(self) -> None:
        """When the opponent's upkeep begins, the trigger should push
        something onto the stack."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Set opponent as active player
        game.active_player_index = 1

        assert game.stack.is_empty()

        event = BeginningOfUpkeepTriggeredEvent()
        game.trigger_manager.fire_event(game, event)

        assert not game.stack.is_empty(), (
            "Upkeep trigger should push an ability onto the stack"
        )

    def test_trigger_controller_is_lorehold_controller(self) -> None:
        """The registered trigger's controller should be the Lorehold controller."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        upkeep_triggers = [
            t for t in triggers
            if t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1
        assert upkeep_triggers[0].controller is p1, (
            "Trigger controller should be the Lorehold controller"
        )
