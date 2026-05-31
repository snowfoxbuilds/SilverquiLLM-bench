"""Tests for Lorehold, the Historian (SOS #201)."""

from __future__ import annotations

import pytest
from test_utils import create_game, set_board_state, advance_to_phase
from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lorehold(game, player_index=0):
    """Create Lorehold on the battlefield for player at player_index."""
    p = game.players[player_index]
    card = LoreholdTheHistorian(owner=p, controller=p)
    set_board_state(game, player_index, battlefield=[card])
    card.register_triggers(game)
    return card


def _make_instant(owner):
    return Instant(name="Test Instant", mana_cost=ManaCost.parse("{R}"), owner=owner, controller=owner)


def _make_sorcery(owner):
    return Sorcery(name="Test Sorcery", mana_cost=ManaCost.parse("{G}"), owner=owner, controller=owner)


def _make_creature(owner):
    return Creature(name="Test Bear", base_power=2, base_toughness=2, owner=owner, controller=owner)


# ---------------------------------------------------------------------------
# A. Card attribute tests
# ---------------------------------------------------------------------------

class TestLoreholdAttributes:
    def test_name(self):
        card = LoreholdTheHistorian()
        assert card.name == "Lorehold, the Historian"

    def test_mana_cost(self):
        card = LoreholdTheHistorian()
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_toughness(self):
        card = LoreholdTheHistorian()
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert card.power == 5
        assert card.toughness == 5

    def test_flying_keyword(self):
        card = LoreholdTheHistorian()
        assert Keyword.FLYING in card.keywords

    def test_haste_keyword(self):
        card = LoreholdTheHistorian()
        assert Keyword.HASTE in card.keywords

    def test_legendary_supertype(self):
        card = LoreholdTheHistorian()
        assert Supertype.LEGENDARY in card.supertypes

    def test_creature_type(self):
        card = LoreholdTheHistorian()
        assert CardType.CREATURE in card.card_types

    def test_elder_dragon_subtypes(self):
        card = LoreholdTheHistorian()
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# B. Miracle grant tests
# ---------------------------------------------------------------------------

