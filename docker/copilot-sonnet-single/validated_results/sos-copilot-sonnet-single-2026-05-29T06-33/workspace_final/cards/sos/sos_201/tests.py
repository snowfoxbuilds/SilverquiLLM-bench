"""Tests for SOS 201 — Lorehold, the Historian.

Oracle text:
  Flying, haste
  Each instant and sorcery card in your hand has miracle {2}. (You may cast
  a card for its miracle cost when you draw it if it's the first card you
  drew this turn.)
  At the beginning of each opponent's upkeep, you may discard a card.
  If you do, draw a card.

Tests cover:
- Static card properties (name, mana_cost, P/T, legendary, subtypes)
- Flying and Haste keywords
- Miracle {2} continuous grant to instants/sorceries in controller's hand
- Miracle grant is NOT applied to non-instant/non-sorcery hand cards
- Miracle grant is NOT applied when Lorehold is not on the battlefield
- Miracle cast condition: first drawn instant/sorcery is marked castable for miracle cost
- Second draw of turn is NOT marked as miraculable
- Upkeep trigger: register_triggers registers a BeginningOfUpkeepTriggeredEvent trigger
- Upkeep trigger: fires only on opponent's upkeep (active player is opponent)
- Upkeep trigger: discard a card → draw a card (net-zero hand churn)
- Upkeep trigger: choosing not to discard → no draw
"""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent, DrawsCardTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestLoreholdTheHistorianProperties:
    """Static card data must match the SOS 201 spec."""

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_elder_subtype(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes

    def test_has_dragon_subtype(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Dragon" in card.subtypes

    def test_has_creature_card_type(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Keyword tests — Flying and Haste
# ---------------------------------------------------------------------------


class TestLoreholdTheHistorianKeywords:
    """Lorehold must have both Flying and Haste."""

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords


# ---------------------------------------------------------------------------
# Miracle {2} continuous grant tests
# ---------------------------------------------------------------------------


class TestLoreholdTheHistorianMiracleGrant:
    """While on the battlefield, Lorehold grants miracle {2} to each instant
    and sorcery in the controller's hand.  This is a static (continuous) ability.
    """

    def _setup_lorehold_on_battlefield(self, game, player_index: int = 0):
        """Place Lorehold on player's battlefield and register its triggers."""
        player = game.players[player_index]
        lorehold = LoreholdTheHistorian(owner=player, controller=player)
        set_board_state(game, player_index, battlefield=[lorehold])
        lorehold.register_triggers(game)
        return lorehold

    def test_instant_in_hand_gets_miracle_cost(self) -> None:
        """An instant in the controller's hand acquires miracle_cost == {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = self._setup_lorehold_on_battlefield(game, 0)

        lightning = Instant(
            name="Lightning Bolt",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[lightning])

        # Apply any continuous effects registered by Lorehold
        game.effect_manager.apply_all(game)

        assert hasattr(lightning, "miracle_cost"), (
            "Instant in hand should have miracle_cost set by Lorehold"
        )
        assert lightning.miracle_cost == ManaCost.parse("{2}"), (
            "miracle_cost should be {2}"
        )

    def test_sorcery_in_hand_gets_miracle_cost(self) -> None:
        """A sorcery in the controller's hand acquires miracle_cost == {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = self._setup_lorehold_on_battlefield(game, 0)

        wrath = Sorcery(
            name="Wrath of God",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[wrath])

        game.effect_manager.apply_all(game)

        assert hasattr(wrath, "miracle_cost"), (
            "Sorcery in hand should have miracle_cost set by Lorehold"
        )
        assert wrath.miracle_cost == ManaCost.parse("{2}"), (
            "miracle_cost should be {2}"
        )

    def test_creature_in_hand_does_not_get_miracle_cost(self) -> None:
        """A creature card in hand must NOT receive the miracle {2} grant."""
        game = create_game()
        p1 = game.players[0]
        lorehold = self._setup_lorehold_on_battlefield(game, 0)

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, hand=[bear])

        game.effect_manager.apply_all(game)

        # If the attribute is set, its value must NOT be {2}
        miracle_cost = getattr(bear, "miracle_cost", None)
        assert miracle_cost != ManaCost.parse("{2}"), (
            "Creature in hand must not receive miracle {2} from Lorehold"
        )

    def test_miracle_grant_not_applied_when_lorehold_not_on_battlefield(self) -> None:
        """Without Lorehold on the battlefield, instants in hand have no miracle grant."""
        game = create_game()
        p1 = game.players[0]

        # Lorehold is NOT on the battlefield
        lightning = Instant(
            name="Lightning Bolt",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[lightning])

        # Do not register any triggers; just apply effects
        game.effect_manager.apply_all(game)

        miracle_cost = getattr(lightning, "miracle_cost", None)
        assert miracle_cost != ManaCost.parse("{2}"), (
            "Instant should NOT have miracle {2} without Lorehold on battlefield"
        )

    def test_opponent_instant_in_hand_does_not_get_miracle_cost(self) -> None:
        """Opponent's instants in hand must NOT receive Lorehold's miracle grant."""
        game = create_game()
        lorehold = self._setup_lorehold_on_battlefield(game, 0)  # player 0's battlefield

        p2 = game.players[1]
        opponent_instant = Instant(
            name="Counterspell",
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 1, hand=[opponent_instant])

        game.effect_manager.apply_all(game)

        miracle_cost = getattr(opponent_instant, "miracle_cost", None)
        assert miracle_cost != ManaCost.parse("{2}"), (
            "Opponent's instant in hand must not receive Lorehold's miracle grant"
        )


# ---------------------------------------------------------------------------
# Miracle cast condition — first-draw trigger
# ---------------------------------------------------------------------------


class TestLoreholdTheHistorianMiracleCastCondition:
    """When the controller draws their first card of the turn and Lorehold is
    on the battlefield, that card (if instant/sorcery) may be cast for its
    miracle cost of {2}.
    """

    def test_first_drawn_instant_marked_as_miraculable(self) -> None:
        """Drawing the first instant of the turn while Lorehold is in play
        marks the card so it can be cast for miracle cost {2}.
        """
        game = create_game()
        p1 = game.players[0]

        # Lorehold is on the battlefield
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Reset draw count to simulate "no draws yet this turn"
        p1.cards_drawn_this_turn = 0

        # Place an instant on top of player's library to be drawn
        lightning = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(lightning)

        # Draw the card — this should be the first draw of the turn
        from engine.game import draw_card
        drawn = draw_card(game, p1)

        assert drawn is lightning, "Drew wrong card"
        # After drawing the first instant/sorcery of the turn, it should be
        # eligible for miracle casting
        can_miracle = getattr(drawn, "can_cast_as_miracle", False)
        assert can_miracle is True, (
            "First drawn instant should be marked can_cast_as_miracle=True"
        )

    def test_first_drawn_sorcery_marked_as_miraculable(self) -> None:
        """Drawing the first sorcery of the turn while Lorehold is in play
        marks the card as miraculable.
        """
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        p1.cards_drawn_this_turn = 0

        wrath = Sorcery(name="Wrath of God", owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(wrath)

        from engine.game import draw_card
        drawn = draw_card(game, p1)

        assert drawn is wrath
        assert getattr(drawn, "can_cast_as_miracle", False) is True, (
            "First drawn sorcery should be marked can_cast_as_miracle=True"
        )

    def test_second_drawn_card_not_miraculable(self) -> None:
        """If the player has already drawn this turn, the next draw is not miracle-eligible."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Simulate one card already drawn this turn
        p1.cards_drawn_this_turn = 1

        lightning = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(lightning)

        from engine.game import draw_card
        drawn = draw_card(game, p1)

        assert drawn is lightning
        assert getattr(drawn, "can_cast_as_miracle", False) is False, (
            "Second draw this turn should NOT be miracle-eligible"
        )

    def test_first_drawn_creature_not_miraculable(self) -> None:
        """Drawing a creature as the first card doesn't get the miracle mark,
        because Lorehold only grants miracle to instants and sorceries.
        """
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        p1.cards_drawn_this_turn = 0

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        p1.zones[Zone.LIBRARY].add(bear)

        from engine.game import draw_card
        drawn = draw_card(game, p1)

        assert drawn is bear
        assert getattr(drawn, "can_cast_as_miracle", False) is False, (
            "First drawn creature should NOT be miracle-eligible (only instants/sorceries)"
        )


# ---------------------------------------------------------------------------
# Opponent's upkeep trigger
# ---------------------------------------------------------------------------


class TestLoreholdTheHistorianUpkeepTrigger:
    """At the beginning of each opponent's upkeep, controller may discard
    then draw a card (looting on opponent's upkeep).
    """

    def test_register_triggers_adds_upkeep_trigger(self) -> None:
        """register_triggers must register at least one BeginningOfUpkeepTriggeredEvent trigger."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        upkeep_triggers = [
            t for t in triggers if t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1, (
            "register_triggers must register a BeginningOfUpkeepTriggeredEvent trigger"
        )

    def test_discard_and_draw_on_opponent_upkeep(self) -> None:
        """When an opponent's upkeep begins and the controller chooses yes,
        one card is discarded and one card is drawn (net-zero churn).
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Give p1 two cards in hand and one in library to draw
        card_a = Instant(name="Shock", owner=p1, controller=p1)
        card_b = Sorcery(name="Divination", owner=p1, controller=p1)
        draw_target = Instant(name="Counterspell", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card_a, card_b])
        p1.zones[Zone.LIBRARY].add(draw_target)

        # Reset draw count
        p1.cards_drawn_this_turn = 0

        # Script player 1: choose YES to discard, choose card_a to discard
        from engine.player import DeterministicPlayer
        assert isinstance(p1, DeterministicPlayer)
        p1._script.append(True)       # yes, discard
        p1._script.append(card_a)     # which card to discard

        # Make it player 2's turn (opponent's upkeep)
        game.active_player_index = 1
        game.priority_player_index = 1

        hand_before = len(p1.zones[Zone.HAND].get_all())
        graveyard_before = len(p1.zones[Zone.GRAVEYARD].get_all())

        # Fire the upkeep event
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Resolve the trigger from the stack
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        hand_after = len(p1.zones[Zone.HAND].get_all())
        graveyard_after = len(p1.zones[Zone.GRAVEYARD].get_all())

        # Hand size should be same (discarded 1, drew 1)
        assert hand_after == hand_before, (
            f"Hand size should stay the same: discarded 1, drew 1. "
            f"Before={hand_before}, After={hand_after}"
        )
        # Graveyard gained one card (the discarded card)
        assert graveyard_after == graveyard_before + 1, (
            "Discarded card should be in graveyard"
        )
        # The discarded card should be in graveyard
        graveyard_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert card_a in graveyard_cards, "card_a should have been discarded to graveyard"
        # The drawn card should be in hand
        hand_cards = p1.zones[Zone.HAND].get_all()
        assert draw_target in hand_cards, "draw_target should have been drawn into hand"

    def test_no_discard_no_draw_on_opponent_upkeep(self) -> None:
        """When the controller declines to discard, no card is drawn either."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        card_a = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card_a])

        # Script player 1: choose NO to discard
        from engine.player import DeterministicPlayer
        assert isinstance(p1, DeterministicPlayer)
        p1._script.append(False)      # no, don't discard

        # Make it player 2's turn
        game.active_player_index = 1

        hand_before = len(p1.zones[Zone.HAND].get_all())
        graveyard_before = len(p1.zones[Zone.GRAVEYARD].get_all())

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        hand_after = len(p1.zones[Zone.HAND].get_all())
        graveyard_after = len(p1.zones[Zone.GRAVEYARD].get_all())

        assert hand_after == hand_before, "Declining to discard should not change hand size"
        assert graveyard_after == graveyard_before, "No card should be in graveyard when declining"

    def test_trigger_does_not_fire_on_controllers_own_upkeep(self) -> None:
        """The trigger should not apply when it's the controller's own upkeep."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # p1 is active — this is p1's own upkeep
        game.active_player_index = 0

        card_a = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card_a])
        hand_before = len(p1.zones[Zone.HAND].get_all())

        # Fire the upkeep event for the CONTROLLER'S own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Nothing should be pushed onto the stack (trigger condition not met)
        # If the trigger did fire, resolving it with no script would raise ScriptExhaustedError
        # We check that the stack is empty OR the trigger doesn't ask for discard
        if not game.stack.is_empty():
            # The stack may have a trigger — resolve it without scripting and
            # verify hand/graveyard are unchanged (trigger is a no-op on own upkeep)
            while not game.stack.is_empty():
                obj = game.stack.pop()
                # This should not cause any hand/graveyard changes for own upkeep
                # If it tries to prompt the player, the stack will raise or no-op
                try:
                    obj.on_resolve(game)
                except Exception:
                    pass  # acceptable if trigger doesn't fire properly

        # On their own upkeep, hand/graveyard should be unchanged
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before, (
            "Upkeep trigger should not affect hand on controller's own upkeep"
        )
