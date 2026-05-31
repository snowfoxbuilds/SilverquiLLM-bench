"""Tests for sos_201 — Lorehold, the Historian (Legendary Elder Dragon)."""
from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game


class TestLoreholdProperties:
    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Lorehold" in card.name

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

    def test_is_legendary_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Dragon" in card.subtypes or "Elder" in card.subtypes


class TestLoreholdMiracleGrant:
    """Each instant and sorcery card in your hand has miracle {2}."""

    def test_grants_miracle_to_instants_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        instant = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"), owner=p1, controller=p1)
        p1.zones[Zone.HAND].add(instant)

        # Call grant_miracle on instants/sorceries in hand.
        card.grant_miracle_to_hand(game)
        assert getattr(instant, "miracle_cost", None) == ManaCost.parse("{2}")
        assert getattr(instant, "has_miracle", False) is True

    def test_grants_miracle_to_sorceries_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        sorcery = Sorcery(name="Ponder", mana_cost=ManaCost.parse("{U}"), owner=p1, controller=p1)
        p1.zones[Zone.HAND].add(sorcery)
        card.grant_miracle_to_hand(game)
        assert getattr(sorcery, "has_miracle", False) is True

    def test_does_not_grant_miracle_to_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.HAND].add(creature)
        card.grant_miracle_to_hand(game)
        assert getattr(creature, "has_miracle", False) is False


class TestLoreholdOpponentUpkeepTrigger:
    """At the beginning of each opponent's upkeep, may discard a card to draw a card."""

    def test_registers_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        before = len(game.trigger_manager._triggers)
        card.register_triggers(game)
        after = len(game.trigger_manager._triggers)
        assert after > before

    def test_upkeep_trigger_condition_fires_for_opponent(self) -> None:
        """Trigger fires when opponent's upkeep begins."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)

        upkeep_triggers = [
            t for t in game.trigger_manager._triggers
            if issubclass(t.event_type, BeginningOfUpkeepTriggeredEvent)
        ]
        assert len(upkeep_triggers) >= 1

    def test_discard_to_draw_at_opponent_upkeep(self) -> None:
        """When trigger fires, controller discards a card to draw one."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)

        # Put a card in p1's hand to discard.
        hand_card = CardImpl(name="Discard Me", owner=p1)
        p1.zones[Zone.HAND].add(hand_card)
        # Put a card in p1's library to draw.
        draw_card = CardImpl(name="Draw Me", owner=p1)
        p1.zones[Zone.LIBRARY].add(draw_card)

        initial_hand = len(p1.zones[Zone.HAND].get_all())
        initial_gy = len(p1.zones[Zone.GRAVEYARD].get_all())

        # Manually invoke the trigger effect (simulating opponent upkeep).
        card.on_opponent_upkeep(game)

        # After: discarded 1, drew 1 → hand size same.
        assert len(p1.zones[Zone.HAND].get_all()) == initial_hand
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == initial_gy + 1
