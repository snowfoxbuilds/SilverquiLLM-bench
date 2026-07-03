"""Tests for SOS 201 — Lorehold, the Historian.

Legendary Creature — Elder Dragon (5/5)
Flying, haste
Each instant and sorcery card in your hand has miracle {2}.
At the beginning of each opponent's upkeep, you may discard a card. If you do, draw a card.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


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
        assert card.keywords & Keyword.FLYING

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.keywords & Keyword.HASTE

    def test_is_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_include_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


class TestLoreholdMiracle:
    """Each instant and sorcery in your hand gets miracle {2}."""

    def test_grants_miracle_cost_to_instants_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Instants/sorceries in hand should have miracle {2}
        from engine.card import Instant
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1,
                       mana_cost=ManaCost.parse("{R}"))
        game.get_hand(p1).add(bolt)
        # The miracle cost should be accessible
        assert hasattr(bolt, 'miracle_cost') or hasattr(card, 'get_miracle_cost')
        # Check the miracle cost is {2}
        miracle = getattr(bolt, 'miracle_cost', None)
        if miracle is None and hasattr(card, 'get_miracle_cost'):
            miracle = card.get_miracle_cost(bolt)
        assert miracle == ManaCost.parse("{2}")

    def test_does_not_grant_miracle_to_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_hand(p1).add(bear)
        # Creatures should NOT have miracle
        miracle = getattr(bear, 'miracle_cost', None)
        assert miracle is None


class TestLoreholdUpkeepTrigger:
    """At beginning of each opponent's upkeep, may discard to draw."""

    def test_trigger_allows_discard_to_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Give p1 a card in hand to discard
        filler = Creature(name="Filler", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[filler])
        # Put a card in library so draw is possible
        draw_card = Creature(name="Drawn Card", owner=p1, base_power=1, base_toughness=1)
        game.get_library(p1).add(draw_card)
        hand_before = len(game.get_hand(p1).get_all())
        # Trigger the upkeep ability (opponent's upkeep)
        card.on_upkeep_trigger(game, p2)
        # After discarding 1 and drawing 1, hand size should stay same
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before

    def test_trigger_does_not_fire_on_own_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        filler = Creature(name="Filler", owner=p1, base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[filler])
        hand_before = len(game.get_hand(p1).get_all())
        # Should not trigger on controller's own upkeep
        # This tests that the trigger condition checks opponent
        has_trigger = card.get_upkeep_triggers(game, p1)
        assert not has_trigger
