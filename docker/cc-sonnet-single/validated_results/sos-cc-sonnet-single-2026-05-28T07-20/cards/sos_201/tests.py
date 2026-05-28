"""Tests for sos_201 — Lorehold, the Historian.

Tests cover:
- Static card properties (name, mana cost, P/T, keywords, supertypes, subtypes)
- Card type and color correctness
- Miracle-cost grant: instants and sorceries in hand have miracle {2}; other
  card types do not
- Opponent upkeep trigger registration and firing
- Trigger fires for opponent's upkeep, not for controller's own upkeep
- Discard-then-draw effect: when the controller discards a card, they draw one
- Decline to discard: if the controller says "no", no draw occurs
"""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
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


class TestLoreholdStaticProperties:
    """Static card data must match the sos_201 spec."""

    def test_name(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords

    def test_is_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_is_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_colors_include_red(self) -> None:
        """The card is red/white: mana cost must contain a red pip."""
        card = LoreholdTheHistorian(owner=None)
        assert ManaType.RED in card.mana_cost.pips

    def test_colors_include_white(self) -> None:
        """The card is red/white: mana cost must contain a white pip."""
        card = LoreholdTheHistorian(owner=None)
        assert ManaType.WHITE in card.mana_cost.pips


# ---------------------------------------------------------------------------
# Miracle-cost grant
# ---------------------------------------------------------------------------


class TestLoreholdMiracleCostGrant:
    """Each instant and sorcery in the controller's hand has miracle {2}."""

    def test_get_miracle_cost_returns_callable_or_manacost(self) -> None:
        """The card exposes a way to determine miracle cost for hand cards."""
        card = LoreholdTheHistorian(owner=None)
        # Must have a get_miracle_cost method
        assert hasattr(card, "get_miracle_cost"), (
            "LoreholdTheHistorian must implement get_miracle_cost(card)"
        )

    def test_instant_in_hand_has_miracle_cost_two(self) -> None:
        """An instant card should receive miracle cost {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        # Place both on battlefield/hand as appropriate
        game.get_battlefield(p1).add(lorehold)
        game.get_hand(p1).add(instant)
        lorehold.register_triggers(game)

        miracle_cost = lorehold.get_miracle_cost(instant)
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Expected miracle cost {{2}} for instant, got {miracle_cost!r}"
        )

    def test_sorcery_in_hand_has_miracle_cost_two(self) -> None:
        """A sorcery card should receive miracle cost {2}."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        game.get_hand(p1).add(sorcery)
        lorehold.register_triggers(game)

        miracle_cost = lorehold.get_miracle_cost(sorcery)
        assert miracle_cost == ManaCost.parse("{2}"), (
            f"Expected miracle cost {{2}} for sorcery, got {miracle_cost!r}"
        )

    def test_creature_does_not_get_miracle_cost(self) -> None:
        """A creature card should NOT receive a miracle cost."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        creature = Creature(name="Test Bear", base_power=2, base_toughness=2,
                            owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        game.get_hand(p1).add(creature)
        lorehold.register_triggers(game)

        miracle_cost = lorehold.get_miracle_cost(creature)
        assert miracle_cost is None, (
            f"Expected None for creature, got {miracle_cost!r}"
        )

    def test_miracle_cost_not_granted_to_opponent_cards(self) -> None:
        """Only cards in the controller's hand get the miracle benefit."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        instant = Instant(name="Opponent Instant", owner=p2, controller=p2)
        game.get_battlefield(p1).add(lorehold)
        game.get_hand(p2).add(instant)
        lorehold.register_triggers(game)

        # The miracle cost query for opponent's card should return None
        miracle_cost = lorehold.get_miracle_cost(instant)
        assert miracle_cost is None, (
            "Miracle {2} should not apply to opponent's cards"
        )


# ---------------------------------------------------------------------------
# Opponent upkeep trigger — registration
# ---------------------------------------------------------------------------


class TestLoreholdOpponentUpkeepTriggerRegistration:
    """register_triggers must register exactly one upkeep-watching trigger."""

    def test_registers_upkeep_trigger_on_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        upkeep_triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1, (
            "Expected at least one BeginningOfUpkeepTriggeredEvent trigger"
        )

    def test_trigger_source_is_lorehold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        upkeep_triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        sources = [t.source for t in upkeep_triggers]
        assert lorehold in sources


# ---------------------------------------------------------------------------
# Opponent upkeep trigger — fires for opponent, not controller
# ---------------------------------------------------------------------------


class TestLoreholdOpponentUpkeepTriggerFiring:
    """Trigger must fire only during opponent's upkeep step."""

    def test_trigger_does_not_fire_on_controllers_own_upkeep(self) -> None:
        """When it is p1's (controller's) upkeep, no trigger should fire."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # p1 is active player (index 0 by default)
        game.active_player_index = 0
        before = game.stack.size()
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        after = game.stack.size()

        assert after == before, (
            "Lorehold trigger should NOT fire during controller's own upkeep"
        )

    def test_trigger_fires_on_opponents_upkeep(self) -> None:
        """When it is p2's (opponent's) upkeep, the trigger should fire."""
        # Script p1 to answer 'yes' to the discard prompt, then provide a card.
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Make p2 the active player (their upkeep)
        game.active_player_index = 1
        before = game.stack.size()
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        after = game.stack.size()

        assert after > before, (
            "Lorehold trigger MUST fire during opponent's upkeep"
        )


# ---------------------------------------------------------------------------
# Discard-then-draw effect
# ---------------------------------------------------------------------------


class TestLoreholdDiscardDrawEffect:
    """When the trigger resolves and controller discards, they draw a card."""

    def _setup_game_with_lorehold_on_board(self):
        """Return (game, p1, p2, lorehold) with lorehold on p1's battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)
        return game, p1, p2, lorehold

    def test_discarding_results_in_drawing_a_card(self) -> None:
        """If controller discards, net hand size stays the same (+1 draw, -1 discard)."""
        game, p1, p2, lorehold = self._setup_game_with_lorehold_on_board()

        # Put two cards in p1's hand, one in library
        discard_card = Instant(name="Discard Target", owner=p1, controller=p1)
        hand_card = Creature(name="Hand Filler", base_power=1, base_toughness=1,
                             owner=p1, controller=p1)
        draw_card = Sorcery(name="Library Top", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[discard_card, hand_card])
        # Put a card in p1's library to draw
        p1.zones[Zone.LIBRARY].add(draw_card)

        hand_before = len(game.get_hand(p1).get_all())  # 2

        # Script p1: yes to discard, then choose discard_card
        from engine.player import DeterministicPlayer
        from collections import deque
        p1._script = deque([True, discard_card])

        # Make p2 the active player and fire the upkeep event
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Resolve the trigger
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        hand_after = len(game.get_hand(p1).get_all())
        # Discarded 1, drew 1 → net 0
        assert hand_after == hand_before, (
            f"Expected hand size unchanged after discard+draw, "
            f"was {hand_before} before and {hand_after} after"
        )

    def test_discarded_card_goes_to_graveyard(self) -> None:
        """The discarded card must end up in the graveyard."""
        game, p1, p2, lorehold = self._setup_game_with_lorehold_on_board()

        discard_card = Instant(name="Discard Me", owner=p1, controller=p1)
        draw_card = Sorcery(name="Library Top", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[discard_card])
        p1.zones[Zone.LIBRARY].add(draw_card)

        from collections import deque
        p1._script = deque([True, discard_card])

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        graveyard = game.get_graveyard(p1).get_all()
        assert discard_card in graveyard, (
            "Discarded card should be in the graveyard"
        )

    def test_declining_to_discard_means_no_draw(self) -> None:
        """If the controller says no to discarding, they must not draw."""
        game, p1, p2, lorehold = self._setup_game_with_lorehold_on_board()

        hand_card = Instant(name="Keeper", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[hand_card])
        # Leave library empty so a draw would be detectable (drawn_from_empty flag)

        from collections import deque
        p1._script = deque([False])  # decline to discard

        hand_before = len(game.get_hand(p1).get_all())

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before, (
            "Declining to discard must not change hand size"
        )

    def test_declining_to_discard_does_not_attempt_library_draw(self) -> None:
        """Declining discard must not set the drawn_from_empty_library flag."""
        game, p1, p2, lorehold = self._setup_game_with_lorehold_on_board()

        from collections import deque
        p1._script = deque([False])  # decline to discard

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert not p1.drawn_from_empty_library, (
            "No draw should occur when discard is declined"
        )