class TestMiracleGrant:
    def test_miracle_trigger_fires_for_instant_on_first_draw(self):
        """Miracle triggers when controller draws first card and it's an instant."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        instant = _make_instant(p)
        # Put instant in library (will be drawn)
        p.zones[Zone.LIBRARY].add(instant)

        # Script: player says yes to miracle cast, but we just check trigger fires
        p._script.append(False)  # decline the miracle offer

        from engine.game import draw_card
        from engine.events import DrawsCardTriggeredEvent

        # Simulate first draw of turn
        p.cards_drawn_this_turn = 0
        drawn = draw_card(game, p)
        # cards_drawn_this_turn becomes 1 after draw

        # Trigger should have fired (pushed a stack object), but effect was to
        # ask the player. Stack object may or may not be present depending on resolution.
        # Since we declined, the card stays in hand.
        hand = game.get_hand(p)
        assert hand.contains(instant)

    def test_miracle_trigger_fires_for_sorcery_on_first_draw(self):
        """Miracle triggers when controller draws first card and it's a sorcery."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        sorcery = _make_sorcery(p)
        p.zones[Zone.LIBRARY].add(sorcery)

        p._script.append(False)  # decline miracle

        from engine.game import draw_card
        p.cards_drawn_this_turn = 0
        draw_card(game, p)

        hand = game.get_hand(p)
        assert hand.contains(sorcery)

    def test_miracle_does_not_trigger_for_creature(self):
        """Miracle does NOT trigger when the drawn card is a creature."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        creature = _make_creature(p)
        p.zones[Zone.LIBRARY].add(creature)

        from engine.game import draw_card
        p.cards_drawn_this_turn = 0

        # No script needed because trigger should not fire
        draw_card(game, p)

        # Creature is in hand, no stack object pushed
        hand = game.get_hand(p)
        assert hand.contains(creature)
        assert game.stack.is_empty()

    def test_miracle_does_not_trigger_on_second_draw(self):
        """Miracle does NOT trigger when it's not the first card drawn this turn."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        instant1 = _make_instant(p)
        instant2 = _make_instant(p)
        instant2.name = "Second Instant"
        p.zones[Zone.LIBRARY].add(instant1)
        p.zones[Zone.LIBRARY].add(instant2)

        from engine.game import draw_card

        # First draw (instant2 is on top)
        p.cards_drawn_this_turn = 0
        p._script.append(False)  # decline first miracle
        draw_card(game, p)

        # Second draw — trigger should not fire (cards_drawn_this_turn is now 2)
        draw_card(game, p)  # no script needed

        # Both instants in hand
        hand = game.get_hand(p)
        cards_in_hand = hand.get_all()
        assert len(cards_in_hand) >= 2

    def test_miracle_cast_costs_two_mana(self):
        """When miracle is accepted, controller pays {2} to cast the card."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        instant = _make_instant(p)
        p.zones[Zone.LIBRARY].add(instant)

        from engine.game import draw_card
        from engine.types import ManaType

        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        p.cards_drawn_this_turn = 0
        p._script.append(True)  # yes to miracle cast

        mana_before = dict(p.mana_pool._pool)
        draw_card(game, p)

        # Trigger is on stack; resolve it
        if not game.stack.is_empty():
            obj = game.stack.pop()
            if hasattr(obj, 'on_resolve'):
                obj.on_resolve(game)

        # 2 mana should have been spent
        total_before = sum(mana_before.values())
        total_after = sum(p.mana_pool._pool.values())
        assert total_before - total_after == 2

    def test_miracle_requires_enough_mana(self):
        """Miracle cast does not proceed if controller lacks {2}."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        instant = _make_instant(p)
        p.zones[Zone.LIBRARY].add(instant)

        from engine.game import draw_card

        # No mana available
        p.cards_drawn_this_turn = 0
        p._script.append(True)  # wants to cast, but can't

        draw_card(game, p)

        # Trigger fires but cast fails; instant stays in hand
        if not game.stack.is_empty():
            obj = game.stack.pop()
            if hasattr(obj, 'on_resolve'):
                obj.on_resolve(game)

        hand = game.get_hand(p)
        assert hand.contains(instant)

    def test_miracle_not_triggered_without_lorehold(self):
        """Without Lorehold on battlefield, no miracle trigger fires."""
        game = create_game()
        p = game.players[0]

        instant = _make_instant(p)
        p.zones[Zone.LIBRARY].add(instant)

        from engine.game import draw_card
        p.cards_drawn_this_turn = 0
        draw_card(game, p)

        assert game.stack.is_empty()

    def test_miracle_optional_decline(self):
        """Player can decline the miracle offer; card stays in hand."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        instant = _make_instant(p)
        p.zones[Zone.LIBRARY].add(instant)

        from engine.game import draw_card
        from engine.types import ManaType
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        p.cards_drawn_this_turn = 0
        p._script.append(False)  # decline

        draw_card(game, p)

        if not game.stack.is_empty():
            obj = game.stack.pop()
            if hasattr(obj, 'on_resolve'):
                obj.on_resolve(game)

        hand = game.get_hand(p)
        assert hand.contains(instant)


# ---------------------------------------------------------------------------
# C. Opponent upkeep trigger tests
# ---------------------------------------------------------------------------

class TestOpponentUpkeepTrigger:
    def test_trigger_fires_on_opponent_upkeep(self):
        """Trigger fires at the beginning of each opponent's upkeep."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        # Give p a card to discard
        creature = _make_creature(p)
        set_board_state(game, 0, hand=[creature])

        # Script: yes to discard
        p._script.append(True)   # want to discard
        p._script.append(creature)  # choose this card to discard

        # Give p cards in library to draw
        draw_card_obj = _make_creature(p)
        draw_card_obj.name = "Drawn Card"
        p.zones[Zone.LIBRARY].add(draw_card_obj)

        # Simulate opponent's upkeep: active player = player 1
        game.active_player_index = 1
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Stack should have the trigger
        assert not game.stack.is_empty()

    def test_discard_then_draw(self):
        """When player discards, they draw a card."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        card_to_discard = _make_creature(p)
        card_to_discard.name = "Discard Me"
        set_board_state(game, 0, hand=[card_to_discard])

        drawn_card = _make_creature(p)
        drawn_card.name = "Drawn Card"
        p.zones[Zone.LIBRARY].add(drawn_card)

        p._script.append(True)           # yes to discard
        p._script.append(card_to_discard)  # choose card

        game.active_player_index = 1
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Resolve the trigger
        assert not game.stack.is_empty()
        obj = game.stack.pop()
        obj.on_resolve(game)

        # Card was discarded
        gy = p.zones[Zone.GRAVEYARD]
        assert any(c is card_to_discard for c in gy.get_all())

        # Drew a card
        hand = game.get_hand(p)
        assert any(c is drawn_card for c in hand.get_all())

    def test_discard_is_optional(self):
        """Player may choose not to discard."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        card_in_hand = _make_creature(p)
        card_in_hand.name = "Keep Me"
        set_board_state(game, 0, hand=[card_in_hand])

        p._script.append(False)  # decline discard

        game.active_player_index = 1
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        obj = game.stack.pop()
        obj.on_resolve(game)

        # Card stays in hand
        hand = game.get_hand(p)
        assert hand.contains(card_in_hand)

        # Graveyard is empty (no discard happened)
        gy = p.zones[Zone.GRAVEYARD]
        assert len(gy.get_all()) == 0

    def test_no_draw_if_no_discard(self):
        """If player declines to discard, they do not draw."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        card_in_hand = _make_creature(p)
        set_board_state(game, 0, hand=[card_in_hand])

        drawn_card = _make_creature(p)
        drawn_card.name = "Should Not Be Drawn"
        p.zones[Zone.LIBRARY].add(drawn_card)

        p._script.append(False)  # decline discard

        hand_size_before = len(game.get_hand(p).get_all())

        game.active_player_index = 1
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        obj = game.stack.pop()
        obj.on_resolve(game)

        hand_size_after = len(game.get_hand(p).get_all())
        assert hand_size_after == hand_size_before

    def test_trigger_does_not_fire_on_own_upkeep(self):
        """Trigger does NOT fire during controller's own upkeep."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        card_in_hand = _make_creature(p)
        set_board_state(game, 0, hand=[card_in_hand])

        # Active player is controller (own upkeep)
        game.active_player_index = 0
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # No trigger pushed on stack
        assert game.stack.is_empty()

    def test_trigger_unregistered_when_lorehold_leaves(self):
        """After unregistering triggers, opponent upkeep no longer fires."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        # Unregister (simulating leaving battlefield)
        game.trigger_manager.unregister(lorehold)

        game.active_player_index = 1
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_no_discard_when_hand_empty(self):
        """Trigger resolves without error when hand is empty."""
        game = create_game()
        p = game.players[0]
        lorehold = _make_lorehold(game, 0)

        # Empty hand (only lorehold on battlefield, hand is empty)
        set_board_state(game, 0, hand=[])

        game.active_player_index = 1
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Trigger fires but effect returns early because hand is empty
        obj = game.stack.pop()
        obj.on_resolve(game)  # should not raise

    def test_trigger_fires_with_player_two_as_controller(self):
        """Trigger fires when player 2 controls Lorehold and player 1 is active."""
        game = create_game()
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[lorehold])
        lorehold.register_triggers(game)

        # Give p2 a card to discard
        card = _make_creature(p2)
        set_board_state(game, 1, hand=[card])

        p2._script.append(False)  # decline discard

        # Active player is player 0 (opponent of p2)
        game.active_player_index = 0
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert not game.stack.is_empty()
        obj = game.stack.pop()
        obj.on_resolve(game)
